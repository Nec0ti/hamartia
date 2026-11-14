# Yerel uygulama başlatıcısı

## Kapsam

- `scripts/dev.py` repo kökünden FastAPI ve Vite'ı birlikte başlatır.
- API `/healthcheck/ready`, frontend HTTP 200 verene kadar başlatma tamamlandı mesajı göstermez.
- Ctrl+C/SIGTERM iki child process'i durdurur.
- Frontend portu varsayılan 5173'tür; `HAMARTIA_FRONTEND_PORT` ile ayarlanır. Vite `--strictPort` kullanır, sessiz port kayması readiness hatası oluşturamaz.
- Python bağımlılığı veya npm kurulumu eksikse çalıştırma öncesi açık hata verir.

## Doğrulama

- Geçici veri dizini ve 5174 portuyla gerçek launcher smoke: API ready ve frontend 200; Ctrl+C sonrası port 5174/8000 kapandı. Önceden kullanımda olan 5173 portundaki Cygnet Vite süreci açık kaldı. Hazır olma ve temiz kapatma toplamı 2.124 sn.
- 5173 çakışma smoke'u launcher'ın hata kodu 1 ile çıktığını, API child'ını kapattığını ve mevcut 5173 uygulamasını koruduğunu doğruladı.
- `npm test` — 4/4 geçti.
- `npm run build` — geçti, 26.07 sn. Bundle 679.49 KB minified / 194.02 KB gzip; 500 KB chunk uyarısı sürüyor.
- `npm run test:browser` — gerçek `scripts/dev.py` üzerinden geçti. Smoke 5174'te, geçici `HAMARTIA_DATA_DIR` ile çalıştı; sınav ve soru CRUD, bugünkü çalışma özeti, sayfa yenileme, 390 px taşmama ve AI endpointlerine istek gitmemesi doğrulandı.
- Browser smoke süreleri: navigasyon 2.610 sn; capture+review persistence 2.451 sn; deneme CRUD 1.448 sn; soru düzenle+sil 0.453 sn.

## Sınırlar

- Launcher Linux/NixOS ortamında çalıştırıldı; Windows process-tree davranışı ayrıca denenmedi.
- API portu sabit 8000'dir; port çakışması API başlatmasını readiness aşamasında başarısız kılar. Yalnızca frontend portu yapılandırılabilir.
- AI yüklenmedi, çağrılmadı veya benchmark edilmedi.
- Bu commit için GitHub Actions sonucu bekleniyor.
