# Hamartia çalışma kuralları

- Önce `backlog.md`, `notes.md` ve son raporları oku; kapsamı küçük ve doğrulanabilir tut.
- Her tamamlanmış kod değişikliğini ayrı bir commit yap. Deneysel/bozuk ara durumu commit etme.
- Veri biçimini değiştirmeden önce `backend/data` uyumluluğunu ve geri dönüş yolunu incele; kullanıcı verisini silme.
- Local AI ayrı bir makinede denenecek. Model çalıştırma, kalite, gecikme ve kaynak kullanımı test/benchmark kapsamı dışındadır.
- AI dışındaki bütün ana akışları uygun test ve benchmarklara dahil et; ölçüm yöntemini raporda belirt.
- Bir özelliği bitmiş saymadan önce ilgili kontrolleri çalıştır ve sonucu `reports/` altında kaydet.
- API ve UI sözleşmelerini birlikte güncelle; mevcut istemci çağrılarını aramadan ortak kodu değiştirme.
- Harici eğitim platformlarının adını/içeriğini kopyalama; Hamartia'nın verisini ve kullanıcı akışını özgün tut.
