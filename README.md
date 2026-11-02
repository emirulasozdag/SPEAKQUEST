# SpeakQuest

**Your Words Change The Story**

SpeakQuest, İngilizce öğrenmeyi interaktif bir macera oyununa dönüştüren, yapay zekâ destekli,
web tabanlı bir dil öğrenme platformudur. Oyuncu kurgusal bir şehre yeni taşınmış bir karakteri
canlandırır, yapay zekâ destekli karakterlerle (NPC) İngilizce konuşur, görevleri tamamlar ve
verdiği kararlarla hikâyenin gidişatını değiştirir.

Sistem oyuncunun dil hatalarını takip eder ve sonraki görevleri bu hatalara göre seçer.
Örneğin oyuncu geçmiş zamanda sürekli hata yapıyorsa, hikâyenin doğal akışı içinde geçmiş zaman
kullanmayı gerektiren yeni bir görev açılır.

> **Proje durumu:** Proje iskeleti hazır (FastAPI, PostgreSQL, Docker, UI taslağı). Bu README proje ilerledikçe güncellenecektir.

---

## İçindekiler

- [Projenin Amacı](#projenin-amacı)
- [Hedef Kitle](#hedef-kitle)
- [Nasıl Çalışır](#nasıl-çalışır)
- [Temel Sistemler](#temel-sistemler)
- [Kapsam (MVP)](#kapsam-mvp)
- [Teknolojiler](#teknolojiler)
- [Mimari](#mimari)
- [Klasör Yapısı](#klasör-yapısı)
- [Kurulum ve Çalıştırma](#kurulum-ve-çalıştırma)
- [Kullanım](#kullanım)
- [Sesli giriş ve NPC seslendirmesi](#sesli-giriş-ve-npc-seslendirmesi)
- [Verilerimi nasıl silerim?](#verilerimi-nasıl-silerim)
- [API Özeti](#api-özeti)
- [Test](#test)
- [Geliştirme Süreci](#geliştirme-süreci)
- [Yol Haritası](#yol-haritası)
- [Ekip](#ekip)

---

## Projenin Amacı

Geleneksel dil öğrenme uygulamaları çoğunlukla kelime ezberine, testlere ve birbirinden bağımsız
alıştırmalara dayanır. SpeakQuest şu problemlere çözüm getirmeyi hedefler:

- İngilizce konuşma pratiği yapacak bir ortam bulamamak.
- Öğrenme sürecinin monotonlaşması ve motivasyon kaybı.
- Sürekli tekrarlanan hataların takip edilmemesi.
- İçeriğin öğrencinin ihtiyaçlarına göre değişmemesi.
- Öğrenilen İngilizcenin gündelik hayat senaryolarına aktarılamaması.

Temel fikir: Kullanıcı yalnızca İngilizce öğrenmez; İngilizceyi kullanarak hikâyenin içinde
yaşar ve hikâyeyi değiştirir. SpeakQuest bir chatbot değil, öğrencinin eksiklerini analiz eden,
görevleri kişiselleştiren ve kararlarını hatırlayan bir öğrenme oyunudur.

## Hedef Kitle

- A1–B2 seviyesinde İngilizce öğrenenler (ilk sürüm **A2–B1** seviyesine odaklanır).
- Üniversite öğrencileri.
- İngilizce konuşma pratiği yapmak isteyenler.
- Oyunlaştırılmış öğrenmeyi tercih eden kullanıcılar.

## Nasıl Çalışır

1. Kullanıcı kayıt olur ve karakterini oluşturur (ad, avatar, İngilizce seviyesi, öğrenme hedefi).
2. Başlangıç görevini tamamlar ve 2D şehir haritasına erişir.
3. Haritadan bir mekâna girer (Café, Apartment, Office) ve oradaki NPC ile İngilizce yazışır.
4. Yapay zekâ NPC'nin cevabını üretir ve kullanıcının mesajını dil bilgisi açısından analiz eder.
5. Backend hataları kaydeder, beceri puanlarını ve hikâye durumunu günceller.
6. Görev tamamlandığında XP kazanılır ve sistem, oyuncunun zayıf olduğu konuya göre sonraki görevi seçer.

**Örnek:** _The Job Interview_ görevinde mülakatçı sorar:

> **NPC:** Can you tell me about your previous experience?
> **Oyuncu:** Last year I work in a restaurant.

Sistem hatayı **Past Simple** olarak işaretler ve _"Last year I worked in a restaurant."_ önerisini
gösterir. Ancak mesaj anlaşılır olduğu için görev başarısız sayılmaz: **iletişim başarısı ile dil
bilgisi doğruluğu ayrı değerlendirilir.** Daha sonra oyuncuya _The Missing Backpack_ görevi açılabilir:
bir arkadaşın çantası kaybolmuştur ve oyuncu dün olanları anlatarak yardım eder. Böylece geçmiş zaman
pratiği hikâyenin içine yerleşir.

## Temel Sistemler

### Learning Engine (Adaptif Öğrenme)

Kullanıcının mesajlarındaki hataları kategorilere ayırır, hangi hataların tekrarlandığını takip eder,
güçlü ve zayıf becerileri belirler ve zaman içindeki gelişimi ölçer. İlk sürümde desteklenen kategoriler:

| Kategori | Örnek hata | Düzeltme |
|---|---|---|
| Present Simple | She go to work every day. | She goes to work every day. |
| Past Simple | Yesterday I go to school. | Yesterday I went to school. |
| Question Formation | Where you live? | Where do you live? |
| Prepositions | I am good in English. | I am good at English. |
| Vocabulary Usage | Can you make me a favor? | Can you do me a favor? |

Yapay zekâ hataları **tespit eder**; hata sıklığı, önceliklendirme, gelişim takibi ve sonraki öğrenme
hedefinin seçimi Python ile yazılan Learning Engine tarafından yapılır. Puan formülü, tekrar eden hata kuralı ve
hedef seçimi [docs/learning-engine.md](docs/learning-engine.md) içinde açıklanır.

### Story Engine (Dinamik Hikâye)

Oyuncunun konumunu, aktif ve tamamlanmış görevlerini, NPC'lerle ilişkisini (güven puanı), verdiği
kararları ve hikâyenin hangi bölümde olduğunu yönetir. Yeni görevlerin açılma koşullarını kontrol
eder ve farklı hikâye sonlarını belirler. Örneğin bir karaktere yardım etmek güven puanını artırır ve
yeni bir görevin kilidini açar; yardım etmemek farklı bir olaya yol açar.

### Adaptive Quest Engine

Learning Engine ve Story Engine'i birleştirerek bir sonraki görevi seçer. Seçim rastgele değildir;
şu kriterlere bakılır: dil seviyesi, tekrar eden hata kategorileri, önceki görevler, hikâye durumu,
görev ön koşulları, NPC ilişkileri ve son çalışılan konular. İlk sürümde görevler önceden hazırlanmış
şablonlardan seçilir; yapay zekâ bu şablonların diyaloglarını kişiselleştirir.
Kurallar ve puanlama [docs/quest-engine.md](docs/quest-engine.md) içindedir.

### Yapay Zekânın Rolü ve Sınırları

Yapay zekâ NPC diyaloglarını üretir, kullanıcı mesajını anlar ve dil hatalarını analiz eder. Cevaplar
yapılandırılmış JSON olarak alınır ve backend tarafından doğrulanır:

```json
{
  "npc_reply": "That sounds great! What did you do there?",
  "communication_success": true,
  "detected_errors": [
    {
      "category": "past_simple",
      "original": "Last year I work in a restaurant.",
      "corrected": "Last year I worked in a restaurant.",
      "explanation": "Geçmişte tamamlanmış olaylarda fiilin geçmiş zaman biçimi kullanılır."
    }
  ],
  "correctly_used": ["prepositions"],
  "feedback": "Good answer! Remember to use the past form of the verb.",
  "suggested_story_action": "interview_positive",
  "objectives_met": ["describe_experience"]
}
```

Güvenlik ve tutarlılık için şu kurallar uygulanır:

- XP, seviye, görev tamamlama ve hikâye durumu **yalnızca backend** tarafından hesaplanır.
  Yapay zekâ oyun durumunu doğrudan değiştiremez.
- `suggested_story_action` yalnızca bir öneridir; nihai kararı Story Engine verir.
- `objectives_met` yalnızca bir iddiadır; hangi hedefin karşılandığına backend karar verir.
  Yalnızca anlaşılan mesajlar ve görevin kendi hedefleri sayılır.
- Doğrulanmamış AI cevabı veritabanına veya oyun durumuna uygulanmaz.
- API anahtarları frontend kodunda bulunmaz, backend ortam değişkenlerinde saklanır.
- AI servisi hata verdiğinde uygulama çökmez, kullanıcıya anlaşılır bir mesaj gösterilir.

NPC'ler oyuncunun en çok ihtiyaç duyduğu yapıyı doğal biçimde kullandıracak sorular sorar: Learning
Engine oyuncunun kendi hatalarından bir hedef beceri seçer (yeni oyuncuda sahnenin becerisi), prompt
NPC'ye bu yapıyı gerektiren sorular sordurur ([docs/learning-engine.md](docs/learning-engine.md)).

Hata analizinin doğruluğu etiketli 48 cümle ve 12 cümlelik bir kontrol setiyle ölçülmüştür: anlaşılır
ama küçük hatalı cümlelerin hiçbiri yanlışlıkla "anlaşılmadı" sayılmaz ve hatalı cümlelerin %99'unda
doğru kategori bulunur. Yöntem, önce/sonra karşılaştırması ve sınırlar:
[docs/evaluation/results.md](docs/evaluation/results.md).

## Kapsam (MVP)

İlk sürüm küçük ama uçtan uca çalışan bir oyun olarak hedeflenmiştir.

**MVP'de olacaklar**

- Kayıt, giriş ve oturum yönetimi
- Karakter oluşturma
- Ana dashboard (profil, seviye, XP, aktif görev, gelişim)
- 2D şehir haritası ve 3 mekân: **Café, Apartment, Office**
- 3 NPC ve 5 temel görev (hikâye, görevler ve sonlar: [docs/story-bible.md](docs/story-bible.md))
- Yapay zekâ destekli yazılı diyalog ve İngilizce hata analizi
- Learning Engine ve Story Engine
- Kullanıcıya göre görev seçimi
- XP ve seviye sistemi
- Öğrenme gelişimi (Learning Progress) ekranı
- Quest Journal (aktif, tamamlanan ve kilitli görevler)
- İki farklı hikâye sonu

**MVP dışında bırakılanlar** (sonraki sürümlere)

- 3D oyun dünyası ve serbest karakter hareketi
- Gerçek zamanlı çok oyunculu sistem
- Sesli konuşma ve mikrofon entegrasyonu
- Gelişmiş karakter animasyonları
- Mobil uygulama
- Kendi dil modelimizi eğitmek
- Ödeme sistemi

## Teknolojiler

| Katman | Teknoloji |
|---|---|
| Frontend | HTML5, CSS3, JavaScript, Bootstrap |
| Backend | Python, FastAPI, REST API |
| Veritabanı | PostgreSQL, SQLAlchemy ORM |
| Yapay Zekâ | Gemini API veya OpenAI API (karar verilecek) |
| Altyapı | Docker, Docker Compose, Alembic (migration), GitHub Actions (CI) |
| Araçlar | Git, GitHub, VS Code, Postman, pytest |

Frontend bilinçli olarak framework kullanmadan (React, Vue vb. olmadan) saf HTML, CSS, JavaScript ve
Bootstrap ile geliştirilir.

## Mimari

```mermaid
flowchart LR
    U[Kullanıcı<br/>Tarayıcı] -->|REST / JSON| API[FastAPI Backend]
    API --> AUTH[Auth & Player]
    API --> DLG[Dialogue Service]
    DLG -->|kontrollü bağlam| AI[(LLM API<br/>Gemini / OpenAI)]
    AI -->|yapılandırılmış JSON| VAL[Cevap Doğrulama]
    VAL --> LE[Learning Engine]
    VAL --> SE[Story Engine]
    LE --> QE[Adaptive Quest Engine]
    SE --> QE
    AUTH --> DB[(PostgreSQL)]
    LE --> DB
    SE --> DB
    QE --> DB
```

Bir mesajın yolculuğu:

1. Frontend, kullanıcının mesajını `POST /dialogue/message` ile gönderir.
2. Backend aktif görevi, NPC'yi ve hikâye durumunu veritabanından alır.
3. Yapay zekâya yalnızca gerekli bağlam gönderilir.
4. Gelen JSON doğrulanır; geçersizse güvenli bir varsayılan cevap kullanılır.
5. Learning Engine hataları kaydeder ve beceri puanlarını günceller.
6. Story Engine önerilen aksiyonun kurallara uygun olup olmadığını kontrol eder ve durumu günceller.
7. Frontend NPC cevabını ve varsa geri bildirimi gösterir.

## Klasör Yapısı

```
SPEAKQUEST/
├── .github/
│   ├── workflows/ci.yml            # her PR'da pytest çalıştıran GitHub Actions
│   ├── ISSUE_TEMPLATE/             # görev ve hata şablonları
│   └── pull_request_template.md
├── src/
│   ├── api/                        # FastAPI backend
│   │   ├── app/
│   │   │   ├── main.py             # uygulama girişi, router'lar ve frontend servisi
│   │   │   ├── core/               # ayarlar, veritabanı bağlantısı, yardımcılar
│   │   │   ├── models/             # SQLAlchemy modelleri
│   │   │   ├── schemas/            # Pydantic şemaları
│   │   │   ├── routers/            # REST endpointleri (/api/...)
│   │   │   ├── services/ai/        # LLM istemcisi ve prompt'lar
│   │   │   ├── engines/            # learning, story, quest motorları ve hata kategorileri
│   │   │   └── content/            # hikâye içeriği: mekânlar, NPC'ler, görevler, sonlar (JSON)
│   │   ├── alembic/                # veritabanı migration'ları
│   │   ├── tests/                  # pytest testleri
│   │   ├── Dockerfile
│   │   ├── requirements.txt        # çalışma bağımlılıkları
│   │   └── requirements-dev.txt    # test bağımlılıkları
│   └── frontend/                   # HTML, CSS, JS, Bootstrap
├── docs/                           # veri modeli ve story bible (hikâye, görevler, içerik formatı)
│       ├── index.html              # landing sayfası
│       ├── pages/                  # diğer sayfalar
│       ├── css/main.css            # tasarım değişkenleri ve ortak bileşenler
│       ├── js/                     # api istemcisi, durum yönetimi, ortak bileşenler
│       └── assets/
├── docker-compose.yml              # PostgreSQL + API geliştirme ortamı
├── .env.example                    # örnek ortam değişkenleri (gerçek anahtar içermez)
└── README.md
```

## Kurulum ve Çalıştırma

> **Proje durumu:** İskelet hazır; **kayıt olma** ve **giriş yapma** çalışıyor
> (`POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, kayıt ve giriş
> sayfaları). Giriş başarılı olunca 24 saat geçerli bir erişim token'ı (JWT) verilir. Oyuncu
> profili API'si de hazır (`GET` ve `PUT /api/player/profile`). Kayıt olan kullanıcı otomatik
> giriş yapar ve karakterini oluşturur; Profile sayfası karakteri gösterir ve günceller. Oyun
> sayfaları giriş gerektirir, süresi dolan oturum login sayfasına döner. Diğer sayfalar UI
> taslağıdır; henüz yazılmamış endpointler `501 Not Implemented` döner.
> Özellikler yol haritasındaki sırayla eklenecektir.

### Docker ile (önerilen)

**Gereksinimler:** Git ve [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
git clone https://github.com/emirulasozdag/SPEAKQUEST.git
cd SPEAKQUEST
docker compose up --build
```

| Adres | İçerik |
|---|---|
| http://localhost:8000 | Uygulama (frontend) |
| http://localhost:8000/api/docs | Otomatik API dokümantasyonu (Swagger) |
| http://localhost:8000/api/health | API ve veritabanı durumu |

`.env` dosyası olmadan da geliştirme varsayılanlarıyla çalışır. Değerleri değiştirmek için
`.env.example` dosyasını `.env` olarak kopyalayın. `.env` dosyası `.gitignore` içindedir ve asla
commitlenmez. Kod ve sayfa değişiklikleri container yeniden başlatılmadan yansır. Durdurmak için
`docker compose down` kullanılır.

**AI (NPC diyaloğu) için:** `.env` içine `AI_PROVIDER=gemini` ve kendi `AI_API_KEY` değerinizi yazın
(ücretsiz anahtar: <https://aistudio.google.com/apikey>). Anahtar boşsa oyun yine çalışır, NPC güvenli bir
yedek cevap verir ve oyunda hiçbir şey değişmez. Model adı `AI_MODEL` ile değiştirilebilir; seçim gerekçesi
[docs/decisions/0001-ai-provider.md](docs/decisions/0001-ai-provider.md) içindedir.

PostgreSQL bilgisayarınızda **5433** portundan erişilebilir (yerel bir PostgreSQL ile çakışmaması
için). Gerekirse `.env` içindeki `POSTGRES_PORT` ile değiştirilebilir.

**Gizli anahtar (`SECRET_KEY`):** giriş token'larını imzalar; bilen herkes herhangi bir oyuncu olarak
giriş yapabilir. Kendi bilgisayarınız dışında kullanmadan önce rastgele bir anahtar üretip `.env`'e yazın:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`ENVIRONMENT=development` (varsayılan) iken varsayılan ya da kısa bir anahtar yalnızca uyarı olarak
loglanır. Başka bir ortamda (ör. `ENVIRONMENT=production`) anahtar varsayılan değer, `.env.example`
içindeki örnek değer ya da 32 karakterden kısaysa uygulama başlamaz.

**Değiştirilebilen ayarlar:** `.env.example` içindeki her ayar Docker'da `api` konteynerine aktarılır
(`docker-compose.yml`): `ENVIRONMENT`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `AI_*` ve deneme
sınırları (`DIALOGUE_RATE_*`, `LOGIN_RATE_*`, `REGISTER_RATE_*`, `PASSWORD_CHECK_RATE_*`). `.env`'i değiştirdikten sonra
`docker compose up -d` konteyneri yeni değerlerle yeniden oluşturur.

### Docker olmadan (yalnızca backend geliştirme)

**Gereksinimler:** Python 3.12+ ve çalışan bir PostgreSQL (örneğin `docker compose up db`).

```bash
cd src/api
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

### Veritabanı migration'ları

Bekleyen migration'lar API container'ı her başladığında otomatik uygulanır (`alembic upgrade head`).
Yeni bir model `src/api/app/models/` altına eklenince migration şöyle oluşturulur:

```bash
docker compose exec api alembic revision --autogenerate -m "create player_profiles table"
docker compose restart api
```

Mevcut tablolar: `users` ve `player_profiles`. Şifreler yalnızca bcrypt hash'i olarak saklanır.
Tüm MVP tabloları, ilişkileri ve hangi iş paketine ait oldukları [docs/data-model.md](docs/data-model.md)
içinde anlatılır. Yeni bir tablo ekleyen PR bu dokümanı da günceller.

## Kullanım

1. **Landing Page** üzerinden _Start Adventure_ ile başlayın, kayıt olun veya giriş yapın.
2. **Character Creation** ekranında karakter adınızı, avatarınızı, İngilizce seviyenizi ve öğrenme
   hedefinizi seçin.
3. **Dashboard** üzerinden seviyenizi, XP'nizi, aktif görevinizi ve öğrenme gelişiminizi görün.
   _Continue Adventure_ ile kaldığınız yerden devam edin.
4. **City Map** üzerinden bir mekâna tıklayın.
5. **Dialogue** ekranında NPC ile İngilizce yazışın. Görev hedefi ve ilerleme göstergesi ekranda yer
   alır; hata yaptığınızda düzeltme ve kısa açıklama gösterilir.
6. **Quest Journal** ekranında aktif, tamamlanan ve kilitli görevleri ve ödüllerini inceleyin. Önerilen
   görev _"Why this quest was suggested for you"_ açıklamasıyla, kilitli görevler de neyi beklediğiyle
   birlikte gösterilir.
7. **Learning Progress** ekranında hata kategorilerinizi, sık yaptığınız hataları ve zaman içindeki
   gelişiminizi takip edin.
8. Oynanabilecek görev kalmadığında hikâye biter. **Ending** ekranı (`/pages/ending.html`) ulaştığınız
   sonu, sizi oraya götüren kararları, kazandığınız XP'yi ve en çok gelişen becerinizi gösterir.

## Sesli giriş ve NPC seslendirmesi

Diyalog ekranında oyuncu **Speak** düğmesiyle cevabını konuşarak girebilir. Tarayıcının Web Speech API'si
konuşmayı mesaj kutusuna yazar; mesaj otomatik gönderilmez, oyuncu düzenleyip kendisi gönderir. Tarayıcı
konuşma tanımayı desteklemiyorsa düğme görünmez; mikrofon izni reddedilirse ne yapılacağını söyleyen bir
mesaj çıkar. Ses kaydı SpeakQuest sunucusuna hiç gönderilmez ve saklanmaz (bazı tarayıcılar, ör. Chrome,
konuşmayı kendi çevrimiçi servisinde metne çevirir; gizlilik sayfasında yazar).

NPC cevapları `speechSynthesis` ile sesli okunabilir: her satırda **Listen** düğmesi vardır; yan paneldeki
**Voice** bölümünden "Read replies aloud" (varsayılan kapalı), İngilizce ses ve hız seçilir. Bu ayarlar
yalnızca tarayıcıda (`localStorage`) tutulur. Kod `src/frontend/js/components/voice.js` içindedir.

## Verilerimi nasıl silerim?

Oyunun hangi verileri sakladığı, mesajların hangi AI servisine gönderildiği ve silme yolları oyun içindeki
**Privacy** sayfasında ([src/frontend/pages/privacy.html](src/frontend/pages/privacy.html), footer'dan ve
kayıt sayfasından bağlantılı) sade İngilizceyle anlatılır. Kayıt formunda ve diyalog ekranında mesaj
kutusunun altında "gerçek kişisel bilgi yazma" uyarısı vardır.

**Profile** sayfasında _Delete account_ butonuna basın, mevcut şifrenizi girin ve onay kutusunu
işaretleyin. Hesabınız, karakteriniz ve size ait tüm oyun ve öğrenme verisi (görev ilerlemesi,
diyaloglar, dil hataları, beceri puanları, hikâye durumu ve kararlar) kalıcı olarak silinir; oturumunuz
kapanır ve landing page'e yönlendirilirsiniz. Bu işlem geri alınamaz.

**Şifre değiştirme:** `POST /api/auth/change-password` mevcut şifreyi doğrular ve yeni bir token döner;
şifre değişince o ana kadar açılmış tüm oturumlar kapanır (eski token'lar `401` alır). Şifre isteyen
işlemlerde (şifre değiştirme, hesap silme) hesap başına deneme sınırı vardır; sınır aşılınca `429`
döner (`PASSWORD_CHECK_RATE_LIMIT`, `.env.example`).

Hesabı silmeden yalnızca oyunu baştan başlatmak için Profile sayfasındaki _Reset game progress_
(`POST /api/player/reset`) kullanılır: görevler, diyaloglar, hatalar, beceri puanları, hikâye durumu ve
kararlar silinir, XP ve seviye sıfırlanır; hesap ve karakter kalır.

Aynı işlem API ile de yapılabilir: `DELETE /api/auth/me` gövdesinde `{"password": "..."}` ister.
Şifre doğruysa `204` döner, yanlışsa `403` döner ve hiçbir şey silinmez. Silinen hesabın token'ı
artık çalışmaz (`401`).

## API Özeti

| Alan | Endpoint |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `DELETE /auth/me`, `POST /auth/change-password` |
| Player | `GET /player/profile`, `PUT /player/profile`, `GET /player/progress`, `POST /player/reset` |
| Locations | `GET /locations`, `GET /locations/{id}` |
| Quests | `GET /quests`, `GET /quests/active`, `POST /quests/{id}/start`, `POST /quests/{id}/complete` |
| Dialogue | `POST /dialogue/message`, `GET /dialogue/history/{quest_id}` |
| Learning | `GET /learning/errors`, `GET /learning/skills`, `GET /learning/recommendations`, `GET /learning/timeline` |
| Story | `GET /story/state`, `GET /story/decisions/{quest_id}`, `POST /story/decision`, `GET /story/ending` |

**Oyuncu profili:** `PUT /api/player/profile` gövdesi `character_name` (1–30 karakter), `avatar`
(1–3), `english_level` (`A2`, `B1`) ve `learning_goal` (`everyday`, `work`, `grammar`) alır. İlk
çağrı karakteri oluşturur (`201`), sonraki çağrılar günceller (`200`). `xp` ve `level` istemciden
gönderilirse istek `422` ile reddedilir; bu değerleri yalnızca backend kuralları değiştirir.
Karakter henüz oluşturulmadıysa `GET /api/player/profile` `404` döner.

**İlerleme özeti:** `GET /api/player/progress` seviye, XP, seviye içi ilerleme, tamamlanan ve toplam
görev sayısı, en zayıf beceri (`weakest_skill`: Learning Engine puanı en düşük, pratik yapılmış beceri;
henüz pratik yoksa `null`) ve son aktivite zamanını (`last_activity_at`) tek cevapta döner. Cevap XP çubuğu için `xp_into_level` (bu seviyede kazanılan XP) ve
`xp_needed_for_next` (sonraki seviye için gereken XP; en yüksek seviyede `null`) alanlarını da içerir.

Tüm endpointler kimlik doğrulama, yetkilendirme ve girdi doğrulaması içerir. Her kullanıcı yalnızca
kendi verisine erişebilir. Görev tamamlama gibi kritik işlemler istemciden gelen değerlere güvenilerek
değil, backend kurallarıyla doğrulanarak yapılır.

**Hata formatı:** her hata cevabı aynı şekildedir: `{"detail": "...", "request_id": "..."}`. Doğrulama
hatalarında (`422`) `detail`, gönderilen değerleri tekrar etmeyen bir alan listesidir. Beklenmeyen bir
hata iç ayrıntı göstermeden `500` ve genel bir cümleyle döner; ayrıntı yalnızca loga yazılır.

**İstek kimliği ve loglama:** her `/api` cevabında `X-Request-ID` başlığı vardır (çağıran geçerli bir
kimlik gönderirse o kullanılır). Backend logları `key=value` satırlarıdır ve her satır o isteğin
kimliğini taşır: istek başına bir satır (`endpoint` rota şablonu olarak, `status`, `ms`) ve diyalogda
AI adımının süresi (`ai analysis ... ms`). Loga istek/cevap gövdesi, sorgu parametreleri, e-posta,
şifre, token, API anahtarı veya oyuncu mesajı yazılmaz. Bir hata bildirildiğinde `request_id` ile
`docker compose logs api | grep <request_id>` o isteğin bütün satırlarını bulur.

**Diyalog hız sınırı:** bir oyuncu dakikada en fazla 10 mesaj gönderebilir
(backend ayarları `dialogue_rate_limit` ve `dialogue_rate_window_seconds`, `app/core/config.py`); sonraki mesaj `429` ve `Retry-After`
başlığıyla reddedilir ve AI çağrılmaz. Bu, paylaşılan ücretsiz AI kotasını tek bir oyuncunun
tüketmesini önler.

## Güvenlik başlıkları

Her cevapta `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` ve
`Referrer-Policy: strict-origin-when-cross-origin` bulunur. Sayfalar bir Content Security Policy ile
sunulur: betikler yalnızca bu sunucudan ve sürümü sabit Bootstrap CDN'inden yüklenir, satır içi betik ve
stil niteliği kullanılmaz, sayfa başka bir sitede çerçeve içinde açılamaz. Politika
`src/api/app/core/security_headers.py` içindedir; yeni bir dış kaynak eklenirse orada da izin verilmelidir.
`/api/docs` (Swagger) kendi satır içi betiğini kullandığı için CSP dışında tutulur.

## Test

Backend testleri `pytest` ile yazılır. Her Pull Request'te GitHub Actions üzerinde otomatik çalışır.
Tarayıcı olmadan çalışabilen ön yüz modüllerinin (ör. ses bileşeni) birim testleri Node'un kendi test
aracıyla yazılır ve CI'da `frontend-tests` işinde çalışır; yerelde Node 20+ ile:
`node --test "src/frontend/tests/*.test.mjs"`.
Yerelde çalıştırmak için:

```bash
docker compose exec api pip install -r requirements-dev.txt
docker compose exec api python -m pytest
```

ya da Docker olmadan `src/api` klasöründe `pytest`.

Testler varsayılan olarak bellekte SQLite ile çalışır. Aynı testleri PostgreSQL'de çalıştırmak için
yalnızca testlere ayrılmış boş bir veritabanı verin (her testte tablolar silinip yeniden kurulur):

```bash
TEST_DATABASE_URL=postgresql+psycopg://speakquest:speakquest@localhost:5433/speakquest_test pytest
```

CI'da iki iş vardır: `api-tests` testleri SQLite'ta çalıştırır. `postgres` işi ise gerçek bir
PostgreSQL'de tek bir migration head olduğunu kontrol eder, boş veritabanında `alembic upgrade head`,
`alembic check` ve `alembic downgrade base` çalıştırır ve testleri PostgreSQL'de koşar.
`tests/test_access_control.py` her korumalı endpoint'in token istediğini ve bir oyuncunun başka bir
oyuncunun verisini okuyup değiştiremediğini doğrular.

Testlerde öncelik verilen alanlar:

- Kayıt, giriş ve yetkilendirme
- Görev başlatma ve tamamlama kuralları
- XP ve seviye hesaplaması
- Learning Engine'in hata sayımı ve öğrenme hedefi seçimi
- Story Engine'in karar ve görev açma kuralları
- Hatalı veya eksik AI JSON cevaplarının güvenli şekilde ele alınması

**Demo senaryosu:** İki kullanıcı aynı başlangıç görevini oynar. Birincisi Past Simple'da, ikincisi
Question Formation'da zorlanır. Sistem bu farkı kaydeder ve iki kullanıcıya farklı sonraki görevler
önerir. Kullanıcıların farklı kararları da NPC ilişkilerini ve hikâye sonunu değiştirir. Adım adım
yol, yazılacak mesajlar ve gerçek AI ile oynanışın sonuçları [docs/demo.md](docs/demo.md) içindedir.

## Geliştirme Süreci

Proje GitHub Flow ile geliştirilir:

- `main` dalı her zaman çalışır durumdadır; doğrudan `main`'e commit yapılmaz.
- Her görev bir GitHub Issue olarak açılır ve kısa ömürlü bir dalda (`feature/...`, `fix/...`) yapılır.
- Değişiklikler Pull Request ile, en az bir ekip üyesinin incelemesinden sonra `main`'e birleştirilir.
- Commitler küçük ve tek amaçlıdır; mesajlar [Conventional Commits](https://www.conventionalcommits.org/)
  biçimini izler (ör. `feat(api): add quest start endpoint`).
- API anahtarları ve `.env` dosyaları asla commitlenmez.
- Sürümler semantic versioning ile etiketlenir (`v0.1.0`, `v1.0.0`) ve GitHub Releases üzerinden yayınlanır.

## Yol Haritası

- [x] **Aşama 1 – Altyapı:** klasör yapısı, FastAPI projesi, PostgreSQL bağlantısı, ortam değişkenleri,
  Docker, CI ve tüm sayfaların UI taslağı
- [ ] **Aşama 2 – Veritabanı ve kullanıcı sistemi:** SQLAlchemy modelleri, kayıt/giriş, karakter profili
- [ ] **Aşama 3 – Frontend:** ortak tasarım sistemi, temel sayfalar, responsive tasarım, harita ve görev ekranları
- [ ] **Aşama 4 – Temel oyun sistemi:** mekânlar, NPC'ler, görev kuralları, XP, hikâye durumu
- [ ] **Aşama 5 – AI entegrasyonu:** AI servis katmanı, NPC diyalogları, hata analizi, JSON doğrulama
- [ ] **Aşama 6 – Learning Engine:** hata kategorileri, beceri puanları, gelişim verileri
- [ ] **Aşama 7 – Adaptive Story Engine:** kararlar, NPC ilişkileri, kişiye göre görev seçimi, farklı sonlar
- [ ] **Aşama 8 – Test ve tamamlama:** unit ve API testleri, demo senaryoları, dokümantasyon

**Sonraki sürümler için fikirler:** sesli konuşma modu, yeni şehirler ve karakterler, premium hikâye
paketleri, gelişmiş öğrenme analizi, eğitim kurumlarına özel kullanım.

## Ekip

| Ad Soyad | GitHub | Sorumluluk |
|---|---|---|
| _eklenecek_ | _eklenecek_ | _eklenecek_ |

---

Bu proje **SENG461 – Web Programming with Python and Git** dersi kapsamında geliştirilmektedir.
