# 2026-11-14 konu çalışma setleri — uygulama ve doğrulama

## Kapsam

Çalışma Planı'na ayrı konu çalışma seti kaydı eklendi. Tarih, ders, konu, doğru/yanlış/boş ve dakika alanları saklanır. Backend neti `doğru - yanlış/4`, doğruluğu `doğru / (doğru + yanlış)` olarak hesaplar; boş sorular doğruluk paydasına girmez. Ders/konu özetleri yalnızca bu kayıtları toplar. Setler düzenlenip silinebilir. `practice_sessions.json` ZIP yedeğine dahil edildi; eski v1 arşivinde bu dosya yoksa boş listeyle restore edilir.

## Doğrulama

- Backend: `cd backend && /tmp/hamartia-venv/bin/python -m unittest discover -s tests -q` — 72 test geçti.
- Frontend: `cd frontend && npm test` — 4/4 geçti.
- Üretim derlemesi: `cd frontend && npm run build` — başarılı; ana JS 689.01 KB minified / 196.30 KB gzip. Vite'ın 500 KB chunk uyarısı sürüyor.
- Gerçek Chromium smoke: practice formu gönderildi, API yanıtı ve sayfanın yeniden yüklenmesi sonrası kayıtlı sonuç doğrulandı. Ölçümler: navigation 2.475 sn, practice persistence 1.436 sn, mistake capture/review persistence 2.850 sn, exam CRUD 3.245 sn, question edit/delete 0.493 sn, backup download 0.262 sn. `ai_included: false`.
- Benchmark: `PYTHONPATH=backend python backend/benchmarks/benchmark_practice_sessions.py` — 1.000 set/20 konu: özet 0.007639 sn, yazma 0.017720 sn, okuma 0.028008 sn; 10.000 set/20 konu: özet 0.055283 sn, yazma 0.107469 sn, okuma 0.317847 sn. Ölçüm model yüklemez/çağırmaz.
- GitHub Actions run #63 (`c1da9aa`) backend ve frontend işleriyle, yeni practice-session benchmarkı dahil, başarılı.

## Sınırlamalar

Build büyük chunk uyarısı veriyor. Tarayıcı süreleri bu makinenin yerel ölçümüdür. Yerel model ve görsel aktarımı başka bilgisayarda sınanmadı ve bu test/benchmarklara dahil edilmedi.
