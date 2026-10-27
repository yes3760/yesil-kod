"""Statik analiz: Python kodunda enerji israfına yol açan kalıpları bulur.

Kod çalıştırılmaz; yalnızca sözdizimi ağacı (AST) incelenir. Bu yüzden
stantta ziyaretçinin yapıştırdığı kodu güvenle analiz edebilir.
"""
from __future__ import annotations

import ast
import json
import re
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
    "YK010": ("Döngüde metin birleştirme", "orta",
              "Metne döngüde += ile eklemek her adımda yeni bir metin oluşturabilir; uzun "
              "metinlerde iş karesel büyür. Parçaları listede toplayıp sonunda ''.join() kullanın."),
    "YK011": ("En küçük ya da en büyük için sıralama", "orta",
              "Bütün listeyi sıralayıp ilk ya da son elemanı almak O(n log n) iştir. "
              "min() ve max() aynı sonucu tek geçişte (O(n)) bulur."),
    "YK012": ("Döngüde aynı dosyayı ya da modeli yeniden yükleme", "yüksek",
              "Aynı dosya ya da model her döngü adımında diskten yeniden okunuyor. Döngüden "
              "önce bir kez yükleyip sonucu kullanın; disk ve işlemci yükü birlikte düşer."),
    "YK013": ("Döngüde listede index() ya da count()", "yüksek",
              "index() ve count() listeyi baştan sona tarar; döngüde iş karesel büyür. "
              "Konumlar için sözlük, sayım için collections.Counter kullanın."),
    "YK014": ("Döngüde bağlantı, istemci ya da havuz oluşturma", "yüksek",
              "Veritabanı bağlantısı, HTTP oturumu, bulut istemcisi ya da iş parçacığı havuzu "
              "kurmak pahalıdır (ağ el sıkışması, kimlik doğrulama). Döngüden önce bir kez "
              "oluşturup yeniden kullanın."),
    "YK015": ("Boş döngüyle bekleme (busy wait)", "yüksek",
              "Gövdesi boş bir döngü, koşul değişene kadar bir işlemci çekirdeğini %100 "
              "meşgul eder. threading.Event, kuyruk ya da time.sleep ile bekleyin."),
    "YK016": ("any() ya da all() içinde liste", "orta",
              "Köşeli parantezli liste önce bütün elemanları hesaplar; any() ve all() ilk "
              "sonuçta duramaz. Köşeli parantezleri kaldırıp üreteç kullanın."),
    "YK017": ("Döngüde listeyi yeniden oluşturma", "orta",
              "L = L + [x] her adımda bütün listeyi kopyalar; iş karesel büyür. "
              "L.append(x) ya da L.extend(...) kullanın."),
    "YK018": ("Döngüde dizi ya da tablo büyütme", "yüksek",
              "pd.concat ve np.append/concatenate/vstack her çağrıda bütün veriyi yeniden "
              "kopyalar. Parçaları listede toplayıp döngüden sonra tek seferde birleştirin."),
    "YK019": ("Döngüde önceden biçimlendirilen log mesajı", "bilgi",
              "f-string ya da format() ile hazırlanan log mesajı, o seviye kapalı olsa bile "
              "her adımda biçimlendirilir. logger.debug('%s', x) biçimini kullanın."),
    "YK020": ("Dosyayı readlines() ile belleğe alma", "bilgi",
              "readlines() bütün dosyayı önce belleğe okur. Satırları doğrudan dosya "
              "nesnesi üzerinde gezin: for satir in dosya."),
    "YK021": ("SELECT * ile gereksiz sütun çekme", "bilgi",
              "SELECT * kullanılmayan sütunları da diskten okur ve ağdan taşır. Yalnızca "
              "gereken sütunları yazın."),
    "YK022": ("Saymak için bütün satırları çekme", "orta",
              "len(...fetchall()) bütün satırları veritabanından taşır. SELECT COUNT(*) ile "
              "sayıyı veritabanına hesaplatın."),
    "YK023": ("Veritabanı yerine Python'da filtreleme", "orta",
              "Bütün satırları çekip Python'da elemek gereksiz veri taşır. Koşulu sorgunun "
              "WHERE kısmına yazın; veritabanı dizinleri kullanır."),
    "YK024": ("JSON ile kopyalama", "orta",
              "json.loads(json.dumps(x)) veriyi metne çevirip geri ayrıştırır. copy.deepcopy "
              "daha az iş yapar ve veri türlerini korur."),
    "YK025": ("sum() ile liste birleştirme", "orta",
              "sum(listeler, []) her adımda yeni bir liste oluşturur; iş karesel büyür. "
              "itertools.chain.from_iterable kullanın."),
    "YK026": ("Döngüde sözlük değerlerinde arama", "yüksek",
              "x in d.values() bütün değerleri tek tek tarar. Değerlerden bir küme (set) "
              "oluşturun ya da ters sözlük tutun."),
    "YK027": ("NumPy dizisinde eleman eleman Python döngüsü", "yüksek",
              "NumPy dizisini Python döngüsüyle gezmek vektörel işlemlerden onlarca kat "
              "yavaştır. Diziyle doğrudan işlem yapın: a * 2, np.where, np.sum."),
    "YK028": ("Döngüde değişmeyen metni yeniden işleme", "orta",
              "Döngü boyunca değişmeyen bir metin her adımda yeniden bölünüyor ya da "
              "dönüştürülüyor. İşlemi döngüden önce bir kez yapın."),
    "YK029": ("Gereksiz liste kopyası", "bilgi",
              "Döngüden önce list() ile kopya oluşturmak bellek ve zaman harcar. "
              "range, map, zip gibi nesneler doğrudan gezilebilir."),
    "YK030": ("Döngüde süreç başlatma", "orta",
              "Her subprocess ya da os.system çağrısı yeni bir işletim sistemi süreci "
              "başlatır. İşi toplu yaptırın ya da aynı işi gören Python kütüphanesini kullanın."),
}

