"""Otomatik düzeltme motoru.

Statik analizin bulduğu israf kalıplarını Python'un sözdizimi ağacı (AST)
üzerinde yeniden yazar. Her dönüşüm davranışı korumak için tasarlanmıştır;
yine de sonucun aynı olduğu her zaman çalıştırılarak doğrulanmalıdır
(bkz. proof.py). Dönüşümler:

  YK001  Döngüde tek kayıt sorgusu (N+1)  ->  döngüden önce toplu IN sorgusu
  YK002  Döngüde listede arama            ->  döngüden önce set()
  YK003  Döngüde değişmeyen iş            ->  döngüden önce bir kez
  YK004  Önbelleksiz çift özyineleme      ->  @functools.lru_cache
  YK011  sorted(x)[0]                     ->  min(x)  (reverse=True ise max(x))
  YK029  for ... in list(range(...))      ->  for ... in range(...)

Düzeltmeler özgün kaynağa satır düzeyinde yerleştirilir: yalnızca değişen
ifadeler yeniden yazılır; yorumlar, boş satırlar ve biçim olduğu gibi kalır.
Sonuç, tam yeniden yazımla aynı sözdizimi ağacını vermiyorsa (ör. aynı satırda
iki ifade) motor güvenli yola döner ve bütün kodu ast.unparse ile yazar.
"""
from __future__ import annotations

import ast
import copy
import difflib
import re
from dataclasses import dataclass, asdict

from .analyzer import INVARIANT_CALLS

SQL_ONE = re.compile(
    r"^\s*SELECT\s+(?P<cols>.+?)\s+FROM\s+(?P<table>\w+)\s+WHERE\s+(?P<key>\w+)\s*=\s*\?\s*;?\s*$",
    re.IGNORECASE | re.DOTALL)
BATCH = 900          # SQLite'ın tek sorgudaki parametre sınırının (999) altında


@dataclass
class Fix:
    kural: str
    satir: int
    aciklama: str

    def to_dict(self):
        return asdict(self)


# ------------------------------------------------------------ yardımcılar
def _stores(node):
    """node içinde atanan (Store) tüm isimler."""
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}


def _loads(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def _mutated(node):
    """x.append(...), x.extend(...), x[...] = ... gibi yerinde değişen isimler."""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name):
            if n.func.attr in {"append", "extend", "insert", "remove", "pop", "clear", "sort", "reverse",
                               "update", "setdefault", "popitem", "add", "discard"}:
                out.add(n.func.value.id)
        if isinstance(n, (ast.Assign, ast.AugAssign, ast.Delete)):
            targets = n.targets if isinstance(n, (ast.Assign, ast.Delete)) else [n.target]
            for t in targets:
                if isinstance(t, (ast.Subscript, ast.Attribute)) and isinstance(t.value, ast.Name):
                    out.add(t.value.id)
    return out


def _call_key(call):
    f = call.func
    if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
        return f.value.id, f.attr
    return None, None


def _stmt(src):
    return ast.parse(src).body


def _is_list_value(v):
    if isinstance(v, (ast.List, ast.ListComp)):
        return True
    return isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id in ("list", "sorted")


