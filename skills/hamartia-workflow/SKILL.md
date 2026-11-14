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

## Ölçüm kuralı

Net hesapları, depolama, API, UI build ve model çağrısız smoke akışları kapsama dahildir. Model açılışı, yanıtı, kalitesi, gecikmesi ve donanım tüketimi kapsam dışıdır.
