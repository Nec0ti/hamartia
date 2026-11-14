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
- Soru dosyası uzantı/MIME denetimine PNG/JPEG/WebP imza doğrulaması eklendi; yanlış başlıklı PNG 415 alıyor.
- Yanlışlar için tekrar edildi durumu eklendi; plan yalnızca bekleyen kayıtları sıralıyor ve kullanıcı durumu geri alabiliyor.
- Kullanıcı XP'si deneme başına hesaplanan XP ile mevcut profil bonusunun toplamı; seviye toplam XP'den, seri deneme günlerinden türetiliyor. Profil ve Cosmos aynı XP projeksiyonunu kullanıyor.
- AI endpoint'i kaydedilmiş ayarları okuyacak async OpenAI client'ı kullanıyor ve görseli data URI ile isteğe ekliyor. Kullanıcı isteği gereği bu yol test/benchmark edilmedi; ayrı bilgisayarda doğrulanması gerekiyor.

## Doğrulama

| İş | Sonuç |
| --- | ---: |
| Backend testleri | 20/20 geçti |
| Frontend formatter testleri | 3/3 geçti |
| Frontend production build (review status akışı dahil) | geçti, 20.55 sn |
| Build ana JS | 661.61 KB minified / 190.49 KB gzip |
| 100 yanlış yükleme benchmarkı | 0.8692 sn / 115.04 kayıt/sn |
| 100 soru listeleme | 0.0017 sn |
| 100 kayıtlı çalışma önceliği hesabı | 0.0031 sn |
| Görsel imzası sonrası 100 soru upload | 0.5873 sn / 170.28 kayıt/sn |
| Aynı tekrar testinde liste/öncelik hesabı | 0.0010 sn / 0.0020 sn |
| Tekrar döngüsü benchmarkı: 100 soru upload | 0.4798 sn / 208.43 kayıt/sn |
| Tekrar listesi / review update | 0.0031 sn / 0.0036 sn |
| 1.000 JSON denemesi append | 13.6749 sn / 73.13 kayıt/sn |
| 1.000 JSON denemesi okuma | 0.0078 sn |
| 1.000 deneme için XP/seri hesabı | 0.0017 sn |
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
- Görsel başlığı doğrulanır, piksel akışı decode edilmez; bozuk ama imza taşıyan dosya kabul edilebilir.
- JSON append her eklemede tüm dosyayı yeniden yazıyor. 1.000 kayıt ölçümü bu maliyeti gösteriyor; eşzamanlı process/çok worker veya büyüyen geçmiş için SQLite'a geçiş gerekir.
- Bundle 500 KB eşiğini aşıyor. Bu çalışma diliminde code-splitting yapılmadı.
- GitHub Actions `feat: add a local mistake review loop`, review undo ve sonraki docs commit'lerinde frontend/backend job'ları başarıyla tamamlandı. XP/seri derived summary workflow'u şu an çalışıyor. Tarayıcı tabanlı uçtan uca akış çalıştırılmadı.
- Yerel `git write-tree` ve GitHub ilerleme dalının tree SHA'sı `55fcba2eb952846ef60936e6bf9bb978daf132c6` ile eşleşti; kaynak `master` `c5642d0` kaldı.

## Model sınırı

Bu rapordaki tüm kontroller ve benchmarklar model çağrısı içermez. Yerel AI'nın donanım, model, prompt ve yanıt kalitesi ölçümleri başka bilgisayarda ayrıca yapılmalıdır.

## 2026-11-14 Cosmos görünümü

- `CosmosTab` artık `/user` ve `/questions/insights` GET uçlarından seviye/XP/seri ve en çok dokuz bekleyen konu yörüngesini gösteriyor. Veri yerelde türetiliyor; ekran Cosmos veya kullanıcı verisine yazmıyor ve AI çağırmıyor.
- Frontend testleri 4/4 geçti; XP progress sınırları ve seviye eşiği assert edildi. `npm run build` 17.64 sn'de geçti.
- Üretim bundle: 668.34 KB minified / 191.82 KB gzip. 500 KB uyarısı devam ediyor.
- Ortak XP barı yardımcılarında ilk seviye hedefi 500 XP olacak şekilde backend formülüyle hizalandı; navbar ve Cosmos aynı hesaplamayı kullanıyor.
- `chromium`, `firefox`, Playwright ve Puppeteer bu ortamda bulunmadığı için tarayıcı smoke/ekran okuyucu kontrolü yapılmadı. Erişilebilir progressbar semantiği derleme ve kaynak seviyesinde kontrol edildi.
- Cosmos saldırı API'si ekrana bağlanmadı: XP ve cosmos JSON'ları ayrı yazılıyor, eşzamanlı çağrılarda tutarsızlık/kayıp olasılığı var; başarısız saldırı da beklenen bahis/refund akışını uygulamıyor. Önce ayrı bir backend işi ve testler gerekiyor.
- Son kod commit'i `0c72061` ve onu izleyen dokümantasyon commit'i için GitHub Actions frontend test/build, backend unittest ve iki AI'siz benchmark adımlarının tamamında başarılı oldu (run `43603845596`). Workflow model servisi çağırmıyor.
