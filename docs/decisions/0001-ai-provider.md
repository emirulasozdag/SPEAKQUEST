# 0001 — AI sağlayıcısı (Gemini mi, OpenAI mı?)

**Durum:** karar verildi, **OpenAI ölçülemedi** (aşağıda nedeni yazılı).
**Issue:** #4 · **Tarih:** 2026-10-29 · **Karar verenler:** ekip (bu belgeyi PR'da onaylar)

## Soru

NPC cevabı üretmek ve oyuncunun İngilizce mesajındaki hataları kategorize etmek için hangi sağlayıcı
kullanılacak? Seçim `AI_PROVIDER` ayarıyla yapılır; kod tek bir arayüzün arkasında kalır (#8), bu
yüzden karar ileride geri alınabilir.

## Karar

**Gemini**, model `gemini-3.1-flash-lite`. Model adı koda gömülmez, ayardan okunur (#8).

Gerekçe:
- Ölçümde en iyi sonucu verdi: 10/10 geçerli şema, 10/10 doğru kategori, medyan 1,6 sn.
- Projede ücretli API bütçesi yok. Gemini ücretsiz anahtarla çalıştı, OpenAI API'si ise ön ödemeli
  bakiye istiyor ve denenemedi.
- Aynı arayüzün arkasında olduğu için, ileride gerekirse OpenAI eklemek yalnızca yeni bir istemci
  yazmaktır.

Bilinen riskler (bunları #8 karşılar):
- **Model ömrü kısa.** `gemini-2.5-flash` ölçüm gününde yeni kullanıcılara kapalıydı (HTTP 404). Model
  adı ayarlanabilir olmalı ve 404 anlaşılır bir hataya dönmeli.
- **Gecikme dalgalanıyor.** 30 istekte 3 tanesi 11–15 sn sürdü, geri kalanı 1–5 sn. #8'de zaman aşımı,
  tek seferlik yeniden deneme ve yedek cevap şart.
- **Yeni modeller aşırı yüklenebiliyor.** `gemini-3.8-flash` aynı gün 45–49 sn'lik cevaplar, HTTP 503 ve
  zaman aşımları verdi; sohbet için kullanılamadı. En yeni model yerine sürümü oturmuş bir "lite" model seçildi.

## Ölçütler

| Ölçüt | Gemini `gemini-3.1-flash-lite` | OpenAI |
|---|---|---|
| Geçerli şema oranı | 10/10 (son çalıştırma) | denenmedi |
| Doğru kategori oranı | 10/10 | denenmedi |
| Küçük hatayı "başarısız" saymama | 10/10 cümlede `communication_success = true` (1–9 anlaşılır cümleler) | denenmedi |
| Hatasız cümlede yanlış alarm | yok (10. cümle) | denenmedi |
| Gecikme | medyan 1,6 sn, ara sıra 11–15 sn | denenmedi |
| Türkçe açıklama kalitesi | ölçülmedi: ekip #8'de gerçek prompt ile puanlar | denenmedi |
| Ücretsiz kota ve fiyat | ücretsiz anahtar çalıştı; güncel kota için aşağıdaki bağlantı | ön ödemeli bakiye gerekiyor, hesapta bakiye yoktu |
| Kurulum | tek tıkla anahtar (aistudio.google.com/apikey) | anahtar kolay, ama bakiye şart |

Bilinçli sınırlar: 10 cümlelik örneklem küçüktür; bir sağlayıcının ya da modelin üstünlüğünü kanıtlamaz,
yalnızca kullanılabilirliğini gösterir. Betik küçük, geçici bir prompt kullandı; asıl prompt'lar #8'de yazılır
ve aynı örneklerle yeniden ölçülmelidir (S05-B'deki 40 cümlelik değerlendirme).

## Nasıl ölçüldü

Örnek cümleler [0001-samples.json](0001-samples.json) içindedir: README'deki 5 hata kategorisinden ikişer
cümle (A2–B1) ve 1 doğru cümle. Ölçüm `src/api/scripts/compare_providers.py` ile, anahtarlar ortam değişkeni
olarak verilerek yapıldı (hiçbir dosyaya yazılmadı):

```bash
export GEMINI_API_KEY=... GEMINI_MODEL=...
export OPENAI_API_KEY=... OPENAI_MODEL=...
cd src/api
python scripts/compare_providers.py gemini
```

## Sonuçlar

### Gemini `gemini-3.1-flash-lite` (2026-10-29, son çalıştırma)

| # | beklenen | geçerli şema | doğru kategori | iletişim | süre (sn) |
|---|---|---|---|---|---|
| 1 | present_simple | evet | evet | True | 1.7 |
| 2 | present_simple | evet | evet | True | 1.2 |
| 3 | past_simple | evet | evet | True | 1.7 |
| 4 | past_simple | evet | evet | True | 2.3 |
| 5 | question_formation | evet | evet | True | 1.0 |
| 6 | question_formation | evet | evet | True | 1.2 |
| 7 | prepositions | evet | evet | True | 1.5 |
| 8 | prepositions | evet | evet | True | 1.5 |
| 9 | vocabulary_usage | evet | evet | True | 15.1 |
| 10 | none | evet | evet | True | 15.1 |

Geçerli şema: 10/10 · doğru kategori: 10/10 · medyan süre: 1,6 sn.

Önceki iki çalıştırmada (şema düzeltilmeden) 9/10 çıktı: 1 numaralı cümlede (*"She go to work every day and I
drink coffee."*) model Present Simple'ı hem hata hem doğru kullanım olarak işaretledi. Bu doğru bir cevaptı;
şemadaki "bir kategori hem hatalı hem doğru olamaz" kuralı fazla katıydı ve kaldırıldı.

### Diğer denemeler

| Model | Sonuç |
|---|---|
| `gemini-2.5-flash` | HTTP 404: yeni kullanıcılara kapalı |
| `gemini-3.8-flash` | 10 istekten 2'si başarılı (45–49 sn), 1 tanesi HTTP 503 (yoğun talep), kalanı zaman aşımı |

### OpenAI

**Denenmedi.** `gpt-4.1-mini-2025-04-14` ile 10 istek de HTTP 429 `credit_balance_exhausted` döndü: hesapta
ön ödemeli bakiye yok ve projede ücretli API bütçesi yok. Kabul kriterindeki "iki sağlayıcıda da denendi"
maddesi bu yüzden **karşılanmadı**; ekip bunu PR incelemesinde bilerek kabul eder. Bakiye yüklenirse
yukarıdaki komutla `openai` çalıştırılıp sonuç bu belgeye eklenir.

### Fiyat ve kota

Kaynak: <https://ai.google.dev/gemini-api/docs/pricing>, bakılan tarih **2026-10-29**
(`gemini-3.1-flash-lite`, Standard katman).

| | Ücretsiz katman | Ücretli katman |
|---|---|---|
| Girdi (1M token) | ücretsiz | $0,25 (metin/görsel/video) |
| Çıktı (1M token) | ücretsiz | $1,50 |
| İçerik Google ürünlerini geliştirmek için kullanılır mı? | **evet** | hayır |

- **Dakikalık/günlük istek limiti** bu fiyat sayfasında bu model için yazılı değil; kullanılan hesabın
  güncel limitleri Google AI Studio'daki kullanım ekranından görülür. Ölçüm sırasında 30 istekte kota
  hatası alınmadı.
- **Gizlilik sonucu:** ücretsiz katmanda oyuncuların yazdığı mesajlar Google tarafından ürün geliştirmede
  kullanılabilir. Geliştirme ve ders demosu için kabul edilebilir, ancak gerçek kullanıcı verisi için değil.
  Oyuncuya gösterilecek bir gizlilik notu ve "gerçek kişisel bilgi yazma" uyarısı (#10 veya #14) eklenmeli;
  canlıya çıkılırsa ücretli katmana geçilmelidir.

## Geri dönüş yolu

- Seçilmeyen sağlayıcı silinmez: arayüz aynı kaldığı için `AI_PROVIDER` değiştirilerek geri dönülebilir.
- Kota dolarsa ya da sağlayıcı yanıt vermezse oyun çökmez: geçersiz ya da boş cevap güvenli bir yedek
  cevaba dönüşür (#8).
- API anahtarı yalnızca backend ortam değişkenlerinde durur; frontend'e ve loglara girmez.
