# 2026-11-14 deneme bağlamı, çözüm sırası ve soru süresi

## Kapsam

Deneme geçmişinden yanlış eklerken deneme kimliği otomatik taşınır. İsteğe bağlı sınavdaki soru numarası, öğrencinin kendi çözüm sırası ve soru başı süre kaydedilir. Çalışma Planı, mevcut denemelerle hâlâ bağlı yanlışların erken/orta/geç çözüm sırası bölümlerini ve bölüm başına medyan süreyi gösterir.

Sadece yanlış soru defterinde bulunan kayıtlar kapsanır. Doğru/boş cevapların paydası olmadığı için sonuçlar başarı veya doğruluk yüzdesi olarak sunulmaz. Silinen sınav kayıtları soruları silmez; bu ilişki sıra özetinden çıkar.

## Doğrulama

- `PYTHONPATH=backend /tmp/hamartia-venv/bin/python -m unittest discover -s backend/tests -q` — 65/65 geçti. Eski kayıt varsayılanları, metadata doğrulaması, medyan, sıra bölmeleri ve silinmiş sınav ilişkisi kapsandı.
- `npm test` — 4/4 geçti.
- `npm run build` — başarılı, 21.82 sn; JS bundle 683.63 KB minified / 195.17 KB gzip. Vite'ın 500 KB chunk uyarısı sürüyor.
- `HAMARTIA_PYTHON=/tmp/hamartia-venv/bin/python PLAYWRIGHT_CHROMIUM_EXECUTABLE=/nix/store/r0f9i35n3r7rng8162xih4c1dag0s1vw-chromium-156.0.8078.47/bin/chromium npm run test:browser` — geçti. Deneme satırından yanlış kaydı, form metadata'sı, yenileme sonrası görünüm, erken sıra/32 sn medyanı ve sınav silindikten sonra soru saklanması kontrol edildi. Smoke ölçümleri: navigasyon 2.253 sn, capture/review 2.423 sn, deneme CRUD 2.318 sn, soru CRUD 0.354 sn, yedek indirme 0.208 sn. Browser'dan AI endpoint çağrısı yok.
- `PYTHONPATH=backend /tmp/hamartia-venv/bin/python backend/benchmarks/benchmark_question_order.py` — yalnızca özet hesabı: 1.000 kayıt 0.014627 sn (68,368 kayıt/sn), 10.000 kayıt 0.137947 sn (72,492 kayıt/sn). Veri hazırlama ve Pydantic nesnesi oluşturma süreye dahil değildir.
- `PYTHONPATH=backend /tmp/hamartia-venv/bin/python backend/benchmarks/benchmark_questions.py` — değişen soru akışı regresyon ölçümü: 100 görsel upload 0.6005 sn (166.53/s), liste 0.0008 sn, özet 0.0015 sn, text capture 1.1541 sn (86.65/s); AI çağrısı yok.
- GitHub Actions run #61 (`3d84fcc`): frontend ve backend job'ları başarılı. Backend işi tam test paketini ve JSON, soru, backup/restore, çözüm sırası benchmarklarını çalıştırdı.

## Veri uyumluluğu ve sınırlar

Yeni `Question` alanları varsayılanlı ve opsiyoneldir; eski `questions.json` kayıtlarına migrasyon gerekmez. Soru numarası/çözüm sırası ilişkili denemedeki doğru+yanlış+boş toplamını aşamaz. Soru başı süre pozitif tam saniyedir. Özet, deneme türü ve ders bazında kaydedilmiş yanlışları toplar; tam sınav doğruluğunu ölçmez.

Build uyarısı mevcut büyük bundle ile ilgilidir. Gerçek local AI çalıştırılmadı ve benchmarklara eklenmedi.
