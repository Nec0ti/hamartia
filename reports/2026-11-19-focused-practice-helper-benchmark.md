# Focused practice helper benchmark

## English

### Purpose and workload

The frontend benchmark measures two deterministic, non-AI helpers used when a focused practice timer is completed: migration recovery for legacy ID-only timers and conversion of elapsed milliseconds to the stored minutes/seconds fields. The existing backend practice-profile benchmark already calls small Node bridge scripts for correctness checks; this adds direct repeated measurements of the production functions and an independently seeded fixture set.

The legacy resolver runs against 256 seeded scenarios per repeat and a 32-row session list: 16 exact matches, 208 rows with one changed field, 16 absent legacy rows, and 16 timers that must not use legacy recovery. Mismatch fixtures independently vary date, subject, topic, correct/incorrect/blank counts, and every scoring-profile identity and rule field. The duration conversion runs against 4,096 seeded nonnegative safe-integer millisecond values, including zero, second/minute/hour boundaries, and `Number.MAX_SAFE_INTEGER`. Expected resolver outcomes come from the fixture category labels rather than a second copy of the production comparison logic; duration values are calculated with `BigInt` division/remainder. Every output is checked against the oracle before timing. The measured operations run for nine repeats after two warmups; median, nearest-rank p95, minimum, and maximum are descriptive only.

### Network and scope boundary

This is a Node-only benchmark: it does not start the API, a browser, Electron, or any provider client. It dynamically imports the two production helper modules after installing fail-fast guards for fetch, sockets, DNS, TCP/TLS, UDP, and HTTP(S). The current run recorded zero network attempts. It includes no provider or model execution and sets no timing pass threshold. These runtime guards are process-level checks for the benchmark, not an OS sandbox.

### Verification

Command: `npm run bench:practice-helpers` from `frontend/`.

Environment: Linux x86_64, Node.js 26.12.1.

The run passed all 256 resolver oracles and all 4,096 duration oracles. Results:

| Measurement | p50 | p95 | Range |
| --- | ---: | ---: | ---: |
| Legacy focused-completion resolution, 256 cases | 0.1793 ms | 0.3406 ms | 0.1097–0.3406 ms |
| Duration conversion, 4,096 cases | 0.3221 ms | 0.6679 ms | 0.3013–0.6679 ms |

The run reported `provider_execution: false`, `model_execution: false`, `browser_used: false`, and `network_attempts: 0`. Timings are machine- and load-dependent and are not regression thresholds. CI invokes the new benchmark after the existing clock benchmark in the frontend job; PR CI validation remains pending.

## Türkçe

### Amaç ve iş yükü

Ön uç benchmark'ı, odaklı çalışma sayacı tamamlanırken kullanılan iki deterministik ve yapay zekâ içermeyen yardımcı işlevi ölçer: yalnızca kimlik içeren eski sayaç kayıtlarının kurtarılması ve geçen milisaniyenin saklanan dakika/saniye alanlarına çevrilmesi. Mevcut arka uç çalışma profili benchmark'ı doğruluk kontrollerinde küçük Node köprü betiklerini zaten çağırıyor; bu ekleme, üretim işlevlerini doğrudan tekrarlarla ölçer ve bağımsız, sabit tohumlu fixture'lar kullanır.

Eski sayaç çözücüsü, her tekrarda 32 satırlı oturum listesiyle 256 sabit tohumlu senaryoyu çalıştırır: 16 tam eşleşme, bir alanı değiştirilmiş 208 satır, bulunmayan 16 eski kayıt ve eski kurtarmaya girmemesi gereken 16 sayaç. Uyumsuzluk fixture'ları tarih, ders, konu, doğru/yanlış/boş sayıları ile puanlama profilinin tüm kimlik ve kural alanlarını ayrı ayrı değiştirir. Süre dönüşümü sıfır, saniye/dakika/saat sınırları ve `Number.MAX_SAFE_INTEGER` dâhil 4.096 sabit tohumlu, negatif olmayan güvenli tamsayı milisaniyeyi işler. Beklenen sayaç sonuçları üretim karşılaştırma mantığının kopyasından değil fixture kategori etiketlerinden gelir; süre oracle'ı `BigInt` bölme/kalan hesabı kullanır. Her çıktı süre ölçümünden önce oracle ile karşılaştırılır. İki ısınma turunun ardından dokuz ölçüm alınır; ortanca, en yakın sıra p95, minimum ve maksimum yalnızca bilgilendirme amaçlıdır.

### Ağ ve kapsam sınırı

Bu yalnızca Node üzerinde çalışan bir benchmark'tır: API, tarayıcı, Electron veya sağlayıcı istemcisi başlatmaz. Üretim yardımcı modüllerini yüklemeden önce fetch, soket, DNS, TCP/TLS, UDP ve HTTP(S) için hata veren korumalar kurar. Bu çalışmada sıfır ağ girişimi kaydedildi. Sağlayıcı veya model çalıştırması yoktur ve süre eşiğiyle geçme şartı kullanılmaz. Bu çalışma zamanı korumaları benchmark süreci içindeki kontrollerdir; işletim sistemi düzeyinde bir sandbox değildir.

### Doğrulama

Komut: `frontend/` dizininden `npm run bench:practice-helpers`.

Ortam: Linux x86_64, Node.js 26.12.1.

Çalıştırma 256 sayaç oracle'ının ve 4.096 süre oracle'ının tamamını geçti. Sonuçlar:

| Ölçüm | Ortanca | p95 | Aralık |
| --- | ---: | ---: | ---: |
| Eski odaklı çalışma tamamlamasını çözme, 256 senaryo | 0,1793 ms | 0,3406 ms | 0,1097–0,3406 ms |
| Süre dönüşümü, 4.096 senaryo | 0,3221 ms | 0,6679 ms | 0,3013–0,6679 ms |

Çıktı `provider_execution: false`, `model_execution: false`, `browser_used: false` ve `network_attempts: 0` bildirdi. Süreler makineye ve sistem yüküne göre değişebilir; performans eşiği değildir. Benchmark, ön uç CI işinde mevcut saat benchmark'ından sonra çalıştırılır; PR CI doğrulaması beklemededir.