# Kurallar sitede ve raporlarda bu gruplarla gösterilir
CATEGORIES = {
    "veritabani": ["YK001", "YK021", "YK022", "YK023"],
    "dongu": ["YK002", "YK003", "YK004", "YK006", "YK009", "YK010", "YK011", "YK013",
              "YK016", "YK017", "YK025", "YK026", "YK028", "YK029"],
    "veri_bilimi": ["YK007", "YK018", "YK027"],
    "kaynak": ["YK005", "YK008", "YK012", "YK014", "YK015", "YK019", "YK020", "YK024", "YK030"],
}
CATEGORY_OF = {k: c for c, ks in CATEGORIES.items() for k in ks}

ROW_ITER = {"iterrows", "itertuples"}
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "request"}
LOAD_CALLS = {("np", "load"), ("numpy", "load"), ("np", "loadtxt"), ("np", "genfromtxt"),
              ("torch", "load"), ("joblib", "load"), ("pickle", "load"), ("yaml", "load")}
LOAD_NAMES = {"load_model", "from_pretrained"}                 # keras, transformers
PANDAS = {"pd", "pandas"}
NUMPY = {"np", "numpy"}
CONNECT_CALLS = {("sqlite3", "connect"), ("psycopg2", "connect"), ("psycopg", "connect"),
                 ("pymysql", "connect"), ("pyodbc", "connect"), ("oracledb", "connect"),
                 ("redis", "Redis"), ("redis", "StrictRedis"), ("pymongo", "MongoClient"),
                 (None, "MongoClient"), (None, "create_engine"), ("sqlalchemy", "create_engine"),
                 ("requests", "Session"), ("httpx", "Client"), ("httpx", "AsyncClient"),
                 ("boto3", "client"), ("boto3", "resource"), (None, "ThreadPoolExecutor"),
                 (None, "ProcessPoolExecutor"), ("multiprocessing", "Pool"), ("mp", "Pool")}
GROW_CALLS = {(p, "concat") for p in PANDAS} | {(n, f) for n in NUMPY for f in
                                                 ("append", "concatenate", "vstack", "hstack",
                                                  "row_stack", "column_stack")}
PROCESS_CALLS = {("subprocess", f) for f in ("run", "call", "check_call", "check_output", "Popen")} | \
                {("os", "system"), ("os", "popen")}
LOGGERS = {"logging", "logger", "log", "_logger", "_log", "LOGGER", "LOG"}
LOG_METHODS = {"debug", "info", "warning", "warn", "error", "critical", "exception"}
STR_METHODS = {"split", "rsplit", "splitlines", "lower", "upper", "casefold", "strip",
               "lstrip", "rstrip", "replace", "encode", "decode"}
