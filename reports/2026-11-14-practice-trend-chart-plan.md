# 2026-11-14 konu çalışma grafiği ve tam geçmiş — plan

## Bulgular

Proje notları ilerlemeyi grafiklerle izleme gereksinimi taşıyor. `practice_topic_summaries()` her konu için kronolojik `{date, net, accuracy}` noktaları üretmiş olsa da arayüz bunlardan yalnızca son altı setin metin netini gösteriyor; doğruluk eğilimi görünmüyor. Altıdan eski setlere ait düzenle/sil eylemi de arayüzde bulunmuyor. Kullanılan Recharts paketiyle yeni veri/API katmanı eklemeden bu boşluk kapatılabilir.

## Kapsam

- Her ders/konu kartında set sırasına göre net ve doğruluk için iki küçük ayrı çizgi grafiği göster.
- Doğruluk yüzde ölçeğinde, yalnızca cevaplanan soru paydasıyla çizilir; boş yanıtlardan doğruluk noktası çıkmaz.
- Grafiğe bütün kayıtlı setleri ver; set listesinde son altı kayıt doğrudan yönetilebilir kalsın, daha eskiler açılır tam geçmişte düzenlenip silinebilsin.
- Aynı gün içindeki birden fazla kayıt kronolojik sırada ayrı noktalar olarak kalır.
- Mevcut API/model/depolama değişmez; gerçek AI çağrısı yok.

## Kabul ve kontroller

- İki setli fixture'da net ve doğruluk değerleri eksiksiz, tarih sıralı ve AI'siz görünür.
- Tek setli / hepsi boş yanıtlı trend hata veya NaN üretmeden render edilir.
- 6'dan eski kayıt açılır listeden düzenlenip silinebilir; son altı eylemi çalışır durumda kalır.
- 390 px görünüm taşmaz; grafiklerin erişilebilir adı vardır.
- Frontend test/build, backend regression ve browser smoke/perf ölçümü güncellenir.
