# 2026-11-14 odaklı konu çalışma oturumu — uygulama ve doğrulama

## Kapsam

Çalışma önceliği kartından bir oturum başlatılabiliyor. Oturumda doğru/yanlış/boş sayaçları ve elapsed time var; sayaçlar sıfırda kalır, timer duraklatılıp sürdürülebilir. Açık taslak aynı tarayıcı profilindeki `localStorage` alanına yazılır, refresh sonrası devam eder. En az bir soru sayımı girilince bitirme mevcut `POST /practice` API'sine bir kayıt ekler. Kullanıcı kendi soru materyalini kullanır; Hamartia soru/cevap sağlamaz.

## Doğrulama

- Backend regression: 72/72 test geçti; backend kodu değişmedi.
- Frontend: `npm test` — 4/4 geçti.
- Chromium smoke: tamamlanmamış oturum bitişi reddedildi; doğru ve boş artırıldı, sıfır yanlış azaltma 0'da kaldı; duraklatma ve yenileme sonrasında geçen süre sabit kaldı; sürdürme sonrası oturum kaydedildi ve yedeğe giren tamamlanmış kayıt doğrulandı. AI endpoint çağrısı gözlenmedi (`ai_included: false`).
- Browser süreleri: navigation 2.785 sn, manuel practice persistence 1.372 sn, focused session lifecycle 3.633 sn, capture/review persistence 2.434 sn, exam CRUD 3.105 sn, question edit/delete 0.462 sn, backup download 0.284 sn.
- Frontend production build başarılı: JS 693.16 KB minified / 197.39 KB gzip; mevcut 500 KB chunk uyarısı sürüyor.
- GitHub Actions run #65, backend ve frontend işleriyle başarılı.

## Sınırlamalar

Devam eden oturum tarayıcı deposunda kalır ve ZIP yedeğine dahil değildir. Tarayıcı depolaması silinirse yalnızca henüz tamamlanmamış taslak kaybolur; tamamlanmış oturum uygulamanın yerel verisindedir ve ZIP yedeğine alınır. Sayaçlar öğrenci tarafından bildirilen sonuçlardır. Yerel AI bu kontrollerde çalıştırılmadı.
