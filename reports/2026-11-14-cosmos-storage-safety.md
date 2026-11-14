# Cosmos yazım güvenliği — 2026-11-14

## Kapsam

- Tek JSON belgeyi aynı dosya kilidi içinde okuyup güncelleyen depolama işlemi.
- Cosmos node upsert ve sektör açma çağrılarında eşzamanlı yazımları koruma.
- Kuralı tanımlanmamış, XP bahisli ve iki dosyaya yazan saldırı rotasını zararsız biçimde kapatma.
- Model çağrısız test, benchmark ve browser regresyonu.

## Uygulanan davranış

- `StorageService.update_doc()` mevcut JSON'u doğrular, yoksa varsayılan model oluşturur, callback'i dosya kilidi altında çalıştırır ve atomik rename ile kaydeder. `load_doc()` da aynı dosya kilidini kullanır.
- Node oluşturma veya aynı konu/etiketin hata sayısını artırma tek `cosmos.json` mutasyonudur. Node ID'leri UUID ile benzersizdir.
- Sektör açma aynı belge mutasyonuyla çalışır; aynı sektörün ikinci kez açılması ek kayıt oluşturmaz.
- `POST /cosmos/nodes/{id}/assault` HTTP 410 döndürür. Eski rotanın başarıda `cosmos.json` ve `user.json` dosyalarını ayrı yazıp XP ödülü vermesi, başarısızlıkta farklı ceza uygulaması ve `cleansed` alanını şemada sunmaması güvenilir bir ekonomi kuralı oluşturmuyordu.
- Assault rotası JSON okuma/yazma yapmaz. Eski frontend API wrapper'ı korunur ama herhangi bir ekran bu rotayı çağırmaz.

## Doğrulama ve ölçümler

| Kontrol | Sonuç |
| --- | ---: |
| Backend unittest | 38/38 geçti |
| Cosmos aynı node'a paralel upsert | 24 çağrı, 1 node, 23 artış |
| Cosmos farklı node'lara paralel upsert | 24/24 farklı node saklandı |
| Sektör unlock yarışı | 3 farklı sektör birer kez saklandı |
| Assault rotası | 410, `cosmos.json` ve `user.json` baytları aynı |
| Frontend Node testleri | 4/4 geçti |
| Frontend üretim derlemesi | 28.68 sn, başarılı |
| Browser smoke regresyon | 3.035 sn navigasyon / 3.615 sn capture+review / 1.045 sn exam CRUD |
| 1.000 exam append / read | 19.8911 sn / 0.0135 sn |
| Exam update / delete | 0.0325 sn / 0.0305 sn |
| Tek user JSON update | 0.0013 sn |
| Progression hesabı | 0.0021 sn |
| 100 görselli soru yükleme | 0.3414 sn / 292.87 kayıt/sn |
| 100 text-only soru kaydı | 0.4828 sn / 207.13 kayıt/sn |

Komutlar:

```sh
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
python backend/benchmarks/benchmark_storage.py
python backend/benchmarks/benchmark_questions.py
cd frontend && npm test && npm run build
cd frontend && npm run test:browser
```

## Sınırlar

- Dosya kilitleri process-local; bu sürüm tek API worker'ı içindir. Çoklu worker desteği için SQLite veya process-wide kilit gerekir.
- XP assault oyun kuralı ve UI bağlantısı yoktur. Bir öğrenme görevi doğrulanabilir biçimde tamamlanmadan XP ödülü verilmez.
- Browser smoke Cosmos mutations'ı UI üzerinden kullanmaz; node/sektör yarışları backend testlerinde AI'siz kontrol edilir.
- Local AI yüklenmedi, çağrılmadı veya benchmark edilmedi.
- Son başarıyla biten GitHub Actions run `43609061343` Cosmos değişikliğinden önceydi; yeni run bu commit aktarıldıktan sonra doğrulanacak.
