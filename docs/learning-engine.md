# Learning Engine

Learning Engine oyuncunun hangi dil becerisinde zorlandığını **açıklanabilir bir kuralla** hesaplar
ve bir sonraki öğrenme hedefini seçer (#16). Kod `src/api/app/engines/learning.py` içindedir. Saf
Python'dur, yapay zekâya bağlı değildir. Yapay zekâ yalnızca hataları **tespit eder**, onların ne
anlama geldiğine bu motor karar verir. Tüm eşikler dosyanın başında tek bir yerde sabit olarak
tanımlıdır; bu belgedeki sayılar oradan gelir.

## Girdi: öğrenme fırsatları

Her oyuncu mesajı, dokunduğu her kategori için bir **fırsat** üretir (`skill_observations`):

- Mesajda o kategoride hata varsa sonuç `incorrect`,
- yapay zekâ kategoriyi doğru kullanılmış olarak bildirdiyse `correct`,
- kategoriye hiç dokunmayan mesaj o kategori için fırsat değildir. Geçmiş zaman içermeyen bir cümle
  Past Simple puanını değiştirmez.

Aynı mesajda aynı kategoride hem hata hem doğru kullanım varsa sonuç `incorrect` olur. Bir mesaj
bir kategori için tek fırsattır.

Kategoriler: `present_simple`, `past_simple`, `question_formation`, `prepositions`,
`vocabulary_usage`.

## Beceri puanı (0–100)

Bir kategorideki fırsatların **ağırlıklı doğru oranıdır**. Son mesajlar daha ağırdır:

```
en yeni fırsatın ağırlığı = 1
her eski fırsatın ağırlığı = bir yenisinin ağırlığı × 0,85      (SCORE_DECAY)

önsel = 2 fırsat ağırlığında %50, en eski fırsattan da önce durur
        ve aynı şekilde söner                        (PRIOR_WEIGHT, PRIOR_SCORE)

puan = 100 × (doğru fırsatların ağırlık toplamı + önsel × 0,5)
           / (tüm fırsatların ağırlık toplamı + önsel)
```

Neden böyle:

- **Son mesajlar daha ağır:** beşinci en yeni fırsat, en yeninin yaklaşık yarısı kadar sayılır.
  Oyuncu geliştikçe eski hataları puanı aşağı çekmeyi bırakır.
- **Önsel:** hiç pratik yapılmamış beceri "kötü" değil, "bilinmiyor"dur; 50'den başlar. Tek bir
  mesaj puanı oynatır ama bir anda 0'a ya da 100'e götürmez.
- **Önsel de söner:** yeterli pratikle puan gerçekten 0'a ya da 100'e ulaşabilir.

Örnek puanlar (D = doğru, H = hata, eskiden yeniye):

| Geçmiş | Puan |
|---|---|
| (fırsat yok) | 50 |
| D | 69 |
| H | 31 |
| D D D | 84 |
| H H H | 16 |
| H H D | 42 |
| D D H | 58 |
| 5 × H, sonra 5 × D (gelişen) | 68 |
| 5 × D, sonra 5 × H (gerileyen) | 32 |
| 8 × D, sonra 1 × H | 78 |
| 10 × D | 97 |

Aynı 5 doğru ve 5 hata, sıraya göre 68 ya da 32 verir: puan oyuncunun **şimdiki** durumunu gösterir.

**Durum bantları:** fırsat yoksa `not_practised`; 50'nin altı `weak` (WEAK_BELOW); 50–74 `developing`;
75 ve üstü `strong` (STRONG_FROM).

## Tekrar eden hata

Bir kategori, oyuncunun **son 10 mesajının** (REPEAT_WINDOW_MESSAGES) **en az 3'ünde**
(REPEAT_MIN_MISTAKES) o kategoride hata varsa tekrar eden hatadır.

- "Son 10 mesaj" oyuncunun tüm görevlerdeki kendi mesajlarıdır; hiçbir beceriye dokunmayan sohbet
  mesajları da sayılır. Böylece pencere oyuncunun gerçekten yazdığı şeyi izler.
- Bir mesaj, içinde o kategoriden kaç hata olursa olsun **bir kez** sayılır. Tek uzun bir cümledeki
  üç hata "tekrar" değildir.
- Eski hatalar pencereden çıkınca `repeated` kendiliğinden kalkar; geçmiş kayıtlar silinmez.

## Öğrenme hedefi seçimi

`choose_learning_target(puanlar, seviye)` bir sonraki görevin çalıştıracağı beceriyi seçer.
`rank_learning_targets()` beş kategorinin tam sırasını verir; ilk eleman hedeftir. Sıralama
**deterministiktir**, aynı girdi her zaman aynı sırayı verir:

1. **Tekrar eden hatalar önce gelir.** Birden fazlaysa son 10 mesajda daha çok hatası olan önce.
2. **Sonra en düşük puan.** Ancak oyuncunun son 3 mesajında (RECENT_PRACTICE_MESSAGES) çalışılmış
   bir beceri sıralamada **15 puan yüksek** sayılır (RECENT_PRACTICE_PENALTY). Böylece az önce
   çalışılan ve yalnızca biraz zayıf olan beceri yerine başka bir beceri gelir (çeşitlilik), ama
   açıkça zayıf bir beceri hedefte kalır.
   - Örnek: bir doğru ve az önce bir hata → 48 + 15 = 63, hiç çalışılmamış becerinin 50'sinin
     üstünde: hedef başka beceri olur.
   - Örnek: art arda dört hata → 12 + 15 = 27: hedef yine bu beceridir.
3. **Eşitlikte seviyenin sırası** (LEVEL_ORDER). Yeni oyuncu da buna göre başlar:
   - A2: Present Simple → Vocabulary Usage → Question Formation → Prepositions → Past Simple
   - B1: Past Simple → Question Formation → Prepositions → Present Simple → Vocabulary Usage

Hedefin gerekçesi (`reason`) şunlardan biridir ve oyuncuya kısa bir cümleyle gösterilir:

| reason | Ne zaman |
|---|---|
| `repeated_mistake` | Kategori tekrar eden hata |
| `not_practised` | Kategoride hiç fırsat yok |
| `weakest_skill` | Pratik yapılmış ve puanı 75'in altında |
| `review` | Pratik yapılmış ve güçlü (75+); tüm beceriler güçlüyken tekrar |

## Saklama

Puanlar **ayrı bir tabloda saklanmaz**, her istekte kayıtlardan hesaplanır
([data-model.md](data-model.md), "Beceri puanları"). Formül değiştiğinde tüm oyuncuların puanı
kendiliğinden yeni formüle uyar.

## API

- `GET /api/learning/skills`: her kategorinin puanı, durumu, sayaçları ve tekrar eden hatalar.
- `GET /api/learning/recommendations`: öğrenme hedefi, gerekçesi ve tam sıralama.
- `GET /api/learning/errors`: oyuncunun hataları, en yeniden eskiye, görev adıyla.

Ayrıntılar [data-model.md](data-model.md) içindedir.

## Kapsam dışı

- Öğrenme amacı (`learning_goal`: everyday, work, grammar) beceri sıralamasını etkilemez. Veri azken
  görev seçimine Adaptive Quest Engine yön verir ([quest-engine.md](quest-engine.md)).
  Diyalogların zayıf beceriye göre kişiselleştirilmesi #20'dedir.
