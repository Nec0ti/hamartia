# Custom sectioned mocks

## English

### Release summary

Hamartia can now record user-defined full mock exams without tying the format to a country's official curriculum. Students name the format and each section, choose an existing versioned scoring profile, and enter each section's correct, incorrect, and blank counts. The 12-section maximum is a product safety limit, not an exam standard. Existing TYT/AYT presets and legacy `branch` records retain their previous semantics.

The manual form, history labels/type filter, custom format analytics grouping, question-section context, and profile snapshots support custom records. Study Agent offers an explicit custom capture flow for ChatGPT subscription and configured OpenAI-compatible endpoints. Its host asks for every field, validates exact quotes from the expected latest student turn, calculates the preview locally, and requires a separate approval to write. The local Study Agent CLI exposes the same draft and approval contract. Missing or uncertain values are asked again; they are never inferred. Approval replay is idempotent, altered replay is rejected, and a deleted approval is blocked by a tombstone preserved in backups.

Custom mock documentation is present in English and Turkish. It describes user-defined labels and avoids claiming official exam or curriculum alignment. The release notes below are a bilingual summary for the eventual merged release.

### Release notes

#### English

- Record custom full mocks with your own format name and up to 12 named sections.
- Select a versioned scoring profile; saved results retain the exact scoring snapshot.
- Capture every field through the Study Agent or local CLI with exact-quote checks, a full preview, and separate approval.
- Use custom format labels in history, filters, analytics, question context, and backups.
- Keep all curriculum and exam labels user-defined; no official alignment is implied.

#### Türkçe

- Kendi biçim adın ve en fazla 12 adlandırılmış bölümünle özel tam deneme kaydet.
- Sürümlü puanlama profilini seç; kayıtlı sonuçlar seçilen kuralın tam anlık görüntüsünü korur.
- Çalışma Asistanı veya yerel CLI ile tüm alanları tek tek gir; tam alıntı denetimi, önizleme ve ayrı kaydetme onayı kullan.
- Özel biçim adlarını geçmiş, filtreler, analiz, soru bağlamı ve yedeklerde kullan.
- Müfredat ve sınav etiketleri kullanıcı tanımlıdır; resmî uyum iddiası yoktur.

### Verification

- Full backend suite: 302 tests passed, one skipped (includes manual CRUD, question-section context, profile snapshot, backup round-trip, Study Agent and CLI coverage).
- Desktop: 58 tests passed, including mocked ChatGPT custom capture and IPC forwarding.
- Frontend: 61 tests passed and production Vite build succeeded. Vite reports the existing 500 KiB chunk-size advisory.
- Provider-free custom benchmark: 3 repeats passed with 12 sections, 53 evidence fields, independent section/aggregate/profile/net checks, full persisted-row oracle, idempotent retry, altered replay rejection, and ambiguous no-write. It blocks provider entry points and non-loopback network/DNS. Sample capture-plus-approval times were 0.41–0.43 seconds on this host; timing is informational only.
- Documentation generator completed successfully. Local docs browser smoke could not launch because this environment's Chromium runtime cannot load `libglib-2.0.so.0`; CI installs Playwright system dependencies and remains the browser verification gate.
- Documentation integrity benchmark passed: 17 EN/TR pages, 1,064 local links/assets, 26 answer rubrics and 156 exact evidence excerpts checked; no errors.
- No real AI/provider calls or external requests were made. Benchmark reports `ai_included: false` and installs provider plus network tripwires.

### Compatibility and review state

Custom data uses the existing `Exam` record shape with optional `format_name`; old rows that omit it continue to load as before. Section-name length is bounded only for custom exams, preserving prior TYT/AYT behavior. The custom approval tombstone ledger is optional for old backups and is included in new backups. The branch still requires rebase after PR #78 merges, independent review, and exact-head CI before it is ready to merge or release.

## Türkçe

### Sürüm özeti

Hamartia artık sınav biçimini bir ülkenin resmî müfredatına bağlamadan kullanıcı tanımlı tam denemeler kaydedebilir. Öğrenci biçime ve her bölüme ad verir, mevcut sürümlü puanlama profillerinden birini seçer ve her bölümün doğru, yanlış ve boş sayılarını girer. En fazla 12 bölüm desteği ürün güvenlik sınırıdır; sınav standardı değildir. Mevcut TYT/AYT hazır biçimleri ve eski `branch` kayıtları önceki davranışlarını korur.

