# Backlog günlüğü

## 2026-11-14 — deneme sırası ve yanlış süresi

- Yanlış soru denemeye bağlanabiliyor; soru no, gerçek çözüm sırası ve o soruda harcanan saniye kalıcı saklanıyor. Eski JSON kayıtları boş varsayılanlarla okunuyor.
- Çalışma Planı, mevcut denemelere bağlı kaydedilmiş yanlışları çözüm sırasının erken/orta/geç üçte birlik bölümlerinde sayıp sürelerin medyanını gösteriyor. Doğru/boş sonuçlar soru kaydı olmadığı için doğruluk yüzdesi üretilmiyor.
- 65 backend testi, 4 frontend testi, üretim build'i ve browser smoke geçti. Smoke veriyi yenileme sonrası okudu ve deneme silinince yanlış kaydının korunduğunu, sıra özetinin ilişkisiz kaldığını doğruladı.
- Sıra özeti benchmarkı (yalnızca hesaplama): 1.000 kayıt 0.0146 sn; 10.000 kayıt 0.1379 sn; AI dahil değil.
- Var olan 100 soruluk akış benchmarkı da yeni alanlarla geçti: upload 0.6005 sn, liste 0.0008 sn, içgörü 0.0015 sn, text capture 1.1541 sn; AI dahil değil.
- GitHub Actions run #61 (`3d84fcc`): frontend ve backend işleri, yeni backup/order benchmark adımları dahil başarılı.
- Rapor: `reports/2026-11-14-question-order-insights.md`.

- 2026-11-14: Sonraki dikey dilim olarak denemeye bağlı yanlış soru sırası ve soru başı süre takibi planlandı. Sıra özeti yalnızca açıkça kaydedilen yanlışları sayacak; doğruluk yüzdesi hesaplamayacak. Kabul ölçütleri `reports/2026-11-14-question-order-plan.md` içinde.

## 2026-11-14 — veri yedeği

- Ayarlar ekranına ZIP yedeği indirme eklendi. Denemeler, yanlışlar, kullanıcı/Cosmos ilerlemesi, ayarlar ve `uploads/` alınır; API anahtarı boşaltılır. Bozuk/şemaya uymayan kayıt veya eksik referanslı dosya yedeği reddedilir.
- Uygulama ömür boyu process lock tutuyor; restore komutu uygulama açıkken çalışmaz. Arşiv önce staging dizininde yol, tür, boyut, checksum, şema ve upload referansı açısından bütünüyle doğrulanır; swap öncesi eski veri klasörü snapshot olarak saklanır.
- 57 backend testi, 4 frontend testi, production build ve gerçek Chromium smoke geçti. Smoke ZIP indirme adımını da doğruladı (285 ms); 390 px görünüm taşmadı.
- 50 x 2 MiB temsili upload ile backup export 8.5842 sn, doğrulama 0.9865 sn, restore 1.0021 sn; ZIP 104,900,138 bayt. 1.000 exam storage ve 100 question flow benchmarkları da geçti. Tüm benchmarklar AI'siz.
- Rapor: `reports/2026-11-14-backup-restore.md`. Yerel API endpoint/model ve multimodal aktarım diğer bilgisayarda doğrulanmayı bekliyor.

## 2026-11-14

