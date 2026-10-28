"""Statik analiz: Python kodunda enerji israfına yol açan kalıpları bulur.

Kod çalıştırılmaz; yalnızca sözdizimi ağacı (AST) incelenir. Bu yüzden
stantta ziyaretçinin yapıştırdığı kodu güvenle analiz edebilir.
Kuralların metinleri ve kaynakları kurallar.py dosyasındadır.
"""
from __future__ import annotations

import ast
import json
import re
import urllib.request

from . import config
from .kurallar import CATEGORIES, CATEGORY_OF, KATEGORILER, RULES, RULES_EN, SOURCES  # noqa: F401

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
                 (None, "ProcessPoolExecutor"), ("multiprocessing", "Pool"), ("mp", "Pool"),
                 ("smtplib", "SMTP"), ("smtplib", "SMTP_SSL"), ("socket", "create_connection")}
GROW_CALLS = {(p, "concat") for p in PANDAS} | {(n, f) for n in NUMPY for f in
                                                 ("append", "concatenate", "vstack", "hstack",
                                                  "row_stack", "column_stack")}
PROCESS_CALLS = {("subprocess", f) for f in ("run", "call", "check_call", "check_output", "Popen")} | \
                {("os", "system"), ("os", "popen")}
LOGGERS = {"logging", "logger", "log", "_logger", "_log", "LOGGER", "LOG"}
LOG_METHODS = {"debug", "info", "warning", "warn", "error", "critical", "exception"}
STR_METHODS = {"split", "rsplit", "splitlines", "lower", "upper", "casefold", "strip",
               "lstrip", "rstrip", "replace", "encode", "decode"}
STR_APPLY = STR_METHODS | {"startswith", "endswith", "title", "capitalize", "zfill", "isdigit",
                           "isalpha", "isnumeric", "find", "count", "contains"}
SELECT_STAR = re.compile(r"\bselect\s+\*\s+from\b", re.I)
ORDER_RANDOM = re.compile(r"order\s+by\s+(rand|random)\s*\(", re.I)
LEADING_LIKE = re.compile(r"\blike\s+['\"]%", re.I)
WRITE_SQL = re.compile(r"^\s*(insert|update|delete|replace)\b", re.I)
AGGREGATE_SQL = re.compile(r"\b(count|sum|max|min|avg|exists)\s*\(", re.I)
SQL_CALLS = {"execute", "executemany", "query", "raw", "read_sql", "read_sql_query", "text"}
FETCH_CALLS = {"fetchall", "fetchmany", "execute"}
LAZY_ITERS = {"range", "map", "filter", "zip", "enumerate", "reversed", "sorted"}
RE_FUNCS = {"match", "search", "fullmatch", "sub", "subn", "split", "findall", "finditer"}
RE_SPECIAL = set(".^$*+?{}[]\\|()")
ARRAY_MAKERS = {"array", "asarray", "zeros", "ones", "full", "arange", "linspace", "eye",
                "tensor", "as_tensor", "from_numpy"}
REDIS_CMDS = {"get", "set", "hget", "hset", "hgetall", "incr", "decr", "sadd", "srem", "lpush",
              "rpush", "exists", "delete", "expire", "zadd"}
WAIT_PREDICATES = {"is_set", "empty", "full", "done", "is_alive", "locked", "running", "is_running",
                   "ready", "isSet", "exists"}
NO_GRAD = {"torch.no_grad()", "torch.inference_mode()", "no_grad()", "inference_mode()"}


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


