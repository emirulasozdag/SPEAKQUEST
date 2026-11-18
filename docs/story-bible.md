# Story Bible

Bu doküman SpeakQuest'in hikâyesini, karakterlerini, görevlerini ve sonlarını anlatır. Oyunun
içindeki metinler İngilizcedir; açıklamalar Türkçedir.

Hikâyenin makine tarafından okunan hali `src/api/app/content/` altındaki JSON dosyalarıdır. Bu
doküman ile dosyalar her zaman aynı şeyi söylemelidir: bir görevi, kararı ya da sonu değiştiren
PR ikisini birlikte günceller. Dosyaların doğruluğunu `tests/test_content_files.py` kontrol eder.

## Dünya

Oyuncu, adı geçmeyen modern bir şehre yeni taşınmıştır. Hikâye tek bir mahallede, **Linden
Street**'te geçer: eski bir apartman, köşedeki kafe, şehir merkezindeki bir seyahat acentesi ve
nehir kenarındaki açık pazar.
Ton sıcak ve günlüktür; büyük maceralar değil, yeni bir şehirde yer edinmenin küçük anları
anlatılır. Oyuncunun İngilizcesi hikâyeyi ilerletir: anlaşılır konuşmak yeterlidir, kusursuz
dil bilgisi gerekmez.

## Mekânlar

| Slug | Ad | Açıklama |
|---|---|---|
| `apartment` | Linden House | Oyuncunun yeni evi. Eski, gıcırdayan merdivenli, herkesin birbirini tanıdığı bir apartman. |
| `cafe` | Corner Café | Apartmanın köşesindeki küçük kafe. Müdavimler Mia'yı ismiyle tanır. |
| `office` | Bright Path Travel | Şehir merkezinde bir seyahat acentesi. Yeni bir müşteri asistanı arıyorlar. |
| `market` | Riverside Market | Linden Street'e birkaç dakika yürüme mesafesinde, nehir kenarında açık pazar. Meyve, çiçek, eski kitap ve sokak yemeği; cumartesileri bütün mahalle buradadır. |

## Karakterler (NPC)

Her NPC'nin `knows` listesi, AI'ın o karakter adına bilebileceği şeylerdir. AI bunların dışında
oyun durumu uyduramaz (yeni mekân, görev, ödül).

`knows` NPC'nin **her** görevinde prompt'a girer. Bu yüzden belli bir görevde olan bir hikâye olayı
(kaybolan çanta, boşalan daire) NPC'nin `knows` listesine değil, o görevin `npc_knows` alanına
yazılır. Yoksa NPC olayı daha olmadan, önceki görevlerde anlatır (#64).

### Alex · komşu (`apartment`)

- **Kişilik:** Arkadaş canlısı, biraz utangaç. Evden çalışan bir grafik tasarımcı, bitkileri
  seviyor ve sürekli mobilya taşıyor.
- **Konuşma tarzı:** Rahat ve gündelik. Kısa cümleler, "oh", "you know"; basit kelimeler ve
  samimi takip soruları.
- **Bildikleri:** Dört yıldır Linden House'da yaşıyor.
- **Yalnızca The Flat Viewing'de bildikleri:** Üst kattaki daire (4B) boşaldı: kira ayda 650,
  faturalar ayrı, iki oda ve küçük bir balkon. Ev sahibi Mr. Patel, Alex'e güvenip daireyi
  göstermesine izin veriyor.

### Mia · kafe sahibi (`cafe`)

- **Kişilik:** Neşeli, sıcak ve konuşkan. Her müdavimin siparişini hatırlar, mahalle
  haberlerini paylaşmayı sever.
- **Konuşma tarzı:** Parlak ve davetkâr. Kafe kelimeleri kullanır (latte, oat milk, to take
  away, croissant) ve müşteriye siparişini nasıl sevdiğini sorar.
- **Bildikleri:** Menü (kahve, çay, sıcak çikolata, kruvasan, tost, günün çorbası).
- **Yalnızca The Missing Backpack'te bildikleri:** Mavi sırt çantası (içinde not defteri ve
  anahtarları) dün öğleden sonra tezgâhın arkasından kayboldu. Saat üç civarında çok benzer mavi
  çantası olan bir kurye geldi; bunu yalnızca oyuncu dünle ilgili doğru sorular sorarsa hatırlar.