- İlk backlog oluşturuldu; kapsam kaynak kod ve eski proje notuna dayalı, kullanıcıyla henüz UX kararları netleştirilmedi.
- `codex/hamartia-rebuild` dalı GitHub'da `master` başlangıç commit'i `c5642d0` üzerinden açıldı.
- Yerel çalışma kopyası GitHub tree/blob içerikleriyle kuruldu; tree SHA kaynak ağaçla eşleşti. DNS kısıtı nedeniyle normal Git taşıması kullanılamıyor.
- Local AI test ve benchmark kapsamı dışında tutuldu.
- Deneme POST akışındaki zorunlu-id sözleşmesi ve geçmişi silen kayıt davranışı düzeltildi; path-paylaşımlı kilit altında append eklendi.
- Dört backend kontrolü geçti; 1.000 JSON kayıt benchmarkı 12.4065 sn append (80.60 kayıt/sn), 0.0091 sn read ölçtü.
- `npm ci --offline`, Vite paketi npm önbelleğinde olmadığı için tamamlanamadı; frontend build ve browser smoke henüz doğrulanmadı.
- 2026-11-14: Backlog, gerçekleşen UI/test/build adımlarıyla güncellendi; sıradaki hedef veri bütünlüğü yarışlarını çözmek oldu.
- 2026-11-14: Kilitli `update_list`, katı JSON liste okuma ve eşzamanlı silme/append testleri eklendi; 13 backend testi geçti. Hamartia'nın doküman listesi için dict koleksiyon round-trip'i sağlandı.
- 2026-11-14: Yerel, AI'siz Çalışma Planı ekranı ve `/questions/insights` eklendi. 14 backend testi, 3 frontend testi geçti; 100 yanlış için öncelik hesabı 0.0031 sn.
- 2026-11-14: Vite 6.4.6 yamalı sürüme alındı; offline temiz kurulum/test/build/audit cache kontrolü geçti. Bundle 659.95 KB; tarayıcı smoke ve GitHub Actions sonucu hâlâ bekliyor.
- 2026-11-14: Görsel yüklemeye PNG/JPEG/WebP imza kontrolü eklendi. 14 backend testi geçti, 100 soru benchmarkı 0.5873 sn upload ölçtü; GitHub Actions yeni commit için sırada.
- 2026-11-14: Yerel kurulum ve model endpoint ayarı README'ye eklendi; AI istemcisi kayıtlı ayarı kullanıp görseli payload'a alıyor. Gerçek local model başka bilgisayarda doğrulanmadı.
- 2026-11-14: Deneme girişi ISO tarih ve 0-59 saniye aralığıyla sınırlandı; 14 backend testi, frontend test/build ve GitHub Actions geçti.
- 2026-11-14: Yanlış soru tekrar edildi durumu, geri alma ve bekleyen konu önceliği eklendi. 16 backend, 3 frontend testi ve model çağrısız benchmark geçti; ilk yeni CI akışı başarılı.
- Yeni AI dışı soru-flow ölçümü: `reports/2026-11-14-storage-and-study-plan.md`.
- 2026-11-14: Review undo ve docs commit'lerinde GitHub Actions frontend/backend işleri başarılı; local ve remote branch tree'leri eşleşti, `master` değişmedi.
- 2026-11-14: XP toplamı/level/seri artık deneme geçmişinden hesaplanıyor ve profil bonusunu koruyor; 20 backend testi, 3 frontend testi ve 1000 deneme progression benchmarkı geçti. GitHub Actions çalışıyor.
- Ölçüm raporu: `reports/2026-11-14-storage-and-study-plan.md`.
- 2026-11-14: Cosmos yer tutucusu salt okunur yerel ilerleme görünümüne çevrildi; XP/seviye/seri ve en çok dokuz bekleyen konu yer alıyor. İlk build 18.49 sn sürdü. Browser smoke ortamda browser/Playwright olmadığı için yapılmadı. Eski random assault endpointinin çok dosyalı XP yazımı ve ödül semantiği incelenip UI kapsamı dışında bırakıldı.
- 2026-11-14: XP çubuğunun 500 XP ilk seviye eşiği backend ile hizalandı; navbar ve Cosmos ortak yardımcıyı kullanıyor. 4 frontend testi ve 17.64 sn build geçti.
- GitHub Actions run `43603845596`: frontend test/build, backend unittest, JSON storage benchmarkı ve soru akışı benchmarkı başarılı.
- 2026-11-14: Soru bazında doğru/yanlış attempt history ve deterministik 1/3/7/14/30 gün tekrar aralıkları eklendi. Text-only capture da API/form/tekrar listesine bağlandı. 29 backend, 4 frontend testi geçti.
- 2026-11-14: Chromium smoke gerçek FastAPI+Vite ile temp veride görselsiz soru ekleme, çözüm persistence, AI route dışılığı, erişilebilir adlar ve 390 px taşmama kontrolünü geçti. 2.715 sn navigasyon, 2.432 sn capture+review persistence. `npm audit` online 0 bulgu.
- 100 görselli soru upload 0.4674 sn; 100 text-only capture 0.6439 sn; iki workflow da AI'siz benchmark.
- Rapor: `reports/2026-11-14-spaced-review-loop.md`. `test:browser` CI'a bağlandı; son Actions çalışması bekleniyor.
- 2026-11-14: Deneme modeline geriye uyumlu TYT/AYT/branş türü, kilitli PUT/DELETE API'si, tam geçmişte görünür düzenleme/silme, tür filtresi ve tür bazlı net/deneme toplamı eklendi. 32 backend testi; 4 frontend testi, build ve gerçek tarayıcı smoke geçti.
- Browser: 390 px taşma yok, dashboard JS/API hatası yok, Recharts NaN/duplicate-key hatası yok. Deneme CRUD döngüsü 1.039 sn; arayüz navigasyonu 2.266 sn; capture+review persistence 3.483 sn.
- 1.000 JSON denemede append 19.178 sn (52.14/s), read 0.0078 sn, update 0.0272 sn, delete 0.0237 sn, progression 0.0017 sn. 100 görselli yanlış 0.3149 sn (317.57/s), 100 text-only yanlış 0.4523 sn (221.11/s); hepsi AI'siz.
- Rapor: `reports/2026-11-14-exam-context-crud.md`. Kod commitleri GitHub dalına ağaç SHA eşleşmesiyle aktarıldı. Actions run `43608878405` (#41) frontend test/build/browser smoke ile backend test ve benchmarklarını başarıyla tamamladı.
- 2026-11-14: `StorageService.update_doc` ile Cosmos node upsert/sector unlock tek belge kilidine taşındı; legacy XP assault 410 ile kapandı. 38 backend testi geçiyor; 24 eşzamanlı node ve 3 paralel sector güncellemesinde kayıt kaybı yok.
- 1.000 exam append 19.8911 sn (50.27/s), read 0.0135 sn, exam update/delete 0.0325/0.0305 sn, tek user document update 0.0013 sn, progression 0.0021 sn. Q-flow 100 görsel 0.3414 sn, 100 text capture 0.4828 sn. Local AI dışarıda.
- Browser smoke (regresyon): navigasyon 3.035 sn, capture+review persistence 3.615 sn, exam CRUD 1.045 sn; frontend 4/4, build başarılı.
- Rapor: `reports/2026-11-14-cosmos-storage-safety.md`; CI doğrulaması bu değişiklikten sonra bekliyor.
- 2026-11-14: Yanlış soru kartlarına ders/konu/metin düzenleme ve onaylı silme eklendi. Düzenleme görseli, analiz etiketini ve tekrar geçmişini koruyor; text-only soru boş metne çevrilemiyor. Silme kaydı atomik listeden çıkarıyor ve yalnızca `uploads/` altındaki görseli kaldırıyor. 43 backend testi, 4 frontend testi, build ve Chromium smoke geçti; AI çağrısı yok.
- 100 soruluk akışta upload 0.3006 sn, text capture 0.4759 sn, tek soru düzenleme 0.0047 sn ve görsel silmeyle soru silme 0.0041 sn ölçüldü. 1.000 JSON denemede append 12.8297 sn (77.94/s), read 0.0077 sn, update/delete 0.0278/0.0241 sn; tüm benchmarklar AI'siz. Benchmark süreçleri eşzamanlı çalıştığı için sonuçlar makine gürültüsüne açık.
- Browser smoke: navigasyon 2.362 sn, capture+review persistence 2.335 sn, deneme CRUD 1.301 sn, soru düzenle+sil 0.423 sn; 390 px taşma, API/JS/console hatası yok. Build 23.50 sn, ana bundle 679.05 KB minified / 193.94 KB gzip; 500 KB chunk uyarısı sürüyor.
- GitHub Actions run #47 (`f372b2f4`) frontend test/build/browser smoke ile backend test ve iki benchmark işini başarıyla tamamladı.
- Rapor: `reports/2026-11-14-question-record-crud.md`.
- 2026-11-14: Çalışma planına bugünkü ilerleme kartı eklendi. Tekrar denenen soru bir kez sayılıyor; doğru/yanlış sayaçları her yanıtı sayıyor. Kayıtlı attempt geçmişinden hesaplanıyor, yeni JSON alanı/ayar/AI çağrısı yok. 45 backend testi, 4 frontend testi, production build ve browser smoke geçti.
- Browser smoke: navigasyon 2.157 sn, capture+review sonrası yenileme 2.335 sn, deneme CRUD 1.234 sn, soru düzenle+sil 0.409 sn; bugünkü sayıların reload sonrası 2 soru, 1 doğru, 1 yanlış kaldığı doğrulandı.
- 100 soru benchmarkı: insight 0.0053 sn; upload 0.604 sn, list 0.0008 sn, attempt 0.0034 sn, review 0.0038 sn, edit/delete 0.0045/0.0030 sn, text capture 0.4463 sn. Hepsi AI'siz.
- Build 22.12 sn, bundle 679.49 KB minified / 194.02 KB gzip (500 KB chunk uyarısı sürüyor). GitHub Actions run #49 (`d0cd18ff`) kod commitini başarıyla doğruladı; dokümantasyon commitinin CI'ı çalışıyor. Rapor: `reports/2026-11-14-todays-study-activity.md`.
- 2026-11-14: `scripts/dev.py` uvicorn ve Vite'ı tek komutla başlatıp readiness kontrol ediyor; Ctrl+C/SIGTERM ile ikisini kapatıyor. Vite sessizce başka porta geçmiyor; 5173 doluysa `HAMARTIA_FRONTEND_PORT` seçeneği kullanılabilir. Browser smoke artık gerçek launcher üzerinden çalışıyor.
- Launcher entegrasyon kontrolü: geçici veri dizininde API/frontend 200 ve Ctrl+C sonrası iki Hamartia portu kapalı; mevcut 5173 uygulaması korundu. Process group cleanup sonrası açılış/kapanış 2.458 sn. Port çakışması smoke'u launcher'ın 1 ile çıktığını ve API child'ını kapatıp mevcut Vite'ı koruduğunu doğruladı.
- Launcher sonrası browser smoke geçti: navigasyon 2.056 sn, capture+review 2.288 sn, deneme CRUD 1.217 sn, soru edit/delete 0.471 sn. Frontend 4/4 test; build 26.07 sn, bundle öncekiyle aynı 679.49/194.02 KB. Process group temizliği ayrı committe; Actions run #54 çalışıyor.
- Rapor: `reports/2026-11-14-local-launcher.md`.
