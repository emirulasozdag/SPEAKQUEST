# Adaptive Quest Engine

Adaptive Quest Engine oyuncuya bir sonraki görevi önerir (#21). Kod
`src/api/app/engines/quest.py` içindedir. Saf Python'dur: veritabanını `services/quests.py` okur ve
motora değer olarak verir. Seçim rastgele değildir ve aynı girdi her zaman aynı sonucu verir.

## Adaylar

Aday görevler, Story Engine'in `is_unlocked()` fonksiyonuna göre ön koşulları sağlanmış ve oyuncunun
henüz başlamadığı görevlerdir. Bir görev aktifken öneri yapılmaz. Hiç aday kalmadığında hikâye
biter (aşağıda "Sonlar").

## Puanlama

Her aday için puan şu parçaların toplamıdır. Sabitler dosyanın başında tek yerde tanımlıdır.

| Parça | Puan | Ne zaman |
|---|---|---|
| `skill_match` | +40 | Görev, odak beceriyi çalıştırıyor |
| `other_weak_skills` | +10 / beceri | Görev, odak dışında zayıf (`weak`) ya da tekrar eden hatalı bir beceriyi de çalıştırıyor |
| `level_fit` | +10 / −30 | Görevin seviye aralığı oyuncunun seviyesini kapsıyor / kapsamıyor |
| `npc_trust` | 0–10 | Görevin NPC'sinin güveni / 10 |
| `recent_topics` | −5 / beceri | Görev, odak dışında son 3 mesajda çalışılmış bir beceriyi çalıştırıyor |

Eşitlikte önce **daha erken bölüm** gelir, böylece hikâye sırasıyla oynanır. Sonra içerik sırası
gelir.

### Odak beceri

- Yeterli veri varsa (toplam en az 5 beceri fırsatı, `MIN_OBSERVATIONS`), odak Learning Engine'in
  `choose_learning_target()` sonucudur: tekrar eden hata, en zayıf beceri, hiç çalışılmamış beceri
  ya da tekrar ([learning-engine.md](learning-engine.md)).
- Yeterli veri yoksa, karakter oluşturulurken seçilen öğrenme hedefi (`learning_goal`) yön verir:

| Öğrenme hedefi | Odak beceriler | Örnek öneri |
|---|---|---|
| `everyday` | Vocabulary Usage, Prepositions | Morning at the Café |
| `work` | Past Simple | The Job Interview |
| `grammar` | Question Formation, Present Simple | The Flat Viewing |

## Gerekçe

Öneri, oyuncuya gösterilen kısa bir cümleyle gelir. Örneğin:
_"It practises Past Simple, a mistake you keep making. Mia already trusts you."_ NPC'nin güveni
20 ve üstündeyse ikinci cümle eklenir.

## Demo kuralı

İki "yardım et" kararını veren ve The Flat Viewing, The Job Interview, The Missing Backpack açık olan
iki oyuncu:

- Past Simple'da zorlanan oyuncu **The Missing Backpack**'i alır. The Job Interview de Past Simple
  çalıştırır, ama Mia'nın güveni (20) Olivia'nınkinden (0) yüksektir.
- Question Formation'da zorlanan oyuncu **The Flat Viewing**'i alır. The Missing Backpack de
  Question Formation çalıştırır; puanlar eşitse erken bölüm (2) öne geçer.

Bu kural `tests/test_quest_engine.py` içinde hem motor düzeyinde hem API üzerinden test edilir.

## Sonlar

Oyuncunun başlatabileceği görev kalmadığında (açık ya da aktif görev yoksa) son görevin
tamamlanmasıyla hikâye kapanır. Story Engine'in `choose_ending()` fonksiyonu
[endings.json](../src/api/app/content/endings.json) sırasıyla ilk uyan sonu seçer ve sonuç
`story_states.ending` alanına yazılır.

- `POST /api/quests/{id}/complete` cevabındaki `ending` alanı sonu ve özetini taşır; hikâye
  sürerken `null`'dur.
- `GET /api/story/ending` ulaşılan sonu döner; hikâye sürerken `404` döner.
- Hikâye kapandıktan sonra yeni karar verilemez (`409`). `POST /api/player/reset` hikâyeyi yeniden
  açar.

## API

`GET /api/quests` her görevi `recommended` ve `recommendation_reason` alanlarıyla döner. Bir görev
aktifken ya da hikâye bittiğinde hiçbir görev önerilmez.
