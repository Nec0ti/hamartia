# Backlog

## P0 — veri bütünlüğü

- [ ] Liste okuma bozuk/kısmi JSON'ı sessizce boş veri gibi göstermesin.
- [ ] Etiketleme, analiz sonucu kaydetme ve silme işlemleri atomik read-modify-write olsun.
- [ ] Rakip güncellemelerde hiçbir kayıt kaybolmadığını test et.

## P1 — öğrenci döngüsü

- [x] Deneme girme, geçmişi koruma, yanlış görselini yerel kaydetme ve etiketleme.
- [x] Ana sayfa ve Yanlışlarım sekmesini gerçek akışa bağlama.
- [ ] Ders/konu hata örüntülerinden deterministik çalışma önceliği çıkarma.
- [ ] Cosmos ve Çalışma Koçu yer tutucularını amaca uygun ekranlara dönüştürme.

## P2 — doğrulama ve sağlamlaştırma

- [x] Formül, sınır doğrulama, kayıt ve görsel rotası için AI dışı backend testleri.
- [x] Depolama ve soru iş akışı benchmarkları; frontend test/build baseline'ı.
- [ ] Gerçek tarayıcı akışında uçtan uca smoke ve erişilebilirlik kontrolü.
- [ ] Canlı frontend bağımlılık güvenlik güncellemelerini doğrulama.
- [ ] Mevcut JSON kayıtları için bozuk/kısmi/eski biçim davranışlarını doğrulama.

## Sonraki küçük iş

P0 atomik koleksiyon güncellemeleri ve malformed JSON davranışı.