### Olivia · işe alım müdürü (`office`)

- **Kişilik:** Profesyonel, sakin ve cesaret verici. İnsanları sınamak değil anlamak ister;
  açık iletişime kusursuz dil bilgisinden daha çok değer verir.
- **Konuşma tarzı:** Kibar ve net. Her seferinde tek soru sorar, çoğunlukla geçmiş deneyim
  hakkında; cevap için zaman tanır.
- **Bildikleri:** İş, ön büroda müşteri asistanlığı: soruları cevaplamak, seyahat
  rezervasyonu yapmak, ziyaretçilere yardım etmek. Daha önce herhangi bir işte insanlarla
  çalışmış, güler yüzlü birini arıyor.
- **Yalnızca First Day at Work'te bildikleri:** Oyuncu mülakattan sonra işi aldı ve bugün ilk günü.
  Ön büro dokuzda açılır, altıda kapanır; asistan her sabah e-postaları kontrol eder, günün
  biletlerini basar ve telefona bakar. Bu ayın en popüler turları: Lizbon'da hafta sonu (iki gece,
  kişi başı 320) ve dağlarda tren turu (beş gün, kişi başı 590).

### Rosa · çiçekçi ve pazar sorumlusu (`market`)

- **Kişilik:** Enerjik, sıcak ve çok doğrudan. Yirmi yıldır nehir kenarında çiçek satıyor,
  mahallenin her sokağını biliyor ve hep bir sonraki pazar etkinliğini planlıyor.
- **Konuşma tarzı:** Hızlı ve samimi. Bir yerin nerede olduğunu simgelerle ve yer edatlarıyla
  anlatır (next to, opposite, behind, between, at the end of) ve karşısındakinin anlayıp
  anlamadığını kontrol eder. Bu yüzden edatları (prepositions) çalıştıran görevlerin NPC'sidir.
- **Bildikleri:** Pazar her gün sekizden ikiye, cumartesileri altıya kadar açık. Pazar nehir ile
  otogar arasında; eski taş köprü pazarın sonunda, eczane köprünün karşısında.
- **Yalnızca A Walk to the Market'te bildikleri:** Hırdavat tezgâhı meyve tezgâhlarının arkasında,
  eski kitapçının yanında. Şehir merkezi otobüsü pazarın sonunda, taş köprünün önünden kalkar.
  Bu cumartesi River Festival var; Rosa düzenliyor ve çiçek tezgâhı için bir gönüllü daha arıyor.
- **Yalnızca The River Festival'da bildikleri:** Festival on birde açılır. Canlı müzik taş
  köprüde, yemek alanı otogarın yanında, çocuk köşesi kitapçının arkasında. Çiçek tezgâhının üç
  masası var: büyük ayçiçeği kovaları önde, küçük saksılar sol masada, fiyat tahtası tezgâhın
  üstünde. Pazarın sonunda boş bir masa var; Rosa onu mahalleden birilerine vermek istiyor.

## Bölümler ve görevler

| Bölüm | Görev | Mekân · NPC | Hedef beceri | Ön koşul |
|---|---|---|---|---|
| 1 · A New Address | Meet Your Neighbor | Apartment · Alex | present_simple | yok (başlangıç) |
| 2 · Settling In | Morning at the Café | Café · Mia | vocabulary_usage, prepositions | Meet Your Neighbor |
| 2 · Settling In | The Flat Viewing | Apartment · Alex | question_formation | Meet Your Neighbor + `helped_alex` |
| 2 · Settling In | The Job Interview | Office · Olivia | past_simple | Meet Your Neighbor |
| 3 · Finding My Feet | The Missing Backpack | Café · Mia | past_simple, question_formation | Morning at the Café + `watched_mia_bag` |
| 3 · Finding My Feet | First Day at Work | Office · Olivia | present_simple, vocabulary_usage | The Job Interview |
| 3 · Finding My Feet | A Walk to the Market | Market · Rosa | prepositions, question_formation | Meet Your Neighbor |
| 4 · The River Festival | The River Festival | Market · Rosa | prepositions, vocabulary_usage | A Walk to the Market + `joined_festival_team` |

