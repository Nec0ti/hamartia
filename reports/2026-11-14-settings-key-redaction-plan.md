# Ayar API anahtarı gizleme planı

## Sorun

`GET /settings` ve `PATCH /settings` tam `Settings` modelini döndürüyor. Bu modelin `api_key` alanı React state'ine de kopyalanıyor. Uygulamanın belgelenen başlatıcısı loopback ile sınırlı olsa da aynı makinedeki süreçler ve izinli tarayıcı origin'leri anahtarı okuyabilir.

## En küçük güvenli değişiklik

- API yanıtı `api_key` değerini hiçbir zaman döndürmesin; yalnızca anahtar ayarlı mı bilgisini versin.
- PATCH'te boş/atlanmış anahtar var olan anahtarı korusun; açık `clear_api_key` işareti anahtarı temizlesin. Yeni girilen anahtar mevcut anahtarın yerini alsın.
- Ayarlar modalında boş alanın anahtarı koruduğu yazsın ve kayıtlı anahtarı temizlemek için açık bir kontrol bulunsun.
- Saklama biçimini ve yedek uyumluluğunu değiştirme.

## Etkilenen sözleşme ve kapsam

- Çağıranlar: `frontend/src/App.jsx`, `frontend/src/components/SettingsModal.jsx`, `frontend/src/services/api.js` ve backend'deki `/settings` rotası.
- Testler: yeni settings API testlerinde GET/PATCH yanıtının gizliliği, boş değerle koruma, yeni değerle değiştirme ve açık temizleme kapsansın.
- AI servisi, model çağrısı ve benchmark akışı değişmeyecek. Tüm kontroller sahte ayarlarla çalışacak.

## Kabul ölçütleri

- Hiçbir `/settings` yanıtında sır saklı anahtar bulunmuyor.
- Var olan istemci alanları GET sonrası normal şekilde düzenlenip kaydedilebiliyor.
- Anahtar girilmeden kayıt yapmak mevcut anahtarı kaybetmiyor; yeni anahtar yazılabiliyor; kullanıcı açıkça temizleyebiliyor.
- Backend testleri, frontend test/build ve mevcut AI'siz browser smoke geçiyor.
- Ölçüm: burada AI dışı yol değişmediği için benchmark sonucu eklenmeyecek; uçtan uca ayar ve API kontrolleri raporlanacak.

## Sıra

1. Bu planı ve backlog maddesini commit et.
2. Ayar yanıt/güncelleme şemasını, form etkileşimini ve API regresyon testlerini tek küçük kod commitinde değiştir.
3. Backend/frontend/browser kontrollerini çalıştır, sonucu raporla ve ayrı docs commit yap.

## Bilinen sınır

Bu, yerel makinede aynı kullanıcı yetkisiyle çalışan güvenilmeyen süreçlere karşı bir gizli kasa değildir. Ama HTTP/UI üzerinden anahtarın gereksiz ifşasını kaldırır.
