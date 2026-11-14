# Aralıklı yanlış tekrar döngüsü — 2026-11-14

## Kapsam

- Her yanlış sorunun çözüm girişimini ve doğru/yanlış sonucunu yerelde saklama.
- Tekrar tarihini deterministik hesaplama; eski `reviewed_at` kayıtlarını koruma.
- Çalışma Planı'nda due soruyu açıp sonucunu kaydetme.
- Gerçek tarayıcı + FastAPI smoke, dar ekran ve temel erişilebilirlik adları.
- Bu akış için AI'siz backend/frontend doğrulama ve performans ölçümü.

## Tekrar kuralı

- Denenmemiş soru hemen çözüm kuyruğuna girer.
- Yanlış cevap ertesi takvim gününe planlanır ve doğru serisini sıfırlar.
- Doğru cevapta ardışık doğru sayısına göre 1, 3, 7, 14, sonra en fazla 30 gün beklenir.
- Eski `reviewed_at` değeri soru arşivini korur. Yeni çözüm denemesi bu işareti temizleyip soruyu tekrar zamanlamaya alır.
- Eski JSON'larda `review_attempts` olmadığı için şema varsayılan boş listeyi kullanır; dosya migrasyonu gerekmez.
- XP üretimi bu işleme bağlanmaz; XP deneme kayıtlarından hesaplanır.

## Uygulanan yollar

- `POST /questions/{id}/attempt` doğru/yanlış sonucunu `StorageService.update_list` ile kilitli read-modify-write içinde ekler.
- `review_state()` tarih, ardışık doğru serisi ve sonraki gün hesabını modelden bağımsız yapar.
- `GET /questions/insights` due soru kuyruğunu ve daha sonra açılacak sayıyı döndürür.
- Study Plan görsel/metni gösterir, doğru/yanlış çözüm düğmeleri sunar ve kayıt sonrası planı yeniden yükler.
- Yanlış soru API'si görsel veya metinle kayıt kabul eder. Görsel yoksa boş `image_name`/`image_path` saklanır; var olan kayıt şemasına yeni attempt listesi eklenmesi geriye uyumludur.
- Browser smoke Playwright Chromium, geçici `HAMARTIA_DATA_DIR`, canlı FastAPI ve Vite kullanır. Görselsiz bir soru formdan eklenir, bir görsel soru yanlış, metin-only soru doğru çözüldü olarak kaydedilir, sayfa yenilenir ve her iki verinin JSON dosyasında kaldığı okunur. Aynı smoke AI route'larına hiç istek gitmediğini, resmin yüklendiğini, düğme erişilebilir adlarını ve 390 px görünümde yatay taşma olmadığını kontrol eder.
- Tarayıcı smoke için `HAMARTIA_DATA_DIR` config override'ı test verisini `backend/data` dışına yazar. Normal kullanım varsayılan dizini değiştirmez.

## Doğrulama ve ölçümler

| Kontrol | Sonuç |
| --- | ---: |
| Backend unittest | 29/29 geçti |
| Frontend Node testleri | 4/4 geçti |
| Frontend üretim derlemesi | 20.91 sn, başarılı |
| Ana JS bundle | 673.35 KB minified / 192.80 KB gzip |
| Online `npm audit` | 0 bulgu |
| 1.000 kayıt JSON append / read | 21.0752 sn / 0.0078 sn |
| 1.000 kayıt XP/seri hesabı | 0.0017 sn |
| 100 görselli soru upload / hız | 0.4674 sn / 213.97 kayıt/sn |
| Soru listesi / çalışma planı hesabı | 0.0011 sn / 0.0129 sn |
| Çözüm sonucu kaydı / eski arşiv işareti | 0.0034 sn / 0.0049 sn |
| 100 text-only soru capture / hız | 0.6439 sn / 155.29 kayıt/sn |
| Browser smoke navigasyon / text capture + sonuç + persistence | 2.715 sn / 2.432 sn |

Komutlar:

```sh
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
python backend/benchmarks/benchmark_storage.py
python backend/benchmarks/benchmark_questions.py
cd frontend && npm test && npm run build && npm audit
cd frontend && npm run test:browser
```

## Sınırlamalar

- Browser smoke iki soru (biri seeded görsel, biri yeni text-only) ile upload ve sonuç write/persistence sınar; başarılı cevap aralıklarının tüm 1/3/7/14/30 gün basamakları tarayıcıda değil unit testlerinde kapsanır.
- Local AI yüklenmedi, çağrılmadı veya benchmark edilmedi.
- Bundle 500 KB uyarısını sürdürüyor.
- JSON dosyası kilidi tek process kapsamındadır; birden fazla server worker desteklenmez.
- CI, bu rapordan sonraki dokümantasyon commit'inde Chromium smoke ve güncel backend benchmarklarını ayrıca doğrulayacak.
