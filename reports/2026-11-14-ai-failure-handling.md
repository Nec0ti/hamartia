# 2026-11-14 yerel model hata işleme — uygulama ve doğrulama

## Değişiklik

`AIService._completions()` provider hatalarını boş cevaba çevirmek yerine yukarı taşır. Soru analiz API'si `OpenAIError` için 502 döndürür; frontend'in mevcut HTTP hata akışı mesajı gösterir. Hata durumunda mevcut Council analizi ve manuel etiket değişmez. Böylece erişim/model hatası başarılı analizmiş gibi saklanmaz.

## Doğrulama

- Backend: `PYTHONPATH=. python -m unittest discover -s tests -q` — 73 test geçti. Yeni sınır testi fake `OpenAIError` üretir ve 502 ile kayıt/etiket korumasını doğrular; gerçek model veya endpoint çağrısı yapmaz.
- Frontend: `npm test` — 4/4 geçti; production build başarılı, JS 695.22 KB / 198.14 KB gzip. 500 KB chunk uyarısı sürüyor.
- Chromium browser smoke başarıyla geçti; UI, practice, grafik ve backup akışları devam ediyor. Smoke `ai_included: false` ve `/agent`/`analyze` istekleri olmadığını doğrular.
- Gerçek AI isteği veya AI benchmarkı çalıştırılmadı.

## Başka bilgisayarda elle doğrulama

README'deki manuel sırayı uygula: text-only bir soruda analiz, ardından görselli bir soruda analiz. İkinci kontrol multimodal endpoint/model desteğini gerçek kullanımda doğrular. Bu doğrulama yapılana kadar bağlantı/model/görsel aktarımı tamamlanmış sayılmaz.