SELECT_STAR = re.compile(r"\bselect\s+\*\s+from\b", re.IGNORECASE)
SQL_CALLS = {"execute", "executemany", "query", "raw", "read_sql", "read_sql_query", "text"}
FETCH_CALLS = {"fetchall", "fetchmany", "execute"}
LAZY_ITERS = {"range", "map", "filter", "zip", "enumerate", "reversed", "sorted"}


def _call_name(node):
    f = node.func
    if isinstance(f, ast.Attribute):
        base = f.value.id if isinstance(f.value, ast.Name) else None
        return base, f.attr
    if isinstance(f, ast.Name):
        return None, f.id
    return None, None


def _receiver(node):
    """Metot çağrısının sahibinin kısa adı: logger.info → logger, self.log.info → log."""
    f = node.func
    if isinstance(f, ast.Attribute):
        v = f.value
        if isinstance(v, ast.Name):
            return v.id
        if isinstance(v, ast.Attribute):
            return v.attr
    return None


def _names_in(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _targets(node):
    out = set()
    for t in ast.walk(node):
        if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store):
            out.add(t.id)
    return out


def _is_str_value(v):
    return (isinstance(v, ast.Constant) and isinstance(v.value, str)) or isinstance(v, ast.JoinedStr)


def _is_list_value(v):
    if isinstance(v, (ast.List, ast.ListComp)):
        return True
    if isinstance(v, ast.Call) and _call_name(v) in ((None, "list"), (None, "sorted")):
        return True
    return isinstance(v, ast.BinOp) and isinstance(v.op, ast.Add) and (
        isinstance(v.left, ast.List) or isinstance(v.right, ast.List))


def _is_range_len(it):
    """range(len(x)), range(x.shape[0]) ya da range(x.size) → x"""
    if not (isinstance(it, ast.Call) and _call_name(it) == (None, "range") and len(it.args) == 1):
        return None
    a = it.args[0]
    if isinstance(a, ast.Call) and _call_name(a) == (None, "len") and a.args and isinstance(a.args[0], ast.Name):
        return a.args[0].id
    if isinstance(a, ast.Subscript) and isinstance(a.value, ast.Attribute) and a.value.attr == "shape" \
            and isinstance(a.value.value, ast.Name):
        return a.value.value.id
    if isinstance(a, ast.Attribute) and a.attr == "size" and isinstance(a.value, ast.Name):
        return a.value.id
    return None


