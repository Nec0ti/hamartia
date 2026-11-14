# Backlog

## P0 — veri bütünlüğü

- [x] Liste okuma bozuk/kısmi JSON'ı sessizce boş veri gibi göstermesin.
- [x] Etiketleme, analiz sonucu kaydetme ve silme işlemleri atomik read-modify-write olsun.
- [x] Rakip güncellemelerde hiçbir kayıt kaybolmadığını test et.

## P1 — öğrenci döngüsü

- [x] Deneme girme, geçmişi koruma, yanlış görselini yerel kaydetme ve etiketleme.
- [x] Ana sayfa ve Yanlışlarım sekmesini gerçek akışa bağlama.
- [x] Ders/konu hata örüntülerinden deterministik çalışma önceliği çıkarma.
- [x] Yanlış soruyu tekrar edildi diye işaretleyip planı güncelleme ve işareti geri alma.
- [x] Doğru/yanlış çözüm denemelerini tarihle saklayıp tekrar aralığını yerelde hesaplama.
- [x] Görsel zorunluluğunu kaldırıp metin tabanlı yanlış yakalama ve görünür kayıt formu sağlama.
- [x] TYT/AYT/branş deneme türünü saklama, türe göre filtreleme ve toplamları ayırma.
- [x] Deneme geçmişinin tamamında mevcut kayıtları düzenleme ve onaylı silme.
- [x] Cosmos yer tutucusunu güvenli, AI'siz yerel ilerleme akışına dönüştürme.
- [x] Kuralı net olmayan eski Cosmos saldırı/ödül rotasını 410 ile kapat; node/sector mutasyonlarını tek belge kilidi altında güvenli yaz.
- [x] Yanlış soru kayıtlarında metin/ders/konu düzeltme; görseli koruyan, uploads dışını silmeyen silme akışı.
- [x] Çalışma planında bugün denenmiş farklı soruları ve tüm doğru/yanlış yanıtlarını göster.
- [x] Yerel API ve frontend'i tek komutla başlat; readiness ve port çakışmasını kontrol et.

## P2 — doğrulama ve sağlamlaştırma

- [x] Formül, sınır doğrulama, kayıt ve görsel rotası için AI dışı backend testleri.
- [x] Depolama ve soru iş akışı benchmarkları; frontend test/build baseline'ı.
- [x] Gerçek tarayıcı akışında uçtan uca smoke ve temel erişilebilirlik kontrolü.
- [x] Frontend bağımlılıklarını güncel advisory'lere karşı online audit et.
- [x] Vite güvenlik yamasını ve frontend bağımlılık kurulum/build'ini doğrulama.
- [x] Bozuk JSON ve eski CouncilAnalysis biçimi davranışlarını doğrulama.

## P3 — diğer bilgisayarda doğrulama

- [ ] Uygulamanın kaydettiği OpenAI uyumlu endpoint/model ayarını ayrı bilgisayarda doğrula.
- [ ] Multimodal endpoint'e görsel gidişini gerçek modelle doğrula; yerel AI testi ve benchmarkını bu depoda çalıştırma.

## Sonraki küçük iş

`backend/data/` için yedek/dışa aktarma ve geri yükleme akışını veri kaybı ölçütleriyle tasarla.
