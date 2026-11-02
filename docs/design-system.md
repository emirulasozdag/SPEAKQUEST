# Tasarım Sistemi

SpeakQuest bir yönetim paneli gibi değil, illüstrasyonlu bir macera oyunu gibi görünmelidir. Bu doküman
ortak görsel dili anlatır. Token'lar `src/frontend/css/main.css` içindeki `:root` bloğundadır; bileşenler
ham renk ve ölçü yerine bu token'ları kullanır. Yeni bir renk veya ölçü gerekiyorsa önce token eklenir.

## Token'lar

| Grup | Token'lar | Not |
|---|---|---|
| Metin ve yüzey | `--sq-ink`, `--sq-ink-soft`, `--sq-muted`, `--sq-paper`, `--sq-surface`, `--sq-line` | Ana metin `--sq-ink`, ikincil metin `--sq-ink-soft` |
| Koyu zemin | `--sq-on-dark`, `--sq-on-dark-soft` | Header ve hero üzerindeki metin |
| Mekân renkleri | `--sq-cafe`, `--sq-apartment`, `--sq-office` ve her biri için `-tint` | Renk çizgi, nokta, buton içindir; `-tint` arka plandır |
| Geri bildirim | `--sq-error`, `--sq-fix`, `--sq-ok` ve koyu zemin sürümleri (`-on-dark`) | Yanlış kelime üstü çizili kırmızı, doğrusu kalın yeşil |
| Yalnızca şekil | `--sq-locked`, `--sq-park` | Kontrastı metin için yeterli değildir, metinde kullanılmaz |
| Tipografi | `--sq-font-display` (Bricolage Grotesque), `--sq-font-body` (Atkinson Hyperlegible), `--sq-text-sm/base/lg` | Gövde fontu okunabilirlik için seçildi |
| Boşluk | `--sq-space-1` … `--sq-space-6` (0.25rem → 3rem) | |
| Köşe | `--sq-radius-sm/md/lg/pill` | Paneller `md`, konuşma balonları `lg` |
| Gölge | `--sq-shadow-sm`, `--sq-shadow-md` | Paneller `sm`, sahnedeki isim kartı `md` |
| Hareket | `--sq-transition` | `prefers-reduced-motion` açıkken tüm geçişler kapanır |

Bootstrap değişkenleri (`--bs-primary`, `--bs-body-color` …) aynı token'lara bağlanır, böylece Bootstrap
bileşenleri de aynı paleti kullanır.

## Mekân temaları

Bir öğeye `sq-cafe`, `sq-apartment` veya `sq-office` sınıfı verilince `--sq-line-color` ve `--sq-tint`
o mekâna göre ayarlanır. Paneldeki istasyon noktası, portre çerçevesi, sahne arka planı ve haritadaki etiket
çerçevesi bu iki değişkeni okur.

| Mekân | İçerikteki adı | Renk | NPC |
|---|---|---|---|
| `apartment` | Linden House | yeşil | Alex |
| `cafe` | Corner Café | amber | Mia |
| `office` | Bright Path Travel | mavi | Olivia |

## İllüstrasyonlar

Tüm görseller `src/frontend/assets/` altındaki elle yazılmış SVG'lerdir; telifli oyun görseli kullanılmaz.

- `logo.svg`: konuşma balonu içinde yıldız.
- `portraits/{mia,alex,olivia}.svg` ve `avatars/avatar-{1,2,3}.svg`: aynı çizim dili. Daire içinde düz
  şekiller, kontur yok, mekân `-tint` rengiyle arka plan.
- `scenes/{cafe,apartment,office}.svg`: diyalog ekranı ve landing kartları için 800×240 sahne arka planları.
- Şehir haritası `pages/map.html` içinde satır içi SVG'dir, böylece CSS ve JS mekânlara erişebilir.

`<img>` ile yüklenen SVG'ler CSS değişkenlerini okuyamaz. Bu yüzden renkleri dosyaya yazılıdır ve
token'larla aynı değerleri kullanır. Bir token değişirse bu dosyalar da güncellenir.

## Bileşenler

- **Şehir haritası:** Her mekân bir `<a class="sq-place sq-<slug>" data-location="<slug>">` öğesidir: bir
  bina (`.sq-building`) ve bir etiket (`.sq-place-label`). Etiketin ikinci satırı (`data-place-status`)
  durumu metinle de söyler. Durum yalnızca renkle anlatılmaz.
  - Açık: varsayılan görünüm, üzerine gelince bina hafifçe yükselir.
  - Kilitli: `is-locked`. Bina gri ve soluk, etiket çerçevesi kesikli, durum metni "Locked".
  - Aktif görev: `is-active`. Etiket mekân rengiyle dolu ve çerçevesi kalın.

  Sınıfları ve durum metnini `js/pages/map.js` (`drawMap()`) API'den gelen görev durumlarına göre koyar.
- **Diyalog sahnesi:** `.sq-scene` (mekân arka planı) ve `.sq-scene-npc` (portre, ad, rol). İsim kartı düz
  beyaz zemin üzerindedir, böylece metnin kontrastı illüstrasyona bağlı kalmaz.
- **Konuşma balonları:** `.sq-bubble-npc` (soldaki küçük portre `.sq-bubble-row` ile) ve
  `.sq-bubble-player`. Düzeltmeler `.sq-wrong` / `.sq-right` ile gösterilir.
- **Dil geri bildirimi:** `.sq-turn-feedback` içindeki `.sq-correction-badge` butonu düzeltmeleri açıp
  kapatır. Varsayılan olarak kapalıdır; `aria-expanded` ve `aria-controls` ile durumunu duyurur.
- **Avatar ve portre:** `.sq-avatar`, `.sq-portrait`, küçük sürümü `.sq-portrait-sm`.

## Erişilebilirlik

- Metin renk çiftleri WCAG AA'yı (normal metin için 4.5:1) karşılar. En düşük metin çifti `--sq-error`
  beyaz üzerinde 5.1:1'dir. Odak halkası (`--sq-cafe`) metin dışı öğeler için gereken 3:1'i karşılar.
  Bootstrap'ın buton ve form alanlarındaki kendi mavi odak gölgesi kapatılır; her öğede aynı halka görünür.
- Bootstrap linkleri ve `.text-secondary` rengi `-rgb` değişkenlerinden okur (`--bs-link-color-rgb`,
  `--bs-secondary-rgb`). Bunlar `:root` içinde token renklerine bağlıdır; yalnızca `--bs-link-color`
  değiştirmek yetmez.
- Formlarda hata metni alanın altındadır (`aria-describedby`, `aria-invalid`) ve gönderimde odak ilk
  hatalı alana gider, böylece ekran okuyucu mesajı okur.
- Dekoratif görseller `alt=""` taşır. Anlam taşıyan bilgi (NPC adı, durum) her zaman metin olarak da vardır.
- `prefers-reduced-motion: reduce` açıkken geçişler ve haritadaki yükselme efekti kapanır.
