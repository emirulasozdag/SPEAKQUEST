# Veri Modeli

Bu doküman SpeakQuest MVP'sinin veritabanı sözleşmesidir. Bir tabloyu ekleyen veya değiştiren PR
bu dosyayı da günceller. Tablolar SQLAlchemy modelleri olarak `src/api/app/models/` altında yazılır
ve her değişiklik tek bir Alembic migration zincirine eklenir.

**Durum:** `users`, `player_profiles`, `locations`, `npcs`, `quest_templates` ve `quest_progress` uygulandı. Diğer tablolar önerilen tasarımdır; sahibi olan
iş paketi uygularken alanları netleştirir ve bu dosyayı günceller.

## Genel kurallar

- Her tablonun `id` adında tam sayı birincil anahtarı vardır.
- Oyuncuya ait her tablo `user_id` üzerinden `users.id`'ye bağlanır ve `ON DELETE CASCADE` kullanır.
  Böylece bir hesap silinince tüm oyun verisi de silinir.
- Endpoint'ler oyuncu verisini her zaman token'daki kullanıcının `user_id`'siyle süzer. Hiçbir endpoint
  istemciden gelen bir `user_id`'ye güvenmez.
- İçerik tabloları (`locations`, `npcs`, `quest_templates`) oyuncuya ait değildir. İçerik dosyalarından
  seed komutuyla yüklenir ve `slug` ile tanımlanır, böylece seed tekrar çalıştırılabilir.
- Sabit değer kümeleri (seviye, kategori, durum) `String` + `CheckConstraint` olarak saklanır. Bu hem
  PostgreSQL'de hem de testlerdeki SQLite'ta aynı şekilde çalışır. Geçerli değerler Python'da tek bir
  yerde tanımlanır ve kod oradan okur.
- Zaman damgaları `DateTime(timezone=True)` ve `server_default=now()` kullanır.
- XP, seviye, görev durumu, güven puanı ve hikâye durumu yalnızca backend kurallarıyla değişir.
  AI çıktısı bu tablolara doğrudan yazılmaz.

## İlişki şeması

```
users 1──1 player_profiles
  │
  ├──1 story_states
  ├──* npc_relationships  *──1 npcs
  ├──* story_decisions    *──1 quest_templates
  ├──* quest_progress     *──1 quest_templates
  │        └──* dialogue_messages
  │                 ├──* language_errors
  │                 └──* skill_observations

locations 1──* npcs 1──* quest_templates
```

## Tablolar

### `users` · uygulandı (#1)

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| email | varchar(255) | unique, index, küçük harfe çevrilmiş |
| password_hash | varchar(255) | bcrypt |
| created_at | timestamptz | |

### `player_profiles` · uygulandı (#3)

Oyuncunun karakteri. Her hesabın en fazla bir profili olur.

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| user_id | int FK → users | unique, cascade |
| character_name | varchar(30) | boş olamaz |
| avatar | smallint | 1–3 |
| english_level | varchar(2) | `A2`, `B1` (ileride A1–B2) |
| learning_goal | varchar(20) | `everyday`, `work`, `grammar` |
| xp | int | varsayılan 0, yalnızca backend değiştirir |
| level | int | varsayılan 1, yalnızca backend değiştirir |
| created_at, updated_at | timestamptz | |

Mevcut bölüm ve konum `story_states`'te, aktif görev `quest_progress`'te tutulur. Profil bunları
kopyalamaz, API cevabında bir araya getirilir.

### `locations` · uygulandı (#9)

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| slug | varchar(40) | unique (`cafe`, `apartment`, `office`) |
| name | varchar(80) | |
| description | text | |
| sort_order | int | haritadaki sıra |

Mekânın kilitli olup olmadığı saklanmaz. Story Engine bunu oyuncunun durumuna göre hesaplar.

### `npcs` · uygulandı (#9)

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| slug | varchar(40) | unique (`mia`, `alex`, `olivia`) |
| location_id | int FK → locations | |
| name | varchar(60) | |
| role | varchar(80) | |
| personality | text | prompt'a girer |
| speaking_style | text | prompt'a girer |
| knows | JSON | NPC'nin bildiği hikâye bilgileri; prompt'a girer |

