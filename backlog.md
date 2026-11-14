# Backlog

## P0 — veri bütünlüğü

- [x] Liste okuma bozuk/kısmi JSON'ı sessizce boş veri gibi göstermesin.
- [x] Etiketleme, analiz sonucu kaydetme ve silme işlemleri atomik read-modify-write olsun.
- [x] Rakip güncellemelerde hiçbir kayıt kaybolmadığını test et.

## P1 — öğrenci döngüsü

- [x] Deneme girme, geçmişi koruma, yanlış görselini yerel kaydetme ve etiketleme.
- [x] Ana sayfa ve Yanlışlarım sekmesini gerçek akışa bağlama.
- [x] Ders/konu hata örüntülerinden deterministik çalışma önceliği çıkarma.
- [ ] Cosmos ve Çalışma Koçu yer tutucularını amaca uygun ekranlara dönüştürme.

## P2 — doğrulama ve sağlamlaştırma

- [x] Formül, sınır doğrulama, kayıt ve görsel rotası için AI dışı backend testleri.
- [x] Depolama ve soru iş akışı benchmarkları; frontend test/build baseline'ı.
- [ ] Gerçek tarayıcı akışında uçtan uca smoke ve erişilebilirlik kontrolü.
- [x] Vite güvenlik yamasını ve frontend bağımlılık kurulum/build'ini doğrulama.
- [x] Bozuk JSON ve eski CouncilAnalysis biçimi davranışlarını doğrulama.

## Sonraki küçük iş

Cosmos sekmesini AI'siz yerel ilerleme ekranına dönüştürme; tarayıcı smoke imkanını doğrulama.
