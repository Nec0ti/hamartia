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
- [x] Cosmos yer tutucusunu güvenli, AI'siz yerel ilerleme akışına dönüştürme.
- [ ] Eski Cosmos saldırı/ödül API'sini UI'ya bağlamadan önce XP bahis kurallarını ve çok dosyalı yazım atomikliğini düzelt.

## P2 — doğrulama ve sağlamlaştırma

- [x] Formül, sınır doğrulama, kayıt ve görsel rotası için AI dışı backend testleri.
- [x] Depolama ve soru iş akışı benchmarkları; frontend test/build baseline'ı.
- [ ] Gerçek tarayıcı akışında uçtan uca smoke ve erişilebilirlik kontrolü.
- [x] Vite güvenlik yamasını ve frontend bağımlılık kurulum/build'ini doğrulama.
- [x] Bozuk JSON ve eski CouncilAnalysis biçimi davranışlarını doğrulama.

## P3 — diğer bilgisayarda doğrulama

- [ ] Uygulamanın kaydettiği OpenAI uyumlu endpoint/model ayarını ayrı bilgisayarda doğrula.
- [ ] Multimodal endpoint'e görsel gidişini gerçek modelle doğrula; yerel AI testi ve benchmarkını bu depoda çalıştırma.

## Sonraki küçük iş

Gerçek tarayıcı smoke ve erişilebilirlik kontrolü için tarayıcı/Playwright ortamını kur; Cosmos saldırı/ödül API'sini ayrı ve testli bir iş olarak güvenli hale getir.