def _root(node):
    """Öznitelik/çağrı zincirinin kökündeki isim: np.random.rand(...) → np."""
    while isinstance(node, (ast.Attribute, ast.Call, ast.Subscript)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def _names_in(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _loads(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def _targets(node):
    out = set()
    for t in ast.walk(node):
        if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store):
            out.add(t.id)
    return out


def _const_str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _sql(call):
    """SQL çağrısının ilk argümanı sabit metinse o metin."""
    _, name = _call_name(call)
    return _const_str(call.args[0]) if name in SQL_CALLS and call.args else None


def _is_str_value(v):
    return _const_str(v) is not None or isinstance(v, ast.JoinedStr)


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


def _int(node):
    """Sabit tam sayı (eksi işaretli olabilir) ya da None."""
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant) \
            and type(node.operand.value) is int:
        return -node.operand.value
    return None


def _append_target(stmt):
    """`L.append(x)` ifadesi ise (L, x)."""
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and _call_name(stmt.value)[1] == "append" \
            and _call_name(stmt.value)[0] and len(stmt.value.args) == 1 and not stmt.value.keywords:
        return _call_name(stmt.value)[0], stmt.value.args[0]
    return None


def _name_call(fn, args, keywords=()):
    return ast.Call(func=ast.Name(id=fn, ctx=ast.Load()), args=list(args), keywords=list(keywords))


def simplify(node):
    """Anlamı değiştirmeden sadeleştirilebilen çağrı ya da kurgu: (kural, yeni düğüm) ya da None.

    Analiz bu fonksiyonla işaretler, düzeltme motoru aynısıyla yeniden yazar."""
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
        if len(node.generators) != 1:
            return None
        g = node.generators[0]
        if g.ifs or g.is_async:
            return None
        if not isinstance(node, ast.DictComp) and isinstance(node.elt, ast.Name) and isinstance(g.target, ast.Name) \
                and node.elt.id == g.target.id:
            return "YK064", _name_call("list" if isinstance(node, ast.ListComp) else "set", [g.iter])
        if isinstance(node, ast.DictComp) and isinstance(g.target, ast.Tuple) and len(g.target.elts) == 2 \
                and all(isinstance(e, ast.Name) for e in g.target.elts) and isinstance(node.key, ast.Name) \
                and isinstance(node.value, ast.Name) and node.key.id == g.target.elts[0].id \
                and node.value.id == g.target.elts[1].id:
            return "YK064", _name_call("dict", [g.iter])
        return None
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and len(node.args) == 1):
        return None
    fn, arg, kw = node.func.id, node.args[0], node.keywords
    if fn in ("sum", "min", "max") and isinstance(arg, ast.ListComp):
        return "YK065", _name_call(fn, [ast.GeneratorExp(elt=arg.elt, generators=arg.generators)], kw)
    if not kw and isinstance(arg, ast.GeneratorExp):
        if fn == "list":
            return "YK113", ast.ListComp(elt=arg.elt, generators=arg.generators)
        if fn == "set":
            return "YK113", ast.SetComp(elt=arg.elt, generators=arg.generators)
        if fn == "dict" and isinstance(arg.elt, ast.Tuple) and len(arg.elt.elts) == 2:
            return "YK113", ast.DictComp(key=arg.elt.elts[0], value=arg.elt.elts[1], generators=arg.generators)
    if not kw:
        if fn == "list" and isinstance(arg, (ast.List, ast.ListComp)):
            return "YK066", arg
        if fn == "tuple" and isinstance(arg, (ast.List, ast.Tuple)):
            return "YK066", ast.Tuple(elts=arg.elts, ctx=ast.Load())
        if fn == "set" and isinstance(arg, (ast.List, ast.Tuple)) and arg.elts:
            return "YK066", ast.Set(elts=arg.elts)
        if fn == "set" and isinstance(arg, ast.ListComp):
            return "YK066", ast.SetComp(elt=arg.elt, generators=arg.generators)
        if fn == "dict" and isinstance(arg, (ast.List, ast.Tuple)) and arg.elts and \
                all(isinstance(e, ast.Tuple) and len(e.elts) == 2 for e in arg.elts):
            return "YK066", ast.Dict(keys=[e.elts[0] for e in arg.elts], values=[e.elts[1] for e in arg.elts])
    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and len(arg.args) == 1:
        inner, ikw, x = arg.func.id, arg.keywords, arg.args[0]
        if fn in ("list", "tuple", "set") and not kw:
            if inner in ("list", "tuple") and not ikw:
                return "YK062", _name_call(fn, [x])
            if inner == "sorted" and fn == "list":
                return "YK062", arg
            if inner == "sorted" and fn == "set":
                return "YK062", _name_call("set", [x])
        if fn == "sorted":
            if inner in ("list", "tuple") and not ikw:
                return "YK062", _name_call("sorted", [x], kw)
            if inner == "sorted" and not ikw and not kw:
                return "YK062", _name_call("sorted", [x])
    return None


def overlapping_recursion(fn):
    """Fonksiyon kendini en az iki kez, parametresinden türetilmiş sayılarla (n - 1, n - 2)
    çağırıyorsa True: aynı alt sonuçlar tekrar tekrar hesaplanır. Ağaç gezme gibi
    alt problemleri örtüşmeyen özyineleme (gez(dugum.sol), gez(dugum.sag)) sayılmaz."""
    params = {a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs}

    def derived(n):
        return isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == fn.name and any(
            isinstance(x, ast.BinOp) and isinstance(x.op, (ast.Sub, ast.Add, ast.FloorDiv, ast.RShift))
            and (_names_in(x) & params) for x in n.args + [k.value for k in n.keywords])

    # Sonuçlar tek bir ifadede birleştiriliyor olmalı (return f(n-1) + f(n-2)); sonucu kullanılmayan,
    # yan etkili özyineleme (Hanoi kuleleri, çizim) önbelleğe alınamaz.
    for st in ast.walk(fn):
        if isinstance(st, (ast.Return, ast.Assign, ast.AugAssign, ast.AnnAssign)) and st.value is not None \
                and sum(1 for n in ast.walk(st.value) if derived(n)) >= 2:
            return True
    return False


def _simple_lambda(lam):
    """lambda x: <yalnızca x, sabitler ve işleçler> → True"""
    if not (isinstance(lam, ast.Lambda) and len(lam.args.args) == 1):
        return False
    arg = lam.args.args[0].arg
    body = lam.body
    if not isinstance(body, (ast.BinOp, ast.UnaryOp, ast.Compare, ast.BoolOp)):
        return False
    for n in ast.walk(body):
        if isinstance(n, (ast.Call, ast.Attribute, ast.Subscript, ast.Lambda)):
            return False
        if isinstance(n, ast.Name) and n.id != arg:
            return False
    return True


