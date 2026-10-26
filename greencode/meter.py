"""Enerji ölçer.

İki modda çalışır:
  * RAPL modu (Linux + Intel/AMD): İşlemcinin kendi enerji sayaçları
    (/sys/class/powercap/intel-rapl:*/energy_uj) okunur. Gerçek ölçümdür.
    Ölçüm sırasında boşta tüketim (idle) çıkarılır; böylece yalnızca kodun
    eklediği enerji kalır.
  * Tahmini mod (Windows, Mac, sanal makine ya da izin yoksa): Kodun
    kullandığı işlemci süresi x çekirdek başına güç. CodeCarbon gibi
    araçların yedek yöntemiyle aynı mantıktır.

Karbon = Enerji (kWh) x Şebeke karbon yoğunluğu (gCO2e/kWh)
"""
from __future__ import annotations

import glob
import os
import statistics
import time
from dataclasses import dataclass, asdict

from . import config

J_PER_KWH = 3_600_000.0


@dataclass
class Measurement:
    energy_j: float          # bir çalıştırmanın enerjisi (J), ortalama
    energy_j_std: float      # tekrarlar arası standart sapma
    wall_s: float            # süre (s), ortalama
    cpu_s: float             # işlemci süresi (s), ortalama
    co2_g: float             # karbon (gCO2e), ortalama
    repeats: int
    mode: str                # "rapl" ya da "tahmini"

    def to_dict(self):
        return asdict(self)


class _Rapl:
    """Intel/AMD RAPL paket sayaçlarını okur."""

    def __init__(self):
        self.zones = []
        for path in sorted(glob.glob("/sys/class/powercap/intel-rapl:*")):
            name = os.path.basename(path)
            if name.count(":") != 1:          # alt bölgeleri (core, dram) atla
                continue
            ef = os.path.join(path, "energy_uj")
            mf = os.path.join(path, "max_energy_range_uj")
            try:
                with open(ef) as f:
                    int(f.read())
                with open(mf) as f:
                    max_range = int(f.read())
            except (OSError, ValueError):
                continue
            self.zones.append((ef, max_range))
        self.available = bool(self.zones)
        self.idle_w = 0.0
        if self.available:
            self.idle_w = self._measure_idle()

    def read_uj(self):
        vals = []
        for ef, _ in self.zones:
            with open(ef) as f:
                vals.append(int(f.read()))
        return vals

    def delta_j(self, before, after):
        total = 0
        for (b, a, (_, max_range)) in zip(before, after, self.zones):
            d = a - b
            if d < 0:                          # sayaç başa döndü
                d += max_range
            total += d
        return total / 1e6

    def _measure_idle(self, seconds=1.0):
        b = self.read_uj()
        t0 = time.perf_counter()
        time.sleep(seconds)
        dt = time.perf_counter() - t0
        return self.delta_j(b, self.read_uj()) / dt


class EnergyMeter:
    def __init__(self):
        self._rapl = _Rapl()
        self.mode = "rapl" if self._rapl.available else "tahmini"

    def info(self):
        return {
            "mode": self.mode,
            "mode_label": "Gerçek ölçüm (RAPL sayaçları)" if self.mode == "rapl"
            else "Tahmini ölçüm (işlemci süresi x çekirdek gücü)",
            "idle_w": round(self._rapl.idle_w, 2) if self.mode == "rapl" else None,
            "cpu_w_per_core": config.CPU_WATTS_PER_CORE,
            "carbon_intensity": config.CARBON_INTENSITY_G_PER_KWH,
            "daily_calls": config.DAILY_CALLS,
            "car_g_per_km": config.CAR_G_CO2_PER_KM,
            "led_w": config.LED_WATTS,
        }

    def _once(self, fn, iters):
        """fn'i iters kez çalıştırır, BİR çağrının ortalama değerlerini döndürür."""
        if self.mode == "rapl":
            b = self._rapl.read_uj()
        c0 = time.process_time()
        t0 = time.perf_counter()
        for _ in range(iters):
            fn()
        wall = time.perf_counter() - t0
        cpu = time.process_time() - c0
        if self.mode == "rapl":
            raw = self._rapl.delta_j(b, self._rapl.read_uj())
            energy = max(raw - self._rapl.idle_w * wall, 0.0)
        else:
            energy = cpu * config.CPU_WATTS_PER_CORE
        return energy / iters, wall / iters, cpu / iters

    @staticmethod
    def _calibrate(fn, min_seconds):
        """Kısa süren kodu, sayaçların doğru ölçebileceği kadar tekrar et."""
        t0 = time.perf_counter()
        fn()                                   # ısınma turu
        one = max(time.perf_counter() - t0, 1e-6)
        return max(1, min(int(min_seconds / one) + 1, 100_000))

    def measure(self, fn, repeats=None, min_seconds=0.25):
        repeats = repeats or config.REPEATS
        iters = self._calibrate(fn, min_seconds)
        es, ws, cs = [], [], []
        for _ in range(repeats):
            e, w, c = self._once(fn, iters)
            es.append(e); ws.append(w); cs.append(c)
        e_mean = statistics.fmean(es)
        return Measurement(
            energy_j=e_mean,
            energy_j_std=statistics.pstdev(es) if len(es) > 1 else 0.0,
            wall_s=statistics.fmean(ws),
            cpu_s=statistics.fmean(cs),
            co2_g=to_co2_g(e_mean),
            repeats=repeats,
            mode=self.mode,
        )


def to_co2_g(energy_j: float) -> float:
    return energy_j / J_PER_KWH * config.CARBON_INTENSITY_G_PER_KWH


def yearly_projection(energy_j_per_call: float, daily_calls: int | None = None):
    """Bir çağrının enerjisini 'günde N çağrı, 1 yıl' ölçeğine taşır."""
    daily_calls = daily_calls or config.DAILY_CALLS
    kwh = energy_j_per_call * daily_calls * 365 / J_PER_KWH
    co2_kg = kwh * config.CARBON_INTENSITY_G_PER_KWH / 1000
    return {
        "kwh": kwh,
        "co2_kg": co2_kg,
        "car_km": co2_kg * 1000 / config.CAR_G_CO2_PER_KM,
        "led_hours": kwh * 1000 / config.LED_WATTS,
    }