Beş hata kategorisinin hepsi en az bir görevde hedeflenir; en az çalışılan iki kategori olan
Prepositions ve Vocabulary Usage, pazar görevleriyle ikişer görev daha kazanır. Spec'teki görev adlarıyla
karşılıkları: _A New Beginning_ → Meet Your Neighbor, _Coffee and Conversations_ → Morning at
the Café, _Finding a Place to Stay_ → The Flat Viewing.

### 1. Meet Your Neighbor

Oyuncu iki bavulla Linden House'a gelir; Alex merdivenlerde kutu taşımaktadır. Oyuncu kendini
tanıtır ve günlük hayatından bahseder (present simple). **Hedefler:** Alex'i selamla; adını ve
nereli olduğunu söyle; her gün ya da her hafta yaptığın bir şeyi anlat.

**Karar · `help_alex_move`:** Alex ağır bir saksı kutusuyla uğraşıyor.
- _Help Alex carry the boxes upstairs._ → `helped_alex` bayrağı, Alex güveni +15.
- _Say you are too tired after the journey._ → etkisi yok.

### 2. Morning at the Café

Şehirdeki ilk sabah. Oyuncu kahvaltı sipariş eder ve Mia ile mahalle hakkında sohbet eder
(kelime bilgisi, edatlar). **Hedefler:** Mia'yı selamla; bir şey sipariş et; siparişini nasıl
sevdiğini söyle; nerede yaşadığını ya da bir yerin nerede olduğunu anlat.

**Karar · `watch_mia_bag`:** Mutfak zamanlayıcısı çalar; Mia birkaç dakika çantasına göz kulak
olmanı ister.
- _Say yes and watch the backpack until Mia comes back._ → `watched_mia_bag`, Mia güveni +15.
- _Say sorry, you are in a hurry._ → etkisi yok.

### 3. The Flat Viewing

Yalnızca Alex'e yardım eden oyuncuya açılır: Alex teşekkür eder ve üst kattaki boş daireyi
gösterir. Oyuncu doğru soruları sorar (soru kurma). **Hedefler:** kirayı sor; odaları,
faturaları ya da komşuları sor; yeni bir evde neye ihtiyacın olduğunu anlat.

### 4. The Job Interview

Bright Path Travel'da müşteri asistanlığı mülakatı. Olivia oyuncunun geçmiş deneyimini sorar
(past simple). **Hedefler:** kendini tanıt; geçmişte yaptığın bir işi, projeyi ya da
sorumluluğu anlat; bu işi neden istediğini açıkla.

README'deki örnek bu görevden gelir: _"Last year I work in a restaurant."_ Past Simple hatası
olarak işaretlenir ama mesaj anlaşılır olduğu için görev devam eder.

### 5. The Missing Backpack

Yalnızca Mia'nın çantasına göz kulak olan oyuncuya açılır. Çanta dün kaybolmuştur; oyuncu dün
gördüklerini anlatır ve doğru sorularla ne olduğunu bulmaya yardım eder (past simple, soru
kurma). **Hedefler:** dün kafede ne yaptığını ve gördüğünü anlat; Mia'ya çantayı en son ne
zaman ve nerede gördüğünü sor; çantayı geri almak için ne yapabileceğini öner.

### 6. First Day at Work

Mülakattan sonra açılır: oyuncu işi almıştır. Olivia ön büroyu gösterir ve oyuncunun ilk
müşterilerine yardım etmesini izler (present simple, kelime bilgisi). **Hedefler:** sabah
rutinini ya da günlük düzenini anlat; müşteri asistanının her gün ne yaptığını açıkla; bir
müşterinin tur, fiyat ya da tarih sorusunu cevapla.

