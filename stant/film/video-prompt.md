# Yeşil Kod tanıtım filmi: prompt ve brif

Bu dosya, filmi profesyonel olarak yeniden yaptırmak için hazırlandı. Üç bölüm var:

1. **Ajansa ya da kurgucuya verilecek kısa brif** (Türkçe, olduğu gibi gönderilebilir)
2. **Yapay zekâ video araçları için sahne promptları** (İngilizce; Veo, Sora, Runway, Kling gibi araçlar İngilizce promptta daha iyi sonuç verir)
3. **Seslendirme metni** (Türkçe, ~80 saniye)

Önemli: Yapay zekâ video araçları ekrana doğru yazı ve sayı yazamaz. Aşağıdaki promptlar yalnızca **ara görüntüler (B-roll)** içindir. Kod satırı, sayılar, grafikler ve QR kodu kurguda (CapCut, Premiere, After Effects, Canva) üstüne eklenmelidir. Mevcut film (`yesil-kod-film-qr.mp4`) bu grafikleri zaten içeriyor; yeni ara görüntüler onun sahneleri arasına kesilebilir.

---

## 1. Ajans / kurgucu brifi

**Proje:** Yeşil Kodlama (Green Coding) ve Dijital Karbon Ayak İzi Optimizasyon Aracı. Sakarya Üniversitesi, COP31 Yeşil Bölge, Antalya, 13–14 Kasım 2026.

**Ne yapıyor:** Python kodunda enerji israf eden satırları bulur, kodu kendisi yeniden yazar, iki sürümün birebir aynı sonucu verdiğini doğrular ve harcanan enerjiyi ölçüp karbona çevirir. Tek satırlık bir düzeltmeyle 465 kat az enerji.

**Filmin işi:** Stanttaki ekranda sessiz döngüde dönmek ve yanından geçen birini 5 saniyede durdurmak; sesli hâliyle de sosyal medyada ve sunumlarda kullanılmak.

**Teslim edilecekler**

- 16:9, 1920×1080 (mümkünse 3840×2160), 75–90 saniye, sesli (seslendirme + müzik)
- Aynı filmin **sessiz döngü** sürümü: seslendirme yerine ekranda kısa Türkçe yazılar, ayrıca İngilizce altyazı dosyası (.srt/.vtt)
- 9:16, 1080×1920, 30 saniyelik dikey kesit (Instagram/LinkedIn)
- MP4 (H.264), müzik telifsiz ve lisanslı

**Görsel kimlik**

- Renkler: koyu yeşil-siyah `#18211C`, açık mineral `#DCE1DB`, kâğıt `#EEF1EC`, yosun yeşili `#2C6A4A`, açık yaprak yeşili `#66B48A`, israfı gösteren kehribar `#C4601A`
- Yazı tipleri: **Martian Mono** (kod, sayılar, logo) ve **Hanken Grotesk** (metin). İkisi de ücretsiz (SIL OFL, Google Fonts).
- Logo: “yeşil**kod**”, Martian Mono kalın; “kod” yeşil.
- Ton: sakin, kesin, kanıta dayalı. Hareketler yumuşak ve az.

**Kaçınılacaklar**

- Klişeler: avuçta dünya, devre kartından çıkan yaprak, yeşil ampul, uçuşan ikili kodlar
- Sayıları değiştirmek ya da yuvarlamak (aşağıdaki sayılar ölçülmüş değerlerdir; olduğu gibi kullanılmalı)
- Sakarya Üniversitesi, YÖK ve COP31 logolarını koordinatörlüğün izni olmadan kullanmak

**Değişmeyecek sayılar ve kaynaklar**

- 465× daha az enerji (yoklama kontrolü), ~4.000× (rota sayısı), 51× (fiyat listesi), 4.001 → 2 sorgu (sipariş raporu). Tahmini ölçüm modu, 26 Ekim 2026.
- Günde 1 milyon istek → yılda ~41 kg CO₂e, yalnızca tek satırdan
- Veri merkezleri: 415 TWh (2024) → ~945 TWh (2030). Kaynak: IEA, Energy and AI (2025)
- Türkiye şebekesi 341 gCO₂e/kWh (Low-Carbon Power, Ağustos 2025–Temmuz 2026)
- Kapanıştaki QR: https://yes3760.github.io/yesil-kod/#dene

**Sahne akışı**


