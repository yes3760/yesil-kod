"""Enerji ölçer.

İki modda çalışır:
  * RAPL modu (Linux + Intel/AMD): İşlemcinin kendi enerji sayaçları
    (/sys/class/powercap/intel-rapl:*/energy_uj) okunur. Gerçek ölçümdür.
    Ölçüm sırasında boşta tüketim (idle) çıkarılır; böylece yalnızca kodun
    eklediği enerji kalır.
  * powermetrics modu (macOS, yönetici izniyle): Apple'ın işlemci güç
    verisi sürekli örneklenir; bir ölçüm penceresinin enerjisi, pencereyle
    örtüşen örneklerin toplamıdır. Boşta tüketim yine çıkarılır.
  * Tahmini mod (Windows, sanal makine ya da izin yoksa): Kodun
    kullandığı işlemci süresi x çekirdek başına güç. CodeCarbon gibi
    araçların yedek yöntemiyle aynı mantıktır.

Karbon = Enerji (kWh) x Şebeke karbon yoğunluğu (gCO2e/kWh)
"""
from __future__ import annotations

import atexit
import glob
import os
import plistlib
import statistics
import subprocess
import sys
import threading
import time
from collections import deque
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


POWERMETRICS = "/usr/bin/powermetrics"


class _PowerMetrics:
    """macOS: powermetrics'in işlemci güç örneklerini arka planda sürekli okur.

    Yönetici izni gerekir. baslat.sh şifreyi bir kez sorar (sudo -v); sunucu
    powermetrics'i aynı terminalden "sudo -n" ile başlatır, böylece şifre
    Python'a hiç gelmez. İzin yoksa sessizce kullanılamaz kalır.
    """
    INTERVAL_MS = 100

    def __init__(self, start=True):
        self.available = False
        self.idle_w = 0.0
        self.samples = deque(maxlen=36000)       # (varış zamanı, süre_s, enerji_j), ~1 saat
        self._cond = threading.Condition()
        self._proc = None
        if start:
            self._start()

    def _start(self):
        if sys.platform != "darwin" or not config.POWERMETRICS or not os.path.exists(POWERMETRICS):
            return
        try:
            sudo = [] if os.geteuid() == 0 else ["sudo", "-n"]
            if sudo and subprocess.run(sudo + ["true"], capture_output=True, timeout=5).returncode != 0:
                return
            self._proc = subprocess.Popen(
                sudo + [POWERMETRICS, "--samplers", "cpu_power", "-i", str(self.INTERVAL_MS),
                        "-b", "0", "-f", "plist"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            return
        atexit.register(self.close)
        threading.Thread(target=self._read, daemon=True).start()
        if not self._wait_until(time.perf_counter() + 0.05, timeout=5):
            self.close()
            return
        self.available = True
        self.idle_w = self._measure_idle()

    def close(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def _read(self):
        buf = b""
        end_tag = b"</plist>"
        while True:
            chunk = self._proc.stdout.read1(65536)
            if not chunk:
                break
            buf += chunk
            # Örnekler NUL ile ayrılır ama ayırıcı bir sonraki örnekle gelebilir;
            # gecikme olmasın diye örnek, kapanış etiketi gelir gelmez işlenir.
            while end_tag in buf:
                i = buf.index(end_tag) + len(end_tag)
                part, buf = buf[:i], buf[i:]
                sample = self.parse(part)
                if sample:
                    with self._cond:
                        self.samples.append((time.perf_counter(), *sample))
                        self._cond.notify_all()

    @staticmethod
    def parse(chunk):
        """Bir plist örneğinden (süre_s, işlemci_enerjisi_j) döndürür."""
        chunk = chunk.strip(b"\0 \t\r\n")
        if not chunk:
            return None
        try:
            d = plistlib.loads(chunk)
        except Exception:
            return None
        dt = d.get("elapsed_ns", 0) / 1e9
        p = d.get("processor", {})
        if dt <= 0:
            return None
        if "cpu_energy" in p:                       # Apple Silicon, mJ
            return dt, p["cpu_energy"] / 1000
        if "cpu_power" in p:                        # mW
            return dt, p["cpu_power"] / 1000 * dt
        if "package_joules" in p:                   # Intel Mac
            return dt, p["package_joules"]
        if "package_watts" in p:
            return dt, p["package_watts"] * dt
        return None

    def _wait_until(self, t, timeout):
        """t anını kapsayan bir örnek gelene kadar bekler."""
        deadline = time.perf_counter() + timeout
        with self._cond:
            while not (self.samples and self.samples[-1][0] >= t):
                left = deadline - time.perf_counter()
                if left <= 0:
                    return False
                self._cond.wait(left)
        return True

    def energy_between(self, t0, t1):
        """[t0, t1] aralığında işlemcinin harcadığı enerji (J)."""
        if not self._wait_until(t1, timeout=3):
            raise RuntimeError("powermetrics örnek göndermiyor")
        total = 0.0
        with self._cond:
            for end, dt, e in reversed(self.samples):
                if end < t0:
                    break
                overlap = min(end, t1) - max(end - dt, t0)
                if overlap > 0:
                    total += e * overlap / dt
        return total

    def _measure_idle(self, seconds=1.5):
        t0 = time.perf_counter()
        time.sleep(seconds)
        t1 = time.perf_counter()
        return self.energy_between(t0, t1) / (t1 - t0)


MODE_LABELS = {
    "rapl": "Gerçek ölçüm (RAPL sayaçları)",
    "powermetrics": "Donanım ölçümü (Apple powermetrics)",
    "tahmini": "Tahmini ölçüm (işlemci süresi x çekirdek gücü)",
}


class EnergyMeter:
    def __init__(self):
        self._rapl = _Rapl()
        self._pm = None
        if self._rapl.available:
            self.mode = "rapl"
        else:
            self._pm = _PowerMetrics()
            self.mode = "powermetrics" if self._pm.available else "tahmini"
        # powermetrics 100 ms'de bir örnek verir; daha kısa pencereler bulanık ölçülür
        self.min_window = 0.6 if self.mode == "powermetrics" else 0.0

    def idle_w(self):
        return {"rapl": self._rapl.idle_w, "powermetrics": self._pm.idle_w if self._pm else 0.0}.get(self.mode)

    def info(self):
        idle = self.idle_w()
        return {
            "mode": self.mode,
            "mode_label": MODE_LABELS[self.mode],
            "idle_w": round(idle, 2) if idle is not None else None,
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
        t1 = time.perf_counter()
        wall = t1 - t0
        cpu = time.process_time() - c0
        if self.mode == "rapl":
            raw = self._rapl.delta_j(b, self._rapl.read_uj())
            energy = max(raw - self._rapl.idle_w * wall, 0.0)
        elif self.mode == "powermetrics":
            raw = self._pm.energy_between(t0, t1)
            energy = max(raw - self._pm.idle_w * wall, 0.0)
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
        min_seconds = max(min_seconds, self.min_window)
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
