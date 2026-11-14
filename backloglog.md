# Backlog günlüğü

## 2026-11-14

- İlk backlog oluşturuldu; kapsam kaynak kod ve eski proje notuna dayalı, kullanıcıyla henüz UX kararları netleştirilmedi.
- `codex/hamartia-rebuild` dalı GitHub'da `master` başlangıç commit'i `c5642d0` üzerinden açıldı.
- Yerel çalışma kopyası GitHub tree/blob içerikleriyle kuruldu; tree SHA kaynak ağaçla eşleşti. DNS kısıtı nedeniyle normal Git taşıması kullanılamıyor.
- Local AI test ve benchmark kapsamı dışında tutuldu.
- Deneme POST akışındaki zorunlu-id sözleşmesi ve geçmişi silen kayıt davranışı düzeltildi; path-paylaşımlı kilit altında append eklendi.
- Dört backend kontrolü geçti; 1.000 JSON kayıt benchmarkı 12.4065 sn append (80.60 kayıt/sn), 0.0091 sn read ölçtü.
- `npm ci --offline`, Vite paketi npm önbelleğinde olmadığı için tamamlanamadı; frontend build ve browser smoke henüz doğrulanmadı.
