# TYT/AYT oturumunda ders bazlı sonuç planı

## Kullanıcı ihtiyacı ve mevcut boşluk

İkinci Beyin'deki proje notu ve kaynak konuşma, yalnız paragraf değil tüm deneme sonuçlarını süre/doğru/yanlış/boşla saklama isteğini tarif ediyor. Depodaki `Exam` kaydı hâlâ tek `subject` ve tek sayı grubuna sahip. Bu nedenle bir TYT/AYT genel denemesi ya tek dersmiş gibi giriliyor ya da birden çok kayda bölünerek oturum/net/XP sayımı bozuluyor.

## Hedef

TYT/AYT genel denemesi tek bir kayıtta dursun; kullanıcının girdiği ders sonuçları o denemeye bağlı olsun. Toplam doğru/yanlış/boş ve net derslerden türesin, süre oturum toplamı olarak girilsin ve XP/seri/deneme sayısı oturum başına bir kez hesaplansın. Branş denemesi bugünkü tek ders girişi olarak kalsın. Ders adları serbest metin olsun; resmi test listesi sabit kodlanmasın.

## Planlanan veri sözleşmesi

- `Exam.sections` yeni ve geriye uyumlu bir listedir; eski kayıtlar ve arşivler için varsayılan `[]` olur.
- Her `ExamSection`: kırpılıp boş olmayan ders adı ile sıfır veya daha büyük doğru/yanlış/boş sayıları.
- Bölüm adları bir oturumda case-insensitive benzersiz olur; sectioned exam en az bir bölüm taşır.
- TYT/AYT section listesi varken üstteki `subject` `TYT Geneli`/`AYT Geneli` olur; doğru/yanlış/boş toplamları bölüm toplamlarından backend'de türetilir. Süre mevcut tek oturum alanında kalır. XP bu aggregate üzerinden bir kez hesaplanır.
- Branş kayıtlarında `sections=[]` ve mevcut alanlar aynen devam eder. Bölümsüz eski TYT/AYT kayıtları da okunur ve düzenlenir.
- Bölüme bağlı yanlış soru eklendiğinde mevcut `Question.subject` bölüm adı olur; API soru numarası/sıra sınırını o bölümün büyüklüğüyle doğrular ve `exam_section_total` snapshot'ını saklar. Eski/branş sorularında bu alan boş kalır. Sıra içgörüsü bölüm adına ve snapshot büyüklüğüne göre hesaplanır.

## Etki alanı

- Backend schema/API: `ExamSection`, toplam türetme/doğrulama, exam create/update, section-bağlı yanlış doğrulaması.
- Hesaplama: progression bir oturumu bir kere sayar; dashboard oturum sayısını tek tutar, ders seçiliyken o bölüm netini kullanır.
- UI: `AddExamModal` branş yolunu korur, TYT/AYT'de ders sonuç satırları ekler/düzenler. `RecentExams` tek oturum satırında ders detayını açar; her ders yanlış ekleme bağlamı taşır. `TrendChart` seçili dersin bölüm sonuçlarını çizer.
- Yedek: `Exam` şemasıyla export/restore mevcut JSON listelerini ve eski arşivleri okumaya devam etmeli; yeni section alanları round-trip etmelidir.
- Doğrulama: backend CRUD/limit/legacy/backup regresyonları, frontend test/build, gerçek tarayıcıda create → reload → edit → delete, bağlı bölüm yanlış sorusu ve trend. AI route çağrısı olmayacak.
- Benchmark: çok bölümlü oturum oluşturma/update/list ve bölüm trend projeksiyonunun maliyetini ayrı, AI'siz betikle ölç; mevcut storage/question/backup/practice benchmarklarını tekrar çalıştır.

## Veri ve davranış riskleri

- Veride live `backend/data` örneği yok; gerçek kullanıcı JSON'ları burada doğrulanamaz. Geriye uyumluluk, legacy fixtures ve eski yedeklerle kanıtlanacak.
- Tek bir toplam XP politikası kullanılır; bölümleri ayrı exam kayıtlarına çevirip XP'yi çoğaltma yok.
- Bölüm adı değişince daha önce bağlanan yanlış sorunun sıra grubu kaymasın diye bölüm büyüklüğü `Question.exam_section_total` içinde snapshot edilir. `Question.subject` hâlihazırda ders adıdır ve bu bilgiyi de taşır.
- Serbest bölüm adı, farklı yazımları birden fazla ders gibi gösterebilir; kullanıcı görünür adları elle tutarlı girmelidir. Standart konu kataloğu bu kapsamda değil.

## Sıra

1. Plan/backlog commit.
2. Geriye uyumlu schema ve backend API/test commit'i.
3. UI ve section filtre/trend/test commit'i.
4. Browser smoke + AI'siz benchmark commit'i.
5. Tüm rapor/notes/backlog güncellemesi; her yerel commit'i GitHub API üzerinden aynı tree SHA ile ayrı ayrı aktar ve Actions tamamlanmasını doğrula.
