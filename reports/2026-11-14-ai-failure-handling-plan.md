# 2026-11-14 yerel model hata işleme — plan

## Bulgu

`AIService._completions()` OpenAI uyumlu endpoint'ten gelen `OpenAIError` hatasını boş metne çeviriyor. `analyze_question()` bu metni varsayılan bir Council sonucuna dönüştürüyor; `/questions/{id}/analyze` bu sonucu kaydedip `[Distractor Trap]` etiketini yazabiliyor. Böylece erişilemeyen endpoint, yanlış model adı, yetkilendirme veya multimodal destek sorunu gerçek teşhis gibi görünür.

## Değişiklik

- Provider hatasını `_completions()` üzerinden yukarı taşı.
- Analyze rotasında hatayı 502 API cevabına dönüştür; UI'nin mevcut hata yüzeyinde göster.
- Başarısız çağrıda mevcut analysis ve `hamartia_tag` değişmediğini doğrula.
- Mevcut `Yerel AI ile incele` eylemini başka bilgisayarda text-only, ardından görselli soruyla elle doğrula; yeni probe endpoint'i ekleme.

## Sınır ve kabul

- Automated test provider hatasını fake `OpenAIError` ile sınar, gerçek local model veya endpoint çağırmaz.
- Test/benchmarkta prompt, model çıktısı, kalite, inference gecikmesi veya kaynak kullanımı ölçülmez.
- Başarılı çağrı davranışı, Council şeması ve görsel payload'ı değiştirilmez.
- Fake provider hatasında API 502 döner; kayıtlı soru/etiket aynı kalır; local model test ve benchmark dışında kalır.
