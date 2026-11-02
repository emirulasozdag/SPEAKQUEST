# AI hata analizinin değerlendirmesi

Bu klasör, yapay zekânın oyuncu mesajlarındaki İngilizce hataları ne kadar doğru bulduğunu ve
iletişim başarısını ne kadar doğru değerlendirdiğini **ölçmek** için kullanılır (#20). Sonuçlar
[results.md](results.md) içindedir.

| Dosya | Ne |
|---|---|
| [sentences.json](sentences.json) | Etiketli 48 A2–B1 cümle (ana set) |
| [holdout.json](holdout.json) | Prompt değişikliğinden sonra yazılmış 12 cümlelik kontrol seti |
| `runs/*.json` | Her ölçümün ham sonucu: her cümle için modelin cevabı ve tüm metrikler |
| [results.md](results.md) | Sonuçlar, önce/sonra karşılaştırması ve yorum |
| `src/api/scripts/evaluate_analysis.py` | Ölçüm betiği |

## Cümle seti

Her cümle, beş MVP görevinden birinde bir NPC cümlesine verilen cevaptır (`scene`, `npc_line`).
Böylece model, oyundaki gerçek bağlamla değerlendirilir.

| Tür (`kind`) | Sayı | Ne ölçer |
|---|---|---|
| `error` | 35 (5 kategori × 7) | Hata bulma ve doğru kategori. Hepsi **anlaşılır ama küçük hatalıdır**, yani yanlışlıkla "anlaşılmadı" sayılma oranı bu 35 cümlede ölçülür. |
| `correct` | 8 | Hatasız cümlede hata uydurulmaması |
| `unclear` | 5 | Anlamsız ya da konuyla ilgisiz cümlenin "anlaşılmadı" sayılması. Model her şeye "anlaşıldı" diyerek yanlışlıkla başarısızlık oranını ucuzca düşüremesin diye vardır. |

Seviyeler (`A2`, `B1`) ve beş görevin hepsi kapsanır.

## Kontrol seti (holdout)

Prompt'taki iyileştirmeler ana setteki hatalara bakılarak yazıldı. Ana sette "sonra" sonucunun iyi
çıkması bu yüzden tek başına yeterli kanıt değildir. [holdout.json](holdout.json), yeni kurallar
yazıldıktan **sonra** hazırlanmış 12 cümledir: aynı dört hata türünü (fiil ya da sıfattan sonra
edat, yanlış kelime seçimi, başka kişiler ya da hikâye hakkında doğru bir cümle, konuyla ilgisiz
cümle) yeni cümlelerle sınar. Bu set hem eski hem yeni prompt'la ölçülür; iyileşme burada da
görülüyorsa genelleşiyor demektir.

İki kural, ölçümün kendi kendini kandırmasını önler:

- Prompt'taki örnekler ana setin ve kontrol setinin hiçbir cümlesiyle içerik kelimesi çifti
  paylaşamaz (`test_the_prompt_never_contains_the_evaluation_sentences`).
- Kontrol seti, prompt örnekleriyle aynı kalıbı da sınamaz. Örneğin prompt *wait the bus* örneğini
  verdiği için kontrol setinde *waiting my friend* yerine *depends of the weather* kullanılır. Bu
  ikinci kural elle kontrol edilir; yeni bir cümle eklerken prompt'taki örneklere bakın.

## Etiketleme kuralları

Bir öğretmen gibi etiketleyin: oyuncuya gösterilmeye değer her gerçek dil hatası işaretlenir.

- **`errors`**: cümledeki her hatanın kategorisi. Aynı kategoride iki hata varsa kategori bir kez
  yazılır.
  - `present_simple`: alışkanlık ve genel doğrular için fiil biçimi (*I works*, *she go*,
    *he don't*).
  - `past_simple`: bitmiş geçmiş olaylar için fiil biçimi, düzensiz fiiller dahil
    (*yesterday I see*, *leaved*, *didn't slept*).
  - `question_formation`: soruda yardımcı fiil ve kelime sırası (*Where you live?*,
    *When I can start?*).
  - `prepositions`: eksik, fazla ya da yanlış edat; fiil ve sıfatlardan sonra da
    (*listen music*, *good in*, *on Monday*).
  - `vocabulary_usage`: dil bilgisi doğru ama kelime ya da kalıp yanlış (*make homework*,
    *win money*, *borrow me*, *funny/fun*).
- **Hata sayılmaz:** yazım, büyük harf ve noktalama (anlamı değiştirmiyorsa); daha doğal bir
  söyleyiş olması; içerik, isim ya da hikâyeye dair tercih.
- **`understood`**: arkadaş canlısı bir anadil konuşanı, oyuncunun bu sahnede ne demek istediğini
  anlar mı? Dil bilgisi hatası tek başına "anlaşılmadı" demek değildir. Anlamsız ya da soruyla ve
  sahneyle ilgisiz cümleler `false`dur.
- Her cümle tek bir hata türünü sınayacak şekilde yazılmıştır. Cümlede istenmeden ikinci bir hata
  varsa ya düzeltilir ya da etikete eklenir.
- `note`: etiketin kısa gerekçesi. İnceleyen kişi buna bakarak katılıp katılmadığını söyler.

**İnceleme durumu:** `sentences.json` içindeki `labelling` alanı, cümleleri kimin hazırladığını ve
kimin gözden geçirdiğini kaydeder. Issue ekipçe etiketlenmiş bir set ister: en az bir ekip üyesi
etiketlere bakıp `reviewed_by` alanına adını ekler. Değiştirilen her etiketten sonra ölçüm yeniden
çalıştırılır.

## Metrikler

Kategori metrikleri yalnızca `error` ve `correct` cümleler üzerinden hesaplanır. Her kategori için
bir cümle o kategoriyi ya içerir ya içermez, model de ya bulur ya bulmaz:

- **Recall:** o kategorideki hataların ne kadarını buldu.
- **Precision:** o kategori dediği hataların ne kadarı gerçekten o kategoriydi.
- **Doğruluk:** cümlelerin ne kadarında o kategori için doğru karar verdi (bulmak ya da bulmamak).

İletişim metrikleri:

- **Yanlışlıkla başarısız (küçük hatalı):** 35 `error` cümlesinden "anlaşılmadı" denenlerin oranı.
  Issue'nun asıl istediği sayı budur; düşük olmalıdır, çünkü oyuncu anlaşılır konuştuğu hâlde
  cezalandırılmış olur.
- **Yanlışlıkla başarısız (hatasız)**, **anlaşılmazı yakalama**, **hatasızda uydurulan hata**,
  **kategori kümesinin birebir doğru olması** ve **kullanılamayan cevap** oranları da raporlanır.

Model aynı cümleye her seferinde aynı cevabı vermez (`temperature` 0,4). Bu yüzden ölçüm
`--repeat 2` ile iki tur yapılır ve her tur ayrı örnek sayılır. Küçük gruplarda (8 hatasız, 5
anlaşılmaz cümle) tek bir cevap oranı 6–10 puan oynatır; sonuçlar bu gözle okunmalıdır.

## Kişiselleştirme ölçümü

`focus` komutu, NPC'nin oyuncuya hedef yapıyı kullandıracak bir soru sorup sormadığını ölçer
(`runs/focus-v1.json`: ilk odak metni, `runs/focus.json`: son hâli). Üç
sahnede, beş becerinin her biri için NPC cevabı iki kez alınır: **odak açık** ve **odak kapalı**
(kontrol). Cevabın bir soru içermesi ve o yapıya dair bir işaret taşıması (ör. Past Simple için
*did you*, *what happened*, *yesterday*) sayılır. Bu bir sezgisel kontroldür; bütün cevaplar
`runs/focus.json` içinde okunmak üzere saklanır.

## Nasıl çalıştırılır

Betik, uygulamanın kendi prompt'unu, doğrulamasını ve tek tekrar denemesini kullanır; yani
ölçülen şey oyunda olanın aynısıdır. Gerçek AI sağlayıcısını çağırır. API anahtarı yalnızca
Docker konteynerindedir, bu yüzden betik orada çalıştırılır ve dosyalar bilgisayarda kalır.
Ücretsiz Gemini katmanının dakikalık sınırı için istekler arasında 4,5 saniye beklenir. Geçici
sağlayıcı hatalarında (dakikalık kota, aşırı yük, zaman aşımı, ağ) betik her seferinde 15 saniye
bekleyerek aynı cümleyi toplam en çok 6 kez dener; yalnızca kalıcı hatalar (ör. yanlış anahtar) cevapsız olarak kaydedilir. Günlük
ücretsiz kota (yaklaşık birkaç yüz istek) dolarsa ölçümü ertesi güne bırakın. Bütün ölçümler
(ana set ve kontrol seti için önce ve sonra, 2 tur, artı odak ölçümü) yaklaşık 300 istektir.

```bash
docker compose exec -T api python scripts/evaluate_analysis.py analyse --label after --repeat 2 < docs/evaluation/sentences.json > docs/evaluation/runs/after.json
```

```bash
docker compose exec -T api python scripts/evaluate_analysis.py focus --label focus --repeat 2 > docs/evaluation/runs/focus.json
```

Kontrol seti için en az cümle sayısı düşürülür:

```bash
docker compose exec -T api python scripts/evaluate_analysis.py analyse --label holdout-after --repeat 2 --min-sentences 10 < docs/evaluation/holdout.json > docs/evaluation/runs/holdout-after.json
```

Başka bir prompt sürümü `--prompt-file` ile ölçülür (ör. kontrol setinde `main`'deki eski prompt).
Doğrulama, tekrar deneme ve puanlama aynı kalır, yalnızca prompt değişir. Ölçüm dosyasındaki
`prompt` parmak izi hangi sürümün kullanıldığını gösterir:

```bash
git show main:src/api/app/services/ai/prompts.py > src/api/old_prompts.py
```

```bash
docker compose exec -T api python scripts/evaluate_analysis.py analyse --label holdout-before --repeat 2 --min-sentences 10 --prompt-file old_prompts.py < docs/evaluation/holdout.json > docs/evaluation/runs/holdout-before.json
```

`old_prompts.py` geçici bir dosyadır, commit'lenmez; işiniz bitince silin.

İki ölçümü karşılaştırmak AI çağırmaz:

```bash
cd src/api && python scripts/evaluate_analysis.py compare ../../docs/evaluation/runs/before.json ../../docs/evaluation/runs/after.json
```

Veri setinin kuralları ve puanlama fonksiyonları `src/api/tests/test_evaluation.py` ile CI'da test
edilir; gerçek ölçüm CI'da çalışmaz.
