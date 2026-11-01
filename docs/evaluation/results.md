# AI hata analizi: değerlendirme sonuçları

**Issue:** #20 · **Model:** `gemini-3.1-flash-lite` (ücretsiz katman) · **Tarih:** 1 Kasım 2026 ·
**Yöntem ve etiketleme kuralları:** [README.md](README.md)

> **Etiket durumu:** cümleleri ve etiketleri bir kişi hazırladı (`labelling.drafted_by`); ikinci bir ekip
> üyesinin incelemesi bekleniyor. Bir etiket değişirse aşağıdaki sayılar betikle yeniden üretilmelidir.

## Özet

- **Asıl soru: anlaşılır ama küçük hatalı cümleler yanlışlıkla "anlaşılmadı" sayılıyor mu?** Hayır.
  35 cümle × 2 tur = 70 örnekte iki prompt'ta da **0/70**. Kontrol setinde de 0.
- **Önceki prompt güçlüydü ama dört sistematik hatası vardı.** Dördü de iki turda birebir
  tekrarlandı, yani rastlantı değil:
  1. fiilden sonra eksik edatı (*listen music*) kelime hatası saymak,
  2. yanlış kelime seçimini (*won money* → *earned*) kaçırmak,
  3. hatasız bir cümlede içeriği "düzeltmek" (*Mia left …* → *I left …*),
  4. konuyla ilgisiz ama doğru bir cümleyi "anlaşıldı" saymak.
- **Prompt iyileştirmesinden sonra** üçü tamamen, dördüncüsü yarı yarıya düzeldi. Hatalı cümlede
  doğru kategori **%94 → %99**, kategori kümesi birebir doğru **%93 → %99**, hatasızda uydurulan hata
  **2/16 → 0/16**, anlaşılmazı yakalama **8/10 → 10/10**.
- **İyileşme genelleşiyor:** kurallar yazıldıktan sonra hazırlanan, tasarımda hiç kullanılmayan
  kontrol setinde konu dışı cümleyi yakalama **1/6 → 4/6**, edat recall'u **%83 → %100**.
- **Kişiselleştirme çalışıyor:** odak açıkken NPC cevaplarının **18/30**'u oyuncuya hedef yapıyı
  kullandıracak bir soru soruyor, odak kapalıyken **0/30**.

## Ana set: önce ve sonra

48 cümle (35 hatalı, 8 hatasız, 5 anlaşılmaz), her biri 2 tur. "Önce" `main` dalındaki prompt'tur
(parmak izi `659699449498`), "sonra" bu PR'daki prompt (`57e09096a529`).

| Ölçüt | Önce | Sonra | Yön |
|---|---|---|---|
| **Yanlışlıkla başarısız (küçük hatalı)** | **0% (0/70)** | **0% (0/70)** | = |
| Yanlışlıkla başarısız (hatasız) | 0% (0/16) | 0% (0/16) | = |
| Anlaşılmazı yakalama | 80% (8/10) | 100% (10/10) | daha iyi |
| Hatasızda uydurulan hata | 12% (2/16) | 0% (0/16) | daha iyi |
| Hatalıda doğru kategori | 94% (66/70) | 99% (69/70) | daha iyi |
| Kategori kümesi birebir | 93% (80/86) | 99% (85/86) | daha iyi |
| Kullanılamayan cevap | 0% (0/96) | 0% (0/96) | = |

Kategori başına (her kategoride 7 cümle × 2 tur = 14 örnek):

| Kategori | Recall önce → sonra | Precision önce → sonra | Doğruluk önce → sonra |
|---|---|---|---|
| present_simple | 100% → 100% | 100% → 100% | 100% → 100% |
| past_simple | 100% → 100% | 88% → 100% | 98% → 100% |
| question_formation | 100% → 100% | 100% → 100% | 100% → 100% |
| prepositions | 86% → 100% | 100% → 100% | 98% → 100% |
| vocabulary_usage | 86% → 93% | 86% → 100% | 95% → 99% |

Ham sonuçlar: [runs/before.json](runs/before.json), [runs/after.json](runs/after.json).

### Önceki prompt'un hataları ve yapılan değişiklik

| Cümle | Beklenen | Önceki prompt (iki turda da) | Değişiklik | Sonra |
|---|---|---|---|---|
| pr6 *I usually listen music.* | prepositions | vocabulary_usage (açıklaması "edat" dediği hâlde) | Her kategorinin kapsamı örnekleriyle yazıldı: fiil/sıfattan sonraki edat `prepositions`'tır | 2/2 doğru |
| vu6 *… I won a lot of money.* (işten) | vocabulary_usage | hata bulunmadı | Aynı rehberde: dil bilgisi doğru ama kelime ya da kalıp yanlışsa `vocabulary_usage` | 1/2 doğru |
| ok5 *Mia left her bag on the chair, …* | hatasız | past_simple: *Mia left* → *I left* | "Yalnızca İngilizceyi düzelt, içeriği değil: isimler, kişiler, olaylar ve oyuncunun hikâyesi aynen kalır" | 2/2 doğru |
| un3 *The dog is purple on Sundays.* (oda sorusuna) | anlaşılmadı | anlaşıldı | İlgisiz ama doğru bir cümlenin `false` olduğu bir örnekle açıklandı | 2/2 doğru |

