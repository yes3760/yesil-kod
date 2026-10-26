"""Yeşil Kod — ayarlar.

Bütün katsayılar burada; kaynakları yanlarında. Stantta farklı bir değer
kullanmak isterseniz ortam değişkeniyle değiştirebilirsiniz.
"""
import os

# Türkiye elektrik şebekesinin karbon yoğunluğu (gCO2e/kWh).
# Kaynak: Low-Carbon Power, Türkiye, Ağustos 2025 – Temmuz 2026 son 12 ay ortalaması:
# https://lowcarbonpower.org/region/Türkei  (EPİAŞ verisiyle güncellenebilir)
CARBON_INTENSITY_G_PER_KWH = float(os.getenv("YK_CARBON_INTENSITY", "341"))

# RAPL okunamadığında (Windows, Mac, sanal makine) tahmini mod:
# işlemcinin bir çekirdeğinin tam yükte çektiği güç (W).
# Dizüstü işlemciler için 10 W makul bir varsayılandır; kendi işlemcinizin
# TDP değeri / çekirdek sayısı ile değiştirin.
CPU_WATTS_PER_CORE = float(os.getenv("YK_CPU_W_PER_CORE", "10"))

# Benzetmeler
# AB'de 2025'te satılan yeni otomobillerin ortalama emisyonu (WLTP, geçici veri), gCO2/km.
# Kaynak: Avrupa Çevre Ajansı (EEA), 2025 geçici verileri.
CAR_G_CO2_PER_KM = 96.7
# 10 W'lık bir LED ampul: 1 saatte 0,01 kWh harcar (doğrudan fizik, katsayı yok).
LED_WATTS = 10.0

# Ölçeklendirme senaryosu: fonksiyon günde kaç kez çağrılıyor?
DAILY_CALLS = int(os.getenv("YK_DAILY_CALLS", "1000000"))

# macOS'ta powermetrics ile donanım ölçümü (yönetici izni gerekir; 0 = kapalı)
POWERMETRICS = os.getenv("YK_POWERMETRICS", "1") != "0"

# Her ölçüm kaç kez tekrarlanıp ortalaması alınacak
REPEATS = int(os.getenv("YK_REPEATS", "5"))

# İsteğe bağlı yapay zekâ önerisi (yoksa kural tabanlı öneriler gösterilir)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.getenv("YK_LLM_MODEL", "claude-haiku-5-5")

HOST = os.getenv("YK_HOST", "127.0.0.1")
PORT = int(os.getenv("YK_PORT", "8000"))