### `quest_templates` · uygulandı (#9, içerik formatı #5)

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| slug | varchar(60) | unique |
| title | varchar(120) | |
| chapter | int | hikâye bölümü |
| location_id | int FK → locations | |
| npc_id | int FK → npcs | |
| target_skills | JSON | hata kategorisi listesi |
| min_level, max_level | varchar(2) | seviye aralığı |
| summary | text | sahnenin kısa anlatımı |
| npc_opening | text | NPC'nin ilk cümlesi |
| objectives | JSON | `[{id, description}]`, tamamlama bunlara bakar |
| prerequisites | JSON | görev, bayrak ve güven eşiği koşulları |
| rewards | JSON | XP ve güven değişimi |
| allowed_story_actions | JSON | AI'nın önerebileceği aksiyonların whitelist'i |
| decision_points | JSON | oyuncu kararları ve seçenekleri |

Şablonların içeriği `src/api/app/content/` altındaki JSON dosyalarıdır (`locations.json`,
`npcs.json`, `quests/<slug>.json`); format ve hikâye [story-bible.md](story-bible.md) içindedir.
İçerik dosyalarında mekân ve NPC slug ile gösterilir; seed komutu (#9) bunları id'lere çevirir ve
`app/content/schema.py` içindeki `load_content()` ile doğrulanmış içeriği okur. Tablo, bu
dosyaların sorgulanabilir kopyasıdır.

**Seed (`python -m app.content.seed`):** satırları `slug` ile eşler. Yeni slug eklenir, değişen satır
aynı `id` ile yerinde güncellenir (oyuncu ilerlemesi geçerli kalır), değişmeyen satıra dokunulmaz;
ikinci çalıştırma hiçbir şeyi değiştirmez. İçerik dosyasından silinen satır **silinmez**, çünkü
oyuncunun o görevde ilerlemesi olabilir; içerik kaldırmak bilinçli bir migration işidir. Docker
başlangıcında `alembic upgrade head`'den sonra çalışır.

**API:** `GET /api/locations` ve `GET /api/locations/{id}` mekânı, NPC'lerini (`id, slug, name, role`)
ve görevleri (`id, slug, title, chapter, summary, npc_slug, status`) döner. `personality`,
`speaking_style`, `knows`, `npc_opening`, `rewards` ve `prerequisites` oyuncuya hiç gönderilmez
(hikâye bilgisi içerebilirler, yalnızca sunucuda ve AI prompt'unda kullanılırlar). Görev `status`
değeri `services/quests.py` içindeki `quest_statuses()` ile hesaplanır; ön koşulsuz görev `available`,
diğerleri `locked` döner. Oyuncu ilerlemesi (`active`, `completed`) #7 ile, bayrak ve güven
koşulları #13 ile bu fonksiyona eklenir; endpoint değişmez.

Hikâye sonları (`endings.json`) tabloya yazılmaz; Story Engine onları doğrudan içerik
dosyasından okur. Oyuncunun ulaştığı son `story_states.ending` alanında slug olarak tutulur.

### `quest_progress` · uygulandı (#7)

Bir oyuncunun bir görevle ilişkisi. Ayrı bir `dialogue_sessions` tablosu yoktur: bir görev denemesi
aynı zamanda o görevin diyalog oturumudur.

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| user_id | int FK → users | cascade |
| quest_template_id | int FK → quest_templates | |
| status | varchar(12) | `active`, `completed` |
| objectives_met | JSON | backend'in doğruladığı hedef id'leri; her diyalog turunda `engines/objectives.py` ekler (#31) |
| xp_awarded | int | tamamlanınca verilen XP, tekrar ödül vermeyi engeller |
| started_at, completed_at | timestamptz | |

`(user_id, quest_template_id)` unique'tir. Kullanıcı başına yalnızca bir `active` görev olabilir:
bunu API'nin kontrolüne ek olarak veritabanı da zorlar (`status = 'active'` üzerinde kısmi unique
index), böylece aynı anda gelen iki istek de ikinci aktif görevi açamaz. `locked` ve `available`
saklanmaz, Story Engine'in `is_unlocked()` fonksiyonu her istekte hesaplar.

**API:** `GET /api/quests` oyuncunun görevlerini durumlarıyla (`locked`, `available`, `active`,
`completed`), `GET /api/quests/active` aktif görevi hedefleriyle (`met` alanını yalnızca backend
doğrular) döner; aktif görev yoksa `404`. `POST /api/quests/{id}/start` görevi başlatır (`201`):
bilinmeyen görev `404`; kilitli, zaten aktif, zaten tamamlanmış ya da başka görev aktifken `409`.
NPC'nin ilk cümlesi (`npc_opening`) bu cevaplarda yoktur; görev başlatılırken aynı transaction'da
şablondan okunup diyaloğun ilk mesajı olarak saklanır ve geçmişte görünür.

`POST /api/quests/{id}/complete` aktif görevi tamamlar ve XP'yi bir kez öder. Tek ölçüt görev
şablonundaki iletişim hedefleridir: her hedef id'si `objectives_met` içinde olmalıdır. Dil bilgisi
hataları tamamlamayı engellemez. Bilinmeyen görev `404`; başlatılmamış, zaten tamamlanmış, hedefleri
eksik ya da karakteri olmayan oyuncu için `409`. Cevap görevi, kazanılan XP'yi, yeni XP/seviyeyi ve
seviye atlanıp atlanmadığını döner. Aynı görev için gelen ikinci istek, `status = 'active'` koşullu
güncellemede satır bulamadığı için XP almaz. Şablondaki güven ödülü (`rewards.trust`) #13 ile uygulanır.

**XP ve seviye:** `engines/progression.py`. Seviye eşikleri `LEVEL_THRESHOLDS = (0, 50, 120, 220, 350,
500)`; MVP'nin 5 görevi toplam 410 XP verir ve oyuncuyu 5. seviyeye çıkarır. Görev tamamlanırken
`add_xp()` sonucu `player_profiles.xp/level` ve `quest_progress.xp_awarded` alanlarına yazılır.

### `dialogue_messages` · uygulandı (#11)

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| quest_progress_id | int FK → quest_progress | cascade, index |
| role | varchar(6) | `player`, `npc` |
| text | text | oyuncu mesajı en fazla 500 karakter |
| communication_success | bool, null | yalnızca oyuncu mesajlarında |
| created_at | timestamptz | |

Prompt'a yalnızca son N mesaj girer. Tüm geçmiş sadece oyuncunun kendisine gösterilir.

**Hedef işaretleme (#31):** AI cevabındaki `objectives_met`, bu mesajın karşıladığını düşündüğü
hedef id'lerinin listesidir (prompt görevin hedeflerini id ve açıklamayla verir). Bu yalnızca bir
iddiadır; `engines/objectives.py` şu kurallarla karar verir: (1) yalnızca görev şablonundaki id'ler
sayılır, bilinmeyen ve başka görevin id'leri yok sayılır ve loglanır; (2) yalnızca
`communication_success` true olan mesaj hedef karşılayabilir, dil bilgisi hataları engellemez; (3)
karşılanmış hedef geri alınmaz. AI hata verirse ya da cevap geçersizse hiçbir hedef işaretlenmez
(zaten hiçbir şey yazılmaz). `POST /api/dialogue/message` cevabı `objectives` (her hedef için `id`,
`description`, `met`) ve bu mesajla ilk kez karşılanan `newly_met` id'lerini döner.

**Düzeltmeler ve özet (#32):** `GET /api/dialogue/history/{quest_id}` her oyuncu mesajı için o mesajın
`language_errors` kayıtlarını `corrections` olarak da döner (NPC mesajlarında boş); böylece rozetler
sayfa yenilenince geri gelir. `GET /api/dialogue/summary/{quest_id}` görev konuşmasının özetini döner:
`messages_sent`, NPC'nin anladığı mesaj sayısı (`understood`), `mistakes`, en sık hata kategorisi
(`top_category`, hata yoksa `null`) ve en fazla 3 örnek düzeltme (`examples`: önce her kategoriden en
yenisi, en sık kategori önce). Özet yalnızca saklanan mesajlardan ve `language_errors`'tan hesaplanır;
başlatılmamış görev ve başka oyuncunun görevi için `404`.

**API:** `GET /api/dialogue/history/{quest_id}` oyuncunun o görevdeki mesajlarını `id` sırasıyla
(eskiden yeniye) döner. Görev yoksa ya da oyuncu onu hiç başlatmadıysa `404`; başka bir oyuncunun
konuşması da aynı şekilde `404` döner. Tablo `users`'a değil `quest_progress`'e bağlı olduğundan
hesap silinirken mesajlar `quest_progress` satırlarından önce açıkça silinir.

### `language_errors` · uygulandı (#12, Learning Engine üzerinden yazılır)

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| user_id | int FK → users | cascade, `(user_id, category)` index |
| message_id | int FK → dialogue_messages | cascade, index (#19) |
| category | varchar(30) | `present_simple`, `past_simple`, `question_formation`, `prepositions`, `vocabulary_usage` |
| original | text | |
| corrected | text | |
| explanation | text | |
| created_at | timestamptz | |

### `skill_observations` · uygulandı (#12; puanlar #16)

Spec'in istediği "öğrenme fırsatı" kaydı. Bir mesaj bir beceriyi kullanma fırsatı verdiyse, kategori
başına bir satır yazılır. Fırsat yoksa satır yoktur. Böylece geçmiş zaman içermeyen bir cümle
Past Simple puanını artırmaz.

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| user_id | int FK → users | cascade, `(user_id, category, created_at)` index |
| message_id | int FK → dialogue_messages | cascade, index (#19) |
| category | varchar(30) | `language_errors` ile aynı enum |
| result | varchar(9) | `correct`, `incorrect` |
| created_at | timestamptz | |

Beceri puanları ve tekrar eden hata kuralı (#16) bu kayıtlardan her istekte hesaplanır, ayrı bir
tabloda saklanmaz (aşağıdaki "Beceri puanları" bölümü).

Satırları yalnızca `engines/learning.record_message_analysis()` yazar. Bir mesajdaki her kategori
tek fırsattır: aynı kategoride hem hata hem doğru kullanım varsa sonuç `incorrect` olur.

**API:** `POST /api/dialogue/message` (`{"message": "..."}`) aktif görevdeki NPC'ye mesaj gönderir.
Akış `services/dialogue.send_message()` içindedir: mesaj kırpılır; boşsa ya da 500 karakteri
aşıyorsa `422`, karakter ya da aktif görev yoksa `409`. Dil modeline yalnızca NPC, görev, seviye,
kısa bir hikâye özeti ve son mesajlar gider. Cevap doğrulandıktan sonra tek transaction'da oyuncu
mesajı (`communication_success` ile) ve NPC cevabı saklanır, hatalar ve fırsatlar Learning Engine
üzerinden yazılır, önerilen hikâye aksiyonu Story Engine'e (`apply_suggested_action`) iletilir. Cevap
`npc_reply`, `communication_success`, `corrections` (`original → corrected` + Türkçe açıklama),
`feedback`, `story_action` (`suggested`, `accepted`) ve saklanan iki mesajı içerir. Dil modeli
yapılandırılmamışsa, hata verirse ya da geçersiz cevap dönerse yine `200` döner ama
`status: "ai_unavailable"` ve yedek NPC cümlesiyle; hiçbir şey saklanmaz, oyuncu mesajı tekrar
gönderebilir. Görev hedeflerinin işaretlenmesi #31'dedir.

### Beceri puanları · uygulandı (#16, tablo yok)

Planda bir `skill_scores` tablosu vardı. Uygulamada **tablo yoktur**: puanlar, tekrar eden hatalar
ve öğrenme hedefi her istekte `skill_observations` ve oyuncunun son mesajlarından
`engines/learning.py` ile hesaplanır. Nedenleri: puan zaten bu kayıtlardan yeniden üretilebilir bir
özetti; saklanan bir kopya her mesajda güncellenmek zorunda kalır ve kayıtlarla çelişebilirdi; formül
değişince eski satırları yeniden hesaplamak gerekirdi. Oyuncu başına kayıt sayısı küçük olduğu için
hesap ucuzdur. Gerekirse ileride önbellek olarak eklenebilir; API değişmez.

Formül, eşikler ve öğrenme hedefi seçimi [learning-engine.md](learning-engine.md) içindedir.

**API:** `GET /api/learning/skills` her kategori için `score` (0–100), `status` (`not_practised`,
`weak`, `developing`, `strong`), `opportunities`, `correct_count`, `error_count`, son 10 mesajdaki hata
sayısı (`recent_mistakes`), `repeated` ve `last_practiced_at` döner; ayrıca tekrar eden hata kategorileri
(`repeated_mistakes`). `GET /api/learning/recommendations` sıradaki öğrenme hedefini (`target`:
`category`, `reason`, oyuncuya gösterilecek `message`, `score`) ve beş kategorinin tam sırasını
(`ranking`) döner; seviye gerektiği için karakter yoksa `404`. `GET /api/learning/errors` oyuncunun
hatalarını en yeniden eskiye, görev adıyla döner (`category` süzgeci, `limit` 1–100 varsayılan 20,
`offset`; cevapta `total`). Hepsi yalnızca token'daki oyuncunun verisini okur.

### `story_states` · uygulandı (#13)

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| user_id | int FK → users | unique, cascade |
| chapter | int | |
| current_location_id | int FK → locations, null | son başlatılan görevin mekânı |
| flags | JSON | kararların açtığı bayrak slug'ları, ör. `["helped_alex"]` |
| ending | varchar(40), null | ulaşılan son |
| updated_at | timestamptz | |

Karakter oluşturulduğunda aynı transaction'da bir kez yaratılır (bölüm 1, bayrak yok); karakteri
düzenlemek sıfırlamaz. Migration, bu tablodan önce oluşturulmuş karakterler için de başlangıç
durumunu ekler. Görev başlatılınca `current_location_id` görevin mekânına geçer. Görev
tamamlanınca bölüm yeniden hesaplanır: hâlâ oynanabilecek (`available` ya da `active`) görevlerin
en küçük bölümü; hiçbiri kalmadıysa son tamamlanan bölüm.

### `npc_relationships` · uygulandı (#13)

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| user_id | int FK → users | cascade |
| npc_id | int FK → npcs | `(user_id, npc_id)` unique |
| trust | int | 0–100, Story Engine sınırlar; veritabanında da CHECK var |

Satırı olmayan NPC'nin güveni 0'dır. Güven yalnızca Story Engine üzerinden değişir
(`services/story.py`): görev tamamlanınca şablondaki `rewards.trust` aynı transaction'da eklenir
(tamamlama bir kez yapılabildiği için ödül de bir kez gelir), AI'nın önerdiği aksiyon
`apply_story_action()` ile süzülür, kararlar (#17) da aynı yolu kullanır.

**API:** `GET /api/story/state` oyuncunun bölümünü, mekânını (`{slug, name}` ya da `null`),
bayraklarını, sonunu ve her NPC için `{slug, name, trust}` listesini döner. Karakter yoksa `404`.
NPC'lerin prompt bilgileri (`personality`, `knows`) bu cevapta yoktur.

### `story_decisions` · uygulandı (#17)

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| user_id | int FK → users | cascade |
| quest_template_id | int FK → quest_templates | |
| decision_key | varchar(60) | şablondaki karar noktası |
| choice | varchar(60) | şablondaki seçeneklerden biri |
| created_at | timestamptz | |

`(user_id, quest_template_id, decision_key)` unique'tir. Aynı karar iki kez verilemez.

Karar yalnızca başlatılmış (aktif ya da tamamlanmış) bir görev için verilebilir
(`POST /api/story/decision`). Seçeneğin etkileri (bayraklar ve güven) Story Engine'in
`apply_decision()` fonksiyonuyla `story_states.flags` ve `npc_relationships` tablolarına yazılır.
`GET /api/story/decisions/{quest_id}` seçenekleri etkileri olmadan döner. Hikâye sonu
`choose_ending()` fonksiyonunda, `endings.json` sırasıyla seçilir.

## Modüller arası sınırlar

| Modül | Okur | Yazar | AI'ya bağlı mı? |
|---|---|---|---|
| AI servisi (`services/ai`) | Prompt için verilen bağlam | Hiçbir tablo | Evet. Sadece doğrulanmış `DialogueAnalysis` döner |
| Learning Engine (`engines/learning.py`) | `skill_observations`, `language_errors`, oyuncunun `dialogue_messages` | `language_errors`, `skill_observations` | Hayır |
| Story Engine (`engines/story.py`) | `story_states`, `npc_relationships`, `story_decisions`, `quest_progress`, `quest_templates` | `story_states`, `npc_relationships`, `story_decisions` | Hayır. AI'nın önerdiği aksiyonu şablonun whitelist'ine göre kabul ya da reddeder |
| Adaptive Quest Engine (`engines/quest.py`) | Learning ve Story Engine'in sonuçları, `quest_templates` | Hiçbir tablo | Hayır. Sadece öneri ve gerekçe döner |
| Progression (`engines/progression.py`) | `quest_progress`, `player_profiles` | `player_profiles.xp`, `level`, `quest_progress.xp_awarded` | Hayır |

Bir diyalog mesajında akış şöyledir: router mesajı alır → AI servisi analiz eder → Learning Engine
hata ve fırsatları kaydeder → Story Engine önerilen aksiyonu doğrular → görev hedefleri güncellenir.
Bu adımlar tek transaction içinde yapılır. AI hata verirse hiçbir tablo değişmez.

## Kullanıcı verisini silme

Tüm oyuncu tabloları `users`'a `ON DELETE CASCADE` ile bağlıdır. Bir hesabı silmek, ona ait tüm
oyun ve öğrenme verisini siler. Hesabı koruyup yalnızca ilerlemeyi sıfırlama #29'dadır.