class _Names:
    """Çakışmayan yeni değişken adları üretir."""

    def __init__(self, tree):
        self.used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
                    {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    def new(self, base):
        name, i = base, 2
        while name in self.used:
            name, i = f"{base}{i}", i + 1
        self.used.add(name)
        return name


class _Rewrite(ast.NodeTransformer):
    """İfade düzeyindeki küçük dönüşümler (YK011, YK029)."""

    def __init__(self, fixes):
        self.fixes = fixes

    def visit_Subscript(self, node):
        self.generic_visit(node)
        v, s = node.value, node.slice
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "sorted" \
                and len(v.args) == 1 and isinstance(s, ast.Constant) and s.value == 0 and not isinstance(s.value, bool) \
                and all(k.arg in ("key", "reverse") for k in v.keywords):
            rev = [k for k in v.keywords if k.arg == "reverse"]
            if rev and not (isinstance(rev[0].value, ast.Constant) and isinstance(rev[0].value.value, bool)):
                return node
            # sorted kararlıdır: ilk eleman, min'in (reverse=True ise max'ın) bulduğu ilk eleman
            fn = "max" if rev and rev[0].value.value else "min"
            self.fixes.append(Fix("YK011", node.lineno, f"Sıralayıp ilk elemanı almak yerine {fn}() kullanıldı; tek geçiş."))
            return ast.copy_location(ast.Call(func=ast.Name(id=fn, ctx=ast.Load()), args=v.args,
                                              keywords=[k for k in v.keywords if k.arg == "key"]), node)
        return node

    def _unlist(self, it):
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "list" and len(it.args) == 1 \
                and not it.keywords and isinstance(it.args[0], ast.Call) and isinstance(it.args[0].func, ast.Name) \
                and it.args[0].func.id == "range":
            self.fixes.append(Fix("YK029", it.lineno, "list(range(...)) yerine doğrudan range(...) gezildi; kopya oluşturulmaz."))
            return it.args[0]
        return it

    def visit_For(self, node):
        self.generic_visit(node)
        node.iter = self._unlist(node.iter)
        return node

    visit_AsyncFor = visit_For

    def visit_comprehension(self, node):
        self.generic_visit(node)
        node.iter = self._unlist(node.iter)
        return node


# ------------------------------------------------------------ motor
class Fixer:
    def __init__(self, code: str):
        self.tree = ast.parse(code)
        self.names = _Names(self.tree)
        self.fixes: list[Fix] = []
        self.need_functools = False
        self.module_lists = {t.id for s in self.tree.body if isinstance(s, ast.Assign) and _is_list_value(s.value)
                             for t in s.targets if isinstance(t, ast.Name)}

    def run(self):
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._memoize(node)
        for node in list(ast.walk(self.tree)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                node.body = self._body(node.body, set(self.module_lists))
        self.tree = _Rewrite(self.fixes).visit(self.tree)
        if self.need_functools:
            self._import_functools()
        ast.fix_missing_locations(self.tree)
        return ast.unparse(self.tree)

    # ---------------------------------------------------- YK004
    def _memoize(self, fn):
        calls = sum(1 for n in ast.walk(fn) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name) and n.func.id == fn.name)
        cached = any("cache" in ast.unparse(d) for d in fn.decorator_list)
        args = fn.args
        hashable_sig = not (args.vararg or args.kwarg or args.kwonlyargs)
        if calls >= 2 and not cached and hashable_sig:
            fn.decorator_list.insert(0, ast.parse("functools.lru_cache(maxsize=None)", mode="eval").body)
            self.need_functools = True
            self.fixes.append(Fix("YK004", fn.lineno,
                                  f"{fn.name}() fonksiyonuna önbellek eklendi; her ara sonuç bir kez hesaplanır."))

    def _import_functools(self):
        for s in self.tree.body:
            if isinstance(s, ast.Import) and any(a.name == "functools" for a in s.names):
                return
        pos = 0
        body = self.tree.body
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                and isinstance(body[0].value.value, str):
            pos = 1
        while pos < len(body) and isinstance(body[pos], (ast.Import, ast.ImportFrom)):
            pos += 1
        body.insert(pos, ast.Import(names=[ast.alias(name="functools")]))

    # ---------------------------------------------------- gövdeleri dolaş
    def _body(self, stmts, lists):
        out = []
        for s in stmts:
            # Bu noktaya kadar liste olarak atanmış yerel isimleri takip et
            for attr in ("body", "orelse", "finalbody"):
                if hasattr(s, attr) and isinstance(getattr(s, attr), list) and getattr(s, attr) \
                        and isinstance(getattr(s, attr)[0], ast.stmt):
                    setattr(s, attr, self._body(getattr(s, attr), set(lists)))
            if isinstance(s, ast.Try):
                for h in s.handlers:
                    h.body = self._body(h.body, set(lists))
            pre = []
            if isinstance(s, (ast.For, ast.While)):
                pre += self._nplus1(s)
                pre += self._loop(s, s.body, self._loop_vars(s), lists)
            for comp in [n for n in ast.walk(s) if isinstance(n, (ast.ListComp, ast.SetComp,
                                                                   ast.GeneratorExp, ast.DictComp))]:
                if isinstance(s, (ast.For, ast.While)) and any(comp is n for b in s.body for n in ast.walk(b)):
                    continue                     # döngü gövdesindekiler zaten işlendi
                region = [comp.elt] if not isinstance(comp, ast.DictComp) else [comp.key, comp.value]
                for g in comp.generators:
                    region += g.ifs
                cvars = set()
                for g in comp.generators:
                    cvars |= _stores(g.target)
                pre += self._loop(s, region, cvars, lists)
            out += pre
            out.append(s)
            if isinstance(s, ast.Assign):
                for t in s.targets:
                    if isinstance(t, ast.Name):
                        (lists.add if _is_list_value(s.value) else lists.discard)(t.id)
        return out

    @staticmethod
    def _loop_vars(loop):
        v = set()
        if isinstance(loop, ast.For):
            v |= _stores(loop.target)
        for b in loop.body:
            v |= _stores(b)
        return v | _mutated(loop)

    # ---------------------------------------------------- YK002 + YK003
    def _loop(self, stmt, region, loop_vars, lists):
        pre, kume = [], {}
        nodes = [n for r in region for n in ast.walk(r)]
        mutated = set()
        for r in region:
            mutated |= _mutated(r)
        # YK002: listede arama -> küme
        for n in nodes:
            if isinstance(n, ast.Compare):
                for i, (op, comp) in enumerate(zip(n.ops, n.comparators)):
                    if isinstance(op, (ast.In, ast.NotIn)) and isinstance(comp, ast.Name) \
                            and comp.id in lists and comp.id not in loop_vars and comp.id not in mutated:
                        if comp.id not in kume:
                            kume[comp.id] = self.names.new(f"{comp.id}_kume")
                            pre += _stmt(f"{kume[comp.id]} = set({comp.id})")
                            self.fixes.append(Fix("YK002", n.lineno,
                                                  f"'{comp.id}' listesi döngüden önce kümeye çevrildi."))
                        n.comparators[i] = ast.Name(id=kume[comp.id], ctx=ast.Load())
        # YK003: değişmeyen çağrıları döngü dışına taşı
        if isinstance(stmt, ast.For) and region is stmt.body:
            assigned_count = {}
            for b in stmt.body:
                for nm in _stores(b):
                    assigned_count[nm] = assigned_count.get(nm, 0) + 1
            keep = []
            for b in stmt.body:
                if isinstance(b, ast.Assign) and len(b.targets) == 1 and isinstance(b.targets[0], ast.Name) \
                        and isinstance(b.value, ast.Call) and _call_key(b.value) in INVARIANT_CALLS \
                        and not (_loads(b.value) & loop_vars) and assigned_count.get(b.targets[0].id) == 1 \
                        and not (b.targets[0].id in _loads(stmt.iter)) \
                        and b.targets[0].id not in _mutated(stmt):           # sonuç döngüde değiştiriliyorsa taşınmaz
                    pre.append(b)
                    self.fixes.append(Fix("YK003", b.lineno,
                                          f"{ast.unparse(b.value.func)}(...) döngü dışına taşındı; bir kez çalışır."))
                else:
                    keep.append(b)
            stmt.body = keep or [ast.Pass()]
        return pre

    # ---------------------------------------------------- YK001
    def _nplus1(self, loop):
        if not isinstance(loop, ast.For):
            return []
        target_vars = _stores(loop.target)
        for b in loop.body:
            for n in ast.walk(b):
                # X.execute("SELECT .. WHERE k = ?", (expr,)).fetchone()
                if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                        and n.func.attr == "fetchone" and not n.args
                        and isinstance(n.func.value, ast.Call)):
                    continue
                ex = n.func.value
                if not (isinstance(ex.func, ast.Attribute) and ex.func.attr == "execute"
                        and isinstance(ex.func.value, ast.Name) and len(ex.args) == 2
                        and isinstance(ex.args[0], ast.Constant) and isinstance(ex.args[0].value, str)
                        and isinstance(ex.args[1], (ast.Tuple, ast.List)) and len(ex.args[1].elts) == 1):
                    continue
                m = SQL_ONE.match(ex.args[0].value)
                key = ex.args[1].elts[0]
                db = ex.func.value.id
                if not m or db in target_vars or not (_loads(key) & target_vars) \
                        or (_loads(key) - target_vars) & self._loop_vars(loop):
                    continue
                cols, table, kcol = m.group("cols"), m.group("table"), m.group("key")
                rows, keys, cache, part, i, row = (self.names.new(x) for x in
                                                   ("_satirlar", "_anahtarlar", "_onbellek", "_parca", "_i", "_satir"))
                tgt = ast.unparse(loop.target)
                sql = f"SELECT {kcol}, {cols} FROM {table} WHERE {kcol} IN ("
                pre = _stmt(
                    f"{rows} = list({ast.unparse(loop.iter)})\n"
                    f"{keys} = list(dict.fromkeys({ast.unparse(key)} for {tgt} in {rows}))\n"
                    f"{cache} = {{}}\n"
                    f"for {i} in range(0, len({keys}), {BATCH}):\n"
                    f"    {part} = {keys}[{i}:{i} + {BATCH}]\n"
                    f"    for {row} in {db}.execute({sql!r} + ','.join('?' * len({part})) + ')', {part}):\n"
                    f"        {cache}[{row}[0]] = tuple({row}[1:])\n")
                loop.iter = ast.Name(id=rows, ctx=ast.Load())
                repl = ast.parse(f"{cache}.get({ast.unparse(key)})", mode="eval").body
                self._replace(b, n, repl)
                self.fixes.append(Fix("YK001", n.lineno,
                                      f"Döngüdeki tek kayıt sorgusu, '{table}' tablosuna toplu IN sorgusuyla değiştirildi."))
                return pre
        return []

    @staticmethod
    def _replace(root, old, new):
        for parent in ast.walk(root):
            for field, value in ast.iter_fields(parent):
                if value is old:
                    setattr(parent, field, new)
                    return
                if isinstance(value, list):
                    for k, v in enumerate(value):
                        if v is old:
                            value[k] = new
                            return


