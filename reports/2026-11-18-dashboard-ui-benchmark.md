# Dashboard chart and lazy-tab UI benchmark

## English

### Purpose and workload

This deterministic Playwright benchmark checks the Dashboard against 512 synthetic, dated Mathematics exams. Each of three repetitions starts a fresh browser context over the same temporary dataset. It validates the complete net-trend and previous-exam-change accessibility tables against independently calculated date, score, and delta rows. It also checks that the initial Dashboard does not request the Study Agent or Clock modules, then selects Study Agent and verifies its lazy module is requested successfully and the view renders.

### Measurement method

The benchmark runs the existing local development launcher, uses the shared Playwright timeout/cleanup helper, and seeds the existing temporary data-directory fixture. Requests to anything other than the two local loopback origins are blocked and counted. It reports navigation-to-complete-chart-summary time, tab-selection-to-render time, script request counts, and the transferred response-body sizes for the selected module. Timing results are descriptive only: there is no wall-clock pass threshold. Module byte counts are raw Vite development-server responses, not production bundle sizes.

### Local result

Command: `PLAYWRIGHT_CHROMIUM_EXECUTABLE=$(command -v chromium) HAMARTIA_PYTHON=/home/necoti/hamartia/.venv/bin/python npm run bench:dashboard-ui --prefix frontend` inside `nix shell nixpkgs#chromium`.

Environment: NixOS, Chromium 156.0.8078.47, Node.js 26.12.1, Python 3.14.8, Vite 6.4.6.

| Measurement | Repeat 1 | Repeat 2 | Repeat 3 | Median | Range |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dashboard navigation to both complete 512-row summaries (ms) | 8,287 | 4,551 | 4,568 | 4,568 | 4,551–8,287 |
| Study Agent selection to rendered heading (ms) | 410 | 249 | 261 | 261 | 249–410 |
| Initial frontend script requests | 53 | 53 | 53 | 53 | 53–53 |
| Requests after selecting Study Agent | 2 | 2 | 2 | 2 | 2–2 |
| Study Agent module response body (bytes) | 193,485 | 193,485 | 193,485 | 193,485 | 193,485–193,485 |

Each repetition checked 512/512 rows in both chart tables against the oracle. Study Agent and Clock were absent from initial script requests; the Study Agent module loaded after selection. `ai_included: false`, `provider_calls: 0`, `external_network_allowed: false`, and `timing_thresholds_used: false` were reported.

### CI

The benchmark is registered as `npm run bench:dashboard-ui` in the frontend CI job after the existing full-browser smoke. The CI result for the pull request must pass before merge; CI timings may differ from the local result.

## Türkçe

### Amaç ve iş yükü

Bu deterministik Playwright benchmark'ı, 512 sentetik ve tarihli Matematik denemesiyle Ana Sayfa'yı kontrol eder. Üç tekrarın her biri aynı geçici veri kümesiyle yeni bir tarayıcı bağlamı başlatır. Net grafiği ve önceki denemeye göre değişim grafiğinin erişilebilirlik tablolarındaki tüm tarih, net ve fark satırlarını bağımsız biçimde hesaplanan sonuçlarla karşılaştırır. Ayrıca ilk yüklemede Çalışma Asistanı ve Saat modüllerinin istenmediğini, Çalışma Asistanı sekmesi seçildiğinde tembel yüklenen modülün başarıyla istendiğini ve görünümün çizildiğini doğrular.

### Ölçüm yöntemi

Benchmark mevcut yerel geliştirme başlatıcısını, paylaşılan Playwright zaman aşımı/temizlik yardımcısını ve geçici veri dizini fixture'ını kullanır. İzin verilen iki yerel loopback kaynağı dışındaki tüm istekler engellenir ve sayılır. Ana Sayfa açılışından iki grafik özeti tamamen çizilene kadar geçen süreyi, sekme seçimi ile görünümün çizilmesi arasındaki süreyi, JavaScript istek sayılarını ve seçilen modülün yanıt gövdesi boyutunu raporlar. Süreler yalnızca bilgilendirme amaçlıdır; duvar saati eşiğiyle testi geçirme şartı yoktur. Modül bayt sayıları ham Vite geliştirme sunucusu yanıtlarıdır; üretim paket boyutları değildir.

### Yerel sonuç

Komut: `nix shell nixpkgs#chromium` içinde `PLAYWRIGHT_CHROMIUM_EXECUTABLE=$(command -v chromium) HAMARTIA_PYTHON=/home/necoti/hamartia/.venv/bin/python npm run bench:dashboard-ui --prefix frontend`.

Ortam: NixOS, Chromium 156.0.8078.47, Node.js 26.12.1, Python 3.14.8, Vite 6.4.6.

| Ölçüm | Tekrar 1 | Tekrar 2 | Tekrar 3 | Ortanca | Aralık |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ana Sayfa'dan iki tam 512 satırlı özete kadar (ms) | 8.287 | 4.551 | 4.568 | 4.568 | 4.551–8.287 |
| Çalışma Asistanı seçiminden başlığın çizilmesine kadar (ms) | 410 | 249 | 261 | 261 | 249–410 |
| İlk yüklemedeki ön uç betik istekleri | 53 | 53 | 53 | 53 | 53–53 |
| Çalışma Asistanı seçildikten sonraki istekler | 2 | 2 | 2 | 2 | 2–2 |
| Çalışma Asistanı modül yanıt gövdesi (bayt) | 193.485 | 193.485 | 193.485 | 193.485 | 193.485–193.485 |

Her tekrarda iki grafik tablosunun 512/512 satırı da oracle ile doğrulandı. Çalışma Asistanı ve Saat ilk isteklerde yoktu; Çalışma Asistanı modülü seçimden sonra yüklendi. Çıktı `ai_included: false`, `provider_calls: 0`, `external_network_allowed: false` ve `timing_thresholds_used: false` bildirdi.

### CI

Benchmark, mevcut tam tarayıcı smoke testinden sonra ön uç CI işine `npm run bench:dashboard-ui` olarak eklendi. Birleştirmeden önce PR CI sonucu geçmelidir; CI süreleri yerel ölçümden farklı olabilir.