class _Visitor(ast.NodeVisitor):
    def __init__(self):
        self.findings = []
        self.loop_stack = []        # her döngüde değişen isimler (döngü değişkeni + gövdede atananlar)
        self.list_names = set()     # liste olarak atanmış isimler
        self.str_names = set()      # metin olarak atanmış isimler
        self.numpy = False          # modül numpy içe aktarıyor mu
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

    def _invariant(self, node):
        """Çağrının argümanları döngüde değişen hiçbir isme bağlı değilse True."""
        names = set()
        for a in node.args + [k.value for k in node.keywords]:
            names |= _names_in(a)
        return not (names & self._loop_vars())

    # --- içe aktarmalar
    def visit_Import(self, node):
        if any(a.name.split(".")[0] == "numpy" for a in node.names):
            self.numpy = True

    def visit_ImportFrom(self, node):
        if (node.module or "").split(".")[0] == "numpy":
            self.numpy = True

    # --- atamalar: hangi isimler liste ya da metin?
    def visit_Assign(self, node):
        v = node.value
        grows_self = isinstance(v, ast.BinOp) and isinstance(v.op, ast.Add) and isinstance(v.left, ast.Name)
        for t in node.targets:
            if not isinstance(t, ast.Name):
                continue
            self_ref = grows_self and v.left.id == t.id
            if _is_list_value(v) or (self_ref and t.id in self.list_names):
                self.list_names.add(t.id)
            elif not self_ref:
                self.list_names.discard(t.id)
            if _is_str_value(v):
                self.str_names.add(t.id)
            elif not self_ref:
                self.str_names.discard(t.id)
            if self.loop_stack and self_ref:
                if t.id in self.str_names:
                    self.add("YK010", node, f"{t.id} = {t.id} + ...")
                elif isinstance(v.right, (ast.List, ast.ListComp)) or t.id in self.list_names:
                    self.add("YK017", node, f"{t.id} = {t.id} + [...]")
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        if self.loop_stack and isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name) \
                and node.target.id in self.str_names:
            self.add("YK010", node, f"{node.target.id} += ...")
        self.generic_visit(node)

    # --- döngüler
    def _row_iter(self, it, at):
        if isinstance(it, ast.Call) and _call_name(it)[1] in ROW_ITER:
            self.add("YK007", at, f"{_call_name(it)[1]}()")
        if isinstance(it, ast.Call) and _call_name(it)[1] == "readlines" and not it.args:
            self.add("YK020", at, "readlines()")
        if isinstance(it, ast.Call) and _call_name(it) == (None, "list") and len(it.args) == 1 \
                and isinstance(it.args[0], ast.Call) and _call_name(it.args[0]) in {(None, n) for n in LAZY_ITERS}:
            self.add("YK029", at, f"list({_call_name(it.args[0])[1]}(...))")

    def _fetch_filter(self, it, filtered, at):
        if filtered and isinstance(it, ast.Call) and _call_name(it)[1] in FETCH_CALLS:
            self.add("YK023", at, f"{_call_name(it)[1]}() sonrası Python'da koşul")

    def visit_For(self, node):
        self._row_iter(node.iter, node)
        body = node.body
        self._fetch_filter(node.iter, len(body) == 1 and isinstance(body[0], ast.If) and not body[0].orelse, node)
        arr = _is_range_len(node.iter)
        if arr and self.numpy:
            i = _targets(node.target)
            for n in ast.walk(ast.Module(body=body, type_ignores=[])):
                if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and (_names_in(n.slice) & i):
                    self.add("YK027", node, f"{arr}[{', '.join(sorted(i))}]")
                    break
        # Döngünün üzerinde döndüğü ifade (node.iter) yalnızca bir kez çalışır
        self.visit(node.iter)
        if self.loop_stack:
            self.add("YK006", node)
        self.loop_stack.append(_targets(node.target) | _targets(ast.Module(body=node.body, type_ignores=[])))
        for child in node.body + node.orelse:
            self.visit(child)
        self.loop_stack.pop()

    visit_AsyncFor = visit_For

    def visit_While(self, node):
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            for n in ast.walk(node):
                if isinstance(n, ast.Call) and _call_name(n) in (("time", "sleep"), (None, "sleep")):
                    self.add("YK005", node)
        if all(isinstance(s, (ast.Pass, ast.Continue)) or
               (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)) for s in node.body):
            self.add("YK015", node)
        if self.loop_stack:
            self.add("YK006", node)
        self.loop_stack.append(_targets(node))
        self.generic_visit(node)
        self.loop_stack.pop()

    def _visit_comp(self, node):
        gens = node.generators
        for g in gens:
            self._row_iter(g.iter, node)
        self._fetch_filter(gens[0].iter, any(g.ifs for g in gens), node)
        self.visit(gens[0].iter)                    # ilk kaynak yalnızca bir kez değerlendirilir
        tv = set()
        for g in gens:
            tv |= _targets(g.target)
        self.loop_stack.append(tv)
        for k, g in enumerate(gens):
            if k:
                self.visit(g.iter)
            for cond in g.ifs:
                self.visit(cond)
        for part in ([node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]):
            self.visit(part)
        self.loop_stack.pop()

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _visit_comp

    # --- çağrılar
    def visit_Call(self, node):
        base, name = _call_name(node)
        args = node.args
        if name == "apply" and any(k.arg == "axis" and isinstance(k.value, ast.Constant)
                                   and k.value.value in (1, "columns") for k in node.keywords):
            self.add("YK007", node, "apply(..., axis=1)")
        if (base, name) in ((None, "any"), (None, "all")) and len(args) == 1 and isinstance(args[0], ast.ListComp):
            self.add("YK016", node, f"{name}([...])")
        if (base, name) == (None, "len") and len(args) == 1 and isinstance(args[0], ast.Call) \
                and _call_name(args[0])[1] == "fetchall":
            self.add("YK022", node, "len(...fetchall())")
        if (base, name) == ("json", "loads") and len(args) == 1 and isinstance(args[0], ast.Call) \
                and _call_name(args[0]) == ("json", "dumps"):
            self.add("YK024", node, "json.loads(json.dumps(...))")
        if (base, name) == (None, "sum") and (
                (len(args) == 2 and isinstance(args[1], ast.List)) or
                any(k.arg == "start" and isinstance(k.value, ast.List) for k in node.keywords)):
            self.add("YK025", node, "sum(..., [])")
        if name in SQL_CALLS and args and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str) \
                and SELECT_STAR.search(args[0].value):
            self.add("YK021", node, "SELECT *")
        if self.loop_stack:
            self._loop_call(node, base, name, args)
        if self.func_stack:
            fn = self.func_stack[-1]
            if _call_name(node) == (None, fn["name"]):
                fn["self_calls"] += 1
        self.generic_visit(node)

    def _loop_call(self, node, base, name, args):
        invariant = False
        if name in DB_METHODS and base not in (None, "dict", "os", "self") and (
                name in ("execute", "query", "raw", "find_one", "fetchone")
                or base in ("session", "db", "cursor", "conn", "objects")):
            self.add("YK001", node, f"{base}.{name}(...)")
        elif (base, name) in INVARIANT_CALLS:
            if self._invariant(node):
                invariant = True
                self.add("YK003", node, f"{base}.{name}(...): {INVARIANT_CALLS[(base, name)]}")
        if base == "requests" and name in HTTP_METHODS and not invariant:
            self.add("YK008", node, f"requests.{name}(...)")
        first = args[0] if args else None
        if isinstance(first, ast.Constant) and first.value == 0 and base and (
                (name == "pop" and len(args) == 1) or (name == "insert" and len(args) == 2)):
            self.add("YK009", node, f"{base}.{name}(0{', ...' if name == 'insert' else ''})")
        loads = (base, name) in LOAD_CALLS or name in LOAD_NAMES or (base, name) == (None, "open") or (
            base in PANDAS and name.startswith("read_") and name != "read_csv")
        if loads and self._invariant(node) and args:
            self.add("YK012", node, f"{base + '.' if base else ''}{name}(...)")
        if name in ("index", "count") and base in self.list_names:
            self.add("YK013", node, f"{base}.{name}(...)")
        if (base, name) in CONNECT_CALLS:
            self.add("YK014", node, f"{base + '.' if base else ''}{name}(...)")
        if (base, name) in GROW_CALLS:
            self.add("YK018", node, f"{base}.{name}(...)")
        if name in LOG_METHODS and _receiver(node) in LOGGERS and first is not None and (
                isinstance(first, ast.JoinedStr) or
                (isinstance(first, ast.Call) and isinstance(first.func, ast.Attribute) and first.func.attr == "format") or
                (isinstance(first, ast.BinOp) and isinstance(first.op, ast.Mod))):
            self.add("YK019", node, f"{_receiver(node)}.{name}(f'...')")
        if name in STR_METHODS and base and base not in self._loop_vars() and base not in ("str", "bytes", "os", "re") \
                and not invariant and self._invariant(node):
            self.add("YK028", node, f"{base}.{name}(...)")
        if (base, name) in PROCESS_CALLS:
            self.add("YK030", node, f"{base}.{name}(...)")

    def visit_Compare(self, node):
        if self.loop_stack:
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.In, ast.NotIn)):
                    if isinstance(comp, ast.Name) and comp.id in self.list_names:
                        self.add("YK002", node, f"'{comp.id}' bir liste")
                    elif isinstance(comp, ast.List):
                        self.add("YK002", node, "sabit liste")
                    elif isinstance(comp, ast.Call) and _call_name(comp)[1] == "values" and not comp.args:
                        self.add("YK026", node, "in ....values()")
        self.generic_visit(node)

    def visit_Subscript(self, node):
        v, s = node.value, node.slice
        if isinstance(v, ast.Call) and _call_name(v) == (None, "sorted") and len(v.args) == 1:
            idx = s.value if isinstance(s, ast.Constant) else (
                -s.operand.value if isinstance(s, ast.UnaryOp) and isinstance(s.op, ast.USub)
                and isinstance(s.operand, ast.Constant) else None)
            if idx in (0, -1):
                self.add("YK011", node, f"sorted(...)[{idx}]")
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
        saved = self.loop_stack, self.list_names, self.str_names
        self.loop_stack, self.list_names, self.str_names = [], set(self.list_names), set(self.str_names)
        self.generic_visit(node)
        self.loop_stack, self.list_names, self.str_names = saved
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
