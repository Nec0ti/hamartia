# Yanlış soru kaydı düzenleme ve güvenli silme

## Kapsam

- Yanlış soru kartında ders, konu ve metin alanı düzenlenebilir.
- Düzenleme görseli, analiz yanıtını, hata etiketini ve çözüm/tekrar geçmişini korur.
- Kayıt silme onay ister; yalnızca yolu `uploads/` içinde çözümlenen görsel dosyası da kaldırılır.
- Görselsiz soru metninin boşaltılması `422` ile reddedilir; bulunmayan kayıt `404` döner.
- Yeni endpointler mevcut `StorageService.update_list` atomik liste mutasyonunu kullanır.

## Doğrulama

- `PYTHONPATH=. /tmp/hamartia-venv/bin/python -m unittest discover -s tests -v` — 43/43 geçti.
- `npm test` — 4/4 geçti.
- `npm run build` — geçti, 23.50 sn. Ana bundle 679.05 KB minified / 193.94 KB gzip; Vite 500 KB chunk uyarısı veriyor.
- `HAMARTIA_PYTHON=/tmp/hamartia-venv/bin/python PLAYWRIGHT_CHROMIUM_EXECUTABLE=/nix/store/r0f9i35n3r7rng8162xih4c1dag0s1vw-chromium-156.0.8078.47/bin/chromium npm run test:browser` — geçti. Düzenleme ve görseliyle silme istekleri, JSON persistence, görsel kaldırma, 390 px taşmama ve AI endpointlerine istek gitmemesi doğrulandı.
- Tarayıcı smoke: navigasyon 2.362 sn; capture+review persistence 2.335 sn; deneme CRUD 1.301 sn; soru düzenle+sil 0.423 sn.
- `backend/benchmarks/benchmark_questions.py` — 100 soru: upload 0.3006 sn, liste 0.0007 sn, insight 0.0121 sn, attempt 0.0041 sn, review 0.0059 sn, update 0.0047 sn, delete 0.0041 sn, text capture 0.4759 sn (210.14/s).
- `backend/benchmarks/benchmark_storage.py` — 1.000 deneme: append 12.8297 sn (77.94/s), read 0.0077 sn, update 0.0278 sn, delete 0.0241 sn, document update 0.0015 sn, progression 0.0016 sn.

## Sınırlar

- Tüm test ve benchmarklar model çağrısı yapmadı; local AI doğrulaması başka bilgisayarda yapılacak.
- İki backend benchmarkı eşzamanlı çalıştırıldı; süreler makine yükünden etkilenmiş olabilir ve donanımlar arası karşılaştırma değildir.
- JSON listesi ile dosya silme tek transaction oluşturamaz. Kayıt listeden çıkarıldıktan sonra süreç durursa yetim görsel kalabilir; silme rotası bu durumda hatayı bildirir. Dış dizindeki dosya silinmez.
- GitHub Actions bu commitler için henüz tamamlanmadı.
