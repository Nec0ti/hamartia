# Hamartia — proje bilgi dökümü

## Amaç

YKS hazırlığında deneme sonuçlarını, yanlış soruları ve hata örüntülerini yerelde takip eden; öğrenciye neyi tekrar çalışacağını gösteren bir sistem. Esin kaynağı, ders/deneme/soru çözümü/ilerleme akışını tek platformda sunan 3-4-5 All Star. Hamartia kendi arayüzünü, verisini ve içerik akışını geliştirecek.

## Kullanıcının daha önce tarif ettiği ihtiyaç

- Deneme sonuçlarını süre ve doğru/yanlış/boş değerleriyle saklamak.
- Yanlış soruların görselini veya metnini kaydetmek.
- Ders/konu bazında hata tekrarlarını görmek.
- İlerlemeyi grafiklerle ve soruların çözüm sırasını dikkate alan ölçülerle izlemek.
- Yerel AI kullanmak; model başka bilgisayarda deneneceği için AI bileşenini test ve benchmarklardan hariç tutmak.

## Mevcut depo (GitHub `master`, 2026-11-14 incelemesi)

- Backend: Python/FastAPI, Pydantic, JSON dosya deposu (`backend/app`).
- Frontend: React 18, Vite, Tailwind, Recharts, Axios (`frontend`).
- Var olan API alanları: denemeler, sorular, kullanıcı/progres, Cosmos oyunlaştırması, AI chat/analiz, ayarlar, healthcheck.
- `backend/app/core/formulas.py`: YKS neti, XP, seviye ve ortalama net formülleri.
- `backend/app/services/storage.py`: JSON kayıtları için atomic write ve aynı dosya yoluna göre paylaşılan process içi kilit. `update_list` kilit altında read-modify-write yapar; bozuk/uyumsuz listeler `StorageError` üretir. Çok worker/multi-process kullanımda SQLite gerekir.
- `backend/app/core/study_plan.py` ve `/questions/insights`: yanlış soru kayıtlarından AI çağırmadan ders/konu tekrar sıklığı, etiket dağılımı ve son kayıt gününü çıkarır.
- Soru görseli yüklemesi uzantı/MIME türünün yanı sıra PNG/JPEG/WebP dosya başlığını doğrular; başlık kontrolü tam görüntü decode'u değildir.
- `backend/app/services/ai_service.py`: LiteLLM/OpenAI uyumlu istemci; local model çalıştırılmayacak.
- `frontend/src/App.jsx`: Dashboard, Yanlışlarım ve deterministik Çalışma Planı gerçek ekran; Cosmos hâlâ yer tutucu.
- `frontend/package.json`: Node test scripti ve AI çağrısı içermeyen formatter testleri var.
- Backend testleri `backend/tests/` altında Git'te izleniyor; AI dışı benchmarklar `backend/benchmarks/` altında.

## Eski tanı tasarımı

`HAMARTIA.md`, yanlış soruların beş farklı bakış açısıyla incelendiği tek LiteLLM çağrılı bir Council of Minds tanımlar: Dissenter, First Principles, Expansionist, Outsider, Executor ve bunları birleştiren President. Model yanıtı hata etiketi, kök neden, tavsiye, zorluk ve konu yakınlığı taşıyan JSON zarfıdır. Şema ve prompt biçimleri arasında olası uyumsuzluklar var; AI dışı çekirdek akış tasarlanmadan önce bunlara bağımlılık kurulmayacak.

## Veri ve uyumluluk notları

- `backend/data/*.json` kişisel uygulama verisi için `.gitignore` kapsamındadır.
- Mevcut depodaki veri örnekleri yok; canlı kullanımdaki şema/örnek dosyalar doğrulanmış değil.
- Yeni sistem eski JSON kayıtlarını silmemeli; şema değişikliği gerekirse geriye uyumlu okuma veya açık migrasyon planı olmalı.
- Soru görselleri `backend/data/uploads/` altında saklanıyor ve Git dışında kalmalı.

## Benchmark sınırı

Benchmarka dahil: net/istatistik hesapları, JSON depolama, API iş akışları, kayıtları listeleme/filtreleme, frontend build ve model çağrısı içermeyen UI smoke akışları.

