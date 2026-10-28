# Yeşil Kod

[![Testler](https://github.com/yes3760/yesil-kod/actions/workflows/ci.yml/badge.svg)](https://github.com/yes3760/yesil-kod/actions/workflows/ci.yml)

Yazılımın enerjisini ölçer, israfı otomatik düzeltir, kazancı kanıtlar.
Sakarya Üniversitesi · COP31 Yeşil Bölge projesi

## Ne yapar

1. **Bulur.** Statik analiz, Python kodunun sözdizimi ağacını (AST) tarar ve enerji israf eden 113 kalıbı satır satır işaretler.
2. **Düzeltir.** Düzeltme motoru on bir kalıbı kendisi yeniden yazar ve yalnızca değişen satırlara dokunur; yorumlar ve biçim korunur: döngüdeki tek kayıt sorgularını toplu `IN` sorgusuna, listede aramayı kümeye çevirir, döngüde değişmeyen işi döngü dışına taşır, çift özyinelemeye önbellek ekler, en küçüğü bulmak için sıralamayı `min()`/`max()` ile değiştirir ve gereksiz kopya ve dönüşümleri (`list(sorted(x))`, `[x for x in y]`, `sum([...])`, `list(range(...))` gibi) kaldırır.
3. **Doğrular.** Özgün ve düzeltilmiş kod çalıştırılır; çıktılar birebir aynı değilse düzeltme reddedilir.
4. **Ölçer.** İşlemcinin enerji sayaçları okunur, aynı sayıda istek için harcanan enerji karşılaştırılır ve Türkiye şebekesinin karbon yoğunluğuyla gCO₂e'ye çevrilir.

Demo senaryolarındaki optimize kod elle yazılmadı; motor üretti.

| Senaryo | Kalıp | Motorun düzeltmesi | Sonuç (tahmini mod, 26 Ekim 2026) |
|---|---|---|---|
| Sipariş raporu | N+1 sorgu | toplu IN sorgusu | 2,9 kat az enerji, sorgu 4.001 → 2 |
| Yoklama kontrolü | listede arama | `set()` | 465 kat az enerji |
| Rota sayısı | önbelleksiz özyineleme | `lru_cache` | yaklaşık 4.000 kat az enerji |
| Fiyat listesi | döngüde değişmeyen iş | döngü dışına taşıma | 51 kat az enerji |

**Proje sayfası:** https://yes3760.github.io/yesil-kod/ (film, sonuçlar ve telefonda kod deneme; Türkçe/İngilizce)
**Proje ekibi:** Yunus Emre Sevindik, Mehmet Zahid Görgeç

## Kurulum ve çalıştırma

Gereken tek şey **Python 3.9 veya üstü**. Ek paket kurulmaz, internet gerekmez.

| Sistem | Komut |
|---|---|
| Windows | `baslat.bat` dosyasına çift tıklayın |
| Linux / Mac | `./baslat.sh` |
| Elle | `python -m greencode` |

Tarayıcıda `http://127.0.0.1:8000` açılır. Stant ekranında **F** ile tam ekran, **T** ile otomatik tur. Otomatik turda dört senaryo sırayla düzeltilir, doğrulanır ve canlı ölçülür.

## Panel

- **Canlı ölçüm:** Motorun yaptığı değişiklik (fark), iki sürümün aynı sayıda isteği işlerken harcadığı enerjinin canlı şeritleri ve biriken enerji grafiği, eşdeğerlik testi, sorgu sayısı ve yıllık tasarruf.
- **Kodunu dene:** Ziyaretçi kendi Python kodunu yapıştırır; bulgular ve motorun önerdiği düzeltme gösterilir. Kod çalıştırılmaz.
- **Nasıl çalışıyor:** Yöntem, SCI formülü, sınırlar ve kaynaklar.

## Komut satırı

```bash
python -m greencode senaryolar                 # 4 senaryoyu düzelt, doğrula, ölç
python -m greencode analiz dosya.py            # israf kalıplarını listele
python -m greencode duzelt dosya.py            # düzeltmenin farkını göster
python -m greencode duzelt dosya.py --yaz      # dosya.yesil.py olarak kaydet
python -m greencode duzelt dosya.py --kanitla rapor_uret
                                               # parametresiz fonksiyonu iki sürümde
                                               # çalıştır, karşılaştır, ölç
python -m greencode olc betik.py               # betiğin enerjisini ölç
python -m greencode rapor src/ --bicim md      # CI raporu (md, html, json)
python -m greencode rapor src/ --esik 0        # yüksek bulgu varsa çıkış kodu 1
```

## Sürekli entegrasyon

`ornekler/github-action.yml`, her pull request'te raporu üretip PR'a yorum olarak yazar ve yüksek önemli bulgu varsa kontrolü durdurur.

## Testler

```bash
python -m unittest discover -s tests -v
```

33 test: analiz kuralları (her kuralın kendi örneği ve yanlış alarm denetimleri), her senaryonun düzeltilip aynı sonucu vermesi, N+1 düzeltmesinin sorgu sayısını düşürmesi, düzeltmenin yorumları ve biçimi koruması, ölçer ve rapor. Her push'ta GitHub Actions ile Python 3.9 ve 3.13'te çalışır; Yeşil Kod kendi kodunu da denetler.

## Ölçüm modları

| Mod | Ne zaman | Nasıl |
|---|---|---|
| Gerçek ölçüm (RAPL) | Linux + Intel/AMD işlemci | İşlemcinin enerji sayaçları okunur, boşta tüketim çıkarılır |
| Donanım ölçümü (powermetrics) | Mac, yönetici izniyle | Apple'ın işlemci güç verisi 100 ms'de bir örneklenir; ölçüm penceresiyle örtüşen örnekler toplanır, boşta tüketim çıkarılır |
| Tahmini ölçüm | Windows, sanal makine ya da izin yoksa | İşlemci süresi × çekirdek başına güç (varsayılan 10 W) |

Linux'ta gerçek ölçüm için: `sudo chmod -R a+r /sys/class/powercap/intel-rapl` (`baslat.sh` bunu sorar). Mac'te `baslat.sh` "Donanım ölçümü açılsın mı?" diye sorar ve şifreyi bir kez ister; şifre Python'a gitmez, powermetrics aynı terminalden `sudo -n` ile başlatılır. Elle: `sudo -v && python3 -m greencode`. Hangi modda olduğunuzu `python3 -m greencode olcer` gösterir. Panelin sağ üstündeki yeşil nokta donanım ölçümünü, turuncu nokta tahmini ölçümü gösterir. Jüriye hangi modda ölçtüğünüzü söyleyin.

Adalet kuralları: kısa süren kod sayaçların ölçebileceği süreye kadar tekrarlanır; her sonuç 5 tekrarın ortalamasıdır; düzeltilmiş koddaki önbellekler her istekten önce temizlenir.

## Ayarlar (ortam değişkenleri)

| Değişken | Varsayılan | Anlamı |
|---|---|---|
| `YK_CARBON_INTENSITY` | 341 | Şebeke karbon yoğunluğu, gCO₂e/kWh |
| `YK_CPU_W_PER_CORE` | 10 | Tahmini modda çekirdek başına güç (W) |
| `YK_DAILY_CALLS` | 1000000 | Yıllık projeksiyon için günlük istek |
| `YK_REPEATS` | 5 | Her ölçümün tekrar sayısı |
| `YK_PORT` | 8000 | Panel portu |
| `YK_POWERMETRICS` | 1 | Mac'te donanım ölçümünü kapatmak için 0 |
| `ANTHROPIC_API_KEY` | (boş) | Tanımlanırsa "Kodunu dene" ekranında yapay zekâ önerisi de istenebilir |

## Proje yapısı

```
greencode/
  kurallar.py   113 kural: kategori, önem, Türkçe/İngilizce metin ve dayandığı kaynak
  analyzer.py   AST tabanlı statik analiz
  fixer.py      AST tabanlı otomatik düzeltme, 11 dönüşüm; değişikliği özgün koda satır düzeyinde yerleştirir
  proof.py      eşdeğerlik testi, sorgu sayacı, ölçüm, canlı yarış
  meter.py      enerji ölçer (RAPL, Mac powermetrics, tahmini mod), karbon ve yıllık projeksiyon
  scenarios.py  4 gerçekçi israflı kod senaryosu ve ortak verileri
  report.py     CI raporu (md, html, json)
  server.py     standart kütüphaneyle web sunucusu, API ve canlı akış (SSE)
  config.py     katsayılar ve kaynakları
web/            panel ve yazı tipleri (Martian Mono, Hanken Grotesk; SIL OFL)
tests/          unittest paketi
ornekler/       örnek israflı kod, GitHub Action
```

## Proje sayfası ve stant malzemeleri

`docs/` klasörü GitHub Pages ile yayınlanır. Site dört bölümden oluşur: **Proje** (tanıtım ve film), **Dashboard** (kodu yapıştır ya da dosya aç; bulgular editörde satır satır işaretlenir, düzeltme kopyalanır ya da indirilir), **Analizler** (bu cihazda yapılan bütün analizlerin geçmişi, grafikler, JSON/CSV dışa aktarma; yalnızca tarayıcıda saklanır) ve **Kurallar** (113 kuralın dokuz gruptaki açıklaması, dayandığı kaynak ve denenebilir örnekleri, `ornekler/kurallar/`). Ziyaretçi QR kodu okutup kendi Python kodunu telefonunda analiz eder; standdaki motor Pyodide ile tarayıcıda (ayrı bir Web Worker'da) çalışır ve kod hiçbir yere gönderilmez. Hazır senaryolarda **Telefonunda ölç** düğmesi iki sürümü telefonda çalıştırır, çıktıların aynı olduğunu doğrular ve işlemci sürelerini karşılaştırır.

`stant/` klasöründe COP31 için her şey var:

| Dosya | Ne |
|---|---|
| `pdf/01-poster-A0.pdf` | Stant posteri (A1/A2'ye oranlı küçülür) |
| `pdf/02-brosur-*-TR.pdf`, `pdf/03-brochure-*-EN.pdf` | A5 broşür; `A4-2li-baski` sürümü kırtasiyede A4'e basılıp ortadan kesilir |
| `pdf/04-masa-karti-A4.pdf` | Ortadan katlanan masa kartı (bir yüz Türkçe, bir yüz İngilizce) |
| `pdf/05-proje-ozeti-A4.pdf` | Yetkililer ve jüri için 2 sayfalık özet |
| `pdf/06-ekran-sunumu-16x9.pdf` | 9 slaytlık ekran sunumu |
| `pdf/07-stant-rehberi-A4.pdf` | Ekip için: takvim, kurulum, baskı listesi, konuşma metinleri, sorular |
| `pdf/08-video-brifi-A4.pdf`, `film/video-prompt.md` | Filmi yeniden yaptırmak için brif, yapay zekâ promptları ve seslendirme metni |
| `pdf/en/` | Posterin, proje özetinin ve ekran sunumunun İngilizce sürümleri |
| `qr/` | QR kodları (SVG baskı için, PNG genel kullanım için) |

Ekip adı ya da adres değişirse `stant/ayarlar.json` dosyasını düzenleyip yeniden üretin:

```bash
python3 stant/hazirla.py            # site, QR, PDF ve film
python3 stant/hazirla.py pdf        # yalnızca PDF'ler (Google Chrome gerekir)
```

QR adımı `pip install segno`, film adımı `ffmpeg` ister.

## Dürüst sınırlar

- Yalnızca işlemci enerjisi ölçülür; bellek, ağ, disk ve soğutma dahil değildir. Gösterilen kazanç alt sınırdır.
- Sipariş raporu senaryosunda veritabanı aynı bilgisayardadır. Gerçek sistemde her sorgu ağdan geçer; bu yüzden sorgu sayısı ayrıca gösterilir.
- Tahmini modda mutlak değerlerden çok oranlar güvenilirdir.
- Düzeltme motoru şimdilik Python içindir. Aynı satırda birden fazla ifade gibi nadir durumlarda biçim korunamaz; motor o zaman kodu `ast.unparse` ile baştan yazar ve bunu bildirir.
- Karbon yoğunluğu yıllık ortalamadır; şebeke saatten saate değişir.

## Kaynaklar

- Türkiye şebekesi 341 gCO₂e/kWh: Low-Carbon Power, Ağustos 2025–Temmuz 2026
- SCI: Green Software Foundation, Software Carbon Intensity (ISO standardı, 2024)
- Otomobil 96,7 gCO₂/km: EEA, 2025 yeni otomobil ortalaması (geçici veri)
- Veri merkezleri 2024'te ~415 TWh: IEA, Energy and AI (2025)