| Süre | Görüntü | Ekrandaki yazı |
|---|---|---|
| 0–6 sn | Karanlık ekranda tek satır kod yazılıyor (B-roll 1) | `return [no for no in GELENLER if no in kayitlilar]` · “Bu satır ne kadar elektrik harcıyor?” |
| 6–14 sn | Sayaç 0’dan 1.000.000’a; arkada satır tekrar tekrar akıyor | “Günde 1.000.000 istek. Bir yıl boyunca.” · “41 kg CO₂e” |
| 14–24 sn | Veri merkezi (B-roll 2–3) → çubuk grafik | “Veri merkezlerinin tüketimi altı yılda iki katını aşıyor.” 415 → ~945 TWh |
| 24–30 sn | Logo açılışı | yeşil**kod** · “Ölçer. Düzeltir. Kanıtlar.” |
| 30–42 sn | Kod farkı: kırmızı satır üstü çiziliyor, iki yeşil satır geliyor | “Motor satırı kendisi yeniden yazdı.” · ✓ “2.000 kayıtlık çıktı birebir aynı.” |
| 42–54 sn | İki enerji şeridi yarışıyor; sayaç (B-roll 4: yavaşlayan elektrik sayacı) | “Aynı istekler, iki sürüm.” → **465×** “daha az enerji, aynı sonuç” |
| 54–64 sn | Dört sonuç satırı tek tek geliyor | Rota ~4.000× · Yoklama 465× · Fiyat 51× · Sipariş 4.001 → 2 sorgu |
| 64–72 sn | Bul · Düzelt · Doğrula · Ölç; stantta öğrenciler (B-roll 5) | “Python için çalışan prototip.” |
| 72–84 sn | Antalya kıyısı (B-roll 6) → QR kapanış kartı | “Ölçülmeyen şey optimize edilemez.” · “Kendi kodunu telefonunda dene.” + QR + adres |

---

## 2. Yapay zekâ video araçları için sahne promptları

Her biri 5–8 saniyelik tek çekim içindir. Çıkan görüntüde okunur yazı, marka ya da logo olmamalı; varsa kurguda bulanıklaştırın ya da kırpın.

### B-roll 1: kod satırı
```
Close-up of a laptop screen in a dim room at night. A single line of code is being typed in a monospace font on a very dark green-black editor theme, cursor blinking. Shallow depth of field, the text itself is soft and unreadable. Slow push-in. Muted charcoal and deep green colour grade with one warm amber highlight. Cinematic, realistic, 4K, no logos, no readable text.
```

### B-roll 2: veri merkezi dışarıdan
```
Aerial drone shot of a large modern data centre at dusk, rows of cooling units on a flat roof, faint steam rising into a cool evening sky. Slow forward glide. Desaturated charcoal and muted green colour grade, soft warm lights from windows. Realistic, cinematic, 4K, no logos, no text.
```

### B-roll 3: sunucu koridoru
```
Slow dolly shot down a long aisle of server racks inside a data centre, tiny status lights blinking, cool blue-green ambient light, light haze in the air. Shallow depth of field, symmetrical composition. Realistic, cinematic, 4K, no logos, no readable labels.
```

### B-roll 4: elektrik sayacı
```
Macro shot of an analog electricity meter with a spinning disk. The disk spins fast at first, then gradually slows down to a gentle pace. Warm practical light, dark background, shallow depth of field. Realistic, 5 seconds, no readable brand names.
```

### B-roll 5: stant
```
Two university students at a small exhibition stand in a bright, modern conference hall. One points at a large screen showing simple green and orange bar charts while two visitors hold up their phones to scan a code on a table card. Natural daylight, documentary handheld style, faces softly out of focus. Realistic, 4K, no logos, no readable text.
```

### B-roll 6: Antalya
```
Slow aerial pan along a Mediterranean coastline at sunrise, calm turquoise sea, steep cliffs and the Taurus mountains in the background, soft golden light, light morning haze. Realistic, cinematic, 4K, no text.
```

### Tek parça kısa tanıtım (yalnızca atmosfer için, 8–10 sn)
```
A cinematic 10-second sequence: a single glowing line of code on a dark screen dissolves into the blinking lights of a server hall, which slowly dim as an electricity meter disk decelerates, ending on a calm Mediterranean sunrise. Muted charcoal, deep green and a single amber accent. Smooth, slow camera moves, realistic, no text, no logos.
```

---

## 3. Seslendirme metni (Türkçe, ~80 saniye)

> Bu satır, bir yoklama sisteminden. Masum görünüyor.
>
> Ama günde bir milyon kez çalıştığında, yılda kırk bir kilogram karbondioksit salıyor. Yalnızca bu satır.
>
> Veri merkezlerinin elektrik tüketimi altı yılda iki katını aşacak. Bu enerjinin bir kısmı, kimsenin görmediği yazılım israfına gidiyor.
>
> Yeşil Kod bu israfı görünür kılıyor.
>
> İsraf eden satırı buluyor, kodu kendisi yeniden yazıyor ve iki sürümün birebir aynı sonucu verdiğini doğruluyor.
>
> Sonra ikisini aynı işle yarıştırıp enerjiyi ölçüyor. Sonuç: dört yüz altmış beş kat daha az enerji. Aynı sonuç.
>
> Dört gerçek israf. Dördünü de motor düzeltti.
>
> Bul. Düzelt. Doğrula. Ölç. Sakarya Üniversitesi’nden, COP31 için.
>
> Ölçülmeyen şey optimize edilemez. Kendi kodunu telefonunda dene.

**İngilizce altyazı** için hazır dosya: `yesil-kod-film-en.vtt` (mevcut filmin zamanlamasına göre).