Mülakat ödülü Olivia'ya her zaman +10 güven verdiği için bu görevde ayrıca güven eşiği yoktur.
Eşik koyulsaydı Quest Journal'daki kilit gerekçesi güven puanını gösterirdi; güven oyuncuya
sayı olarak gösterilmez.

**Karar · `late_customer`:** Kapanışa beş dakika kala treni iptal olmuş yorgun bir yolcu gelir.
- _Stay a little longer and help the traveller book a new ticket._ → `helped_late_customer`,
  Olivia güveni +15.
- _Politely ask the traveller to come back tomorrow morning._ → etkisi yok.

### 7. A Walk to the Market

Yeni daire için birkaç şey lazımdır; oyuncu nehir kenarındaki pazara iner. Rosa her tezgâhı
bilir. Oyuncu yol sorar ve bir yerin nerede olduğunu anlatır (edatlar, soru kurma).
**Hedefler:** Rosa'ya bir şeyin nerede olduğunu sor; bir yerin ya da tezgâhın nerede olduğunu
next to, behind, opposite gibi kelimelerle söyle; pazardan bir şey al ve neden lazım olduğunu söyle.

Bölüm 3'tedir, çünkü yalnızca başlangıç görevini ister ve bölüm 2 görevleriyle aynı anda açılır.
Bölüm sıralamada eşitliği bozar: hedefi "everyday" olan yeni oyuncuya ilk önce yine Morning at
the Café önerilir.

**Karar · `festival_volunteer`:** Rosa cumartesi günkü River Festival'dan bahseder ve çiçek
tezgâhı için bir kişiye daha ihtiyacı vardır.
- _Say yes and promise to help at the flower stall on Saturday._ → `joined_festival_team`,
  Rosa güveni +15.
- _Say sorry, you already have plans this weekend._ → etkisi yok.

### 8. The River Festival

Yalnızca gönüllü olan oyuncuya açılır. Cumartesi sabahı, festival iki saat sonra açılacaktır.
Oyuncu Rosa'yla tezgâhı kurar ve ilk ziyaretçilere festivalde ne bulabileceklerini anlatır
(edatlar, kelime bilgisi). **Hedefler:** masaların, çiçeklerin ya da fiyat tahtasının nereye
konacağını söyle; bir ziyaretçiye tezgâhtaki çiçekleri anlat; bir ziyaretçiye müziğin, yemeğin ya
da çocuk köşesinin nerede olduğunu söyle.

**Karar · `invite_neighbours`:** Rosa pazarın sonundaki boş masayı gösterir: "Bunu isteyecek
birini tanıyor musun?" Oyuncunun aklına Alex'in bitkileri ve Mia'nın tarçınlı çörekleri gelir.
- _Call Alex and Mia and invite them to share the empty table._ → `invited_neighbours`,
  Rosa +10, Alex +5, Mia +5.
- _Say you are happy to focus on the flower stall today._ → etkisi yok.

## Kararlar ve dallanma

Beş karar var. Üçü bir görevin kilidini açar, ikisi yalnızca hangi sona gidileceğini değiştirir:

| Karar | Seçim | Açtığı içerik |
|---|---|---|
| `help_alex_move` | help | The Flat Viewing |
| `watch_mia_bag` | watch | The Missing Backpack |
| `festival_volunteer` | volunteer | The River Festival |
| `late_customer` | stay_and_help | A Place in the City ve Heart of the Neighbourhood sonları |
| `invite_neighbours` | invite | Heart of the Neighbourhood sonu |

Yardım etmeyen oyuncu o görevi hiç görmez ve kararlarına göre "A Place in the City" ya da
"New in Town" sonuna gider. Böylece kararların
sonucu oyuncunun hangi görevleri oynadığında ve hangi sonu gördüğünde hissedilir.

