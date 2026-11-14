# Deneme türü ve geçmiş yönetimi — 2026-11-14

## Kapsam

- Denemeyi TYT, AYT veya branş olarak kaydetme; eski JSON kayıtlarını kayıpsız okuma.
- Tür filtresini ders filtresinden ayrı tutup tür seçimini deneme toplamları ve trendlerde uygulama.
- Deneme geçmişindeki kayıtları düzenleme veya onayla silme.
- Gerçek API ve UI akışını geçici yerel veride çalıştırma; AI route'larına çağrı olmamasını doğrulama.

## Veri ve API davranışı

- `Exam.exam_type` izinli değerleri `tyt`, `ayt`, `branch`; tür içermeyen eski JSON kayıtları `branch` kabul edilir. Dosya migrasyonu gerekmez.
- `PUT /exams/{id}` kilitli `update_list` kullanır; tür ve sonuç alanlarını değiştirir, `id` ile `created_at` değerini korur. Kayıt bulunmazsa 404 döner.
- `DELETE /exams/{id}` aynı kilitli mutasyon desenini kullanır; bulunmayan kayıt 404 döner.
- Dashboard TYT/AYT/branş filtresiyle deneme sayısını, ortalama neti, trendi ve tabloyu daraltır. XP profili tüm deneme geçmişinden türemeye devam eder.
- Tüm denemeler tarihe göre sıralı listelenir; her satır düzenleme ve onaylı silme düğmeleri sunar.
- Browser smoke, oluşturulan AYT denemesini TYT + yeni ders adıyla günceller, onaylayıp siler ve geçici `exams.json` dosyasının boş kaldığını doğrular.

## Doğrulama

| Kontrol | Sonuç |
| --- | ---: |
| Backend unittest | 32/32 geçti |
| Frontend Node testleri | 4/4 geçti |
| Frontend üretim derlemesi | 20.77 sn, başarılı |
| Ana JS bundle | 676.80 KB minified / 193.58 KB gzip |
| Online `npm audit` | 0 bulgu |
| Chromium smoke navigasyon / capture+review / exam CRUD | 2.266 / 3.483 / 1.039 sn |
| 1.000 kayıt JSON append / read | 19.178 sn / 0.0078 sn |
| Tek kayıt update / delete | 0.0272 sn / 0.0237 sn |
| 1.000 kayıt progression hesabı | 0.0017 sn |
| 100 görselli yanlış kaydı | 0.3149 sn / 317.57 kayıt/sn |
| 100 text-only yanlış kaydı | 0.4523 sn / 221.11 kayıt/sn |

Komutlar:

```sh
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
python backend/benchmarks/benchmark_storage.py
python backend/benchmarks/benchmark_questions.py
cd frontend && npm test && npm run build && npm audit
cd frontend && npm run test:browser
```

## Bulunan ve düzeltilen sorunlar

- Browser smoke gerçek dashboard'da `api.user.get()` çağrıldığını, fakat default API nesnesinde `user` export'unun olmadığını gösterdi. Varsayılan export düzeltildi ve smoke ilk yüklemede bu hatanın çıkmadığını assert eder.
- Profil rozeti dar ekranda navbar'ı 390 px dışına taşıyordu. Küçük ekranda marka yazısı ve XP çubuğu gizlenip gezinme simgeleri korundu.
- Boş varsayılan radar, numeric `PolarAngleAxis` ve yinelenen `PolarRadiusAxis` yüzünden duplicate tick key ve NaN SVG çizgisi üretiyordu. Kategorik eksen ve tek yarıçap ekseniyle giderildi.

## Sınırlamalar

- Eski kayıtların gerçek sınav türü JSON'da bulunmadığı için varsayılan olarak branş sayılır; kullanıcı bu türü düzenleyebilir.
- İstatistikler seçili tür ve ders filtresine bağlıdır. XP toplamı kasıtlı olarak filtre dışıdır.
- Browser smoke örnek kayıtla CRUD ve persistence'i sınar; çok büyük geçmişlerde gerçek kullanıcı veri hacmi benchmark edilmedi.
- Local AI yüklenmedi, çağrılmadı veya benchmark edilmedi. Başka bilgisayardaki multimodal endpoint doğrulaması bekliyor.
- Üretim JS paketi 500 KB tavsiye eşiğini aşıyor; mevcut build başarılı ancak Vite uyarısı sürüyor.
- GitHub Actions run `43608878405` (#41), aynı kaynak kodu için frontend test/build/browser smoke ile backend test ve benchmark adımlarının ikisini de başarıyla tamamladı.
