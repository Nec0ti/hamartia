# Hamartia

YKS denemelerini ve yanlış soruları bu bilgisayarda tutan, çalışma önceliğini kayıtlı hata tekrarlarından çıkaran yerel çalışma alanı. Hamartia'nın özgün bir uygulamasıdır; dış platformların içeriklerini kullanmaz.

## Yerelde çalıştırma

Python 3.12 ve Node.js 22 gerekir. İlk kurulumda:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend && npm ci
```

Günlük kullanımda repo kökünde tek terminal aç:

```sh
.venv/bin/python scripts/dev.py
```

Başlatıcı API'nin hazır olduğunu kontrol eder ve iki süreci birlikte kapatır; durdurmak için Ctrl+C kullan. Arayüz `http://127.0.0.1:5173`, API dokümanı `http://127.0.0.1:8000/docs` adresindedir. 5173 başka bir uygulamada açıksa `HAMARTIA_FRONTEND_PORT=5174 .venv/bin/python scripts/dev.py` ile boş bir port seç.

Deneme, yanlış soru ve ayarlar `backend/data/` altında saklanır. Soru görselleri de bu dizinin `uploads/` klasöründedir. Ayarlar'dan ZIP yedeği indirebilirsin. Yedekte kişisel API anahtarı bulunmaz; geri yükleme mevcut bilgisayarın anahtarını korur.

Geri yükleme sırasında uygulamayı kapat ve repo kökünde çalıştır:

```sh
.venv/bin/python scripts/restore_backup.py hamartia-backup.zip
```

Geri yükleme tüm arşivi ve kayıt şemalarını doğrular, sonra mevcut `backend/data/` klasörünü `backend/data.before-restore-.../` adıyla saklar. Windows'ta `.venv\\Scripts\\python.exe` kullan. Hamartia çalışırken işlem güvenli şekilde reddedilir.

## Yerel AI bağlantısı

AI test ve benchmarklarda çalıştırılmaz. Soru görseli analizi başka bilgisayardaki OpenAI uyumlu chat-completions sunucusuna bağlanmak için hazırlanmıştır. Uygulamadaki ayarlarda sunucu adresini, sunucunun beklediği model adını ve anahtarı gir. Aynı bilgisayardaki varsayılan adres `http://localhost:4000/v1`; diğer bilgisayar için güvenilir yerel ağdaki adresini ve portunu kullan. Bağlanan modelin görsel içerik kabul etmesi gerekir.

Soru metni ve görsel baytları ayarlarda yazan sunucuya gönderilir. İnternete açık veya güvenmediğin bir endpoint kullanma. Bağlantı ve model yanıtı henüz başka bilgisayarda doğrulanmadı.

## AI dışı doğrulama

Repo kökünde backend testleri:

```sh
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
python backend/benchmarks/benchmark_storage.py
python backend/benchmarks/benchmark_questions.py
python backend/benchmarks/benchmark_backup.py
python backend/benchmarks/benchmark_question_order.py
```

Frontend:

```sh
cd frontend
npm test
npm run build
npx playwright install chromium
npm run test:browser
```

Browser smoke `scripts/dev.py` başlatıcısıyla gerçek FastAPI ve Vite sunucularını geçici bir veri dizininde açar; görselsiz yanlış soru kaydı/tekrarını, bugünkü etkinlik özetini ve düzenleme-silme akışını, TYT/AYT/branş denemesi oluşturma-düzenleme-silme akışını ve yenileme sonrası saklamayı kontrol eder. Test için Python backend bağımlılıkları kurulu olmalı; etkin sanal ortam kullan veya `HAMARTIA_PYTHON` ile Python yolunu belirt.

Bu komutlar model yüklemez veya model endpoint'ine istek göndermez. GitHub Actions frontend test/build/browser smoke ile backend test/benchmark akışlarını çalıştırır.
