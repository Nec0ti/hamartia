# Backlog günlüğü

## 2026-11-14

- İlk backlog oluşturuldu; kapsam kaynak kod ve eski proje notuna dayalı, kullanıcıyla henüz UX kararları netleştirilmedi.
- `codex/hamartia-rebuild` dalı GitHub'da `master` başlangıç commit'i `c5642d0` üzerinden açıldı.
- Yerel çalışma kopyası GitHub tree/blob içerikleriyle kuruldu; tree SHA kaynak ağaçla eşleşti. DNS kısıtı nedeniyle normal Git taşıması kullanılamıyor.
- Local AI test ve benchmark kapsamı dışında tutuldu.
- Deneme POST akışındaki zorunlu-id sözleşmesi ve geçmişi silen kayıt davranışı düzeltildi; path-paylaşımlı kilit altında append eklendi.
- Dört backend kontrolü geçti; 1.000 JSON kayıt benchmarkı 12.4065 sn append (80.60 kayıt/sn), 0.0091 sn read ölçtü.
- `npm ci --offline`, Vite paketi npm önbelleğinde olmadığı için tamamlanamadı; frontend build ve browser smoke henüz doğrulanmadı.
- 2026-11-14: Backlog, gerçekleşen UI/test/build adımlarıyla güncellendi; sıradaki hedef veri bütünlüğü yarışlarını çözmek oldu.
- 2026-11-14: Kilitli `update_list`, katı JSON liste okuma ve eşzamanlı silme/append testleri eklendi; 13 backend testi geçti. Hamartia'nın doküman listesi için dict koleksiyon round-trip'i sağlandı.
- 2026-11-14: Yerel, AI'siz Çalışma Planı ekranı ve `/questions/insights` eklendi. 14 backend testi, 3 frontend testi geçti; 100 yanlış için öncelik hesabı 0.0031 sn.
- 2026-11-14: Vite 6.4.6 yamalı sürüme alındı; offline temiz kurulum/test/build/audit cache kontrolü geçti. Bundle 659.95 KB; tarayıcı smoke ve GitHub Actions sonucu hâlâ bekliyor.
- 2026-11-14: Görsel yüklemeye PNG/JPEG/WebP imza kontrolü eklendi. 14 backend testi geçti, 100 soru benchmarkı 0.5873 sn upload ölçtü; GitHub Actions yeni commit için sırada.
- 2026-11-14: Yerel kurulum ve model endpoint ayarı README'ye eklendi; AI istemcisi kayıtlı ayarı kullanıp görseli payload'a alıyor. Gerçek local model başka bilgisayarda doğrulanmadı.
- 2026-11-14: Deneme girişi ISO tarih ve 0-59 saniye aralığıyla sınırlandı; 14 backend testi, frontend test/build ve GitHub Actions geçti.
- 2026-11-14: Yanlış soru tekrar edildi durumu, geri alma ve bekleyen konu önceliği eklendi. 16 backend, 3 frontend testi ve model çağrısız benchmark geçti; ilk yeni CI akışı başarılı.
- Yeni AI dışı soru-flow ölçümü: `reports/2026-11-14-storage-and-study-plan.md`.
- 2026-11-14: Review undo ve docs commit'lerinde GitHub Actions frontend/backend işleri başarılı; local ve remote branch tree'leri eşleşti, `master` değişmedi.
- 2026-11-14: XP toplamı/level/seri artık deneme geçmişinden hesaplanıyor ve profil bonusunu koruyor; 20 backend testi, 3 frontend testi ve 1000 deneme progression benchmarkı geçti. GitHub Actions çalışıyor.
- Ölçüm raporu: `reports/2026-11-14-storage-and-study-plan.md`.
- 2026-11-14: Cosmos yer tutucusu salt okunur yerel ilerleme görünümüne çevrildi; XP/seviye/seri ve en çok dokuz bekleyen konu yer alıyor. 4 frontend testi ve 18.49 sn production build geçti. Browser smoke ortamda browser/Playwright olmadığı için yapılmadı. Eski random assault endpointinin çok dosyalı XP yazımı ve ödül semantiği incelenip UI kapsamı dışında bırakıldı.
