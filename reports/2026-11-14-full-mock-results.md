# TYT/AYT ders bölümlü deneme — sonuç

## Uygulama

- TYT/AYT denemesi tek `Exam` kaydında bölüm adı ve doğru/yanlış/boş sayılarıyla tutulur. Backend toplamları doğrular; süre oturum süresi olarak kalır. XP, seri ve deneme sayımı aynı oturum için bir kez yapılır.
- Branş denemeleri ile eski bölüm içermeyen TYT/AYT kayıtları çalışmaya devam eder. Eski tam deneme düzenleme formuna açıldığında mevcut sayıları tek bölüm olarak korur.
- Geçmiş tek satırda toplamı gösterir ve ders sonuçlarını açar. Ders filtresi istatistik/net trendini o bölüm üzerinden hesaplar.
- Bölümden yanlış ekleme ders adını taşır; soru no/çözüm sırası bölüm soru sayısına göre doğrulanır. Soru, kayıt anındaki bölüm büyüklüğünü snapshot olarak saklar.
- Backup restore yeni `sections` alanını round-trip eder; eski JSON/backup alanları için varsayılanlar korunur.

## Doğrulama

- Backend: `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -q` — 81 test geçti.
- Frontend: `npm test` — 7 test geçti.
- Frontend production: `npm run build` — başarılı. Mevcut büyük bundle uyarısı var: 699.82 KB minified / 199.51 KB gzip.
- Chromium smoke: `npm run test:browser` — başarılı. İçinde branş ve TYT/AYT oluşturma, TYT reload, bölümden yanlış soru ekleme, düzenleme, ders filtresi ve silme var. Toplam `exam_crud_ms`: 10,840 ms; diğer adımlar komut çıktısında ölçüldü.
- `git diff --check` — temiz.

## AI dışı benchmark ölçümleri

Yerel geliştirme makinesinde tekil çalıştırma; her betik başarı assert'leriyle bitti. Ölçüler makine/yük bağımlıdır, CI performans eşiği değildir.

| Akış | Veri | Sonuç |
| --- | --- | --- |
| JSON sınav depolama | 1.000 kayıt, 10 tam deneme | append 19.2337 sn (51.99 kayıt/sn), read 0.0206 sn, update 0.0489 sn, delete 0.0374 sn, progression 0.0051 sn |
| Soru yakalama/içgörü | 100 görselli + 100 metin, 40 bölüme bağlı | upload 0.8938 sn, text capture 1.2757 sn, bölüm sorusu upload 0.6774 sn, bölüm sırası özeti 0.0091 sn |
| Backup/restore | 50 x 2 MiB upload, ZIP 104,900,284 bayt | export 6.8527 sn, validation 1.0435 sn, restore 1.1368 sn |
| Soru çözüm sırası özeti | 1.000 / 10.000 kayıt | 0.016647 / 0.178777 sn |
| Konu çalışma seti | 1.000 / 10.000 oturum | summary 0.009912 / 0.076962 sn; write 0.022863 / 0.172899 sn; read 0.049215 / 0.400616 sn |

`ai_included:false` bütün benchmark çıktılarında yer aldı. Gerçek model yüklenmedi, endpoint çağrılmadı.

## Git aktarımı ve kalanlar

- Yerel UI commit `040462e2bf9a73271d622741b63c9cd616c1ceb4`; remote karşılığı `de19c4f56883d460eac80649e18b54468135dbcf`. İki ağacın SHA'sı `8bed8506808519c6812b31fc9528e130fc172c74`.
- Yerel backup/benchmark commit `a7f7b556488418857d86ad812217a63157586960`; remote karşılığı `7c8b57a87447540484bb64259d7b5876e2d11e5b`. Ağaç SHA'sı `9cc28a65ae406a2915be33dd7ee7618e9274144f`.
- GitHub `codex/hamartia-rebuild` ref'i bu sırayla fast-forward güncellendi. Son commit için GitHub combined status boş döndü ve açık PR bulunmadı; dolayısıyla bu dilim için Actions sonucu oluşmuş/doğrulanmış değil.
- Checkout'ta canlı `backend/data` olmadığı için kullanıcının gerçek JSON kayıtları sınanmadı. P3'teki endpoint/model ve görsel analiz doğrulaması ayrı bilgisayarda elle yapılacak.