Prompt'taki örnekler bilerek değerlendirme cümlelerinden **farklı** seçildi. Aksi hâlde ölçüm
kuralın işe yarayıp yaramadığını değil, modelin örneği ezberleyip ezberlemediğini gösterirdi.
`test_the_prompt_never_contains_the_evaluation_sentences` bunu her CI çalışmasında denetler.

**Kalan tek hata:** vu6'da *won money* iki turun birinde hâlâ kaçıyor. *win money* kendi başına doğru
bir İngilizce ifade; yanlışlık yalnızca bağlamda (işten kazanılan para) ortaya çıkıyor. Bu tür
bağlama bağlı kelime hataları modelin en zayıf olduğu alan.

## Kontrol seti (holdout): iyileşme genelleşiyor mu?

[holdout.json](holdout.json): yeni kurallar yazıldıktan sonra hazırlanmış, prompt örnekleriyle ne
kelime ne kalıp paylaşan 12 cümle (6 hatalı, 3 hatasız, 3 konu dışı). İki prompt da aynı sette,
2'şer tur çalıştırıldı.

| Ölçüt | Eski prompt | Yeni prompt | Yön |
|---|---|---|---|
| Yanlışlıkla başarısız (küçük hatalı) | 0% (0/12) | 0% (0/11) | = |
| Yanlışlıkla başarısız (hatasız) | 0% (0/6) | 0% (0/6) | = |
| **Konu dışı cümleyi yakalama** | **17% (1/6)** | **67% (4/6)** | daha iyi |
| Hatasızda uydurulan hata | 0% (0/6) | 0% (0/6) | = |
| Hatalıda doğru kategori | 92% (11/12) | 100% (11/11) | daha iyi |
| Kategori kümesi birebir | 94% (17/18) | 100% (17/17) | daha iyi |
| Kullanılamayan cevap | 0% (0/24) | 4% (1/24) | daha kötü* |

\* Tek kullanılamayan cevabın nedeni `network`, yani geçici bir bağlantı hatası; prompt'la ilgisi
yok. Bu yüzden yeni prompt'ta 23 örnek puanlandı.

