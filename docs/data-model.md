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
  └──* skill_scores

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
| objectives_met | JSON | backend'in doğruladığı hedef id'leri |
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

**API:** `GET /api/dialogue/history/{quest_id}` oyuncunun o görevdeki mesajlarını `id` sırasıyla
(eskiden yeniye) döner. Görev yoksa ya da oyuncu onu hiç başlatmadıysa `404`; başka bir oyuncunun
konuşması da aynı şekilde `404` döner. Tablo `users`'a değil `quest_progress`'e bağlı olduğundan
hesap silinirken mesajlar `quest_progress` satırlarından önce açıkça silinir.

### `language_errors` · #12 (Learning Engine üzerinden yazılır)

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| user_id | int FK → users | cascade, `(user_id, category)` index |
| message_id | int FK → dialogue_messages | cascade |
| category | varchar(30) | `present_simple`, `past_simple`, `question_formation`, `prepositions`, `vocabulary_usage` |
| original | text | |
| corrected | text | |
| explanation | text | |
| created_at | timestamptz | |

### `skill_observations` · #12 / #16

Spec'in istediği "öğrenme fırsatı" kaydı. Bir mesaj bir beceriyi kullanma fırsatı verdiyse, kategori
başına bir satır yazılır. Fırsat yoksa satır yoktur. Böylece geçmiş zaman içermeyen bir cümle
Past Simple puanını artırmaz.

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| user_id | int FK → users | cascade, `(user_id, category, created_at)` index |
| message_id | int FK → dialogue_messages | cascade |
| category | varchar(30) | `language_errors` ile aynı enum |
| result | varchar(9) | `correct`, `incorrect` |
| created_at | timestamptz | |

`skill_scores` bu kayıtlardan hesaplanır. "Son 10 fırsatta 3 hata" gibi tekrar eden hata kuralı da
bu tabloya bakar.

### `skill_scores` · #16

Learning Engine'in her beceri için hesapladığı özet. `skill_observations`'tan yeniden üretilebilir.

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| user_id | int FK → users | cascade |
| category | varchar(30) | `(user_id, category)` unique |
| score | int | 0–100, formül `docs/learning-engine.md` içinde |
| opportunities | int | |
| correct_count | int | |
| error_count | int | |
| last_practiced_at | timestamptz | |

### `story_states` · #13

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| user_id | int FK → users | unique, cascade |
| chapter | int | |
| current_location_id | int FK → locations, null | |
| flags | JSON | ör. `{"helped_neighbor": true}` |
| ending | varchar(40), null | ulaşılan son |
| updated_at | timestamptz | |

Karakter oluşturulduğunda bir kez yaratılır (#13).

### `npc_relationships` · #13

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| user_id | int FK → users | cascade |
| npc_id | int FK → npcs | `(user_id, npc_id)` unique |
| trust | int | 0–100, Story Engine sınırlar |

### `story_decisions` · #17

| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| user_id | int FK → users | cascade |
| quest_template_id | int FK → quest_templates | |
| decision_key | varchar(60) | şablondaki karar noktası |
| choice | varchar(60) | şablondaki seçeneklerden biri |
| created_at | timestamptz | |

`(user_id, quest_template_id, decision_key)` unique'tir. Aynı karar iki kez verilemez.

## Modüller arası sınırlar

| Modül | Okur | Yazar | AI'ya bağlı mı? |
|---|---|---|---|
| AI servisi (`services/ai`) | Prompt için verilen bağlam | Hiçbir tablo | Evet. Sadece doğrulanmış `DialogueAnalysis` döner |
| Learning Engine (`engines/learning.py`) | `skill_observations`, `language_errors` | `language_errors`, `skill_observations`, `skill_scores` | Hayır |
| Story Engine (`engines/story.py`) | `story_states`, `npc_relationships`, `story_decisions`, `quest_progress`, `quest_templates` | `story_states`, `npc_relationships`, `story_decisions` | Hayır. AI'nın önerdiği aksiyonu şablonun whitelist'ine göre kabul ya da reddeder |
| Adaptive Quest Engine (`engines/quest.py`) | Learning ve Story Engine'in sonuçları, `quest_templates` | Hiçbir tablo | Hayır. Sadece öneri ve gerekçe döner |
| Progression (`engines/progression.py`) | `quest_progress`, `player_profiles` | `player_profiles.xp`, `level`, `quest_progress.xp_awarded` | Hayır |

Bir diyalog mesajında akış şöyledir: router mesajı alır → AI servisi analiz eder → Learning Engine
hata ve fırsatları kaydeder → Story Engine önerilen aksiyonu doğrular → görev hedefleri güncellenir.
Bu adımlar tek transaction içinde yapılır. AI hata verirse hiçbir tablo değişmez.

## Kullanıcı verisini silme

Tüm oyuncu tabloları `users`'a `ON DELETE CASCADE` ile bağlıdır. Bir hesabı silmek, ona ait tüm
oyun ve öğrenme verisini siler. Hesabı koruyup yalnızca ilerlemeyi sıfırlama #29'dadır.
