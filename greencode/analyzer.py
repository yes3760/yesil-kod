"""Statik analiz: Python kodunda enerji israfına yol açan kalıpları bulur.

Kod çalıştırılmaz; yalnızca sözdizimi ağacı (AST) incelenir. Bu yüzden
stantta ziyaretçinin yapıştırdığı kodu güvenle analiz edebilir.
"""
from __future__ import annotations

import ast
import json
import urllib.request

from . import config

DB_METHODS = {"execute", "fetchone", "fetchall", "query", "filter", "get", "find",
              "find_one", "select", "raw"}
INVARIANT_CALLS = {
    ("json", "loads"): "JSON ayrıştırma",
    ("json", "load"): "JSON dosyası okuma",
    ("re", "compile"): "düzenli ifade (regex) derleme",
    ("yaml", "safe_load"): "YAML ayrıştırma",
    ("requests", "get"): "HTTP isteği",
    ("pd", "read_csv"): "CSV dosyası okuma",
}

RULES = {
    "YK001": ("Döngü içinde veritabanı sorgusu (N+1)", "yüksek",
              "Her döngü adımı veritabanına ayrı bir istek gönderiyor. Verinin tamamını "
              "tek bir JOIN ya da 'WHERE id IN (...)' sorgusuyla çekin."),
    "YK002": ("Döngü içinde listede arama", "yüksek",
              "Listede 'in' araması her seferinde listeyi baştan sona tarar. Döngüden "
              "önce listeyi set() ile kümeye çevirin; arama sabit sürede yapılır."),
    "YK003": ("Döngüde değişmeyen işi tekrar yapma", "orta",
              "Bu çağrının sonucu döngü boyunca değişmiyor. Döngüden önce bir kez yapın "
              "ve sonucu bir değişkende tutun."),
    "YK004": ("Önbelleksiz çift özyineleme", "yüksek",
              "Fonksiyon kendini birden fazla kez çağırıyor; aynı ara sonuçlar katlanarak "
              "yeniden hesaplanır. @functools.lru_cache ekleyin ya da döngüye çevirin."),
    "YK005": ("Sürekli sorgulama (polling)", "orta",
              "Sonsuz döngüde bekleyip tekrar kontrol etmek işlemciyi ve ağı boşuna "
              "meşgul eder. Olay tabanlı yapı (webhook, kuyruk, bildirim) kullanın ya da "
              "bekleme süresini artırın."),
    "YK006": ("İç içe döngü (O(n²))", "bilgi",
              "İç içe döngüler veri büyüdükçe karesel olarak yavaşlar. İç döngü bir "
              "eşleştirme yapıyorsa sözlük (dict) ile tek geçişe indirin."),
    "YK007": ("Pandas tablosunu satır satır gezme", "yüksek",
              "iterrows, itertuples ve axis=1 ile apply her satırı yavaş bir Python döngüsünde "
              "işler. Sütun işlemleri, merge ve groupby gibi vektörel pandas/numpy işlemlerini "
              "kullanın; yapılan iş genellikle onlarca kat azalır."),
    "YK008": ("Döngüde oturumsuz HTTP isteği", "orta",
              "Her requests çağrısı yeni bir bağlantı ve TLS el sıkışması kurar. Döngüden önce "
              "requests.Session() açıp istekleri onunla gönderin; bağlantı yeniden kullanılır."),
    "YK009": ("Listenin başından ekleme ya da çıkarma", "orta",
              "pop(0) ve insert(0, ...) listenin bütün elemanlarını kaydırır. collections.deque "
              "kullanın: popleft ve appendleft sabit sürede çalışır."),
}
ROW_ITER = {"iterrows", "itertuples"}
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "request"}


def _call_name(node):
    f = node.func
    if isinstance(f, ast.Attribute):
        base = f.value.id if isinstance(f.value, ast.Name) else None
        return base, f.attr
    if isinstance(f, ast.Name):
        return None, f.id
    return None, None


def _names_in(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _targets(node):
    out = set()
    for t in ast.walk(node):
        if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store):
            out.add(t.id)
    return out


