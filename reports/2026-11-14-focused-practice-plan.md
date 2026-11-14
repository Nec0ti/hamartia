# 2026-11-14 odaklı konu çalışma oturumu — plan

## Amaç

Öğrenciyi yalnızca tamamlanmış set girmeye bırakmak yerine, Çalışma Planı'ndaki öncelikli konudan kendi materyaliyle gerçekten çalışmaya başlatmak. Dış soru bankası veya platform içeriği eklenmeyecek.

## Akış

1. Öncelik kartından "Odaklı çalış" seçilir ve ders/konu oturum açılışına gelir.
2. Oturum başlayınca süre ve doğru/yanlış/boş sayaçları gösterilir. Sayaçlar sıfırın altına inmez; oturum duraklatılıp sürdürülebilir.
3. Aktif taslak tarayıcı `localStorage` alanında saklanır; sayfa yenilenince oturum ve süre kaldığı yerden devam eder.
4. Bitirirken en az bir soru sonucu gerekir. Oturum süresi dakika+saniyeye çevrilerek mevcut `POST /practice` şemasına bir kez kaydedilir; var olan topic özetleri güncellenir.

## Sınırlar ve riskler

- Yeni backend modeli veya API gerekmez; tamamlanan kayıt mevcut `practice_sessions.json` ve ZIP yedeğinde yer alır.
- Tamamlanmamış taslak yalnızca aynı tarayıcı profilinde tutulur ve ZIP yedeğine girmez. Tarayıcı verisi silinirse aktif oturum geri getirilemez.
- Hamartia soru veya cevap sağlamaz; öğrenci kendi materyalini çözer ve sonucu kendisi işaretler.
- Herhangi bir AI endpoint'i kullanılmaz.

## Doğrulama

- Timer başlangıç, duraklatma, sürdürme ve yenileme sonrası elapsed time.
- Doğru/yanlış/boş sayaçları ve sıfırın altına inme engeli.
- Sıfır sonuçla kayıt reddi; tamamlama tek bir kayıt üretir ve konu özetinde görünür.
- Chromium smoke, frontend test/build, backend regression ve AI'siz benchmarklar.
