# 2026-11-14 — başlangıç depolama ve deneme akışı

## Kapsam

Deneme oluşturma API mantığı, JSON geçmişinin korunması, eşzamanlı kayıt ve depolama mikrobenchmarkı. Local AI veya herhangi bir model çağrılmadı.

## Kontroller

`backend/tests/test_exams.py`: 4 kontrol geçti.

- UI'nın gönderdiği kimliksiz payload ile ID/zaman üretilmesi ve eski kaydın korunması.
- Boş ders ve negatif doğru sayısının reddedilmesi.
- Aynı JSON dosyasına farklı `StorageService` örneklerinden 32 eşzamanlı ekleme.
- Bozuk JSON'un append sırasında değiştirilmemesi.

Çalıştırma ortamı Python 3.14 ve sistem Nix store'undaki FastAPI 0.141.1/Pydantic 2.13.4 paketleriydi. Bu, backend HTTP sunucusunun tamamını veya AI rotalarını test etmez.

## Benchmark

`backend/benchmarks/benchmark_storage.py`, geçici dizinde 1.000 sınav kaydını sırayla ekleyip yeniden okudu. Sonuç: append 12.4065 sn (80.60 kayıt/sn), read 0.0091 sn. Dosya tabanlı JSON'un her append'te listeyi yeniden yazması bu yapay toplu yükü pahalı kılıyor; kullanıcı başına tipik kayıt hızını temsil etmez. Daha büyük/çok süreçli kullanımda SQLite değerlendirilmelidir.

## Frontend doğrulaması

`npm ci --offline` Vite 5.4.21 paketi yerel npm cache'inde olmadığı için başarısız oldu. Frontend build ve browser smoke çalıştırılmadı; bu yüzden kayıt akışının arayüzden uçtan uca çalıştığı henüz kanıtlanmış değil.