class _Visitor(ast.NodeVisitor):
    def __init__(self):
        self.findings = []
        self.loop_stack = []        # her döngüde tanımlanan değişkenler
        self.list_names = set()     # liste olarak atanmış isimler
        self.func_stack = []
        self._seen = set()

    # --- yardımcılar
    def add(self, rule, node, detail=""):
        key = (rule, node.lineno)
        if key in self._seen:
            return
        self._seen.add(key)
        title, severity, fix = RULES[rule]
        self.findings.append({"kural": rule, "baslik": title, "onem": severity,
                              "satir": node.lineno, "detay": detail, "oneri": fix})

    def _loop_vars(self):
        s = set()
        for v in self.loop_stack:
            s |= v
        return s

    # --- atamalar: hangi isimler liste?
    def visit_Assign(self, node):
        is_list = isinstance(node.value, (ast.List, ast.ListComp)) or (
            isinstance(node.value, ast.Call) and _call_name(node.value)[1] in ("list", "sorted"))
        for t in node.targets:
            if isinstance(t, ast.Name):
                if is_list:
                    self.list_names.add(t.id)
                else:
                    self.list_names.discard(t.id)
        if self.loop_stack:
            self.loop_stack[-1] |= _targets(node)
        self.generic_visit(node)

    # --- döngüler
    def _visit_loop(self, node, loop_vars):
        if self.loop_stack:
            self.add("YK006", node)
        self.loop_stack.append(set(loop_vars))
        self.generic_visit(node)
        self.loop_stack.pop()

    def _row_iter(self, it, at):
        if isinstance(it, ast.Call) and _call_name(it)[1] in ROW_ITER:
            self.add("YK007", at, f"{_call_name(it)[1]}()")

    def visit_For(self, node):
        self._row_iter(node.iter, node)
        # Döngünün üzerinde döndüğü ifade (node.iter) yalnızca bir kez çalışır
        self.visit(node.iter)
        if self.loop_stack:
            self.add("YK006", node)
        self.loop_stack.append(_targets(node.target))
        for child in node.body + node.orelse:
            self.visit(child)
        self.loop_stack.pop()

    visit_AsyncFor = visit_For

    def visit_While(self, node):
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            for n in ast.walk(node):
                if isinstance(n, ast.Call) and _call_name(n) in (("time", "sleep"), (None, "sleep")):
                    self.add("YK005", node)
        self._visit_loop(node, set())

    def _visit_comp(self, node):
        tv = set()
        for g in node.generators:
            self._row_iter(g.iter, node)
            tv |= _targets(g.target)
        self.loop_stack.append(tv)
        self.generic_visit(node)
        self.loop_stack.pop()

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _visit_comp

    # --- çağrılar
    def visit_Call(self, node):
        base, name = _call_name(node)
        if name == "apply" and any(k.arg == "axis" and isinstance(k.value, ast.Constant)
                                   and k.value.value in (1, "columns") for k in node.keywords):
            self.add("YK007", node, "apply(..., axis=1)")
        if self.loop_stack:
            invariant = False
            if name in DB_METHODS and base not in (None, "dict", "os", "self") and (
                    name in ("execute", "query", "raw", "find_one", "fetchone")
                    or base in ("session", "db", "cursor", "conn", "objects")):
                self.add("YK001", node, f"{base}.{name}(...)")
            elif (base, name) in INVARIANT_CALLS:
                args_names = set()
                for a in node.args + [k.value for k in node.keywords]:
                    args_names |= _names_in(a)
                if not (args_names & self._loop_vars()):
                    invariant = True
                    self.add("YK003", node, f"{base}.{name}(...): {INVARIANT_CALLS[(base, name)]}")
            if base == "requests" and name in HTTP_METHODS and not invariant:
                self.add("YK008", node, f"requests.{name}(...)")
            first = node.args[0] if node.args else None
            if isinstance(first, ast.Constant) and first.value == 0 and base and (
                    (name == "pop" and len(node.args) == 1) or (name == "insert" and len(node.args) == 2)):
                self.add("YK009", node, f"{base}.{name}(0{', ...' if name == 'insert' else ''})")
        if self.func_stack:
            fn = self.func_stack[-1]
            if _call_name(node) == (None, fn["name"]):
                fn["self_calls"] += 1
        self.generic_visit(node)

    def visit_Compare(self, node):
        if self.loop_stack:
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.In, ast.NotIn)):
                    if isinstance(comp, ast.Name) and comp.id in self.list_names:
                        self.add("YK002", node, f"'{comp.id}' bir liste")
                    elif isinstance(comp, ast.List):
                        self.add("YK002", node, "sabit liste")
        self.generic_visit(node)

    # --- fonksiyonlar
    def visit_FunctionDef(self, node):
        cached = any(
            (isinstance(d, ast.Name) and d.id in ("cache", "lru_cache")) or
            (isinstance(d, ast.Attribute) and d.attr in ("cache", "lru_cache")) or
            (isinstance(d, ast.Call) and _call_name(d)[1] in ("cache", "lru_cache"))
            for d in node.decorator_list)
        info = {"name": node.name, "self_calls": 0}
        self.func_stack.append(info)
        saved_stack, self.loop_stack = self.loop_stack, []
        self.generic_visit(node)
        self.loop_stack = saved_stack
        self.func_stack.pop()
        if info["self_calls"] >= 2 and not cached:
            self.add("YK004", node, f"{node.name}() kendini {info['self_calls']} kez çağırıyor")

    visit_AsyncFunctionDef = visit_FunctionDef


def analyze(code: str):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"hata": f"Sözdizimi hatası, satır {e.lineno}: {e.msg}", "bulgular": []}
    v = _Visitor()
    v.visit(tree)
    order = {"yüksek": 0, "orta": 1, "bilgi": 2}
    bulgular = sorted(v.findings, key=lambda f: (order[f["onem"]], f["satir"]))
    return {"hata": None, "bulgular": bulgular}


def ai_suggestion(code: str, bulgular: list):
    """İsteğe bağlı: LLM'den optimize sürüm ister. Anahtar yoksa None döner."""
    if not config.ANTHROPIC_API_KEY:
        return None
    ozet = "\n".join(f"- Satır {b['satir']}: {b['baslik']} ({b['detay']})" for b in bulgular)
    prompt = (
        "Aşağıdaki Python kodunu enerji verimliliği için optimize et. Davranışı ve "
        "çıktıyı değiştirme. Önce optimize kodun tamamını tek bir ```python bloğunda ver, "
        "sonra Türkçe en fazla 3 madde ile neyi neden değiştirdiğini yaz.\n\n"
        f"Statik analiz bulguları:\n{ozet or '- (bulgu yok)'}\n\nKod:\n```python\n{code}\n```")
    body = json.dumps({"model": config.LLM_MODEL, "max_tokens": 1500,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"x-api-key": config.ANTHROPIC_API_KEY,
                 "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        return "".join(b.get("text", "") for b in data.get("content", []))
    except Exception as e:                                  # stantta demo çökmesin
        return f"(Yapay zekâ önerisi alınamadı: {e})"
