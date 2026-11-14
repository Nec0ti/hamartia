# Backlog

## P0 — veri bütünlüğü

- [x] Liste okuma bozuk/kısmi JSON'ı sessizce boş veri gibi göstermesin.
- [x] Etiketleme, analiz sonucu kaydetme ve silme işlemleri atomik read-modify-write olsun.
- [x] Rakip güncellemelerde hiçbir kayıt kaybolmadığını test et.
- [ ] Yerel model/endpoint hatası sahte bir Council teşhisi veya hata etiketi olarak kaydedilmesin; hatayı görünür kıl ve kayıtları koru.

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
- [x] Deneme bağlamından yanlış eklerken soru numarası, çözüm sırası ve soru süresini sakla; kaydedilen yanlışların sıra ve süre dağılımını göster.
- [x] Tamamlanan konu çalışma setlerini ayrı kayıt et; yalnızca bu setlerden net, cevaplanan soru doğruluğu ve konu trendi üret.
- [x] Öncelikli konudan odaklı çalışma oturumu başlat; süre ve doğru/yanlış/boş sayaçlarını takip edip bitince mevcut set kaydına dönüştür.
- [x] Konu çalışma setlerinde net ve doğruluk eğilimlerini grafikle göster; son altı kaydın öncesindeki setler için de düzenle/sil erişimi sağla.
- [x] Yerel API ve frontend'i tek komutla başlat; readiness ve port çakışmasını kontrol et.

## P2 — doğrulama ve sağlamlaştırma

- [x] Formül, sınır doğrulama, kayıt ve görsel rotası için AI dışı backend testleri.
- [x] Depolama ve soru iş akışı benchmarkları; frontend test/build baseline'ı.
- [x] Gerçek tarayıcı akışında uçtan uca smoke ve temel erişilebilirlik kontrolü.
- [x] Frontend bağımlılıklarını güncel advisory'lere karşı online audit et.
- [x] Vite güvenlik yamasını ve frontend bağımlılık kurulum/build'ini doğrulama.
- [x] Bozuk JSON ve eski CouncilAnalysis biçimi davranışlarını doğrulama.
- [x] Ayarlar'dan API anahtarı hariç ZIP yedeği indirme ve uygulama kapalıyken doğrulamalı geri yükleme.
- [x] Geri yüklemeden önce mevcut veri klasörünü snapshot olarak tutma ve dizin değişimini process lock ile koruma.
- [x] Temsilî veri boyutunda yedek oluşturma, doğrulama ve geri yüklemeyi AI'siz benchmarka alma.

## P3 — diğer bilgisayarda doğrulama

- [ ] Uygulamanın kaydettiği OpenAI uyumlu endpoint/model ayarını ayrı bilgisayarda doğrula.
- [ ] Multimodal endpoint'e görsel gidişini gerçek modelle doğrula; yerel AI testi ve benchmarkını bu depoda çalıştırma.

## Sonraki küçük iş

Model çağrısı hatasında teşhisi/etiketi koru ve hatayı kullanıcıya göster: [uygulama planı](reports/2026-11-14-ai-failure-handling-plan.md). Ardından diğer bilgisayarda text-only ve görselli soruyla manuel doğrula.
