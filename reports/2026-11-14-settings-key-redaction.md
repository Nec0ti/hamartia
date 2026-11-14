# Ayarlar API anahtarı gizleme

## Sonuç

`GET /settings` ve `PATCH /settings` artık kayıtlı API anahtarını tarayıcıya göndermez. Yanıt yalnızca `has_api_key` boolean alanını taşır. Boş anahtar güncellemesi kayıtlı anahtarı korur; yeni değer anahtarı değiştirir, açık `clear_api_key` isteği temizler. Arayüz anahtar alanını sunucu yanıtından doldurmaz ve modal kapanınca yazılmış anahtarı React state'inden boşaltır.

## Kontroller

- Backend: Python 3.14 `.venv` ortamında `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -q` — **76/76 geçti**. Yeni testler GET/PATCH redaksiyonu, koruma, değiştirme ve temizlemeyi kapsar.
- Frontend: `npm test` — **4/4 geçti**.
- Production build başarılı: JS **695.72 KB / 198.31 KB gzip**. Vite'ın 500 KB chunk uyarısı sürüyor.
- Gerçek Chromium browser smoke: geçti. Ayar anahtarı ekle/sil turu yanıtlarda API key olmadığını, diskte temizlendiğini doğruladı; **1.269 ms**.
- Diğer browser smoke ölçümleri (ms): navigasyon **3756**, konu seti persistence **2196**, odaklı oturum **9952**, trend/tam geçmiş **4937**, yanlış kaydetme+tekrar persistence **5628**, deneme CRUD **5318**, yanlış düzenle/sil **1022**, yedek indirme **172**. `ai_included: false`.
- Backend AI'siz benchmarkları: 1.000 deneme JSON append **23.4282 s** (42.68 kayıt/s), read **0.0087 s**; 100 yanlış akışında görsel upload **0.4985 s**, metin yakalama **0.7865 s**, liste **0.0021 s**, insight **0.0063 s**; 50 x 2 MiB yedek export/validation/restore **5.6322 / 0.9249 / 0.9199 s**; soru sıra özeti 1.000/10.000 kayıtta **0.013671 / 0.139487 s**; konu seti özeti 1.000/10.000 kayıtta **0.013875 / 0.074794 s**.
- Her benchmark model çağrısı olmadan çalıştı. Bu kod yalnızca ayar saklama/yanıt yolunu değiştiriyor; benchmark sayıları makine yükü ve dosya sistemi performansına bağlı.

## Uygulama notu

Testler ilk kez sistem Python'ıyla çalıştırıldığında o ortamda FastAPI/Pydantic bulunmadığı için import aşamasında durdu. Repo içindeki yok sayılan `.venv` oluşturulup `backend/requirements.txt` kuruldu ve tam backend suite başarıyla tekrarlandı. İlk Playwright Chromium ikilisi sistem `glib` kitaplığını bulamadı; smoke Nix Chromium ikilisiyle geçti.

## Sınır

API anahtarı artık HTTP yanıtlarından ve modal state'inden çıkmıyor. Tek kullanıcılı localhost uygulaması aynı makinedeki yetkisiz yerel süreçleri engellemez; bunun için OS secret store veya ayrı kullanıcı sınırı gerekir. Gerçek local model çağrısı yapılmadı ve backlog'da ayrı bilgisayar doğrulamasında kalıyor.