# ------------------------------------------------------------ biçimi koruyarak yerleştirme
_BLOCKS = ("body", "orelse", "finalbody")


def _d(node):
    return ast.dump(node, include_attributes=False)


def _start(node):
    """İfadenin ilk satırı (varsa dekoratörler dahil)."""
    return min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])


def _pos(n):
    return n.lineno, n.col_offset, n.end_lineno, n.end_col_offset


def _same_kind(a, b):
    return type(a) is type(b) and getattr(a, "name", None) == getattr(b, "name", None)


def _header(node):
    """Gövdeler ve dekoratörler dışındaki her şey. Başlık aynıysa yalnızca gövdelere inilir."""
    h = copy.copy(node)
    for f in _BLOCKS + ("decorator_list",):
        if hasattr(h, f):
            setattr(h, f, [])
    return _d(h)


class _Splice:
    """Özgün kaynağa yalnızca değişen ifadeleri yerleştirir."""

    def __init__(self, src, tree):
        self.lines = src.splitlines(keepends=True)
        self.edits = []                  # (başlangıç, bitiş, sıra, metin); 0 tabanlı satır aralığı
        # Özgün ifadeler, konumlarına göre: taşınan bir ifade özgün yazımıyla yerleştirilir
        self.orig = {_pos(n): _d(n) for n in ast.walk(tree) if isinstance(n, ast.stmt)}

    def _edit(self, start, end, text):
        self.edits.append((start, end, len(self.edits), text))

    def _source(self, n, indent):
        """n özgün koddan değişmeden geldiyse o satırlar (yeni girintiyle), yoksa None."""
        if not hasattr(n, "lineno") or self.orig.get(_pos(n)) != _d(n):
            return None
        old = self.lines[n.lineno - 1][:n.col_offset]
        seg = self.lines[_start(n) - 1:n.end_lineno]
        if not seg[-1].endswith("\n"):
            seg[-1] += "\n"
        return "".join(indent + line[len(old):] if line.startswith(old) else line for line in seg)

    def _indent(self, node):
        return self.lines[node.lineno - 1][:node.col_offset]

    def _put(self, start, end, nodes, indent):
        text = "".join(self._source(n, indent) or
                       "".join((indent + line if line else "") + "\n" for line in ast.unparse(n).splitlines())
                       for n in nodes)
        self._edit(start, end, text)

    def _after(self, node, nodes):
        self._put(node.end_lineno, node.end_lineno, nodes, self._indent(node))

    def _before(self, node, nodes):
        self._put(_start(node) - 1, _start(node) - 1, nodes, self._indent(node))
        if not self._indent(node) and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                and all(isinstance(n, (ast.Import, ast.ImportFrom)) for n in nodes):
            self._edit(_start(node) - 1, _start(node) - 1, "\n\n")      # PEP 8: tanımdan önce iki boş satır

    def stmts(self, old, new):
        sm = difflib.SequenceMatcher(None, [_d(n) for n in old], [_d(n) for n in new], autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "equal":
                continue
            # Değişen bloktaki ifadeleri eşleştir (sondan başa: motor yeni ifadeleri
            # her zaman değişen ifadenin önüne ekler, değişenin kendisi en sondadır).
            pairs, j = [], j2
            for i in range(i2 - 1, i1 - 1, -1):
                k = next((x for x in range(j - 1, j1 - 1, -1) if _same_kind(old[i], new[x])), None)
                if k is not None:
                    pairs.append((i, k))
                    j = k
            pairs.reverse()
            paired = {i for i, _ in pairs}
            for i in range(i1, i2):
                if i not in paired:
                    self._edit(_start(old[i]) - 1, old[i].end_lineno, "")
            nxt = j1
            for i, k in pairs:
                if k > nxt:
                    if i == i1 and i1 > 0:
                        self._after(old[i1 - 1], new[nxt:k])     # ör. import, öncekilerin hemen ardına
                    else:
                        self._before(old[i], new[nxt:k])         # ör. döngüden önce kurulan küme
                self.stmt(old[i], new[k])
                nxt = k + 1
            if nxt < j2:
                if pairs:
                    self._after(old[pairs[-1][0]], new[nxt:j2])
                elif i1 > 0:
                    self._after(old[i1 - 1], new[nxt:j2])
                else:
                    self._before(old[i1], new[nxt:j2])

    def _is_elif(self, node):
        return isinstance(node, ast.If) and self.lines[node.lineno - 1][node.col_offset:].startswith("elif")

    def _replace(self, o, n):
        """o'nun satırlarını n ile değiştirir (elif dalı elif olarak kalır)."""
        self._put(_start(o) - 1, o.end_lineno, [n], self._indent(o))
        if self._is_elif(o):
            start, end, seq, text = self.edits[-1]
            self.edits[-1] = (start, end, seq, text.replace("if ", "elif ", 1))

    def _header_end(self, o):
        """Bileşik ifadenin başlık satırının sonu (gövdeyle aynı satırdaysa None)."""
        parts = {ast.For: ("target", "iter"), ast.AsyncFor: ("target", "iter"),
                 ast.While: ("test",), ast.If: ("test",)}.get(type(o))
        if not parts:
            return None
        end = max(getattr(o, f).end_lineno for f in parts)
        return end if o.body[0].lineno > end else None

    def stmt(self, o, n):
        if _d(o) == _d(n):
            return
        if any(bool(getattr(o, f, None)) != bool(getattr(n, f, None)) for f in _BLOCKS):
            self._replace(o, n)
            return
        if _header(o) != _header(n):
            end = self._header_end(o)
            if end is None:
                self._replace(o, n)
                return
            # Yalnızca başlık satırı değişti (ör. döngünün üzerinde döndüğü ifade); gövdeye ayrıca bakılır
            h = copy.copy(n)
            h.body, h.orelse = [ast.Pass()], []
            head = ast.unparse(h).splitlines()[:-1]
            if self._is_elif(o):
                head[0] = "el" + head[0]
            self._edit(o.lineno - 1, end, "".join(self._indent(o) + line + "\n" for line in head))
            for f in _BLOCKS:
                if getattr(o, f, None):
                    self.stmts(getattr(o, f), getattr(n, f))
            return
        od = [_d(x) for x in getattr(o, "decorator_list", [])]
        nd = getattr(n, "decorator_list", [])
        if od != [_d(x) for x in nd]:
            k = len(nd) - len(od)
            if k <= 0 or [_d(x) for x in nd[k:]] != od:
                self._replace(o, n)
                return
            at, ind = _start(o) - 1, self._indent(o)
            self._edit(at, at, "".join(f"{ind}@{ast.unparse(x)}\n" for x in nd[:k]))
        for f in _BLOCKS:
            if getattr(o, f, None):
                self.stmts(getattr(o, f), getattr(n, f))

    def result(self):
        lines = list(self.lines)
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        # Sondan başa uygula ki satır numaraları kaymasın. Aynı noktaya yapılan eklemeler
        # kayıt sırasıyla dizilsin diye önce sonradan kaydedilen uygulanır.
        for start, end, _, text in sorted(self.edits, reverse=True):
            lines[start:end] = [text] if text else []
        return "".join(lines)


def fix(code: str):
    """(düzeltilmiş kod, karşılaştırılacak özgün kod, düzeltmeler) döndürür.

    Biçim korunabildiyse fix.bicim_korundu True olur ve özgün kod olduğu gibi
    döner; korunamadıysa iki sürüm de ast.unparse biçimindedir.
    """
    fix.bicim_korundu = False
    original_tree = ast.parse(code)
    f = Fixer(code)
    new = f.run()
    fixes = sorted(f.fixes, key=lambda x: x.satir)
    if not fixes:
        return code, code, fixes
    try:
        sp = _Splice(code, original_tree)
        sp.stmts(original_tree.body, f.tree.body)
        spliced = sp.result()
        if _d(ast.parse(spliced)) == _d(ast.parse(new)):
            fix.bicim_korundu = True
            return spliced, code, fixes
    except (SyntaxError, ValueError, IndexError):
        pass
    return new, ast.unparse(original_tree), fixes


fix.bicim_korundu = False


def unified_diff(a: str, b: str, name="kod.py"):
    return "\n".join(difflib.unified_diff(a.splitlines(), b.splitlines(),
                                          f"a/{name}", f"b/{name}", lineterm="", n=2))


def side_by_side(a: str, b: str):
    """Arayüz için satır satır fark: [{'tur': 'esit|sil|ekle', 'metin': ...}]"""
    out = []
    sm = difflib.SequenceMatcher(None, a.splitlines(), b.splitlines())
    al, bl = a.splitlines(), b.splitlines()
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out += [{"tur": "esit", "metin": x} for x in al[i1:i2]]
        else:
            out += [{"tur": "sil", "metin": x} for x in al[i1:i2]]
            out += [{"tur": "ekle", "metin": x} for x in bl[j1:j2]]
    return out
