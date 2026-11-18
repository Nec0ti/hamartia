# Focused practice helper benchmark

## English

### Purpose and workload

The frontend benchmark measures two deterministic, non-AI helpers used when a focused practice timer is completed: migration recovery for legacy ID-only timers and conversion of elapsed milliseconds to the stored minutes/seconds fields. The existing backend practice-profile benchmark already calls small Node bridge scripts for correctness checks; this adds direct repeated measurements of the production functions and an independently seeded fixture set.

The legacy resolver runs against 192 seeded scenarios per repeat and a 32-row session list: 24 exact matches, 120 rows with one changed field, 24 absent legacy rows, and 24 timers that must not use legacy recovery. The duration conversion runs against 4,096 seeded nonnegative safe-integer millisecond values, including zero, second/minute/hour boundaries, and `Number.MAX_SAFE_INTEGER`. Every output is checked against an independent oracle before timing. The measured operations run for nine repeats after two warmups; median, nearest-rank p95, minimum, and maximum are descriptive only.

### Network and scope boundary

This is a Node-only benchmark: it does not start the API, a browser, Electron, or any provider client. It dynamically imports the two production helper modules after installing fail-fast guards for fetch, sockets, DNS, TCP/TLS, UDP, and HTTP(S). The current run recorded zero network attempts. It includes no provider or model execution and sets no timing pass threshold. These runtime guards are process-level checks for the benchmark, not an OS sandbox.

### Verification

Command: `npm run bench:practice-helpers` from `frontend/`.

Environment: Linux x86_64, Node.js 26.12.1.

The run passed all 192 resolver oracles and all 4,096 duration oracles. Results:

| Measurement | p50 | p95 | Range |
| --- | ---: | ---: | ---: |
| Legacy focused-completion resolution, 192 cases | 0.1403 ms | 0.2511 ms | 0.1259–0.2511 ms |
| Duration conversion, 4,096 cases | 0.1599 ms | 0.4169 ms | 0.1516–0.4169 ms |

The run reported `provider_execution: false`, `model_execution: false`, `browser_used: false`, and `network_attempts: 0`. Timings are machine- and load-dependent and are not regression thresholds. CI registration and PR validation are pending; no full CI result is claimed here.

## Türkçe

### Amaç ve iş yükü

Ön uç benchmark'ı, odaklı çalışma sayacı tamamlanırken kullanılan iki deterministik ve yapay zekâ içermeyen yardımcı işlevi ölçer: yalnızca kimlik içeren eski sayaç kayıtlarının kurtarılması ve geçen milisaniyenin saklanan dakika/saniye alanlarına çevrilmesi. Mevcut arka uç çalışma profili benchmark'ı doğruluk kontrollerinde küçük Node köprü betiklerini zaten çağırıyor; bu ekleme, üretim işlevlerini doğrudan tekrarlarla ölçer ve bağımsız, sabit tohumlu fixture'lar kullanır.

Eski sayaç çözücüsü, her tekrarda 32 satırlı oturum listesiyle 192 sabit tohumlu senaryoyu çalıştırır: 24 tam eşleşme, bir alanı değiştirilmiş 120 satır, bulunmayan 24 eski kayıt ve eski kurtarmaya girmemesi gereken 24 sayaç. Süre dönüşümü sıfır, saniye/dakika/saat sınırları ve `Number.MAX_SAFE_INTEGER` dâhil 4.096 sabit tohumlu, negatif olmayan güvenli tamsayı milisaniyeyi işler. Her çıktı, süre ölçümünden önce bağımsız oracle ile karşılaştırılır. İki ısınma turunun ardından dokuz ölçüm alınır; ortanca, en yakın sıra p95, minimum ve maksimum yalnızca bilgilendirme amaçlıdır.

### Ağ ve kapsam sınırı

Bu yalnızca Node üzerinde çalışan bir benchmark'tır: API, tarayıcı, Electron veya sağlayıcı istemcisi başlatmaz. Üretim yardımcı modüllerini yüklemeden önce fetch, soket, DNS, TCP/TLS, UDP ve HTTP(S) için hata veren korumalar kurar. Bu çalışmada sıfır ağ girişimi kaydedildi. Sağlayıcı veya model çalıştırması yoktur ve süre eşiğiyle geçme şartı kullanılmaz. Bu çalışma zamanı korumaları benchmark süreci içindeki kontrollerdir; işletim sistemi düzeyinde bir sandbox değildir.

### Doğrulama

Komut: `frontend/` dizininden `npm run bench:practice-helpers`.

Ortam: Linux x86_64, Node.js 26.12.1.

Çalıştırma 192 sayaç oracle'ının ve 4.096 süre oracle'ının tamamını geçti. Sonuçlar:

| Ölçüm | Ortanca | p95 | Aralık |
| --- | ---: | ---: | ---: |
| Eski odaklı çalışma tamamlamasını çözme, 192 senaryo | 0,1403 ms | 0,2511 ms | 0,1259–0,2511 ms |
| Süre dönüşümü, 4.096 senaryo | 0,1599 ms | 0,4169 ms | 0,1516–0,4169 ms |

Çıktı `provider_execution: false`, `model_execution: false`, `browser_used: false` ve `network_attempts: 0` bildirdi. Süreler makineye ve sistem yüküne göre değişebilir; performans eşiği değildir. CI kaydı ve PR doğrulaması beklemededir; burada tam CI sonucu iddia edilmemektedir.
