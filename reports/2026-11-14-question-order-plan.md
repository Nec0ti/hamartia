# 2026-11-14 deneme bağlamı ve çözüm sırası — uygulama planı

## Sorun

Deneme kayıtları yalnızca toplam doğru/yanlış/boş ve toplam süreyi saklıyor. Yanlış soru kaydı deneme kimliği, sınavdaki soru numarası, çözümde kaçıncı sırada ele alındığı veya o soruya harcanan süreyi saklamıyor. Bu yüzden deneme sırasına göre hata örüntüsü görülemiyor.

## Kullanıcı akışı

Deneme geçmişindeki satırdan yanlış soru eklemeyi açınca ders, deneme kimliği, tarih ve tür bağlamı taşınsın. Formda kullanıcı isteğe bağlı soru numarası, kendi çözüm sırası ve soru başı süreyi eklesin. Elle açılan genel yanlış soru formu eskisi gibi çalışsın.

## Veri ve hesaplama

- `Question` modeline varsayılanı boş/`None` olan `exam_id`, `question_number`, `solve_order`, `time_spent_seconds` alanları ekle; eski `questions.json` için migrasyon yapma.
- İlişkili deneme silinirse yanlış kayıtlarını tut. Deneme kimliği artık mevcut değilse sıra özetine katma.
- Çalışma planında sadece mevcut denemeye bağlı ve gerekli sıra/süre alanları dolu yanlış kayıtlarının erken/orta/geç çözüm sırasındaki adedini ve soru başı medyan süresini göster.
- Bu özet yalnızca kaydedilmiş yanlışları kapsar; doğru/boş cevapların toplamı olmadığı için doğruluk yüzdesi üretmez.
- Soru numarası ve sıra, deneme toplam soru sayısını aşamaz; süre en az bir saniyedir.

## Değişiklik yüzeyleri

- `backend/app/models/schemas.py`, `backend/app/api/questions.py`, `backend/app/core/study_plan.py`
- `frontend/src/tabs/RecentExams.jsx`, `DashboardTab.jsx`, `App.jsx`, `QuestionsTab.jsx`, `StudyPlanTab.jsx`, `frontend/src/services/api.js`
- Backend şema/API/özet testleri, frontend form testi ve browser smoke.
- 1.000 ve 10.000 soru için AI'siz özet benchmarkı.

## Kabul ölçütleri

- Eski soru JSON kayıtları varsayılan alanlarla okunur; mevcut soru ekleme akışında yeni alanlar opsiyoneldir.
- Denemeden açılan form doğru deneme bağlamını kaydeder ve yenilemede korur.
- Sınır dışı soru numarası/sıra/süre reddedilir; silinmiş deneme bağlı soru kayıtlarını silmez veya özetlemez.
- Sıra/süre özeti uç değerleri medyan ile dayanıklı biçimde toplar; eksik metadata özet dışı kalır.
- Browser smoke AI endpoint'ine gitmez. Özet benchmarkı model yüklemez/çağırmaz.
