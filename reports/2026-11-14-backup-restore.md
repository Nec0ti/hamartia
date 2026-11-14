# 2026-11-14 veri yedeği ve geri yükleme

## Kapsam

- Ayarlar'dan ZIP yedeği indirme; JSON kayıtları ve `uploads/` dahil, kişisel API anahtarı hariç.
- CLI ile uygulama kapalıyken geri yükleme; checksum/şema/path/upload referansı doğrulama ve mevcut klasörü saklama.
- Geri yükleme sırasında uygulama process lock'u ile eşzamanlı yazmayı önleme.
- AI çağrısı yapılmadı; local AI davranışı kapsam dışı.

## Doğrulama

- `PYTHONPATH=backend /tmp/hamartia-venv/bin/python -m unittest discover -s backend/tests -v` — 58/58 geçti.
- `npm test` — 4/4 geçti.
- `npm run build` — başarılı; 680.48 KB minified JS ve Vite'ın 500 KB chunk uyarısı.
- `HAMARTIA_PYTHON=/tmp/hamartia-venv/bin/python PLAYWRIGHT_CHROMIUM_EXECUTABLE=/nix/store/r0f9i35n3r7rng8162xih4c1dag0s1vw-chromium-156.0.8078.47/bin/chromium npm run test:browser` — geçti; gerçek ZIP indirme 285 ms, ekran navigasyonu 2.293 sn, capture/review kalıcılığı 2.336 sn, deneme CRUD 1.344 sn, yanlış düzenle/sil 0.417 sn. 390 px taşma ve tarayıcı hatası yok.
- `PYTHONPATH=backend /tmp/hamartia-venv/bin/python backend/benchmarks/benchmark_backup.py` — 50 adet 2 MiB upload (100 MiB): export 8.5842 sn, validation 0.9865 sn, restore 1.0021 sn, ZIP 104,900,138 bayt.
- Aynı oturumda storage benchmarkı: 1.000 deneme append 19.6104 sn (50.99 kayıt/sn), read 0.0099 sn, update 0.0223 sn, delete 0.0249 sn; 100 soru benchmarkı da geçti.

## Veri güvenliği

Geri yükleme arşivi sibling staging dizininde tümüyle doğrulandıktan sonra uygulanır. Mevcut klasör snapshot olarak kalır; yeni dizin swap'ı başarısız olursa önceki klasör geri konur. API anahtarı yedek ZIP'ine yazılmaz ve aynı bilgisayarda restore edilirken mevcut ayardan korunur. Yeni bilgisayarda API anahtarı boş kalır.

## Sınırlar

- Test ortamında ZIP API client'ı `httpx` deprecation uyarısı verdi; test başarılı.
- Benchmarklar yerel makine ve geçici SSD/tmp alanında ölçüldü; gerçek kullanıcı arşivlerinin boyutu değişebilir.
- Gerçek AI endpoint/model başka bilgisayarda henüz doğrulanmadı.