Karar, görev sürerken verilir. **Açık (verilmemiş) karar noktası olan görev tamamlanamaz**
(`POST /api/quests/{id}/complete` → `409`, "Make your choice before finishing this quest."). Diyalog
ekranı hedefler bitse de karar açıkken "Complete quest" yerine karar paneline yönlendirir. Böylece
oyuncu bir dalı yalnızca seçerek kaybeder, kararı atlayarak değil. Kararın açtığı görev, görev
tamamlanınca cevaptaki `unlocked_quests` alanında bildirilir.

Adaptive Quest Engine için iki karar da "yardım et" seçildiğinde bölüm 2 ve 3'te hem Past
Simple (The Job Interview, The Missing Backpack) hem Question Formation (The Flat Viewing, The
Missing Backpack) çalıştıran görevler açık olur. README'deki demo kuralı (iki farklı oyuncuya
iki farklı görev önerisi) bu durumda gösterilir.

## Sonlar

Sonlar `endings.json` dosyasındaki sırayla kontrol edilir; koşulları sağlanan ilk son oyuncunun
sonudur. Son, oyuncunun açabileceği bütün görevler tamamlandığında değerlendirilir.

| Son | Koşullar |
|---|---|
| **Heart of the Neighbourhood** | Sekiz görevin hepsi tamamlandı (The Flat Viewing, The Missing Backpack, First Day at Work ve The River Festival ile birlikte); beş "evet" bayrağının hepsi (`helped_alex`, `watched_mia_bag`, `helped_late_customer`, `joined_festival_team`, `invited_neighbours`); Alex, Mia, Olivia ve Rosa güveni ≥ 30 |
| **Home at Last** | The Flat Viewing ve The Missing Backpack tamamlandı; `helped_alex` ve `watched_mia_bag`; Alex güveni ≥ 30, Mia güveni ≥ 30 |
| **A Place in the City** | First Day at Work tamamlandı; `helped_late_customer`; Olivia güveni ≥ 30 |
| **New in Town** | Koşul yok: diğer bütün oyuncular bu sona ulaşır |

Sıra önemlidir: en zor son en başta durur. Heart of the Neighbourhood, Home at Last ve A Place in
the City'nin istediği her şeyi ister (`test_the_best_ending_needs_everything_the_others_need`);
böylece hem komşularına hem işe yardım eden ama festivalde komşularını çağırmayan oyuncu Home at
Last'a, yalnızca işte yardım eden oyuncu A Place in the City'ye gider.

Güven eşikleri ulaşılabilirdir:

| NPC | Kazanılabilecek güven (sohbet bonusu hariç) |
|---|---|
| Alex | 5 (Meet Your Neighbor) + 15 (yardım) + 10 (Flat Viewing) + 5 (festival daveti) = 35 |
| Mia | 5 (Morning at the Café) + 15 (çanta) + 15 (Missing Backpack) + 5 (festival daveti) = 40 |
| Olivia | 10 (Job Interview) + 15 (geç gelen yolcu) + 10 (First Day at Work) = 35 |
| Rosa | 5 (A Walk to the Market) + 15 (gönüllü) + 10 (festival daveti) + 10 (River Festival) = 40 |

- **Heart of the Neighbourhood:** Festivalin sonunda Alex, Mia, Rosa ve Olivia oyuncuyla eski taş
  köprüde oturup sudaki ışıkları izler. Oyuncu komşularına, yeni ekibine ve bütün pazara yardım
  etmiştir; sokakta artık adı Mia'nınki gibi anılır.
- **Home at Last:** Alex ve Mia, Linden House'un avlusunda küçük bir hoş geldin partisi verir.
  Oyuncu komşularına ihtiyaç duyduklarında yardım etmiştir ve şehir artık ev gibidir.
- **A Place in the City:** Bir ay sonra Olivia oyuncuya pencere kenarında kendi masasını verir;
  müşteriler onu ismiyle sorar. Oyuncu bütün komşularını tanımaz ama işi ona şehirde bir yer
  açmıştır.
- **New in Town:** Oyuncu şehirde yolunu bulmuştur ama burası hâlâ biraz yabancı gelir. Kapanış,
  bir dahaki sefere yardım isteyen bir komşuya "evet" demeyi önerir; oyunu tekrar oynamaya
  davet eder.

