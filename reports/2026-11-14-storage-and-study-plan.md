# Veri bütünlüğü ve çalışma öncelikleri — 2026-11-14

## Kapsam

- Bozuk koleksiyon JSON'ının okunması ve korunması.
- Eşzamanlı deneme/soru güncellemeleri.
- Yanlış defterinden deterministik ders/konu önceliği.
- Local AI kullanmayan backend ve frontend doğrulamaları.
- Vite güvenlik yaması ve frontend üretim build'i.

## Değişiklikler

- `StorageService.update_list` kilit altında oku-değiştir-yaz sunuyor. Deneme silme, soru etiketi/analiz kaydı ve çalışma belgesi ekleme bu yolu kullanıyor.
- JSON bozuksa veya kayıt şemaya uymuyorsa okuma `StorageError` veriyor; veriyi boş liste sanıp ezmiyor.
- `/questions/insights` yanlış kayıtlarını ders/konu bazında birleştiriyor; tekrar sayısı yüksek konu üstte, eşitlikte ad alfabetik. Hata etiketleri ve en son kayıt günü de dönüyor.
- Çalışma Planı ekranı bu sonuçları gösteriyor. Hiçbir endpoint gerçek modele bağlanmıyor.
- Vite `^5.4.8` yerine `^6.4.6` oldu. Resmi [GHSA-p4f5-76q4-ffq7](https://github.com/vitejs/vite/security/advisories/GHSA-p4f5-76q4-ffq7) duyurusunda <=6.4.5 etkileniyor; [6.4.6 release](https://github.com/vitejs/vite/releases) yamalı sürüm.

## Doğrulama

| İş | Sonuç |
| --- | ---: |
| Backend testleri | 14/14 geçti |
| Frontend formatter testleri | 3/3 geçti |
| Frontend production build | geçti, 21.38 sn |
| Build ana JS | 659.95 KB minified / 190.16 KB gzip |
| 100 yanlış yükleme benchmarkı | 0.8692 sn / 115.04 kayıt/sn |
| 100 soru listeleme | 0.0017 sn |
| 100 kayıtlı çalışma önceliği hesabı | 0.0031 sn |
| 1.000 JSON denemesi append | 15.8939 sn / 62.92 kayıt/sn |
| 1.000 JSON denemesi okuma | 0.0132 sn |
| `npm audit --offline` | cache'de 0 bulgu |

AI dışı benchmark komutları:

```sh
python backend/benchmarks/benchmark_storage.py
python backend/benchmarks/benchmark_questions.py
```

Frontend doğrulama komutları:

```sh
npm test
npm run build
```

## Sınırlamalar

- Python testleri sistem Python 3.14/Nix FastAPI ve Pydantic paketlerini kullandı; eksik `openai` ve `python_multipart` importları test harness'inde stub edildi. Model yüklenmedi veya çağrılmadı.
- Frontend bağımlılıkları `npm ci --offline --ignore-scripts` ile kuruldu. Sandbox ortamında kurulum script'leri çalıştırılmadı; Vite build ve test yine de geçti.
- `npm audit --offline` yalnızca yerel npm cache'ini temsil eder, güncel internet audit'i değildir.
- JSON append her eklemede tüm dosyayı yeniden yazıyor. 1.000 kayıt ölçümü bu maliyeti gösteriyor; eşzamanlı process/çok worker veya büyüyen geçmiş için SQLite'a geçiş gerekir.
- Bundle 500 KB eşiğini aşıyor. Bu çalışma diliminde code-splitting yapılmadı.
- GitHub Actions workflow dosyası var; branch API commit'lerinden sonra CI run henüz doğrulanmadı. Tarayıcı tabanlı uçtan uca akış çalıştırılmadı.

## Model sınırı

Bu rapordaki tüm kontroller ve benchmarklar model çağrısı içermez. Yerel AI'nın donanım, model, prompt ve yanıt kalitesi ölçümleri başka bilgisayarda ayrıca yapılmalıdır.