Benchmark dışı: model yükleme/çalıştırma, prompt kalitesi, AI yanıt kalitesi, AI latency/token/VRAM/RAM ölçümleri. Testlerde AI servisi mock veya atlanmış olmalı; gerçek local AI'a istek gönderilmemeli.

## Başlangıç ve erişim kanıtı

- Kaynak: `Nec0ti/hamartia`, `master` başındaki GitHub commit `c5642d0cb2f133e641b0d1c73a12faaf57a611c6`.
- Çalışma kopyası GitHub salt-okunur blob/tree uç noktalarından geri kuruldu; yerel `git write-tree` SHA'sı kaynak ağaç `48414fcdac4bd612370a191206a95dae26686c32` ile eşleşti.
- Ortamda `github.com` DNS çözümlemesi başarısız olduğundan normal `git clone/fetch/push` yapılamıyor. İlerleme dalı GitHub API üzerinden açıldı; yayın/commit aktarımı aynı araçla yapılmalı ve her remote SHA ayrıca doğrulanmalı.
- İzole yerel checkout'un başlangıç commit'i `8255e39` kaynak commit'in kendisi değildir; yalnızca kaynak ağaç aynıdır. Bu farkı remote ile senkron kanıtı diye sunma.
- Yerel docs commit'i `6b48813`, deneme kaydı commit'i `513ce14`; GitHub branch eş ağaçları sırasıyla `a6ac8d0` ve `24c8fbef` commitlerinde. Yerel başlangıç commit'i `8255e39` kaynak `master` commit'iyle aynı SHA değil. SHA farkı, yerel kaynağın API üzerinden yeniden kurulmuş olmasından kaynaklanıyor.

## 2026-11-14 doğrulama güncellemesi

- Liste okuma bozuk/şema dışı JSON'ı boş veri gibi göstermiyor; etiketleme, analiz sonucu yazımı, deneme silme ve belge ekleme kilitli koleksiyon mutasyonlarını kullanıyor.
- 14 backend testi geçti. Python 3.14 Nix paket yolları kullanıldı; yerelde eksik `openai` ve `python_multipart` importları test harness'inde stub edildi. Gerçek AI çağrısı yapılmadı.
- Soru akışı benchmarkı: 100 yükleme 0.8692 sn (115.04/s), listeleme 0.0017 sn, çalışma önceliği 0.0031 sn. JSON depolama benchmarkı: 1.000 append 15.8939 sn (62.92/s), okuma 0.0132 sn.
- PNG imzası sınırı eklendikten sonraki 100 soru tekrarı: upload 0.5873 sn (170.28/s), listeleme 0.0010 sn, öncelik hesabı 0.0020 sn; 14/14 backend testi geçti.
- Frontend: 3 test geçti; Vite 6.4.6 build'i 21.38 sn, ana bundle 659.95 KB minified ve 190.16 KB gzip. Rollup büyük bundle uyarısı devam ediyor.
- `npm ci --offline --ignore-scripts` sandbox'ta paket kurulum script'lerini çalıştırmadan geçti; build/test başarılı. `npm audit --offline` mevcut cache'de 0 bulgu verdi; bu güncel online audit değildir.
- Vite 6.4.6'ya geçildi. Resmi GHSA-p4f5-76q4-ffq7 duyurusu 6.4.5 ve altını etkiliyor; uzaktaki istemcilerden erişilebilen dev server koşulu varsa kritik risk oluşuyor. Hamartia dev server'ı varsayılan localhost ayarıyla bırakıyor.
- GitHub CI için workflow mevcut, ancak branch güncellemesinden sonra GitHub Actions çalışması doğrulanmadı. Normal `git push/fetch` DNS nedeniyle kullanılamıyor; branch GitHub API üzerinden commitleniyor.

## Açık kararlar

- Deneme girişinde TYT/AYT genel deneme ve branş denemesi nasıl ayrılacak?
- Konu/alt konu etiketlerini kullanıcı mı girecek, başlangıçta serbest metin mi kalacak?
- Yanlış soru girişi fotoğraf, metin ve manuel hata etiketi akışlarından hangileriyle başlayacak?
- Masaüstü ve mobil yerel kullanım için hedeflenen ilk çalıştırma biçimi nedir?