## Görev şablonu formatı

Her görev `src/api/app/content/quests/<slug>.json` dosyasıdır; dosya adı görevin slug'ıyla
aynıdır. Alanların doğrulaması `src/api/app/content/schema.py` içindeki `QuestTemplate`
modelindedir. Bilinmeyen alan adı hatadır.

| Alan | Anlamı |
|---|---|
| `slug` | Görevin kalıcı kimliği (`küçük_harf_ve_alt_çizgi`). Ön koşullar ve kayıtlar bunu kullanır. |
| `title` | Oyuncuya görünen ad. |
| `chapter` | Hikâyedeki bölüm (1'den başlar). |
| `location`, `npc` | Mekân ve NPC slug'ı. NPC o mekânda yaşamalıdır. |
| `target_skills` | Görevin çalıştırdığı hata kategorileri (`app/engines/categories.py`). En az bir tane. |
| `min_level`, `max_level` | Uygun İngilizce seviyesi aralığı (`A2`, `B1`). |
| `summary` | Sahnenin kısa anlatımı; oyuncuya ve AI'ya bağlam olarak verilir. Görevi açan kararları anlatabilir, çünkü görev açıldığında gösterilir. |
| `locked_summary` | Görev kilitliyken Quest Journal'da ve haritada `summary` yerine gösterilen kısa, tarafsız metin. Oyuncunun vermediği bir kararı varsaymaz. Ön koşulu olan her görevde zorunludur (#65). |
| `npc_knows` | NPC'nin yalnızca bu görevde bildikleri; `knows` listesine eklenerek prompt'a girer, API'den hiç dönmez. Bu görevde olan hikâye olayları buraya yazılır (#64). İsteğe bağlı. |
| `npc_opening` | NPC'nin konuşmayı açan ilk cümlesi. |
| `objectives` | `[{id, description}]`. Ölçülebilir iletişim hedefleri; görev bunlar karşılanınca tamamlanır, dil bilgisi hataları tamamlamayı engellemez. |
| `prerequisites` | `quests_completed` (tamamlanmış görevler), `flags` (kararlarla açılan bayraklar), `min_trust` (`{npc: 0–100}`). Hepsi sağlanmalıdır. Boşsa görev başlangıç görevidir; tam bir tane olabilir. |
| `rewards` | `xp` ve `trust` (`{npc: değişim}`). Görev tamamlanınca backend tarafından verilir. |
| `allowed_story_actions` | AI'ın bu görevde önerebileceği hikâye aksiyonları. Story Engine bu listede olmayanı reddeder. |
| `decision_points` | `[{id, prompt, options[{id, label, effects{flags, trust}}]}]`. Oyuncunun verdiği kararlar ve sonuçları. En az iki seçenek. |

### Hikâye aksiyonları

AI her cevapta bir `suggested_story_action` önerebilir; bu yalnızca bir öneridir. Ortak
aksiyonlar:

- `continue`: konuşma sürüyor, durum değişmiyor.
- `npc_pleased`: NPC memnun; Story Engine küçük, sınırlı bir güven artışı uygulayabilir.
- `npc_confused`: NPC oyuncuyu anlamadı; oyuncudan tekrar denemesi beklenir.

Göreve özel aksiyonlar (`order_taken`, `viewing_positive`, `interview_positive`,
`interview_concern`, `clue_found`, `directions_understood`, `customer_helped`, `stall_ready`,
`visitor_helped`) o görevin anlatımı içindir. İçerik dosyası yalnızca hangi
aksiyonların geçerli olduğunu söyler; etkilerini Story Engine (`engines/story.py`,
`apply_story_action`) belirler:

- Görevin `allowed_story_actions` listesinde olmayan aksiyon reddedilir, hiçbir şey değişmez.
- `npc_pleased`, `order_taken`, `viewing_positive`, `interview_positive`, `clue_found`,
  `directions_understood`, `customer_helped`, `stall_ready`, `visitor_helped`: görevin
  NPC'sinin güvenine en fazla +2 eklenir (100'ü geçmez). Bir görevin sohbetinden gelen toplam güven
  en fazla **+6**'dır (`ACTION_TRUST_CAP_PER_QUEST`); oyuncu ne kadar yazarsa yazsın bu aşılmaz.
  Sayaç `quest_progress.story_trust_gained` alanında tutulur. Hikâyeyi asıl ilerleten kararlar (+15)
  ve görev ödülleridir; bu tavandan etkilenmezler ve sohbet yalnızca küçük bir bonustur.
