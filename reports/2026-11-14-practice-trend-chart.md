# 2026-11-14 konu çalışma grafikleri ve tam geçmiş — uygulama ve doğrulama

## Değişiklik

Her ders/konu çalışma kartında kayıtlı setlerin tüm tarih sıralı noktalarıyla iki küçük grafik var: set neti ve yalnızca cevaplanan soru paydasındaki doğruluk. Boş-only set doğruluk çizgisine nokta üretmez. Son altı setin düzenleme/silme eylemleri doğrudan görünür, eskiler açılır geçmişte yönetilebilir. Liste/özet istekleri farklı anda tamamlanırsa listede eşleşmeyen kayıt için hatalı eylem gösterilmez. Model veya backend veri biçimi değişmedi.

## Doğrulama

- Backend regression: 72/72 test geçti.
- Frontend: `npm test` — 4/4 geçti.
- Production build başarılı: JS 695.22 KB minified / 198.14 KB gzip; 500 KB chunk uyarısı sürüyor.
- Chromium smoke: tek noktalı, 8 noktalı, aynı tarihli, tüm yanıtları boş olan grafikler; 390 px taşmama; 6'dan eski seti düzenleme ve silme; net/doğruluk etiketleri doğrulandı. Practice graph + full-history edit/delete bölümü 1.420 sn; AI isteği yok.
- AI'siz konu seti depolama/özet benchmarkı, 20 konu: 1.000 set — özet 0.007644 sn, yazma 0.009294 sn, okuma 0.023394 sn; 10.000 set — özet 0.043044 sn, yazma 0.089774 sn, okuma 0.233654 sn.

## Sınırlamalar

Her konu kartında iki grafik bulunur; çok fazla farklı konu aynı anda kayıtlıysa sayfa uzar. Mevcut veriler yalnızca kullanıcının kaydettiği setleri temsil eder. Yerel AI bu kontrol ve ölçümlere dahil edilmedi.