- Eski prompt *She is married **with** a doctor* cümlesindeki edatı bir turda kelime hatası saydı
  (ana setteki *listen music* hatasının aynısı); yeni prompt iki turda da doğru kategori verdi (edat
  recall'u %83 → %100).
- Konu dışı cümlelerde en büyük fark: eski prompt üçünden yalnızca biri için bir kez "anlaşılmadı"
  dedi. Yeni prompt *Elephants are very big animals.* ve *Football is popular in Brazil.* için her
  seferinde doğru karar verdi; *My favourite colour is green.* (evcil hayvan sorusuna) cevabını ise
  iki turda da "anlaşıldı" saydı. Konu dışı cümleler bu sette yeni prompt'un en zayıf kaldığı yer.

Ham sonuçlar: [runs/holdout-before.json](runs/holdout-before.json),
[runs/holdout-after.json](runs/holdout-after.json). Eski prompt, betiğin `--prompt-file` seçeneğiyle
`main` dalındaki `prompts.py` dosyasından ölçüldü. `main`'in prompt'u ana sette `659699449498`
("önce" ölçümüyle aynı), kontrol setinde `0eee8b094528` parmak izini verir; yani dört ölçümün de hangi
prompt'la yapıldığı dosyalardan doğrulanabilir.

## Kişiselleştirme: NPC hedef yapıyı kullandıracak sorular soruyor mu?

Üç sahnede (komşuyla tanışma, kafe, iş görüşmesi), beş becerinin her biri için NPC'nin ilk cevabı
iki kez alındı: **odak açık** ve **odak kapalı**. Oyuncunun cümlesi her durumda aynı ve nötrdür
(*Hi! I'm the new neighbour. Nice to meet you.* gibi). Bir cevap, hem soru içeriyor hem de o yapıya
dair bir işaret taşıyorsa (ör. Past Simple için *did you*, *what happened*) sayıldı.

| Beceri | Odak açık (v1) | Odak açık (son) | Odak kapalı (son) |
|---|---|---|---|
| Present Simple | 4/6 | 4/6 | 0/6 |
| Past Simple | 4/6 | 4/6 | 0/6 |
| Soru kurma | 3/6 | 2/6 | 0/6 |
| Edatlar | 4/6 | 4/6 | 0/6 |
| Kelime kullanımı | 4/6 | 4/6 | 0/6 |
| **Toplam** | **19/30** | **18/30** | **0/30** |

Cevaplar tek tek okundu ([runs/focus-v1.json](runs/focus-v1.json), [runs/focus.json](runs/focus.json)):

- **v1'de model örnek soruları kopyalıyordu.** Kafedeki barista *"How would you describe your old
  flat?"* diye soruyordu; bu prompt'taki örneğin aynısıydı. Son sürümde "örnekler yalnızca fikri
  gösterir, bu sahne ve karakter için kendi sorunu yaz" kuralı eklendi. Örneğin kelimesi kelimesine
  tekrarı **9/30 → 4/30**'a indi; davet oranı aynı kaldı (19 → 18, bu örnek büyüklüğünde fark yok).
  Örnek cevaplar: *"Do you usually drink coffee in the morning?"* (kafe, Present Simple), *"Where
  exactly is your new home in this neighbourhood?"* (kafe, edatlar), *"Can you tell me about a job you
  had before?"* (görüşme, Past Simple).
- **İş görüşmesinin ilk cevabında odak neredeyse hiç etkili değil.** NPC her durumda oyuncudan
  kendini tanıtmasını istiyor. Bu beklenen bir sonuç: görevin ilk hedefi zaten kendini tanıtmak ve
  prompt, odağın görev hedeflerinden önce gelmemesini söylüyor. Sonraki turlarda odak devreye girer.
- **Soru kurma en zayıf beceri (2/6).** NPC'nin oyuncuyu soru sormaya davet etmesi, diğer yapılara
  göre bir sahnenin akışına daha zor oturuyor.
- İşaretler sezgiseldir; bir cevap hedefi doğal biçimde tetikleyip sayılmayabilir (*"Can you tell me
  about your past work experience?"*) ya da tersi olabilir. Odak açık/kapalı karşılaştırması aynı
  sezgiyle yapıldığı için fark yine de anlamlıdır.

### Gerçek oyunda bir konuşma

Docker'daki gerçek uygulamada, yeni bir A2 oyuncunun komşusuyla konuşması (sahnenin becerisi
Present Simple). Oyuncu ikinci mesajdan itibaren edat hatası yapıyor:

| Oyuncu | Bulunan hata | NPC'nin sorusu |
|---|---|---|
| *Hi Alex! Nice to meet you, I am Deniz.* | – | *What do you usually do on your weekends?* (Present Simple) |
| *I arrived to the city in Monday.* | prepositions ×2 | *What do you usually do on your free days here?* |
| *I live in the flat at the second floor.* | prepositions | *Do you have many plants in your flat **on** the second floor?* |
| *I usually listen music in the evening.* | prepositions | *Do you listen to it **in** your living room or **in** your bedroom?* |
| *Yes, I like it here.* | – | *Do you like to listen to music **at** night or **in** the afternoon?* |

Oyuncu ilk edat hatasını yapınca Learning Engine edatları zayıf beceri olarak gördü ve sonraki
cevaptan itibaren NPC yer ve zaman soruları sormaya başladı. Odak, cevaplanan mesajdan önceki
kayıtlarla hesaplandığı için ikinci cevap henüz Present Simple'a yöneliktir.

## Sınırlar

- **Etiketler tek kişiden.** İkinci bir ekip üyesinin incelemesi bekleniyor.
- **Küçük gruplar.** 8 hatasız ve 5 anlaşılmaz cümlede tek bir cevap oranı 6–10 puan oynatır. Bu
  yüzden her ölçüm 2 tur yapıldı ve önemli bulgular kontrol setiyle de sınandı.
- **Kurallar ana setteki hatalara bakılarak yazıldı.** Ana setteki "sonra" sonucu bu nedenle iyimser
  olabilir. Kontrol seti, aynı iyileşmenin tasarımda kullanılmayan cümlelerde de görüldüğünü
  gösteriyor, ama yalnızca 12 cümle.
- **Tek model ve sıcaklık 0,4.** Sonuçlar `gemini-3.1-flash-lite` içindir. Model değişirse ölçüm
  yeniden yapılmalıdır.
- **Her cümle tek NPC cümlesine verilen cevap.** Gerçek oyunda model son 8 mesajı görür; uzun
  konuşmaların etkisi ölçülmedi.

## Yeniden üretmek

[README.md](README.md) içindeki komutlar. Ana set ve kontrol seti için iki ölçüm toplam 240 AI
isteğidir (ücretsiz katman yeterli). Puanlama ve veri seti kuralları `tests/test_evaluation.py` ile
her CI çalışmasında test edilir.