- `continue`, `npc_confused`, `interview_concern`: kabul edilir ama durumu değiştirmez. Dil
  öğrenen oyuncu anlaşılmadığı için hikâyede cezalandırılmaz.

### Örnek

```json
{
  "slug": "the_flat_viewing",
  "title": "The Flat Viewing",
  "chapter": 2,
  "location": "apartment",
  "npc": "alex",
  "target_skills": ["question_formation"],
  "min_level": "A2",
  "max_level": "B1",
  "summary": "Alex remembers your help with the boxes and tells you that the bigger flat upstairs is free.",
  "locked_summary": "Something is changing in Linden House, and Alex may have news for you.",
  "npc_knows": [
    "The bigger flat upstairs (4B) has just become empty. The rent is 650 a month, bills are extra, and it has two rooms and a small balcony."
  ],
  "npc_opening": "Thanks again for helping me the other day! The flat upstairs is empty now. Ask me anything.",
  "objectives": [
    { "id": "ask_price", "description": "Ask how much the rent is." },
    { "id": "ask_details", "description": "Ask about the rooms, the bills or the neighbours." },
    { "id": "describe_needs", "description": "Explain what you need in a new home." }
  ],
  "prerequisites": { "quests_completed": ["meet_your_neighbor"], "flags": ["helped_alex"] },
  "rewards": { "xp": 80, "trust": { "alex": 10 } },
  "allowed_story_actions": ["continue", "npc_pleased", "npc_confused", "viewing_positive"],
  "decision_points": []
}
```

### İçerik dosyalarına konan kurallar

`schema.py` ve `tests/test_content_files.py` şunları garanti eder:

- Bütün slug'lar benzersizdir; mekân, NPC ve görev referansları var olan kayıtlara işaret eder.
- Her görev en az bir geçerli hata kategorisini hedefler.
- Tam bir başlangıç görevi vardır ve görev ön koşullarında döngü yoktur.
- Koşullarda geçen her bayrağı bir karar açar; kararların açtığı her bayrak bir yerde kullanılır.
- Her güven eşiği, oyunda kazanılabilecek güvenle ulaşılabilirdir.
- Son ending koşulsuzdur, böylece her oyuncu bir sona ulaşır.
- Ön koşulu olan her görevin bir `locked_summary` metni vardır.
- Mia'nın çantası, Alex'in boş dairesi, Rosa'nın festivali ve Olivia'nın oyuncuyu işe alması
  yalnızca kendi görevlerinin `npc_knows` alanındadır.
- Her mekânın en az bir NPC'si ve bir görevi vardır; en iyi son, oyundaki her görevi gerektirir.
- Her mekânın haritada bir girişi, renk teması ve diyalog sahnesi, her NPC'nin bir portresi vardır
  (`tests/test_frontend_assets.py`).

### Yeni görev eklemek

1. `quests/` altına `<slug>.json` dosyası ekle; gerekiyorsa `npcs.json` ve `locations.json`'u
   güncelle. Yeni mekân için `pages/map.html`'e bir giriş, `css/main.css`'e `--sq-<slug>` ve
   `--sq-<slug>-tint` renkleri ile `.sq-<slug>` teması, `assets/scenes/<slug>.svg` sahnesi; yeni
   NPC için `assets/portraits/<slug>.svg` portresi ekle.
2. Bu dokümandaki tabloları ve görev anlatımını güncelle.
3. `pytest tests/test_content_files.py tests/test_frontend_assets.py` çalıştır.
