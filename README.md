# Hamartia

YKS denemelerini ve yanlış soruları bu bilgisayarda tutan, çalışma önceliğini kayıtlı hata tekrarlarından çıkaran yerel çalışma alanı. Hamartia'nın özgün bir uygulamasıdır; dış platformların içeriklerini kullanmaz.

## Yerelde çalıştırma

Python 3.12 ve Node.js 22 gerekir. İki terminal kullan:

### 1. API

Repo kökünde:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

API dokümanı `http://127.0.0.1:8000/docs` adresinde açılır.

### 2. Arayüz

İkinci terminalde:

```sh
cd frontend
npm ci
npm run dev
```

Tarayıcıda `http://localhost:5173` adresini aç.

Deneme, yanlış soru ve ayarlar `backend/data/` altında saklanır. Soru görselleri de bu dizinin `uploads/` klasöründedir. Bu klasörü düzenli olarak yedekle; içindeki veriler git'e eklenmez.

## Yerel AI bağlantısı

AI test ve benchmarklarda çalıştırılmaz. Soru görseli analizi başka bilgisayardaki OpenAI uyumlu chat-completions sunucusuna bağlanmak için hazırlanmıştır. Uygulamadaki ayarlarda sunucu adresini, sunucunun beklediği model adını ve anahtarı gir. Aynı bilgisayardaki varsayılan adres `http://localhost:4000/v1`; diğer bilgisayar için güvenilir yerel ağdaki adresini ve portunu kullan. Bağlanan modelin görsel içerik kabul etmesi gerekir.

Soru metni ve görsel baytları ayarlarda yazan sunucuya gönderilir. İnternete açık veya güvenmediğin bir endpoint kullanma. Bağlantı ve model yanıtı henüz başka bilgisayarda doğrulanmadı.

## AI dışı doğrulama

Repo kökünde backend testleri:

```sh
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
python backend/benchmarks/benchmark_storage.py
python backend/benchmarks/benchmark_questions.py
```

Frontend:

```sh
cd frontend
npm test
npm run build
npx playwright install chromium
npm run test:browser
```

Browser smoke gerçek yerel FastAPI ve Vite sunucularını geçici bir veri diziniyle açar; görselsiz soru ekleyip sonucunu, TYT/AYT/branş denemesi oluşturma-düzenleme-silme akışını ve sayfa yenileme sonrası saklamayı kontrol eder. Test için Python backend bağımlılıkları kurulu olmalı; etkin sanal ortam kullan veya `HAMARTIA_PYTHON` ile Python yolunu belirt.

Bu komutlar model yüklemez veya model endpoint'ine istek göndermez. GitHub Actions frontend test/build/browser smoke ile backend test/benchmark akışlarını çalıştırır.
