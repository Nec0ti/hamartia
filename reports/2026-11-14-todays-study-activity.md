# Bugünkü çalışma etkinliği

## Kapsam

- Çalışma planı kartı bugün yanıtlanan farklı soru sayısını ve doğru/yanlış yanıt toplamlarını gösterir.
- Aynı soruya gün içinde tekrar yanıt verilirse soru metriği bir artar; sonuç sayaçları her yanıt için artar.
- Değerler `review_attempts` listesinden hesaplanır; yeni depolama alanı, ayar ya da veri migrasyonu yoktur.
- Etkinlik tarihi, aralıklı tekrar kodunun kullandığı ISO attempt gün bileşeniyle karşılaştırılır.

## Doğrulama

- `PYTHONPATH=. /tmp/hamartia-venv/bin/python -m unittest discover -s tests -v` — 45/45 geçti.
- `npm test` — 4/4 geçti.
- `npm run build` — geçti, 22.12 sn. Bundle 679.49 KB minified / 194.02 KB gzip; 500 KB chunk uyarısı devam ediyor.
- Chromium browser smoke — geçti. Yanlış/doğru yanıt sonrası yenilemede 2 farklı soru, 1 doğru ve 1 yanlış yanıt gösterildi. AI endpoint çağrısı yok; yatay taşma ve frontend/API/console hatası yok.
- Smoke süreleri: navigasyon 2.157 sn, capture+review persistence 2.335 sn, deneme CRUD 1.234 sn, soru düzenle+sil 0.409 sn.
- 100 soruluk local flow benchmarkı: insight 0.0053 sn; upload 0.604 sn, list 0.0008 sn, attempt 0.0034 sn, review 0.0038 sn, edit/delete 0.0045/0.0030 sn, text capture 0.4463 sn. `ai_included: false`.

## Sınırlar

- Model yüklenmedi ve AI çağrılmadı; local AI başka bilgisayarda doğrulanacak.
- Gün hesabı var olan scheduler gibi kayıtlı ISO zaman damgasının tarih bileşenini ve backend'in `date.today()` değerini kullanır. Backend başka saat dilimindeki bir bilgisayara taşınırsa gün sınırında kullanıcı yereliyle fark görülebilir.
- Benchmark tek yerel çalışmadır, donanımlar arası performans iddiası değildir.
- Kod commitinin GitHub Actions run #49 (`d0cd18ff`) frontend test/build/browser smoke ile backend test ve benchmark adımlarını başarıyla tamamladı. Bu rapor güncellemesini içeren docs-only run henüz çalışıyor.