Özel kayıtlar elle giriş, geçmiş etiketleri/tür filtresi, biçime göre analiz gruplaması, soru-bölüm bağlamı ve puanlama profili anlık görüntüleriyle desteklenir. Çalışma Asistanı, ChatGPT aboneliği ve yapılandırılmış OpenAI uyumlu uç noktalar için ayrı özel deneme akışı sunar. Ana bilgisayar her alanı sorar, beklenen son öğrenci mesajındaki tam alıntıyı doğrular, önizlemeyi yerel hesaplar ve kayıt için ayrıca onay ister. Yerel Çalışma Asistanı CLI aracı aynı taslak ve onay sözleşmesini kullanır. Eksik veya belirsiz değerler tahmin edilmez; yeniden sorulur. Aynı onayın tekrarı aynı kaydı döndürür, değiştirilmiş tekrar reddedilir ve silinmiş bir onay yedeklerde korunan tombstone kaydıyla yeniden oluşturulamaz.

Özel deneme belgeleri İngilizce ve Türkçe yayımlanır. Belgeler kullanıcı tanımlı adları açıklar ve resmî sınav veya müfredat uyumu iddiasında bulunmaz. Aşağıdaki iki dilli sürüm notları, PR birleştikten sonra yayımlanacak sürüm için özettir.

### Sürüm notları

#### English

- Record custom full mocks with your own format name and up to 12 named sections.
- Select a versioned scoring profile; saved results retain the exact scoring snapshot.
- Capture every field through the Study Agent or local CLI with exact-quote checks, a full preview, and separate approval.
- Use custom format labels in history, filters, analytics, question context, and backups.
- Keep all curriculum and exam labels user-defined; no official alignment is implied.

#### Türkçe

- Kendi biçim adın ve en fazla 12 adlandırılmış bölümünle özel tam deneme kaydet.
- Sürümlü puanlama profilini seç; kayıtlı sonuçlar seçilen kuralın tam anlık görüntüsünü korur.
- Çalışma Asistanı veya yerel CLI ile tüm alanları tek tek gir; tam alıntı denetimi, önizleme ve ayrı kaydetme onayı kullan.
- Özel biçim adlarını geçmiş, filtreler, analiz, soru bağlamı ve yedeklerde kullan.
- Müfredat ve sınav etiketleri kullanıcı tanımlıdır; resmî uyum iddiası yoktur.

### Doğrulama

- Tüm backend paketi: 302 test geçti, bir test atlandı (elle CRUD, soru-bölüm bağlamı, profil anlık görüntüsü, yedekleme, Çalışma Asistanı ve CLI kapsamı dahil).
- Desktop: özel ChatGPT yakalama ve IPC yönlendirmesi için taklit kullanan testler dahil 58 test geçti.
- Frontend: 61 test geçti ve üretim Vite derlemesi başarılı oldu. Vite mevcut 500 KiB parça boyutu uyarısını verdi.
- Sağlayıcısız özel benchmark: 12 bölüm, 53 kanıt alanı, bağımsız bölüm/toplam/profil/net kontrolleri, tam kayıt oracle'ı, idempotent tekrar, değiştirilmiş tekrar reddi ve belirsiz yanıtta yazmama ile 3 tekrar geçti. Sağlayıcı giriş noktaları ve loopback dışı ağ/DNS engellenir. Bu makinedeki kayıt ve onay ölçümleri 0,41–0,43 saniyeydi; süre yalnızca bilgi amaçlıdır.
- Dokümantasyon üreticisi başarılı çalıştı. Yerel Chromium ortamı `libglib-2.0.so.0` kütüphanesini yükleyemediği için doküman tarayıcı smoke testi açılamadı; CI Playwright sistem bağımlılıklarını kurar ve tarayıcı doğrulamasının kapısıdır.
- Dokümantasyon bütünlük benchmarkı geçti: 17 EN/TR sayfası, 1.064 yerel bağlantı/varlık, 26 yanıt ölçütü ve 156 kesin kanıt alıntısı denetlendi; hata yok.
- Gerçek AI/sağlayıcı çağrısı veya dış istek yapılmadı. Benchmark `ai_included: false` raporlar ve sağlayıcı ile ağ tripwire'larını etkinleştirir.

### Uyumluluk ve inceleme durumu

Özel kayıtlar isteğe bağlı `format_name` alanıyla mevcut `Exam` biçimini kullanır; bu alanı içermeyen eski kayıtlar eskisi gibi yüklenir. Bölüm adı uzunluğu yalnızca özel denemelerde sınırlıdır; TYT/AYT davranışı korunur. Özel onay tombstone dosyası eski yedeklerde isteğe bağlıdır ve yeni yedeklere eklenir. PR #78 birleştikten sonra bu dalın rebase edilmesi, bağımsız inceleme ve birleştirmeden/yayımdan önce tam kafa CI doğrulaması gerekir.
