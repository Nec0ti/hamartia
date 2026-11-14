---
name: hamartia-workflow
description: Hamartia YKS takip uygulamasında değişiklik, yerel AI sınırı ve benchmark iş akışı.
---

# Hamartia iş akışı

1. `AGENTS.md`, `notes.md`, `backlog.md` ve en son `reports/` kaydını oku.
2. Değişikliğin kullanan API/UI noktalarını ve JSON veri uyumluluğunu incele.
3. Tek, öğrenciye görünen bir dikey dilim seç; ilgili backend ve frontend parçalarını aynı iş içinde tamamla.
4. AI dışı davranışı test et; gerçek local AI servisini çağırma.
5. Test/benchmark komutlarını ve sonuçları tarihli `reports/` raporuna yaz.
6. Her tamamlanan küçük dilimi commit et; GitHub'a aktarırken kaynak dal SHA'sını, yeni commit SHA'sını ve ref sonucunu doğrula.
7. Veri export/restore değişikliklerinde tüm kayıt türlerini ve `uploads/` dizinini say; secret alanlarını dışarıda tut, arşivi staging'de tamamen doğrula ve eski veriyi swap öncesi koru. Restore'u uygulama process lock'u ile çakışmaya karşı denetle.
8. Sınav bağlamlı yanlış analizlerinde ölçüm paydasını açık belirt; yalnızca yanlış kaydı olan sorulardan doğruluk oranı türetme. Eski soru JSON'ları geriye uyumlu okunmalı ve silinmiş sınav ilişkileri özetleri kirletmemeli.
9. Konu başarı ölçüsünü yalnızca tamamlanmış `practice_sessions.json` kayıtlarından üret; doğruluk paydasında boş soruları çıkar ve eski backup arşivlerini yeni liste dosyası olmadan da kabul et.
10. Odaklı oturum taslağı yalnızca aynı tarayıcı profilinde geçici saklanır; tamamlanan sonuçları mevcut practice API'sine bir kez yaz ve gerçek model çağırma.
11. Konu trend grafikleri yalnızca kayıtlı çalışma setlerinden üret; null doğruluğu sıfır gibi çizme ve son altıdan eski setler için de yönetim eylemi bırak.

## Ölçüm kuralı

Net hesapları, depolama, API, UI build ve model çağrısız smoke akışları kapsama dahildir. Model açılışı, yanıtı, kalitesi, gecikmesi ve donanım tüketimi kapsam dışıdır.