def _string_lambda(lam):
    """lambda x: x.lower() ya da len(x) → True"""
    if not (isinstance(lam, ast.Lambda) and len(lam.args.args) == 1 and isinstance(lam.body, ast.Call)):
        return False
    arg, c = lam.args.args[0].arg, lam.body
    if isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Name) and c.func.value.id == arg:
        return c.func.attr in STR_APPLY
    return _call_name(c) == (None, "len") and len(c.args) == 1 and isinstance(c.args[0], ast.Name) and c.args[0].id == arg


class _Visitor(ast.NodeVisitor):
    def __init__(self):
        self.findings = []
        self.loop_stack = []        # her döngüde değişen isimler (döngü değişkeni + gövdede atananlar)
        self.loop_nodes = []
        self.list_names = set()     # liste olarak atanmış isimler
        self.str_names = set()      # metin olarak atanmış isimler
        self.dict_names = set()
        self.set_names = set()
        self.np_names = set()       # NumPy dizisi olarak atanmış isimler
        self.redis_names = set()
        self.numpy = False          # modül numpy içe aktarıyor mu
        self.func_stack = []
        self.eval_models = [set()]  # eval() moduna alınmış modeller (fonksiyon başına)
        self.no_grad = 0
        self.async_depth = 0
        self.in_return = 0          # return ifadesindeki çağrı döngüde bir kez çalışır
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

    def _block(self, stmts):
        """Ardışık ifadelerde görülen kalıplar."""
        for a, b in zip(stmts, stmts[1:]):
            x, y = _append_target(a), _append_target(b)
            if x and y and x[0] == y[0]:
                self.add("YK112", a, f"{x[0]}.append(...) × 2+")

    # --- modül ve içe aktarmalar
    def visit_Module(self, node):
        self._block(node.body)
        self.generic_visit(node)

    def visit_Import(self, node):
        if any(a.name.split(".")[0] == "numpy" for a in node.names):
            self.numpy = True
        if self.loop_stack:
            self.add("YK059", node, "import")

    def visit_ImportFrom(self, node):
        if (node.module or "").split(".")[0] == "numpy":
            self.numpy = True
        if self.loop_stack:
            self.add("YK059", node, "from ... import")

    # --- atamalar: isimlerin türünü izle
    def visit_Assign(self, node):
        v = node.value
        grows_self = isinstance(v, ast.BinOp) and isinstance(v.op, ast.Add) and isinstance(v.left, ast.Name)
        for t in node.targets:
            if isinstance(t, ast.Name):
                self._track(t.id, v, grows_self and v.left.id == t.id, node)
            self._assign_target(t, v, node)
        self.generic_visit(node)

    def _track(self, name, v, self_ref, node):
        if _is_list_value(v) or (self_ref and name in self.list_names):
            self.list_names.add(name)
        elif not self_ref:
            self.list_names.discard(name)
        if _is_str_value(v):
            self.str_names.add(name)
        elif not self_ref:
            self.str_names.discard(name)
        (self.dict_names.add if isinstance(v, (ast.Dict, ast.DictComp)) or
         (isinstance(v, ast.Call) and _call_name(v) == (None, "dict")) else self.dict_names.discard)(name)
        (self.set_names.add if isinstance(v, (ast.Set, ast.SetComp)) or
         (isinstance(v, ast.Call) and _call_name(v) == (None, "set")) else self.set_names.discard)(name)
        (self.np_names.add if isinstance(v, ast.Call) and _root(v.func) in NUMPY else self.np_names.discard)(name)
        if isinstance(v, ast.Call) and (_call_name(v) in (("redis", "Redis"), ("redis", "StrictRedis")) or
                                        (_call_name(v)[1] == "from_url" and _root(v.func) in ("redis", "Redis"))):
            self.redis_names.add(name)
        if self.loop_stack and self_ref:
            if name in self.str_names:
                self.add("YK010", node, f"{name} = {name} + ...")
            elif isinstance(v.right, (ast.List, ast.ListComp)) or name in self.list_names:
                self.add("YK017", node, f"{name} = {name} + [...]")
        if self.loop_stack and isinstance(v, ast.Call) and _call_name(v) == (name, "append"):
            self.add("YK075", node, f"{name} = {name}.append(...)")
        if isinstance(v, ast.Subscript) and isinstance(v.value, ast.Name) and v.value.id == name \
                and isinstance(v.slice, ast.Slice) and v.slice.lower is None and v.slice.upper is None \
                and _int(v.slice.step) == -1:
            self.add("YK107", node, f"{name} = {name}[::-1]")

    def _assign_target(self, t, v, node):
        if not isinstance(t, ast.Subscript):
            return
        if self.loop_stack and isinstance(t.value, ast.Attribute) and t.value.attr == "loc" \
                and isinstance(t.value.value, ast.Name) and isinstance(t.slice, ast.Call) \
                and _call_name(t.slice) == (None, "len"):
            self.add("YK076", node, "df.loc[len(df)] = ...")
        if isinstance(t.value, ast.Subscript) and isinstance(t.value.value, ast.Name) and _const_str(t.value.slice):
            self.add("YK082", node, "df['sütun'][...] = ...")
        if isinstance(t.value, ast.Name) and isinstance(v, ast.BinOp) and isinstance(v.op, ast.Add) \
                and isinstance(v.left, ast.Call) and _call_name(v.left) == (t.value.id, "get") \
                and len(v.left.args) == 2 and _int(v.left.args[1]) == 0:
            self.add("YK057", node, "d[k] = d.get(k, 0) + 1")

    def visit_AugAssign(self, node):
        if self.loop_stack and isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name) \
                and node.target.id in self.str_names:
            self.add("YK010", node, f"{node.target.id} += ...")
        self.generic_visit(node)

    def visit_Delete(self, node):
        if self.loop_stack:
            for t in node.targets:
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and _int(t.slice) == 0:
                    self.add("YK046", node, f"del {t.value.id}[0]")
        self.generic_visit(node)

    # --- koşullar
    def visit_If(self, node):
        t = node.test
        if isinstance(t, ast.Compare) and len(t.ops) == 1 and isinstance(t.comparators[0], ast.Name):
            d, op, b = t.comparators[0].id, t.ops[0], node.body
            sub_d = lambda x: isinstance(x, ast.Subscript) and isinstance(x.value, ast.Name) and x.value.id == d
            if isinstance(op, ast.In) and len(b) == 1 and isinstance(b[0], ast.AugAssign) and sub_d(b[0].target) \
                    and len(node.orelse) == 1 and isinstance(node.orelse[0], ast.Assign) and sub_d(node.orelse[0].targets[0]):
                self.add("YK057", node, f"if k in {d}: {d}[k] += ... else: ...")
            if isinstance(op, ast.NotIn) and len(b) == 1 and isinstance(b[0], ast.Assign) and sub_d(b[0].targets[0]) \
                    and isinstance(b[0].value, (ast.List, ast.Dict, ast.Set)) and not getattr(b[0].value, "elts", getattr(b[0].value, "keys", [])):
                self.add("YK058", node, f"if k not in {d}: {d}[k] = []")
            if isinstance(op, ast.In) and len(b) == 1 and not node.orelse and isinstance(b[0], ast.Expr) \
                    and isinstance(b[0].value, ast.Call) and _call_name(b[0].value) == (d, "remove"):
                self.add("YK106", node, f"if x in {d}: {d}.remove(x)")
        self._block(node.body)
        self._block(node.orelse)
        self.generic_visit(node)

    def visit_With(self, node):
        guard = any(isinstance(i.context_expr, ast.Call) and (
            ast.unparse(i.context_expr) in NO_GRAD or ast.unparse(i.context_expr).replace(" ", "")
            in ("torch.set_grad_enabled(False)", "set_grad_enabled(False)")) for i in node.items)
        self.no_grad += guard
        self._block(node.body)
        self.generic_visit(node)
        self.no_grad -= guard

    visit_AsyncWith = visit_With

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

    def _loop_body(self, node):
        """Döngü gövdesinin bütününe bakan kalıplar (Ruff PERF/FURB benzeri)."""
        body = node.body
        if any(isinstance(s, ast.Try) for s in body):
            self.add("YK049", node, "try/except")
        if not isinstance(node, ast.For) or node.orelse or len(body) != 1:
            return
        tgt = node.target.id if isinstance(node.target, ast.Name) else None
        s = body[0]
        inner = s.body[0] if isinstance(s, ast.If) and not s.orelse and len(s.body) == 1 else s
        ap = _append_target(inner)
        if ap and ap[0] in self.list_names and ap[0] != tgt:
            if inner is s and isinstance(ap[1], ast.Name) and ap[1].id == tgt:
                self.add("YK051", node, f"{ap[0]}.append({tgt})")
            else:
                self.add("YK050", node, f"{ap[0]}.append(...)")
        if isinstance(inner, ast.Assign) and len(inner.targets) == 1 and isinstance(inner.targets[0], ast.Subscript) \
                and isinstance(inner.targets[0].value, ast.Name) and inner.targets[0].value.id in self.dict_names:
            self.add("YK052", node, f"{inner.targets[0].value.id}[...] = ...")
        if inner is s and isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and _call_name(s.value)[1] == "add" \
                and _call_name(s.value)[0] in self.set_names and len(s.value.args) == 1 \
                and isinstance(s.value.args[0], ast.Name) and s.value.args[0].id == tgt:
            self.add("YK053", node, f"{_call_name(s.value)[0]}.add({tgt})")
        if inner is s and isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and _call_name(s.value)[1] == "write" \
                and len(s.value.args) == 1 and tgt and tgt in _names_in(s.value.args[0]):
            self.add("YK105", node, f"{_call_name(s.value)[0] or 'f'}.write(...)")

    def visit_For(self, node):
        self._row_iter(node.iter, node)
        body, it = node.body, node.iter
        self._fetch_filter(it, len(body) == 1 and isinstance(body[0], ast.If) and not body[0].orelse, node)
        loads = _loads(ast.Module(body=body, type_ignores=[]))
        arr = _is_range_len(it)
        i = _targets(node.target)
        subs = [n for n in ast.walk(ast.Module(body=body, type_ignores=[]))
                if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and (_names_in(n.slice) & i)]
        if arr and self.numpy and subs:
            self.add("YK027", node, f"{arr}[{', '.join(sorted(i))}]")
        elif arr and any(s.value.id == arr for s in subs) and isinstance(node.target, ast.Name):
            self.add("YK056", node, f"range(len({arr}))")
        if isinstance(node.target, ast.Tuple) and len(node.target.elts) == 2 and isinstance(it, ast.Call) \
                and _call_name(it)[1] == "items" and not it.args:
            for e in node.target.elts:
                if isinstance(e, ast.Name) and e.id != "_" and not e.id.startswith("_") and e.id not in loads:
                    self.add("YK054", node, f"{e.id} kullanılmıyor")
        if isinstance(node.target, ast.Name):
            d = it.id if isinstance(it, ast.Name) else (
                _call_name(it)[0] if isinstance(it, ast.Call) and _call_name(it)[1] == "keys" and not it.args else None)
            if d and any(isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == d
                         and isinstance(n.slice, ast.Name) and n.slice.id == node.target.id and isinstance(n.ctx, ast.Load)
                         for n in ast.walk(ast.Module(body=body, type_ignores=[]))):
                self.add("YK055", node, f"{d}[{node.target.id}]")
        self._loop_body(node)
        # Döngünün üzerinde döndüğü ifade (node.iter) yalnızca bir kez çalışır
        self.visit(it)
        if self.loop_stack:
            self.add("YK006", node)
        self.loop_stack.append(i | _targets(ast.Module(body=body, type_ignores=[])))
        self.loop_nodes.append(node)
        self._block(body)
        for child in body + node.orelse:
            self.visit(child)
        self.loop_nodes.pop()
        self.loop_stack.pop()

    visit_AsyncFor = visit_For

    def visit_While(self, node):
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            for n in ast.walk(node):
                if isinstance(n, ast.Call) and _call_name(n) in (("time", "sleep"), (None, "sleep")):
                    self.add("YK005", node)
        # Koşuldaki çağrı iş yapıyorsa (while f.read(n): pass) bu bekleme değil, boşaltmadır
        calls = [n for n in ast.walk(node.test) if isinstance(n, ast.Call)]
        if all(isinstance(s, (ast.Pass, ast.Continue)) or
               (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)) for s in node.body) \
                and all(_call_name(c)[1] in WAIT_PREDICATES for c in calls):
            self.add("YK015", node)
        self._loop_body(node)
        if self.loop_stack:
            self.add("YK006", node)
        self.loop_stack.append(_targets(node))
        self.loop_nodes.append(node)
        self._block(node.body)
        self.generic_visit(node)
        self.loop_nodes.pop()
        self.loop_stack.pop()

    def _visit_comp(self, node):
        gens = node.generators
        for g in gens:
            self._row_iter(g.iter, node)
        self._fetch_filter(gens[0].iter, any(g.ifs for g in gens), node)
        s = simplify(node)
        if s:
            self.add(s[0], node, "kurgu")
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
        args, kws = node.args, {k.arg: k.value for k in node.keywords}
        first = args[0] if args else None
        if name == "apply" and isinstance(kws.get("axis"), ast.Constant) and kws["axis"].value in (1, "columns"):
            self.add("YK007", node, "apply(..., axis=1)")
        elif name == "apply" and first is not None:
            if _simple_lambda(first):
                self.add("YK077", node, "apply(lambda x: ...)")
            elif _string_lambda(first):
                self.add("YK078", node, "apply(lambda x: x.<metin>())")
        if name == "apply" and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Call) \
                and _call_name(node.func.value)[1] == "groupby":
            self.add("YK083", node, "groupby(...).apply(...)")
        if (base, name) in ((None, "any"), (None, "all")) and len(args) == 1 and isinstance(first, ast.ListComp):
            self.add("YK016", node, f"{name}([...])")
        s = simplify(node)
        if s:
            self.add(s[0], node, f"{name}(...)")
        if (base, name) == (None, "len") and len(args) == 1 and isinstance(first, ast.Call):
            if _call_name(first)[1] == "fetchall":
                self.add("YK022", node, "len(...fetchall())")
            elif ".objects." in ast.unparse(first) or (_call_name(first)[1] == "all" and not first.args):
                self.add("YK035", node, "len(queryset)")
            elif _call_name(first) in ((None, "list"), (None, "tuple")):
                self.add("YK067", node, "len(list(...))")
        if (base, name) in ((None, "sum"), (None, "min"), (None, "max")) and len(args) == 1:
            if isinstance(first, (ast.GeneratorExp, ast.ListComp)) and isinstance(first.generators[0].iter, ast.Call) \
                    and (_call_name(first.generators[0].iter)[1] in FETCH_CALLS or ".objects." in ast.unparse(first.generators[0].iter)):
                self.add("YK039", node, f"{name}(... satırlar ...)")
            if isinstance(first, ast.Name) and first.id in self.np_names:
                self.add("YK080", node, f"{name}({first.id})")
        if (base, name) == ("json", "loads") and len(args) == 1 and isinstance(first, ast.Call) \
                and _call_name(first) == ("json", "dumps"):
            self.add("YK024", node, "json.loads(json.dumps(...))")
        if (base, name) == (None, "sum") and (
                (len(args) == 2 and isinstance(args[1], ast.List)) or isinstance(kws.get("start"), ast.List)):
            self.add("YK025", node, "sum(..., [])")
        self._sql_checks(node, base, name)
        if (base, name) in ((None, "map"), (None, "filter")) and args and isinstance(first, ast.Lambda):
            self.add("YK061", node, f"{name}(lambda ...)")
        if (base, name) == (None, "reversed") and len(args) == 1 and isinstance(first, ast.Call) \
                and _call_name(first) == (None, "sorted"):
            self.add("YK063", node, "reversed(sorted(...))")
        if base == "re" and name in RE_FUNCS and _const_str(first) is not None and _const_str(first):
            if not (set(_const_str(first)) & RE_SPECIAL):
                self.add("YK069", node, f"re.{name}('{_const_str(first)}', ...)")
            elif self.loop_stack:
                self.add("YK070", node, f"re.{name}(...)")
        f = node.func
        if name == "replace" and isinstance(f, ast.Attribute) and isinstance(f.value, ast.Call) \
                and _call_name(f.value)[1] == "replace" and isinstance(f.value.func, ast.Attribute) \
                and isinstance(f.value.func.value, ast.Call) and _call_name(f.value.func.value)[1] == "replace":
            self.add("YK071", node, ".replace().replace().replace()")
        if name in ("split", "splitlines") and isinstance(f, ast.Attribute) and isinstance(f.value, ast.Call) \
                and _call_name(f.value)[1] == "read" and not f.value.args:
            self.add("YK073", node, f"read().{name}(...)")
        if (base, name) in (("np", "vectorize"), ("numpy", "vectorize")):
            self.add("YK079", node, "np.vectorize")
        if base in PANDAS and name == "read_csv" and "usecols" not in kws and "chunksize" not in kws:
            self.add("YK084", node, "read_csv(...)")
        if name == "to_csv":
            self.add("YK085", node, "to_csv(...)")
        if (base, name) == (None, "list") and len(args) == 1 and isinstance(first, ast.Name) and first.id in self.np_names:
            self.add("YK086", node, f"list({first.id})")
        if base == "requests" and name in HTTP_METHODS:
            if "timeout" not in kws:
                self.add("YK097", node, f"requests.{name}(...)")
            if self.async_depth:
                self.add("YK095", node, f"requests.{name}(...)")
        if self.async_depth and (base, name) == ("time", "sleep"):
            self.add("YK096", node, "time.sleep")
        if (base, name) in PROCESS_CALLS and isinstance(kws.get("shell"), ast.Constant) and kws["shell"].value is True:
            self.add("YK103", node, "shell=True")
        if name == "run" and isinstance(kws.get("debug"), ast.Constant) and kws["debug"].value is True:
            self.add("YK104", node, "run(debug=True)")
        if name == "count" and _const_str(first) == "1" and isinstance(f, ast.Attribute) and isinstance(f.value, ast.Call) \
                and _call_name(f.value) == (None, "bin"):
            self.add("YK109", node, "bin(x).count('1')")
        if (base, name) == ("math", "log") and len(args) == 2 and _int(args[1]) in (2, 10):
            self.add("YK110", node, f"math.log(x, {_int(args[1])})")
        if self.loop_stack:
            self._loop_call(node, base, name, args, kws)
        self.generic_visit(node)

    def _sql_checks(self, node, base, name):
        sql = _sql(node)
        if sql is not None:
            if SELECT_STAR.search(sql):
                self.add("YK021", node, "SELECT *")
            if ORDER_RANDOM.search(sql):
                self.add("YK037", node, "ORDER BY RANDOM()")
            if LEADING_LIKE.search(sql):
                self.add("YK038", node, "LIKE '%...'")
        if name in ("execute", "executemany") and node.args:
            q = node.args[0]
            if isinstance(q, ast.JoinedStr) or (isinstance(q, ast.BinOp) and isinstance(q.op, ast.Mod)) or \
                    (isinstance(q, ast.Call) and isinstance(q.func, ast.Attribute) and q.func.attr == "format"):
                self.add("YK040", node, "f-string / format ile SQL")
        if name == "fetchone" and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Call):
            q = _sql(node.func.value)
            if q and q.lstrip().lower().startswith("select") and not re.search(r"\b(where|limit)\b", q, re.I) \
                    and not AGGREGATE_SQL.search(q):
                self.add("YK036", node, "fetchone() ve LIMIT yok")

    def _loop_call(self, node, base, name, args, kws):
        invariant = False
        first = args[0] if args else None
        write_sql = name in ("execute",) and _const_str(first) is not None and WRITE_SQL.match(_const_str(first))
        if write_sql:
            self.add("YK032", node, f"{base or ''}.execute('{_const_str(first).split()[0].upper()} ...')")
        elif name in DB_METHODS and base not in (None, "dict", "os", "self") and (
                name in ("execute", "query", "raw", "find_one", "fetchone")
                or base in ("session", "db", "cursor", "conn", "objects")):
            self.add("YK001", node, f"{base}.{name}(...)")
        elif (base, name) in INVARIANT_CALLS:
            if self._invariant(node):
                invariant = True
                self.add("YK003", node, f"{base}.{name}(...): {INVARIANT_CALLS[(base, name)]}")
        if base == "requests" and name in HTTP_METHODS and not invariant:
            self.add("YK008", node, f"requests.{name}(...)")
        if isinstance(first, ast.Constant) and first.value == 0 and base and (
                (name == "pop" and len(args) == 1) or (name == "insert" and len(args) == 2)):
            self.add("YK009", node, f"{base}.{name}(0{', ...' if name == 'insert' else ''})")
        loads = (base, name) in LOAD_CALLS or name in LOAD_NAMES or (base, name) == (None, "open") or (
            base in PANDAS and name.startswith("read_") and name != "read_csv")
        if loads and self._invariant(node) and args and not self.in_return:
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
        if name == "commit" and not args:
            self.add("YK031", node, f"{base or ''}.commit()")
        f = node.func
        if name == "create" and isinstance(f, ast.Attribute) and isinstance(f.value, ast.Attribute) and f.value.attr == "objects":
            self.add("YK033", node, "objects.create(...)")
        if name == "save" and not args and not kws and isinstance(f, ast.Attribute):
            self.add("YK034", node, ".save()")
        if name == "remove" and base in self.list_names:
            self.add("YK045", node, f"{base}.remove(...)")
        if name == "join" and len(args) == 1 and isinstance(first, ast.Name) and self.loop_nodes \
                and first.id not in self.loop_stack[-1]:          # her adımda yeniden kurulan liste sayılmaz
            lst = first.id
            loop = self.loop_nodes[-1]
            if any((isinstance(n, ast.Call) and _call_name(n) in ((lst, "append"), (lst, "extend"))) or
                   (isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) and n.target.id == lst)
                   for n in ast.walk(loop)):
                self.add("YK047", node, f"join({lst})")
        if (base, name) in (("copy", "deepcopy"), (None, "deepcopy")):
            self.add("YK048", node, "deepcopy")
        if (base, name) in ((None, "dict"), (None, "list"), (None, "tuple")) and not args and not kws:
            self.add("YK060", node, f"{name}()")
        if base == "math" and args and self._invariant(node):
            self.add("YK068", node, f"math.{name}(...)")
        if _root(f) in NUMPY | {"torch"} and name in ARRAY_MAKERS and args and self._invariant(node):
            self.add("YK081", node, f"{_root(f)}.{name}(...)")
        if name in ("predict", "predict_proba", "decision_function") and args and not self._invariant(node):
            self.add("YK088", node, f".{name}(...)")
        if name in ("item", "cpu", "numpy") and not args and isinstance(f, ast.Attribute):
            self.add("YK089", node, f".{name}()")
        if isinstance(f, ast.Attribute) and _root(f.value) not in self._loop_vars() and (
                (name == "cuda" and not args) or (name == "to" and len(args) == 1 and (
                    (isinstance(first, ast.Name) and ("device" in first.id or "cuda" in first.id)) or
                    (isinstance(first, ast.Attribute) and first.attr == "device") or
                    (_const_str(first) or "").split(":")[0] in ("cuda", "cpu", "mps")))):
            self.add("YK090", node, f".{name}(...)")
        if isinstance(f, ast.Name) and f.id in self.eval_models[-1] and not self.no_grad:
            self.add("YK091", node, f"{f.id}(...) no_grad dışında")
        if name in ("get_object", "head_object", "get_item"):
            self.add("YK092", node, f".{name}(...)")
        if base in self.redis_names and name in REDIS_CMDS:
            self.add("YK093", node, f"{base}.{name}(...)")
        if name == "urlopen":
            self.add("YK094", node, "urlopen(...)")
        if name == "flush" and not args:
            self.add("YK098", node, ".flush()")
        if (base, name) == ("os", "fsync"):
            self.add("YK099", node, "os.fsync")
        if (base, name) == (None, "print"):
            self.add("YK100", node, "print(...)")
        if (base, name) in (("os", "listdir"), ("os", "scandir"), ("os", "walk"), ("glob", "glob"), ("glob", "iglob")) \
                and self._invariant(node):
            self.add("YK101", node, f"{base}.{name}(...)")
        if (base, name) in (("time", "sleep"), (None, "sleep")) and isinstance(first, ast.Constant) \
                and isinstance(first.value, (int, float)) and 0 < first.value < 0.05:
            self.add("YK102", node, f"sleep({first.value})")

    def visit_Compare(self, node):
        left = node.left
        for op, comp in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)):
                single = isinstance(comp, (ast.List, ast.Tuple, ast.Set)) and len(comp.elts) == 1
                if single:
                    self.add("YK108", node, "x in [y]")
                if self.loop_stack:
                    if isinstance(comp, ast.Name) and comp.id in self.list_names:
                        self.add("YK002", node, f"'{comp.id}' bir liste")
                    elif isinstance(comp, ast.List) and not single:
                        self.add("YK002", node, "sabit liste")
                    elif isinstance(comp, ast.Call) and _call_name(comp)[1] == "values" and not comp.args:
                        self.add("YK026", node, "in ....values()")
                    elif isinstance(comp, ast.Call) and _call_name(comp) in {(None, c) for c in
                                                                            ("set", "list", "tuple", "frozenset", "sorted")} \
                            and comp.args and self._invariant(comp):
                        self.add("YK044", node, f"in {_call_name(comp)[1]}(...)")
            if isinstance(left, ast.Call) and _call_name(left)[1] == "find" and _int(comp) in (-1, 0) \
                    and isinstance(op, (ast.Eq, ast.NotEq, ast.GtE, ast.Gt, ast.Lt)):
                self.add("YK072", node, "find(...) != -1")
            if isinstance(left, ast.Call) and _call_name(left)[1] == "nunique" and _int(comp) in (0, 1, 2):
                self.add("YK111", node, "nunique() == 1")
            if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(left, ast.Subscript) and isinstance(left.slice, ast.Slice) \
                    and _const_str(comp) is not None and left.slice.step is None:
                lo, hi, n = left.slice.lower, left.slice.upper, len(_const_str(comp))
                if (lo is None or _int(lo) == 0) and _int(hi) == n and n > 1:
                    self.add("YK074", node, f"s[:{n}] == '...'")
                elif hi is None and _int(lo) == -n and n > 1:
                    self.add("YK074", node, f"s[-{n}:] == '...'")
        self.generic_visit(node)

    def visit_Subscript(self, node):
        v, s = node.value, node.slice
        if isinstance(v, ast.Call) and _call_name(v) == (None, "sorted") and len(v.args) == 1:
            if _int(s) in (0, -1):
                self.add("YK011", node, f"sorted(...)[{_int(s)}]")
            if isinstance(s, ast.Slice) and s.step is None and (
                    (s.lower is None and _int(s.upper) is not None and _int(s.upper) > 0) or
                    (s.upper is None and _int(s.lower) is not None and _int(s.lower) < 0)):
                self.add("YK043", node, "sorted(...)[:k]")
            if isinstance(s, ast.Slice) and s.lower is None and s.upper is None and _int(s.step) == -1:
                self.add("YK063", node, "sorted(...)[::-1]")
        if isinstance(v, ast.ListComp) and _int(s) == 0:
            self.add("YK041", node, "[...][0]")
        if isinstance(v, ast.Call) and _call_name(v) == (None, "list") and len(v.args) == 1 and _int(s) == 0:
            self.add("YK042", node, "list(...)[0]")
        if self.loop_stack and isinstance(v, ast.Name) and isinstance(s, ast.Compare):
            col = s.left
            if ((isinstance(col, ast.Subscript) and isinstance(col.value, ast.Name) and col.value.id == v.id) or
                    (isinstance(col, ast.Attribute) and isinstance(col.value, ast.Name) and col.value.id == v.id)) \
                    and (_names_in(ast.Tuple(elts=s.comparators, ctx=ast.Load())) & self._loop_vars()):
                self.add("YK087", node, f"{v.id}[{v.id}[...] == ...]")
        self.generic_visit(node)

    def visit_Return(self, node):
        self.in_return += 1
        self.generic_visit(node)
        self.in_return -= 1

    # --- fonksiyonlar
    def visit_FunctionDef(self, node):
        cached = any(
            (isinstance(d, ast.Name) and d.id in ("cache", "lru_cache")) or
            (isinstance(d, ast.Attribute) and d.attr in ("cache", "lru_cache")) or
            (isinstance(d, ast.Call) and _call_name(d)[1] in ("cache", "lru_cache"))
            for d in node.decorator_list)
        info = {"name": node.name}
        self.func_stack.append(info)
        models = {_call_name(n)[0] for n in ast.walk(node) if isinstance(n, ast.Call)
                  and _call_name(n)[1] == "eval" and _call_name(n)[0] and not n.args}
        self.eval_models.append(models)
        is_async = isinstance(node, ast.AsyncFunctionDef)
        self.async_depth += is_async
        saved = (self.loop_stack, self.loop_nodes, self.list_names, self.str_names, self.dict_names,
                 self.set_names, self.np_names)
        self.loop_stack, self.loop_nodes = [], []
        self.list_names, self.str_names, self.dict_names = set(self.list_names), set(self.str_names), set(self.dict_names)
        self.set_names, self.np_names = set(self.set_names), set(self.np_names)
        self._block(node.body)
        self.generic_visit(node)
        (self.loop_stack, self.loop_nodes, self.list_names, self.str_names, self.dict_names,
         self.set_names, self.np_names) = saved
        self.async_depth -= is_async
        self.eval_models.pop()
        self.func_stack.pop()
        if not cached and overlapping_recursion(node):
            self.add("YK004", node, f"{node.name}() kendini küçülen argümanlarla birden çok kez çağırıyor")

    visit_AsyncFunctionDef = visit_FunctionDef


def analyze(code: str):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"hata": f"Sözdizimi hatası, satır {e.lineno}: {e.msg}", "bulgular": []}
    v = _Visitor()
    v.visit(tree)
    order = {"yüksek": 0, "orta": 1, "bilgi": 2}
    bulgular = sorted(v.findings, key=lambda f: (order[f["onem"]], f["satir"], f["kural"]))
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
