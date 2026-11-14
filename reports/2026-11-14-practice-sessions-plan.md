# 2026-11-14 konu çalışma setleri — uygulama planı

## Sorun

Çalışma Planı'ndaki konu listesi yanlış defterinde hâlâ tekrar bekleyen kayıt sayısını gösteriyor. Bu sayı konuya çalışılmış toplam soruyu veya başarıyı ölçmez; başarı yüzdesi sayılmamalı.

## Kullanıcı akışı

Öğrenci bir konu setini çözdükten sonra tarih, ders, konu, doğru/yanlış/boş sayısı ve toplam süreyi kaydeder. Aynı ders/konu için kayıtlı setlerin sıralı net ve doğruluk eğilimi görünür. Kayıt listesi düzeltme ve silme sunar; set verisi yanlış soru defterini değiştirmez.

## Veri ve hesaplama

- Ayrı `practice_sessions.json` ve `PracticeSession` modeli; var olmayan dosya boş liste olarak açılır, exams/questions biçimi değişmez.
- Doğruluk `correct / (correct + incorrect)`; boş cevap paydaya girmez. Hiç cevaplanmamış ama boş soruları olan sette doğruluk null gösterilir.
- Net `correct - incorrect / 4`.
- Eğilim yalnızca normalize edilmiş birebir `subject + topic` eşleşmesine göre gruplanır; otomatik alias birleştirmesi yapılmaz.
- Yalnızca kaydedilmiş çalışma setleri için sonuç verir; kullanıcının tüm konu bilgisi veya genel başarı yüzdesi diye sunulmaz.
- Yeni dosya backup formatına eklenir; eski backup manifest sürümü geriye uyumlu kalır ya da açık migrasyon sürümüyle okunur.

## Değişiklik yüzeyleri

- `backend/app/models/schemas.py`, yeni `backend/app/api/practice.py`, yeni `backend/app/core/practice.py`, `backend/app/main.py`.
- `frontend/src/services/api.js`, çalışma planında form ve kayıtlı set/konu trendi görünümü.
- Backup şeması/default listesi ve testleri; API/core/browser testleri.
- 1.000 ve 10.000 set için AI'siz trend özeti benchmarkı; CI'a bağla.

## Kabul ölçütleri

- Negatif sayılar, boş ders/konu, geçersiz tarih ve tümü sıfır sonuç reddedilir; eski dosya yoksa sistem boş başlar.
- Kaydetme, düzenleme ve silme kalıcıdır; aynı konu eğilimi tarih sıralı görünür.
- Doğruluk yalnızca cevaplanmış soru sayısını payda yapar; boşlar dışarıda kalır.
- Yedekleme yeni `practice_sessions.json` verisini içerir ve restore sırasında şemayı denetler.
- Browser smoke yenileme sonrası sonucu doğrular; hiçbir AI endpoint çağrılmaz.
