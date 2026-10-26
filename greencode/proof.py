"""Kanıt: özgün ve düzeltilmiş kodu çalıştırır, aynı sonucu verdiklerini
doğrular ve enerjilerini ölçer.

Önemli adalet kuralı: Düzeltilmiş sürümdeki önbellekler (lru_cache) her
ölçümden önce temizlenir. Böylece optimize kod "önceki ölçümden kalan
sonuçlarla" kazanmaz; her istek sıfırdan hesaplanır.
"""
from __future__ import annotations

import time

from . import fixer
from .meter import EnergyMeter, yearly_projection


def _norm(x):
    if isinstance(x, (list, tuple)):
        return [_norm(i) for i in x]
    return x


def _clear_caches(ns):
    for v in list(ns.values()):
        if callable(v) and hasattr(v, "cache_clear"):
            v.cache_clear()


class CountingDB:
    """Veritabanı bağlantısını sarar ve gönderilen sorguları sayar."""

    def __init__(self, db):
        self._db, self.count = db, 0

    def execute(self, *args, **kwargs):
        self.count += 1
        return self._db.execute(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._db, name)


def prepare(code, entry, data):
    """İki sürümü hazırlar: (özgün_fn, düzeltilmiş_fn, düzeltilmiş_kod, normalize_özgün, düzeltmeler)."""
    fixed_code, original_norm, fixes = fixer.fix(code)
    ns_a, ns_b = dict(data), dict(data)
    if "DB" in data:
        ns_a["DB"], ns_b["DB"] = CountingDB(data["DB"]), CountingDB(data["DB"])
    prepare.last_ns = (ns_a, ns_b)
    exec(compile(code, "<özgün>", "exec"), ns_a)
    exec(compile(fixed_code, "<düzeltilmiş>", "exec"), ns_b)
    fa, fb = ns_a[entry], ns_b[entry]

    def run_a():
        _clear_caches(ns_a)
        return fa()

    def run_b():
        _clear_caches(ns_b)
        return fb()

    return run_a, run_b, fixed_code, original_norm, fixes


def verify(run_a, run_b):
    a, b = run_a(), run_b()
    return _norm(a) == _norm(b), (len(a) if hasattr(a, "__len__") else None)


def prove(code, entry, data, meter: EnergyMeter, measure=True):
    run_a, run_b, fixed_code, original_norm, fixes = prepare(code, entry, data)
    ns_a, ns_b = prepare.last_ns
    same, n_out = verify(run_a, run_b)
    queries = None
    if "DB" in data and ns_a["DB"].count:
        queries = {"ozgun": ns_a["DB"].count, "duzeltilmis": ns_b["DB"].count}
    result = {
        "sorgu_sayisi": queries,
        "duzeltmeler": [f.to_dict() for f in fixes],
        "fark": fixer.side_by_side(original_norm, fixed_code),
        "duzeltilmis_kod": fixed_code,
        "esdeger": same,
        "cikti_sayisi": n_out,
    }
    if not same:
        result["hata"] = "Düzeltilmiş kod farklı sonuç verdi; düzeltme reddedildi."
        return result
    if not measure:
        return result
    a, b = meter.measure(run_a), meter.measure(run_b)
    result |= {
        "ozgun": a.to_dict() | {"yillik": yearly_projection(a.energy_j)},
        "duzeltilmis": b.to_dict() | {"yillik": yearly_projection(b.energy_j)},
        "kat": a.energy_j / b.energy_j if b.energy_j > 0 else None,
        "tasarruf_yuzde": (1 - b.energy_j / a.energy_j) * 100 if a.energy_j else 0,
    }
    return result


def race(code, entry, data, meter: EnergyMeter, seconds=8.0, tick=0.12):
    """Canlı yarış: iki sürüm AYNI sayıda isteği işler. Her parça gerçekten
    çalıştırılıp ölçülür; ilerleme olay olarak akıtılır (generator)."""
    run_a, run_b, *_ = prepare(code, entry, data)
    t0 = time.perf_counter()
    run_a()
    per_a = max(time.perf_counter() - t0, 1e-6)
    n = max(5, min(2000, int(seconds / per_a)))
    yield {"tur": "basla", "istek": n}

    # Düzeltilmiş sürüm çok hızlı: istek başı enerjisi kalibre edilmiş ölçümle
    # alınır (sayaç çözünürlüğü için), n istekle çarpılır.
    tb0 = time.perf_counter()
    mb = meter.measure(run_b, repeats=3, min_seconds=0.15)
    e_b = mb.energy_j * n
    yield {"tur": "ilerleme", "surum": "duzeltilmis", "bitti": n, "enerji_j": e_b,
           "sure_s": mb.wall_s * n, "olcum_s": time.perf_counter() - tb0}

    done_a, e_a, ta0 = 0, 0.0, time.perf_counter()
    k = max(1, int(tick / per_a))
    while done_a < n:
        kk = min(k, n - done_a)
        e, w, _ = meter._once(run_a, kk)
        e_a += e * kk
        done_a += kk
        yield {"tur": "ilerleme", "surum": "ozgun", "bitti": done_a, "enerji_j": e_a,
               "sure_s": time.perf_counter() - ta0}
    yield {"tur": "son", "istek": n, "ozgun_j": e_a, "duzeltilmis_j": e_b,
           "kat": e_a / e_b if e_b else None}
