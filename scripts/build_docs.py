"""Build the static bilingual Hamartia help wiki from this page catalog."""

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BASE = "https://nec0ti.github.io/hamartia/"

PAGES = {
    "getting-started": {
        "en": ("Getting Started", "Install Hamartia, choose a language, and make a first study record.", """
<p class="lead">Hamartia keeps exam history, missed questions, focused practice, and review records on this computer. Start with the desktop app; an AI provider is optional.</p>
<h2 id="download">1. Download and install</h2><p>Use the latest <a href="https://github.com/Nec0ti/hamartia/releases/latest">GitHub release</a>. Choose the Windows installer for Windows 10/11, the <code>.deb</code> for Debian-based Linux, or the AppImage for compatible Linux desktops. Detailed steps are on <a href="../install/">Install by operating system</a>.</p>
<h2 id="language">2. Choose a language</h2><p>The interface opens in English. Open <strong>Settings</strong> and choose English or Türkçe. The preference is saved on this computer. The documentation also has a Turkish version using the language link at the top of every page.</p>
<h2 id="first-session">3. Record your first session</h2><ol><li>On <strong>Dashboard</strong>, add a TYT/AYT full mock or a single-subject exam and enter its date, duration, and results.</li><li>Open <strong>My Mistakes</strong> to save a missed question as text or attach a supported image. Add subject and topic labels; if it came from an exam, capture it there to keep the exam context.</li><li>Open <strong>Study Plan</strong> to see due questions, topic priorities, and focused practice. Its stopwatch uses the same timer shown in <strong>Clock</strong>.</li></ol>
<h2 id="data">Where your data lives</h2><p>Hamartia stores its records in this OS user's application-data folder. Data is not synced between computers automatically. Create a ZIP backup in Settings before moving records. See <a href="../backup-and-restore/">Backup and restore</a> and <a href="../privacy-and-consent/">Privacy and consent</a>.</p>
<aside class="note"><strong>AI is optional.</strong> Exam entry, review scheduling, topic summaries, practice records, and Clock work without an AI provider. Study Agent and question analysis are separate optional features with distinct data flows.</aside>
"""),
        "tr": ("Başlarken", "Hamartia'yı yükle, dili seç ve ilk çalışma kaydını oluştur.", """
<p class="lead">Hamartia; deneme geçmişini, yanlış soruları, odaklı çalışmayı ve tekrar kayıtlarını bu bilgisayarda tutar. Masaüstü uygulamasıyla başla; AI sağlayıcısı kullanmak zorunlu değildir.</p>
<h2 id="download">1. İndir ve yükle</h2><p><a href="https://github.com/Nec0ti/hamartia/releases/latest">En son GitHub sürümünü</a> kullan. Windows 10/11 için Windows yükleyicisini, Debian tabanlı Linux için <code>.deb</code> paketini veya uyumlu Linux masaüstleri için AppImage'i seç. Ayrıntılar için <a href="../install/">İşletim sistemine göre kurulum</a> sayfasına bak.</p>
<h2 id="language">2. Dili seç</h2><p>Arayüz İngilizce açılır. <strong>Ayarlar</strong>'ı açıp English veya Türkçe seç. Tercih bu bilgisayarda saklanır. Her sayfanın üstündeki dil bağlantısından dokümanların İngilizce sürümüne de geçebilirsin.</p>
<h2 id="first-session">3. İlk çalışma kaydını oluştur</h2><ol><li><strong>Ana Sayfa</strong>'nda TYT/AYT tam denemesi veya tek ders denemesi ekle; tarih, süre ve sonuçları gir.</li><li>Bir yanlış soruyu metin olarak kaydetmek veya desteklenen bir görsel eklemek için <strong>Yanlışlarım</strong>'ı aç. Ders ve konu etiketleri ekle; denemeden geldiyse deneme bağlamını korumak için soruyu oradan kaydet.</li><li>Vadesi gelen soruları, konu önceliklerini ve odaklı çalışmayı görmek için <strong>Çalışma Planı</strong>'nı aç. Planın kronometresi <strong>Saat</strong>'teki aynı zamanlayıcıyı kullanır.</li></ol>
<h2 id="data">Veriler nerede saklanır?</h2><p>Hamartia kayıtlarını bu işletim sistemi kullanıcısına ait uygulama verisi klasöründe tutar. Veriler bilgisayarlar arasında otomatik eşitlenmez. Kayıtları taşımadan önce Ayarlar'dan ZIP yedeği oluştur. <a href="../backup-and-restore/">Yedekleme ve geri yükleme</a> ile <a href="../privacy-and-consent/">Gizlilik ve onay</a> sayfalarına bak.</p>
<aside class="note"><strong>AI isteğe bağlıdır.</strong> Deneme girişi, tekrar planlama, konu özetleri, çalışma kayıtları ve Saat bir AI sağlayıcısı olmadan çalışır. Çalışma Asistanı ve soru analizi ayrı ve isteğe bağlı özelliklerdir; veri akışları farklıdır.</aside>
"""),
    },
    "system-architecture": {
        "en": ("System architecture", "How the desktop app, local API, stored records, and optional providers fit together.", """
<p class="lead">Hamartia is a desktop application with a local web interface and a loopback-only backend. Study data is stored on the same computer; optional provider requests are separate outbound actions.</p>
<h2 id="desktop">Desktop app and local API</h2><p>The packaged app uses Electron to open the interface and start the bundled backend. The backend binds to a loopback address on a dynamically selected local port; it is not intended to be exposed to the public internet. The renderer talks to that local API for exam, question, practice, Clock, settings, and backup operations. Electron provides the desktop-only ChatGPT sign-in and restore flows.</p>
<h2 id="storage">Local records and files</h2><p>The backend stores validated JSON documents under the current OS user's Hamartia data directory. Writes use per-file atomic replacement and locks for shared mutations. Question images and other uploaded data are stored under the same local data directory. The app does not automatically sync this data to a server.</p>
<h2 id="providers">Optional provider boundary</h2><p>Most screens need no AI. Study Agent requests go to the explicitly selected ChatGPT subscription flow or configured OpenAI-compatible endpoint after consent. The configured URL may be remote. Question analysis is a distinct request and may send question text or an image to that endpoint. Provider credentials have different storage rules; see <a href="../study-agent/">Study Agent and providers</a> and <a href="../privacy-and-consent/">Privacy and consent</a>.</p>
<h2 id="backup">Backup boundary</h2><p>The ZIP export captures validated study documents and referenced uploads as one point-in-time snapshot. It excludes the configured API key and ChatGPT sign-in credentials. Restore validates and stages the archive, preserves the current data directory as a snapshot, then replaces it. Clock timers restore paused and reminders disabled. See <a href="../backup-and-restore/">Backup and restore</a>.</p>
"""),
        "tr": ("Sistem mimarisi", "Masaüstü uygulaması, yerel API, kayıtlı veriler ve isteğe bağlı sağlayıcıların ilişkisi.", """
<p class="lead">Hamartia; yerel web arayüzü ve yalnızca loopback'e bağlı backend'i olan bir masaüstü uygulamasıdır. Çalışma verileri aynı bilgisayarda saklanır; isteğe bağlı sağlayıcı istekleri ayrı dış bağlantılardır.</p>
<h2 id="desktop">Masaüstü uygulaması ve yerel API</h2><p>Paketlenmiş uygulama arayüzü açmak ve paketlenmiş backend'i başlatmak için Electron kullanır. Backend dinamik seçilen yerel bağlantı noktasında loopback adresine bağlanır; genel internete açılmak üzere tasarlanmamıştır. Renderer deneme, soru, çalışma, Saat, ayarlar ve yedek işlemleri için yerel API ile iletişim kurar. Electron masaüstüne özel ChatGPT giriş ve geri yükleme akışlarını sağlar.</p>
<h2 id="storage">Yerel kayıtlar ve dosyalar</h2><p>Backend doğrulanmış JSON belgelerini geçerli işletim sistemi kullanıcısının Hamartia veri dizininde saklar. Yazmalarda dosya başına atomik değiştirme ve ortak değişiklikler için kilitler kullanılır. Soru görselleri ve diğer yüklemeler aynı yerel veri dizinindedir. Uygulama bu verileri otomatik olarak sunucuyla eşitlemez.</p>
<h2 id="providers">İsteğe bağlı sağlayıcı sınırı</h2><p>Çoğu ekran AI gerektirmez. Çalışma Asistanı istekleri onaydan sonra açıkça seçilen ChatGPT abonelik akışına veya yapılandırılmış OpenAI uyumlu uç noktaya gider. Yapılandırılmış adres uzakta olabilir. Soru analizi ayrı bir istektir ve soru metni/görselini bu uç noktaya gönderebilir. Sağlayıcı kimlik bilgilerinin saklama kuralları farklıdır; <a href="../study-agent/">Çalışma Asistanı ve sağlayıcılar</a> ile <a href="../privacy-and-consent/">Gizlilik ve onay</a> sayfalarına bak.</p>
<h2 id="backup">Yedek sınırı</h2><p>ZIP dışa aktarımı doğrulanmış çalışma belgelerini ve başvurulan yüklemeleri tek bir zaman noktasından alır. Yapılandırılmış API anahtarını ve ChatGPT giriş kimlik bilgilerini dışarıda bırakır. Geri yükleme arşivi doğrulayıp hazırlar, mevcut veri dizinini kopya olarak korur ve sonra değiştirir. Saat zamanlayıcıları duraklatılmış, hatırlatıcılar kapalı geri yüklenir. <a href="../backup-and-restore/">Yedekleme ve geri yükleme</a> sayfasına bak.</p>
"""),
    },
    "purpose-and-scope": {
        "en": ("Purpose and scope", "What Hamartia stores, what it supports, and what it does not claim.", """
<p class="lead">Hamartia is a local-first study record and review tool. It connects exam results, student-saved mistakes, topic practice, and scheduled review. Its summaries describe saved records; they do not certify learning.</p>
<h2 id="in-scope">Included workflows</h2><ul><li>TYT/AYT full mock and single-subject exam records.</li><li>Text or image missed-question records, subject/topic labels, and optional user-entered curriculum references.</li><li>Deterministic due-question and topic summaries; completed topic-practice records.</li><li>Cosmos progression summaries and review-topic orbits derived from saved records.</li><li>A shared Clock timer, Pomodoro, countdown, stopwatch/laps, and local reminders.</li><li>Optional Study Agent providers in the packaged desktop app and optional separate question analysis.</li></ul>
<h2 id="out-of-scope">Limits</h2><p>Hamartia does not provide exam questions or answer keys, import an official curriculum, verify user-entered curriculum references, or infer mastery from a score, tag, AI suggestion, or one correct answer. Built-in net calculation follows the YKS wrong-answer penalty. Other exam formats and scoring rules may require adaptation. The app is not a cloud sync service or a wake-from-sleep alarm.</p>
        <h2 id="where-next">Find the details</h2><p>Use <a href="../system-architecture/">System architecture</a>, <a href="../study-workflows/">Study workflows</a>, <a href="../exam-formats-and-maarif/">Exam formats and Maarif</a>, <a href="../learning-evidence/">Learning evidence and claims</a>, and <a href="../clock-and-reminders/">Clock and reminders</a>.</p>
"""),
        "tr": ("Amaç ve kapsam", "Hamartia'nın tuttuğu kayıtlar, desteklediği akışlar ve iddia etmediği konular.", """
<p class="lead">Hamartia, yerel öncelikli bir çalışma kaydı ve tekrar aracıdır. Deneme sonuçlarını, öğrencinin kaydettiği yanlışları, konu çalışmalarını ve planlı tekrarları ilişkilendirir. Özetleri yalnızca kayıtları açıklar; öğrenmeyi belgelemez.</p>
<h2 id="in-scope">Dahil olan akışlar</h2><ul><li>TYT/AYT tam deneme ve tek ders denemesi kayıtları.</li><li>Metin veya görsel yanlış soru kayıtları, ders/konu etiketleri ve isteğe bağlı kullanıcı girişi program referansları.</li><li>Deterministik vadesi gelen soru ve konu özetleri; tamamlanan konu çalışma kayıtları.</li><li>Paylaşılan Saat zamanlayıcısı, Pomodoro, geri sayım, kronometre/turlar ve yerel hatırlatıcılar.</li><li>Paketlenmiş masaüstü uygulamasında isteğe bağlı Çalışma Asistanı sağlayıcıları ve bundan ayrı isteğe bağlı soru analizi.</li></ul>
<h2 id="out-of-scope">Sınırlar</h2><p>Hamartia deneme sorusu veya cevap anahtarı sağlamaz, resmî programı içe aktarmaz, kullanıcının girdiği program referanslarını doğrulamaz ve puandan, etiketten, AI önerisinden veya tek doğru yanıttan ustalık çıkarmaz. Yerleşik net hesabı YKS yanlış-ceza kuralını kullanır. Diğer sınav türleri ve puanlama kuralları uyarlama gerektirebilir. Uygulama bulut eşitleme hizmeti veya bilgisayarı uykudan uyandıran alarm değildir.</p>
        <h2 id="where-next">Ayrıntılar</h2><p><a href="../system-architecture/">Sistem mimarisi</a>, <a href="../study-workflows/">Çalışma akışları</a>, <a href="../exam-formats-and-maarif/">Sınav biçimleri ve Maarif</a>, <a href="../learning-evidence/">Öğrenme kanıtı ve iddialar</a> ile <a href="../clock-and-reminders/">Saat ve hatırlatıcılar</a> sayfalarına bak.</p>
"""),
    },
    "study-workflows": {
        "en": ("Study workflows", "How exam entry, saved mistakes, topic practice, and review connect.", """
<p class="lead">The app keeps the student's records connected without requiring an AI call. A typical loop starts with an exam result, continues with selected missed questions, then returns to those questions or a topic practice session.</p>
<h2 id="exam">Record an exam</h2><p>Dashboard accepts TYT/AYT full mocks and single-subject exams. Full mocks keep section results together while preserving subject summaries. Enter correct, incorrect, blank, and duration values. The net preview uses the built-in YKS penalty formula. You can edit or delete a saved exam.</p>
<h2 id="mistakes">Capture mistakes</h2><p>Open My Mistakes or use the incorrect-answer entry from an exam. Save text, attach a supported image, add subject/topic labels, and optionally record exam question number, solve order, or time spent. Curriculum reference fields are optional and user-entered. Saved records can be edited, searched, reviewed, and deleted.</p>
<h2 id="practice">Study and review</h2><p>Study Plan groups due questions by topic, shows available mistake tags and exam-order counts, and offers focused practice. A completed practice set records date, subject/topic, correct/incorrect/blank counts, and time. The trend summary is computed from completed sets; blanks are excluded from the answered-accuracy denominator.</p>
<h2 id="progress">Read progress carefully</h2><p>Exam, review, practice, and Clock histories report what was entered. Missing records, free-text labels, and self-reported answers affect their summaries. Cosmos adds XP, level, streak, and review-topic orbits from saved records; those are progression displays, not evidence of mastery. See <a href="../cosmos-and-progression/">Cosmos and progression</a>, <a href="../mistakes-and-review/">Mistakes and review</a>, and <a href="../learning-evidence/">Learning evidence</a>.</p>
"""),
        "tr": ("Çalışma akışları", "Deneme girişi, yanlış sorular, konu çalışması ve tekrarın nasıl bağlandığı.", """
<p class="lead">Uygulama, AI çağrısı gerektirmeden öğrencinin kayıtlarını ilişkilendirir. Tipik akış deneme sonucuyla başlar, seçilen yanlış sorularla sürer, sonra bu sorulara veya konu çalışmasına geri döner.</p>
<h2 id="exam">Deneme kaydet</h2><p>Ana Sayfa TYT/AYT tam denemelerini ve tek ders denemelerini kabul eder. Tam denemeler bölüm sonuçlarını bir arada tutarken ders özetlerini de korur. Doğru, yanlış, boş ve süre değerlerini gir. Net önizlemesi yerleşik YKS yanlış-ceza formülünü kullanır. Kaydedilen denemeyi düzenleyebilir veya silebilirsin.</p>
<h2 id="mistakes">Yanlışları kaydet</h2><p>Yanlışlarım'ı aç veya denemedeki yanlış cevap girişini kullan. Metin kaydet, desteklenen bir görsel ekle, ders/konu etiketleri ekle; istersen soru numarası, çözüm sırası veya süreyi de kaydet. Program referansı alanları isteğe bağlıdır ve kullanıcı tarafından doldurulur. Kayıtları düzenleyebilir, arayabilir, gözden geçirebilir veya silebilirsin.</p>
<h2 id="practice">Çalış ve tekrar et</h2><p>Çalışma Planı vadesi gelen soruları konuya göre gruplar, kayıtlı hata etiketlerini ve denemedeki soru sırası sayılarını gösterir, odaklı çalışma başlatır. Tamamlanan çalışma seti tarih, ders/konu, doğru/yanlış/boş sayısı ve süreyi kaydeder. Eğilim özeti tamamlanan setlerden hesaplanır; cevaplanan doğruluk paydasında boşlar sayılmaz.</p>
<h2 id="progress">İlerlemeyi dikkatle yorumla</h2><p>Deneme, tekrar, çalışma ve Saat geçmişleri girilmiş kayıtları raporlar. Eksik kayıtlar, serbest metin etiketleri ve öğrencinin kendi bildirdiği yanıtlar özetleri etkiler. Cosmos XP, seviye, seri ve tekrar konu yörüngelerini bu kayıtlardan üretir; bunlar ustalık kanıtı değildir. <a href="../cosmos-and-progression/">Cosmos ve ilerleme</a>, <a href="../mistakes-and-review/">Yanlışlar ve tekrar</a> ile <a href="../learning-evidence/">Öğrenme kanıtı</a> sayfalarına bak.</p>
"""),
    },
    "cosmos-and-progression": {
        "en": ("Cosmos and progression", "Understand levels, XP, streaks, and the review-topic map.", """
<p class="lead">Cosmos is a read-only local progress view. It uses saved exam history and current Study Plan priorities; it does not use AI or create new records.</p>
<h2 id="levels">XP and levels</h2><p>XP is calculated from saved exam results using Hamartia's exam progression formula. A level is derived from cumulative XP; the first threshold is 500 XP and later levels use the same 500-XP step. This is app progression, not a grade or learning score.</p>
<h2 id="streak">Study streak</h2><p>The displayed streak is derived from dates on saved exam records. It counts a consecutive run ending today or yesterday; it is not a record of every study activity and does not mean learning occurred on each counted day. Missing or incorrectly dated exam entries affect it.</p>
<h2 id="orbits">Review orbits</h2><p>The map shows up to nine subject/topic groups with questions currently due for review. Groups with more pending missed-question records appear first. The topic labels and counts come from saved records and the deterministic Study Plan summary. Adding or reviewing a question changes the underlying record and therefore can change the map.</p>
<h2 id="limits">What Cosmos cannot tell you</h2><p>XP, level, streak, and orbit position do not establish knowledge, mastery, effort, or future exam performance. A low or interrupted streak is not a judgment about the student. Use these displays as navigation cues only; check understanding with fresh practice and explanations. See <a href="../learning-evidence/">Learning evidence and claims</a> and <a href="../study-workflows/">Study workflows</a>.</p>
"""),
        "tr": ("Cosmos ve ilerleme", "Seviye, XP, seri ve tekrar konu haritasını anla.", """
<p class="lead">Cosmos, yerel ve salt okunur bir ilerleme görünümüdür. Kaydedilmiş deneme geçmişini ve Çalışma Planı önceliklerini kullanır; AI kullanmaz veya yeni kayıt oluşturmaz.</p>
<h2 id="levels">XP ve seviyeler</h2><p>XP, kaydedilen deneme sonuçlarından Hamartia'nın deneme ilerleme formülüyle hesaplanır. Seviye toplam XP'den türetilir; ilk eşik 500 XP, sonraki seviyeler de aynı 500 XP aralığını kullanır. Bu, uygulama ilerlemesidir; not veya öğrenme puanı değildir.</p>
<h2 id="streak">Çalışma serisi</h2><p>Gösterilen seri, kaydedilmiş deneme tarihlerinden hesaplanır. Bugün veya dün biten kesintisiz günleri sayar; her çalışma etkinliğinin kaydı değildir ve sayılan her günde öğrenme gerçekleştiği anlamına gelmez. Eksik ya da yanlış tarihli deneme kayıtları sonucu etkiler.</p>
<h2 id="orbits">Tekrar yörüngeleri</h2><p>Harita, şu anda tekrarı vadesi gelen sorulara sahip en fazla dokuz ders/konu grubunu gösterir. Daha çok bekleyen yanlış soru kaydı olan gruplar önce görünür. Konu adları ve sayılar kayıtlı veriden ve deterministik Çalışma Planı özetinden gelir. Soru eklemek veya tekrar etmek kaydı, dolayısıyla haritayı değiştirebilir.</p>
<h2 id="limits">Cosmos neyi gösteremez?</h2><p>XP, seviye, seri ve yörünge konumu bilgiyi, ustalığı, çabayı veya gelecekteki sınav performansını kanıtlamaz. Düşük ya da kesilmiş seri öğrenci hakkında hüküm değildir. Bu görünümleri yalnızca gezinme ipucu olarak kullan; anlayışı yeni alıştırmalar ve açıklamalarla kontrol et. <a href="../learning-evidence/">Öğrenme kanıtı ve iddialar</a> ile <a href="../study-workflows/">Çalışma akışları</a> sayfalarına bak.</p>
"""),
    },
    "mistakes-and-review": {
        "en": ("Mistakes and review", "How saved mistakes, deterministic patterns, and due dates work.", """
<p class="lead">A missed-question record is a prompt for later study, not a complete account of an exam or a verified diagnosis.</p>
<h2 id="record">What a record contains</h2><p>A record may contain text, an image, subject/topic, a built-in tag, linked exam details, and optional user-entered curriculum reference fields. Add only context you want to retain. To remove an image or change its labels, edit the question record.</p>
<h2 id="patterns">Patterns shown by Study Plan</h2><p>Study Plan counts saved pending questions by subject, topic, and available tags: Knowledge gap, Distractor trap, Misread the question, and Time pressure. If question number/order and time were recorded, it groups saved wrong questions into early, middle, and late portions and reports counts and median recorded time. These summaries cover saved mistakes only; they cannot infer the correct-answer denominator, so they are not an exam accuracy rate or a psychological diagnosis.</p>
<h2 id="schedule">Due-date rules</h2><p>New questions are due immediately. A wrong self-recorded review is due after one day. Consecutive correct reviews use intervals of 1, 3, 7, 14, then 30 days. Due dates use the device's local calendar day; older attempts without a saved local day use the legacy UTC fallback. Marking a question reviewed removes it from the active queue; it does not declare mastery.</p>
<h2 id="undo">Change a review mark</h2><p>Use the undo action on a reviewed question to return it to the pending workflow. Edit or delete its saved record if its text, image, or labels are wrong. See <a href="../study-workflows/">Study workflows</a>.</p>
"""),
        "tr": ("Yanlışlar ve tekrar", "Kaydedilen yanlışların, deterministik örüntülerin ve vade tarihlerinin işleyişi.", """
<p class="lead">Yanlış soru kaydı daha sonra çalışmak için bir ipucudur; denemenin eksiksiz kaydı veya doğrulanmış bir teşhis değildir.</p>
<h2 id="record">Kayıtta neler bulunur?</h2><p>Kayıtta metin, görsel, ders/konu, yerleşik etiket, bağlı deneme ayrıntıları ve isteğe bağlı kullanıcı girişi program referansı alanları bulunabilir. Yalnızca saklamak istediğin bağlamı ekle. Görseli kaldırmak veya etiketleri değiştirmek için soru kaydını düzenle.</p>
<h2 id="patterns">Çalışma Planı'nın gösterdiği örüntüler</h2><p>Çalışma Planı bekleyen kayıtlı soruları ders, konu ve etiketlere göre sayar: Konu eksiği, Çeldirici tuzağı, Soruyu yanlış okuma ve Zaman baskısı. Soru numarası/sırası ve süresi kaydedilmişse yanlışları denemenin erken, orta ve geç bölümlerinde gruplar; sayıları ve kayıtlı sürelerin ortancasını gösterir. Bu özetler yalnızca kaydedilmiş yanlışları kapsar; doğru yanıt paydasını çıkaramadığı için deneme doğruluk oranı veya psikolojik teşhis değildir.</p>
<h2 id="schedule">Vade kuralları</h2><p>Yeni sorular hemen vadelidir. Öğrencinin yanlış işaretlediği tekrar bir gün sonra yeniden vadelidir. Art arda doğru tekrarların aralığı 1, 3, 7, 14 ve sonra 30 gündür. Vade cihazın yerel takvim gününü kullanır; yerel gün bilgisi olmayan eski denemelerde eski UTC geri dönüşü uygulanır. Soruyu gözden geçirilmiş işaretlemek onu etkin listeden çıkarır; ustalık ilan etmez.</p>
<h2 id="undo">Tekrar işaretini değiştir</h2><p>İncelenmiş sorunun geri alma işlemiyle onu bekleyen akışa döndür. Metin, görsel veya etiket yanlışsa kaydı düzenle ya da sil. <a href="../study-workflows/">Çalışma akışları</a> sayfasına bak.</p>
"""),
    },
    "exam-formats-and-maarif": {
        "en": ("Exam formats and Maarif", "Current scoring support, curriculum references, and adaptation boundaries.", """
<p class="lead">Hamartia grew from Turkish mock-exam workflows. Exam-format support is specific; free-text labels do not change scoring rules.</p>
<h2 id="supported">Current built-in exam support</h2><p>The app records TYT/AYT full mock sessions and single-subject exams. Full mocks retain subject sections. Its net calculation uses the YKS wrong-answer penalty. Other systems with compatible scoring may reuse the workflow; formats such as LGS or different scoring rules need adaptation through a contribution or fork. The app does not create official exams, questions, or answer keys.</p>
<h2 id="maarif">Curriculum is not an exam mode</h2><p>Türkiye Yüzyılı Maarif Modeli is a curriculum framework and assessment approach, not a national-exam name. Hamartia does not import MEB curriculum text or make official/verified alignment. A student may enter a reference on a missed question (framework, source/version, grade/year, unit/theme, paraphrased outcome, process component, optional URL). The URL is not fetched or verified. Study Agent context may include these user-entered references after consent.</p>
<h2 id="adapt">Adapting a format</h2><p>When contributing another exam system, document its session structure, section totals, scoring formula, validation limits, tests, and migration/backup compatibility. Keep labels and curriculum references separate from score calculation. See <a href="../contributing/">Contributing</a> and <a href="../learning-evidence/">Learning evidence</a>.</p>
<p class="source-links">Official context: <a href="https://tymm.meb.gov.tr/olcme-degerlendirme">MEB Maarif assessment overview</a> · <a href="https://tymm.meb.gov.tr/upload/brosur/2024programortakmetinOnayli.pdf">Maarif common text (PDF)</a> · <a href="https://www.osym.gov.tr/2026yks-basvurularin-alinmasi">2026 YKS schedule</a> · <a href="https://www.meb.gov.tr/meb_iys_dosyalar/2026_04/03170012_LGS_Basvuru_ve_Uygulama_Kilavuzu_2026_.pdf">2026 LGS guide (PDF)</a>. Check current official pages for later dates.</p>
"""),
        "tr": ("Sınav biçimleri ve Maarif", "Mevcut puanlama desteği, program referansları ve uyarlama sınırları.", """
<p class="lead">Hamartia, Türkiye'deki deneme sınavı akışlarından doğdu. Sınav biçimi desteği belirli sistemlere yöneliktir; serbest metin etiketleri puanlama kurallarını değiştirmez.</p>
<h2 id="supported">Mevcut yerleşik sınav desteği</h2><p>Uygulama TYT/AYT tam denemelerini ve tek ders denemelerini kaydeder. Tam denemelerde ders bölümleri korunur. Net hesabı YKS yanlış-ceza kuralını kullanır. Benzer puanlama kullanan başka sistemler akışı tekrar kullanabilir; LGS gibi biçimler veya farklı puanlama kuralları katkı ya da fork ile uyarlama gerektirir. Uygulama resmî sınav, soru veya cevap anahtarı oluşturmaz.</p>
<h2 id="maarif">Program, sınav türü değildir</h2><p>Türkiye Yüzyılı Maarif Modeli bir öğretim programı ve ölçme-değerlendirme yaklaşımıdır; ulusal sınav adı değildir. Hamartia MEB program metnini içe aktarmaz ve resmî/doğrulanmış eşleştirme yapmaz. Öğrenci yanlış soruya referans girebilir (çerçeve, kaynak/sürüm, sınıf/yıl, ünite/tema, başka sözcüklerle çıktı, süreç bileşeni, isteğe bağlı adres). Adres otomatik alınmaz veya doğrulanmaz. Onay verildikten sonra Çalışma Asistanı bağlamına bu kullanıcı girişi referanslar dahil olabilir.</p>
<h2 id="adapt">Başka bir biçime uyarlama</h2><p>Yeni bir sınav sistemi ekleyen katkı; oturum yapısını, bölüm toplamlarını, puanlama formülünü, doğrulama sınırlarını, testleri ve taşıma/yedek uyumluluğunu belgelemelidir. Etiketleri ve program referanslarını puan hesabından ayrı tut. <a href="../contributing/">Katkı</a> ve <a href="../learning-evidence/">Öğrenme kanıtı</a> sayfalarına bak.</p>
<p class="source-links">Resmî kaynaklar: <a href="https://tymm.meb.gov.tr/olcme-degerlendirme">MEB Maarif ölçme-değerlendirme açıklaması</a> · <a href="https://tymm.meb.gov.tr/upload/brosur/2024programortakmetinOnayli.pdf">Maarif ortak metni (PDF)</a> · <a href="https://www.osym.gov.tr/2026yks-basvurularin-alinmasi">2026 YKS takvimi</a> · <a href="https://www.meb.gov.tr/meb_iys_dosyalar/2026_04/03170012_LGS_Basvuru_ve_Uygulama_Kilavuzu_2026_.pdf">2026 LGS kılavuzu (PDF)</a>. Sonraki tarihler için güncel resmî sayfalara bak.</p>
"""),
    },
    "install": {
        "en": ("Install by operating system", "Choose the packaged desktop installer for Windows or Linux.", """
<p class="lead">Hamartia publishes a Windows installer, Debian package, and Linux AppImage. Download the current files from <a href="https://github.com/Nec0ti/hamartia/releases/latest">GitHub Releases</a>. Packages are for x64; no macOS package is currently documented.</p>
<h2 id="windows">Windows 10/11</h2><ol><li>Download the Windows <code>.exe</code> installer.</li><li>Run it and follow the installer prompts. Choose the install folder if desired.</li><li>Launch Hamartia from the installed shortcut. User data is kept separately in the current Windows user's application-data directory.</li></ol><p>If Windows blocks or warns about the installer, verify the file came from the project’s Releases page before deciding whether to continue. Do not download a similarly named binary elsewhere.</p>
<h2 id="debian">Debian and compatible distributions</h2><p>Download the release <code>.deb</code> file. Open it with the system package installer, or from the directory containing the file run:</p><pre><code>sudo apt install ./Hamartia-linux-x64.deb</code></pre><p>Use the actual downloaded filename if it differs. The package manager may ask to install dependencies.</p>
<h2 id="appimage">Linux AppImage</h2><p>Download the AppImage and run these commands from its directory:</p><pre><code>chmod +x Hamartia-linux-x64.AppImage
./Hamartia-linux-x64.AppImage</code></pre><p>Use the actual filename. Some desktops require FUSE or system integration support; consult your distribution if it does not start.</p>
<h2 id="first-run">First launch</h2><p>The app starts in English. Change language in Settings. Study data is stored separately from the installer files in the OS user's application-data area. Before uninstalling or moving computers, make a backup rather than assuming that reinstalling will recover it. See <a href="../backup-and-restore/">Backup and restore</a> and <a href="../troubleshooting/">Troubleshooting</a>.</p>
"""),
        "tr": ("İşletim sistemine göre kurulum", "Windows veya Linux için paketlenmiş masaüstü yükleyicisini seç.", """
<p class="lead">Hamartia; Windows yükleyicisi, Debian paketi ve Linux AppImage yayımlar. Güncel dosyaları <a href="https://github.com/Nec0ti/hamartia/releases/latest">GitHub Releases</a> sayfasından indir. Paketler x64 içindir; şu anda macOS paketi belgelenmiyor.</p>
<h2 id="windows">Windows 10/11</h2><ol><li>Windows <code>.exe</code> yükleyicisini indir.</li><li>Çalıştır ve yükleyici adımlarını izle. İstersen yükleme klasörünü seç.</li><li>Kurulu kısayoldan Hamartia'yı aç. Kullanıcı verileri geçerli Windows kullanıcısının uygulama verisi dizininde ayrı tutulur.</li></ol><p>Windows yükleyiciyi engeller veya uyarı verirse devam etmeye karar vermeden önce dosyanın projenin Releases sayfasından geldiğini doğrula. Başka yerlerdeki benzer adlı ikili dosyaları indirme.</p>
<h2 id="debian">Debian ve uyumlu dağıtımlar</h2><p>Sürümdeki <code>.deb</code> dosyasını indir. Sistem paket yükleyicisinde aç veya dosyanın bulunduğu dizinde şu komutu çalıştır:</p><pre><code>sudo apt install ./Hamartia-linux-x64.deb</code></pre><p>Dosya adı farklıysa indirdiğin gerçek adı kullan. Paket yöneticisi bağımlılıkların kurulmasını isteyebilir.</p>
<h2 id="appimage">Linux AppImage</h2><p>AppImage'i indir ve bulunduğu dizinde şu komutları çalıştır:</p><pre><code>chmod +x Hamartia-linux-x64.AppImage
./Hamartia-linux-x64.AppImage</code></pre><p>Dosya adı farklıysa gerçek adı kullan. Bazı masaüstü ortamları FUSE veya sistem entegrasyonu gerektirir; açılmazsa dağıtımının belgelerine bak.</p>
<h2 id="first-run">İlk açılış</h2><p>Uygulama İngilizce açılır. Dili Ayarlar'dan değiştir. Çalışma verileri işletim sistemi kullanıcısının uygulama veri alanında, yükleyici dosyalarından ayrı saklanır. Kaldırmadan ya da bilgisayar değiştirmeden önce yeniden kurulumda geri geleceğini varsaymak yerine yedek al. <a href="../backup-and-restore/">Yedekleme ve geri yükleme</a> ile <a href="../troubleshooting/">Sorun giderme</a> sayfalarına bak.</p>
"""),
    },
    "study-agent": {
        "en": ("Study Agent and providers", "Select the desktop Study Agent provider and understand its controls.", """
<p class="lead">The Study Agent is optional and available in the packaged desktop app. Question analysis is a separate optional action in My Mistakes. Neither is needed for ordinary exam, review, practice, or Clock flows.</p>
<h2 id="chatgpt">ChatGPT subscription</h2><p>The desktop Study Agent defaults to ChatGPT subscription. Select sign-in, complete the ChatGPT flow, and separately approve OpenAI's request to use the ChatGPT plan. Available models and usage limits depend on the account. Hamartia does not silently switch providers if a request fails. Sign out attempts remote revocation; follow the app's instructions if OpenAI cannot confirm it.</p>
<h2 id="endpoint">Configured OpenAI-compatible endpoint</h2><p>In Settings, enter the endpoint URL, model name, and optional API key. Select the configured endpoint explicitly in Study Agent. It may run on this computer or on a remote host: Hamartia does not verify that it is a local model or isolated from the network. Review the exact URL, transport warnings, and per-request consent. The operator may retain requests under its own policy. The API key is stored unencrypted in local app settings and is omitted from backups and API responses.</p>
<h2 id="consent">Consent and request content</h2><p>Before each Study Agent request, Hamartia displays a consent screen. It sends the typed prompt plus a bounded summary of saved study counts, subject/topic/tag summaries, topic-practice aggregates, and up to eight user-entered curriculum references. Saved question text and images and Study Agent conversation history are not included or stored by Hamartia. The consent screen describes the destination and data categories. Read it before sending and decline if you do not want the request sent.</p>
<h2 id="analysis">Question analysis</h2><p>“Review with Local AI” uses the configured OpenAI-compatible endpoint and may send that saved question's text or image. The endpoint can be remote; “local” in the control label is not a locality guarantee. The actual model behavior and local machine setup have not been verified by this documentation. See <a href="../privacy-and-consent/">Privacy and consent</a>.</p>
"""),
        "tr": ("Çalışma Asistanı ve sağlayıcılar", "Masaüstü Çalışma Asistanı sağlayıcısını seç ve denetimlerini öğren.", """
<p class="lead">Çalışma Asistanı isteğe bağlıdır ve paketlenmiş masaüstü uygulamasında kullanılabilir. Yanlışlarım'daki soru analizi bundan ayrı ve isteğe bağlı bir işlemdir. Normal deneme, tekrar, çalışma ve Saat akışları için ikisi de gerekmez.</p>
<h2 id="chatgpt">ChatGPT aboneliği</h2><p>Masaüstü Çalışma Asistanı varsayılan olarak ChatGPT aboneliğini kullanır. Giriş seçeneğini kullan, ChatGPT akışını tamamla ve OpenAI'ın ChatGPT planını kullanma isteğine ayrıca onay ver. Kullanılabilen modeller ve kullanım sınırları hesaba bağlıdır. İstek başarısız olursa Hamartia sessizce sağlayıcı değiştirmez. Çıkış uzaktan iptali dener; OpenAI doğrulayamazsa uygulamanın talimatlarını izle.</p>
<h2 id="endpoint">Yapılandırılmış OpenAI uyumlu uç nokta</h2><p>Ayarlar'da uç nokta adresi, model adı ve isteğe bağlı API anahtarını gir. Çalışma Asistanı'nda yapılandırılmış uç noktayı açıkça seç. Bu bilgisayarda veya uzaktaki bir ana makinede çalışabilir: Hamartia modelin yerel ya da ağdan yalıtılmış olduğunu doğrulamaz. Tam adresi, aktarım uyarılarını ve her istek öncesi onayı incele. İşletmecinin istekleri kendi politikasına göre saklaması mümkündür. API anahtarı yerel uygulama ayarlarında şifrelenmeden tutulur; yedeklere ve API yanıtlarına eklenmez.</p>
<h2 id="consent">Onay ve istek içeriği</h2><p>Her Çalışma Asistanı isteğinden önce Hamartia onay ekranı gösterir. Yazdığın istemi ve kaydedilmiş çalışma sayıları, ders/konu/etiket özetleri, konu çalışma toplamları ve en fazla sekiz kullanıcı girişi program referansından oluşan sınırlı bir özeti gönderir. Kaydedilmiş soru metinleri ve görselleri ile Çalışma Asistanı konuşma geçmişi gönderilmez veya Hamartia tarafından saklanmaz. Onay ekranı hedefi ve veri kategorilerini açıklar. Göndermeden önce oku; istek gönderilmesini istemiyorsan reddet.</p>
<h2 id="analysis">Soru analizi</h2><p>“Review with Local AI” yapılandırılmış OpenAI uyumlu uç noktayı kullanır ve kayıtlı sorunun metnini veya görselini gönderebilir. Uç nokta uzakta olabilir; düğmedeki “Local” sözü yerel olma garantisi değildir. Gerçek model davranışı ve yerel makine kurulumu bu dokümantasyonla doğrulanmış değildir. <a href="../privacy-and-consent/">Gizlilik ve onay</a> sayfasına bak.</p>
"""),
    },
    "privacy-and-consent": {
        "en": ("Privacy and consent", "Where records are stored and what optional AI requests send.", """
<p class="lead">By default, study records are stored in the current OS user's application-data folder. There is no automatic cloud sync. Moving or sharing a backup is a separate action.</p>
<h2 id="local-data">Local records</h2><p>Exam results, saved missed questions and images, review attempts, topic-practice records, Clock timers and reminders, progression data, and settings are stored locally. The Clock notification preference and reminders are local state; due alerts are checked only while Hamartia is running and the device is awake. Notifications can be suppressed by OS settings.</p>
<h2 id="agent-data">Study Agent requests</h2><p>Each request requires explicit consent and goes directly to the selected provider. ChatGPT calls use OpenAI's public Responses API with storage disabled by the app. The prompt and bounded summary categories are shown before sending. Hamartia does not store Study Agent transcripts. Configured endpoints may be remote and may have their own retention rules.</p>
<h2 id="question-data">Question analysis</h2><p>Question analysis is a separate user-triggered request. It can send the selected question's text/image to the configured OpenAI-compatible endpoint. Do not assume it has the same payload as Study Agent. Review Settings and the exact endpoint before use.</p>
<h2 id="credentials">Credentials</h2><p>ChatGPT renewable credentials use OS-protected storage; sign-in is unavailable if that protection cannot be used. The configured endpoint API key is stored unencrypted in local settings, not returned by the Settings API and not included in backups. Do not publish logs, screenshots, or backups containing private study material or credentials. See <a href="../study-agent/">Study Agent and providers</a> and <a href="../backup-and-restore/">Backup and restore</a>.</p>
"""),
        "tr": ("Gizlilik ve onay", "Kayıtların nerede saklandığı ve isteğe bağlı AI isteklerinin neler gönderdiği.", """
<p class="lead">Çalışma kayıtları varsayılan olarak bu işletim sistemi kullanıcısının uygulama veri klasöründe saklanır. Otomatik bulut eşitleme yoktur. Yedeği taşımak veya paylaşmak ayrı bir işlemdir.</p>
<h2 id="local-data">Yerel kayıtlar</h2><p>Deneme sonuçları, yanlış soru ve görsel kayıtları, tekrar denemeleri, konu çalışma kayıtları, Saat zamanlayıcıları ve hatırlatıcıları, ilerleme verisi ve ayarlar yerel saklanır. Saat bildirim tercihi ve hatırlatıcılar yerel durumdur; vadeli uyarılar yalnızca Hamartia çalışırken ve cihaz uyanıkken kontrol edilir. İşletim sistemi ayarları bildirimleri engelleyebilir.</p>
<h2 id="agent-data">Çalışma Asistanı istekleri</h2><p>Her istek açık onay gerektirir ve seçilen sağlayıcıya doğrudan gider. ChatGPT çağrıları uygulamanın saklama kapalı ayarıyla OpenAI'ın herkese açık Responses API'sini kullanır. Göndermeden önce istem ve sınırlı özet kategorileri gösterilir. Hamartia Çalışma Asistanı konuşmalarını saklamaz. Yapılandırılmış uç noktalar uzakta olabilir ve kendi saklama kurallarına sahip olabilir.</p>
<h2 id="question-data">Soru analizi</h2><p>Soru analizi kullanıcı tarafından ayrı başlatılan bir istektir. Seçilen sorunun metnini/görselini yapılandırılmış OpenAI uyumlu uç noktaya gönderebilir. Çalışma Asistanı ile aynı veriyi gönderdiğini varsayma. Ayarları ve tam hedefi kullanmadan önce incele.</p>
<h2 id="credentials">Kimlik bilgileri</h2><p>Yenilenebilir ChatGPT kimlik bilgileri işletim sisteminin korumalı deposunu kullanır; bu koruma çalışmıyorsa giriş kullanılamaz. Yapılandırılmış uç noktanın API anahtarı yerel ayarlarda şifrelenmeden tutulur, Ayarlar API'sinden döndürülmez ve yedeklere eklenmez. Özel çalışma verisi veya kimlik bilgisi içeren günlükleri, ekran görüntülerini ya da yedekleri yayımlama. <a href="../study-agent/">Çalışma Asistanı ve sağlayıcılar</a> ile <a href="../backup-and-restore/">Yedekleme ve geri yükleme</a> sayfalarına bak.</p>
"""),
    },
    "backup-and-restore": {
        "en": ("Backup and restore", "Create a portable ZIP and safely restore it on this or another computer.", """
<p class="lead">Backups are manual ZIP files. Store them somewhere you control and protect them as private study records. Hamartia does not sync them automatically.</p>
<h2 id="create">Create a backup</h2><ol><li>Open Settings and select <strong>Download backup</strong>.</li><li>Save the ZIP to a location you can find. Move it to another computer using a transfer method you trust.</li><li>The archive includes study records, question images, settings except secret key material, and Clock state. The configured endpoint API key and ChatGPT sign-in credentials are not included.</li></ol>
<h2 id="restore">Restore in the desktop app</h2><ol><li>Open Settings and choose <strong>Restore backup</strong>, then select the ZIP.</li><li>Read the confirmation. Restore replaces current study data; Hamartia first saves a timestamped snapshot of the existing data folder.</li><li>Confirm and keep the app open while it validates, restores, restarts, and reloads.</li></ol><p>Clock timers restore paused with their remaining/elapsed time frozen at backup creation; imported reminders restore disabled. Review them and explicitly resume or enable them.</p>
<h2 id="older">Older backups and errors</h2><p>Current restore validates archive paths, sizes, checksums, data schemas, and referenced uploads before replacing data. Older supported archives without newer optional records receive safe defaults. A failed validation should leave current data in place. Keep the original ZIP until you have checked the restored records. See <a href="../troubleshooting/">Troubleshooting</a>.</p>
<aside class="note"><strong>Restore is replacement.</strong> It does not merge two histories. Make a fresh backup of the destination computer first if you may need its current data.</aside>
"""),
        "tr": ("Yedekleme ve geri yükleme", "Taşınabilir ZIP yedeği oluştur ve bu ya da başka bir bilgisayarda güvenle geri yükle.", """
<p class="lead">Yedekler elle oluşturulan ZIP dosyalarıdır. Özel çalışma kayıtları olarak koruyup kontrol ettiğin bir yerde sakla. Hamartia otomatik eşitleme yapmaz.</p>
<h2 id="create">Yedek oluştur</h2><ol><li>Ayarlar'ı açıp <strong>Download backup</strong> seçeneğini seç.</li><li>ZIP'i bulabileceğin bir yere kaydet. Başka bilgisayara güvendiğin bir aktarım yöntemiyle taşı.</li><li>Arşiv çalışma kayıtlarını, soru görsellerini, gizli anahtar malzemesi hariç ayarları ve Saat durumunu içerir. Yapılandırılmış uç noktanın API anahtarı ile ChatGPT giriş kimlik bilgileri eklenmez.</li></ol>
<h2 id="restore">Masaüstü uygulamasında geri yükle</h2><ol><li>Ayarlar'da <strong>Restore backup</strong> seç ve ZIP dosyasını seç.</li><li>Onayı oku. Geri yükleme mevcut çalışma verilerini değiştirir; Hamartia önce mevcut veri klasörünün tarihli bir kopyasını alır.</li><li>Onayla ve doğrulama, geri yükleme, yeniden başlatma ve yeniden yükleme bitene kadar uygulamayı açık tut.</li></ol><p>Saat zamanlayıcıları yedek oluşturulduğu andaki kalan/geçen süreyle duraklatılmış geri yüklenir; alınan hatırlatıcılar kapalı geri yüklenir. Gözden geçirip açıkça sürdür veya etkinleştir.</p>
<h2 id="older">Eski yedekler ve hatalar</h2><p>Güncel geri yükleme, veriyi değiştirmeden önce arşiv yollarını, boyutları, sağlama toplamlarını, veri şemalarını ve başvurulan yüklemeleri doğrular. Yeni isteğe bağlı kayıtları içermeyen eski desteklenen arşivler güvenli varsayılanlarla tamamlanır. Doğrulama başarısız olursa mevcut veri yerinde kalmalıdır. Geri yüklenen kayıtları kontrol edene kadar özgün ZIP'i sakla. <a href="../troubleshooting/">Sorun giderme</a> sayfasına bak.</p>
<aside class="note"><strong>Geri yükleme değiştirme işlemidir.</strong> İki geçmişi birleştirmez. Hedef bilgisayardaki mevcut veriye sonra ihtiyaç duyabilirsin; önce yeni bir yedek al.</aside>
"""),
    },
    "clock-and-reminders": {
        "en": ("Clock and reminders", "Use the local clock, one shared timer, and optional due notifications.", """
<p class="lead">Clock shows local date/time and offers Pomodoro, countdown, stopwatch/laps, and one-off or weekday reminders. Study Plan focused practice and Clock use one shared active timer; a second active timer cannot run in parallel.</p>
<h2 id="timers">Pomodoro, countdown, and stopwatch</h2><p>Set Pomodoro work/break durations, then start, pause, resume, reset, or skip a phase. The default interval is a convenience, not a claim of an optimal study schedule. Countdown accepts a duration. Stopwatch records elapsed time and laps. The display is derived from saved timestamps rather than counting UI ticks.</p>
<h2 id="practice">Focused practice</h2><p>Starting focused practice from a Study Plan topic uses the shared timer. Correct, incorrect, and blank counters belong to that practice draft. Finish saves one completed practice set; cancelling discards the draft after confirmation. If a Clock timer is already active, resolve it before starting another.</p>
<h2 id="alarms">One-off and recurring reminders</h2><p>Reminders use the device's local time zone. Recurrences can select weekdays. Choose whether to allow Web Notifications; keep reminders enabled only if you want alerts. Due events are reconciled while the app is running, including when another Hamartia tab is selected. Overdue reminders remain visible in Clock. After missed recurring occurrences, the app advances to the next future time rather than replaying a burst.</p>
<h2 id="limits">Delivery limits</h2><p>Notifications are checked only while the app is open and the device is awake. Hamartia cannot wake the device and does not promise delivery after the app closes. OS notification settings can suppress alerts. Daylight-saving gaps/folds follow the documented local JavaScript date behavior; other regions depend on the device time-zone database.</p>
<h2 id="backup">Restart and backup</h2><p>Timer state is saved locally and restored after app restart. ZIP backup freezes timers at export time; restore pauses those timers and disables imported alarms. Review them before use. See <a href="../backup-and-restore/">Backup and restore</a>.</p>
"""),
        "tr": ("Saat ve hatırlatıcılar", "Yerel saati, ortak zamanlayıcıyı ve isteğe bağlı vade bildirimlerini kullan.", """
<p class="lead">Saat yerel tarih/saati gösterir; Pomodoro, geri sayım, kronometre/turlar ve tek seferlik veya haftalık hatırlatıcılar sunar. Çalışma Planı odaklı çalışma ile Saat aynı etkin zamanlayıcıyı kullanır; iki etkin zamanlayıcı paralel çalışamaz.</p>
<h2 id="timers">Pomodoro, geri sayım ve kronometre</h2><p>Pomodoro çalışma/dinlenme süresini belirleyip aşamayı başlat, duraklat, sürdür, sıfırla veya atla. Varsayılan aralık kolaylık içindir; en iyi çalışma düzeni olduğu iddiası değildir. Geri sayım süre kabul eder. Kronometre geçen zamanı ve turları kaydeder. Gösterge arayüz tiklerini saymak yerine saklanan zaman damgalarından hesaplanır.</p>
<h2 id="practice">Odaklı çalışma</h2><p>Çalışma Planı konusundan odaklı çalışma başlatmak ortak zamanlayıcıyı kullanır. Doğru, yanlış ve boş sayaçları o çalışma taslağına aittir. Bitirince tek bir tamamlanmış çalışma seti kaydedilir; vazgeçme onayından sonra taslak silinir. Saat'te zaten zamanlayıcı çalışıyorsa yenisini başlatmadan önce onu çöz.</p>
<h2 id="alarms">Tek seferlik ve tekrarlı hatırlatıcılar</h2><p>Hatırlatıcılar cihazın yerel saat dilimini kullanır. Tekrarlar haftanın günlerine göre seçilebilir. Web Bildirimlerine izin verip vermeyeceğini seç; yalnızca uyarı istiyorsan hatırlatıcıları etkin bırak. Vadeli olaylar uygulama açıkken, Hamartia'nın başka sekmesi seçiliyken de denetlenir. Geciken hatırlatıcılar Saat'te görünür. Kaçırılmış tekrarlı olaylardan sonra uygulama bir dizi bildirim göndermek yerine gelecek ilk saate ilerler.</p>
<h2 id="limits">Bildirim sınırları</h2><p>Bildirimler yalnızca uygulama açık ve cihaz uyanıkken kontrol edilir. Hamartia cihazı uyandıramaz ve uygulama kapalıyken teslimat garantisi vermez. İşletim sistemi ayarları uyarıları engelleyebilir. Yaz saati boşlukları/çakışmaları yerel JavaScript tarih davranışını izler; diğer bölgeler cihazın saat dilimi veritabanına bağlıdır.</p>
<h2 id="backup">Yeniden başlatma ve yedekleme</h2><p>Zamanlayıcı durumu yerel kaydedilir ve uygulama yeniden başlayınca geri gelir. ZIP yedeği dışa aktarım anında zamanlayıcıları dondurur; geri yükleme bunları duraklatır ve alınan hatırlatıcıları kapatır. Kullanmadan önce gözden geçir. <a href="../backup-and-restore/">Yedekleme ve geri yükleme</a> sayfasına bak.</p>
"""),
    },
    "accessibility-and-language": {
        "en": ("Accessibility and language", "Language preference and verified accessibility guidance.", """
<p class="lead">Hamartia currently offers English (default) and Turkish. Change the app language in Settings. Number/date formatting follows the selected locale for supported UI flows.</p>
<h2 id="language">Switch language</h2><p>Choose English or Türkçe from the Settings language selector. The app stores this preference in the current browser profile. Reloading the app should retain it. The documentation language switch opens the matching page when a translation exists.</p>
<h2 id="accessibility">Using the interface</h2><p>Use semantic buttons and form labels; keyboard users can move between controls with Tab and activate buttons with Enter/Space. Timer state is exposed as text and due reminders remain visible rather than depending only on a notification. Browser/system screen-reader and contrast behavior can vary by OS and version. The repository's smoke checks cover selected labels, focus, and viewport behavior; they are not a complete screen-reader certification.</p>
<h2 id="report">Report a barrier</h2><p>If a label, focus order, keyboard action, contrast, or translation blocks a task, include the page/screen, OS and app version, language, and expected/actual behavior in a GitHub issue. Do not attach real study records, account tokens, or API keys. See <a href="../contributing/">Contributing</a>.</p>
"""),
        "tr": ("Erişilebilirlik ve dil", "Dil tercihi ve doğrulanmış erişilebilirlik bilgisi.", """
<p class="lead">Hamartia şu anda İngilizce (varsayılan) ve Türkçe sunar. Uygulama dilini Ayarlar'dan değiştir. Desteklenen arayüz akışlarında sayı/tarih biçimi seçilen yerel ayarı izler.</p>
<h2 id="language">Dili değiştir</h2><p>Ayarlar'daki dil seçicisinden English veya Türkçe seç. Uygulama tercihi geçerli tarayıcı profilinde saklar. Uygulamayı yeniden açınca tercih korunmalıdır. Doküman dil seçicisi çevirisi bulunan eş sayfayı açar.</p>
<h2 id="accessibility">Arayüzü kullan</h2><p>Anlamsal düğmeleri ve form etiketlerini kullan; klavye kullanıcıları Tab ile kontroller arasında ilerleyebilir, Enter/Space ile düğmeleri etkinleştirebilir. Zamanlayıcı durumu metin olarak sunulur; vadeli hatırlatıcılar yalnızca bildirime bağlı olmadan görünür kalır. Tarayıcı/işletim sistemi ekran okuyucu ve kontrast davranışı işletim sistemi ve sürüme göre değişebilir. Depodaki smoke kontrolleri seçili etiket, odak ve görüntü alanlarını kapsar; eksiksiz ekran okuyucu sertifikasyonu değildir.</p>
<h2 id="report">Engeli bildir</h2><p>Etiket, odak sırası, klavye eylemi, kontrast veya çeviri bir işi engelliyorsa GitHub issue'sunda sayfa/ekranı, işletim sistemi ve uygulama sürümünü, dili ve beklenen/gerçek davranışı belirt. Gerçek çalışma kayıtları, hesap belirteçleri veya API anahtarları ekleme. <a href="../contributing/">Katkı</a> sayfasına bak.</p>
"""),
    },
    "learning-evidence": {
        "en": ("Learning evidence and claims", "What app records can show and what they cannot establish.", """
<p class="lead">Hamartia helps organize practice and retrieval. Its interface reports submitted records; it does not measure all learning or establish that a particular routine will improve grades.</p>
<h2 id="what-it-shows">What the records show</h2><p>Exam results show values entered for a selected exam. Practice trends summarize completed sets. Review history reflects the student's own correct/incorrect marks. Pattern counts cover saved mistakes and available labels/order metadata. A Clock duration shows recorded elapsed time, not attention or learning quality.</p>
<h2 id="what-it-does-not">What they do not prove</h2><p>These records do not provide a complete denominator for unsaved questions, independently grade answers, verify a curriculum match, or demonstrate mastery from a single result. AI-generated advice is a suggestion that may be wrong; it does not mark tasks complete or certify outcomes. Time in the app, streaks, XP, and timer use are not evidence of improved learning.</p>
<h2 id="design">Study design context</h2><p>Retrieval and distributed practice have evidence of average benefits in classroom research, with variation by task and outcome. Concrete plans can support follow-through in studied contexts, but results do not guarantee effects in Hamartia. Fixed Pomodoro intervals have not been established as universally superior. Read the cited studies and their limits before generalizing:</p><ul><li><a href="https://doi.org/10.1007/s10648-026-10225-5">Retrieval, distributed, and interleaved practice in authentic classrooms (2026 review)</a>.</li><li><a href="https://doi.org/10.1016/j.cedpsych.2025.102422">Planning and studying micro-randomized trial (2025)</a>.</li><li><a href="https://doi.org/10.3390/bs15070861">Pomodoro, Flowtime, and self-regulated breaks (2025 study)</a>.</li></ul>
<h2 id="feedback">Interpreting progress</h2><p>Use trends to choose a next practice step, then check understanding with fresh questions and explanations. Treat summaries as prompts for reflection, not judgments about a student. See <a href="../mistakes-and-review/">Mistakes and review</a>.</p>
"""),
        "tr": ("Öğrenme kanıtı ve iddialar", "Uygulama kayıtlarının ne gösterebildiği ve neyi kanıtlayamadığı.", """
<p class="lead">Hamartia çalışma ve geri çağırma pratiğini düzenlemeye yardım eder. Arayüz girilen kayıtları raporlar; öğrenmenin tamamını ölçmez ve belirli bir düzenin notları artıracağını göstermez.</p>
<h2 id="what-it-shows">Kayıtlar ne gösterir?</h2><p>Deneme sonuçları seçilen sınav için girilen değerleri gösterir. Çalışma eğilimleri tamamlanmış setleri özetler. Tekrar geçmişi öğrencinin kendi doğru/yanlış işaretlerini yansıtır. Örüntü sayıları kaydedilen yanlışları, mevcut etiket ve sıra bilgisini kapsar. Saat süresi kaydedilen zamanı gösterir; dikkati veya öğrenme niteliğini değil.</p>
<h2 id="what-it-does-not">Neyi kanıtlamazlar?</h2><p>Bu kayıtlar kaydedilmemiş soruların tam paydasını sunmaz, yanıtları bağımsız olarak puanlamaz, program eşleşmesini doğrulamaz veya tek sonuçtan ustalık göstermez. AI önerisi yanlış olabilecek bir tavsiyedir; görevi tamamlandı işaretlemez veya çıktıyı doğrulamaz. Uygulamada geçirilen süre, seri, XP ve zamanlayıcı kullanımı öğrenmenin arttığına kanıt değildir.</p>
<h2 id="design">Çalışma araştırmalarının bağlamı</h2><p>Geri çağırma ve aralıklı çalışma, sınıf araştırmalarında ortalama yararlarla ilişkilidir; görev ve sonuca göre değişir. Somut planlar incelenen bağlamlarda takibi destekleyebilir; bu sonuçlar Hamartia'da aynı etkiyi garanti etmez. Sabit Pomodoro aralıklarının evrensel olarak üstün olduğu gösterilmemiştir. Genelleme yapmadan önce çalışmaları ve sınırlarını oku:</p><ul><li><a href="https://doi.org/10.1007/s10648-026-10225-5">Gerçek sınıflarda geri çağırma, aralıklı ve iç içe çalışma (2026 derlemesi)</a>.</li><li><a href="https://doi.org/10.1016/j.cedpsych.2025.102422">Planlama ve çalışma mikro-rastgele deneyi (2025)</a>.</li><li><a href="https://doi.org/10.3390/bs15070861">Pomodoro, Flowtime ve öz-düzenlemeli molalar (2025 araştırması)</a>.</li></ul>
<h2 id="feedback">İlerlemeyi yorumla</h2><p>Eğilimleri sonraki çalışma adımını seçmek için kullan; ardından yeni sorular ve açıklamalarla anlayışı kontrol et. Özetleri öğrenci hakkında hüküm değil, düşünme ipucu say. <a href="../mistakes-and-review/">Yanlışlar ve tekrar</a> sayfasına bak.</p>
"""),
    },
    "faq": {
        "en": ("FAQ", "Short answers to common setup, data, scoring, and study questions.", """
<h2 id="offline">Does Hamartia need AI?</h2><p>No. The main exam, mistake, practice, review, and Clock flows are local. Study Agent and question analysis are optional.</p>
<h2 id="sync">Does it sync my records?</h2><p>No automatic cross-device sync. Create and move a backup yourself. Credentials are not carried in the backup.</p>
<h2 id="formats">Does it score LGS or every exam?</h2><p>Built-in formats are TYT/AYT full mocks and single-subject exams, with YKS wrong-answer penalty net calculation. Other formats may require adaptation. See <a href="../exam-formats-and-maarif/">Exam formats</a>.</p>
<h2 id="local-ai">Is the configured endpoint guaranteed local?</h2><p>No. The URL can name a remote host; Hamartia does not verify locality or network isolation. See <a href="../study-agent/">Study Agent</a>.</p>
<h2 id="alarm">Will a reminder wake my computer?</h2><p>No. Delivery is not guaranteed while the app is closed or the computer sleeps. See <a href="../clock-and-reminders/">Clock and reminders</a>.</p>
<h2 id="marks">Does a better streak or XP prove that I learned more?</h2><p>No. These are app progression records. They are not an independent learning assessment. See <a href="../learning-evidence/">Learning evidence</a>.</p>
"""),
        "tr": ("Sık sorulan sorular", "Kurulum, veri, puanlama ve çalışma hakkındaki kısa yanıtlar.", """
<h2 id="offline">Hamartia AI gerektirir mi?</h2><p>Hayır. Temel deneme, yanlış, çalışma, tekrar ve Saat akışları yereldir. Çalışma Asistanı ve soru analizi isteğe bağlıdır.</p>
<h2 id="sync">Kayıtlarım eşitleniyor mu?</h2><p>Cihazlar arasında otomatik eşitleme yoktur. Yedeği kendin oluşturup taşı. Kimlik bilgileri yedeğe eklenmez.</p>
<h2 id="formats">LGS'yi veya her sınavı puanlıyor mu?</h2><p>Yerleşik biçimler TYT/AYT tam denemeleri ve tek ders denemeleridir; net hesabında YKS yanlış-ceza kuralı kullanılır. Diğer biçimler uyarlama gerektirebilir. <a href="../exam-formats-and-maarif/">Sınav biçimleri</a> sayfasına bak.</p>
<h2 id="local-ai">Yapılandırılmış uç noktanın yerel olduğu garanti mi?</h2><p>Hayır. Adres uzaktaki ana makineyi gösterebilir; Hamartia yerelliği veya ağ yalıtımını doğrulamaz. <a href="../study-agent/">Çalışma Asistanı</a> sayfasına bak.</p>
<h2 id="alarm">Hatırlatıcı bilgisayarımı uyandırır mı?</h2><p>Hayır. Uygulama kapalıyken veya bilgisayar uykudayken teslimat garantisi yoktur. <a href="../clock-and-reminders/">Saat ve hatırlatıcılar</a> sayfasına bak.</p>
<h2 id="marks">Seri veya XP'nin artması daha çok öğrendiğimi kanıtlar mı?</h2><p>Hayır. Bunlar uygulamadaki ilerleme kayıtlarıdır; bağımsız öğrenme ölçümü değildir. <a href="../learning-evidence/">Öğrenme kanıtı</a> sayfasına bak.</p>
"""),
    },
    "troubleshooting": {
        "en": ("Troubleshooting", "Recover from install, endpoint, restore, timer, and notification problems.", """
<h2 id="install">The installer or app will not open</h2><p>Confirm you downloaded the matching package from the official Releases page and that the OS/architecture are supported. For AppImage, check the executable bit and your distribution's FUSE requirements. On Debian, install the downloaded <code>.deb</code> with apt or the system installer. If it still fails, record OS version and exact error text without private paths or tokens.</p>
<h2 id="endpoint">Study Agent or endpoint fails</h2><p>Check the selected provider. For ChatGPT, confirm the desktop app is used, sign-in is connected, and the account can access the chosen model. For a configured endpoint, verify exact URL, model name, network/service availability, authentication, and the endpoint's format. Read any remote-host or HTTP warning. Hamartia does not silently fall back to another provider.</p>
<h2 id="backup">Backup will not restore</h2><p>Keep the original ZIP and check that it is a Hamartia backup, complete, and not modified. Restore from Settings in the packaged desktop app. Do not manually unpack files into the live data folder. A failed validation should preserve existing data; keep the timestamped pre-restore snapshot and seek help before deleting data.</p>
<h2 id="clock">Timer or reminder appears late</h2><p>Clock reconciles deadlines when the app runs and after it returns from suspension. Check the Clock tab for overdue items and verify device local date/time and time zone. OS notifications can be disabled or suppressed. The app cannot wake a sleeping device or notify after it closes.</p>
<h2 id="report">Ask for help safely</h2><p>Include app version, OS, language, steps, expected result, and exact non-sensitive error. Never share API keys, ChatGPT tokens, real question images, or unredacted backup files. See <a href="../privacy-and-consent/">Privacy</a> and <a href="../contributing/">Contributing</a>.</p>
"""),
        "tr": ("Sorun giderme", "Kurulum, uç nokta, yedek, zamanlayıcı ve bildirim sorunlarını çöz.", """
<h2 id="install">Yükleyici veya uygulama açılmıyor</h2><p>Resmî Releases sayfasından doğru paketi indirdiğini ve işletim sistemi/mimarisinin desteklendiğini doğrula. AppImage için çalıştırılabilir izin ve dağıtımının FUSE gereksinimlerini kontrol et. Debian'da indirdiğin <code>.deb</code> dosyasını apt veya sistem yükleyicisiyle kur. Sorun sürerse işletim sistemi sürümünü ve özel yol/belirteç içermeyen tam hata metnini kaydet.</p>
<h2 id="endpoint">Çalışma Asistanı veya uç nokta çalışmıyor</h2><p>Seçili sağlayıcıyı kontrol et. ChatGPT için masaüstü uygulamasını kullandığını, girişin bağlı olduğunu ve hesabın seçilen modele erişebildiğini doğrula. Yapılandırılmış uç nokta için tam adresi, model adını, ağ/hizmet erişimini, kimlik doğrulamayı ve uç noktanın biçimini kontrol et. Uzak ana makine veya HTTP uyarılarını oku. Hamartia sessizce başka sağlayıcıya dönmez.</p>
<h2 id="backup">Yedek geri yüklenmiyor</h2><p>Özgün ZIP'i sakla; Hamartia yedeği olduğunu, eksiksiz ve değiştirilmemiş olduğunu kontrol et. Paketlenmiş masaüstü uygulamasında Ayarlar'dan geri yükle. Dosyaları canlı veri klasörüne elle açma. Doğrulama hatası mevcut veriyi korumalıdır; tarihli geri yükleme öncesi kopyayı tut ve veriyi silmeden destek iste.</p>
<h2 id="clock">Zamanlayıcı veya hatırlatıcı geç görünüyor</h2><p>Saat, uygulama çalışırken ve askıdan döndükten sonra vadeleri yeniden hesaplar. Saat sekmesindeki geciken öğeleri kontrol et; cihazın yerel tarih/saatini ve saat dilimini doğrula. İşletim sistemi bildirimleri kapatabilir veya engelleyebilir. Uygulama uyuyan cihazı uyandıramaz veya kapalıyken bildirim gönderemez.</p>
<h2 id="report">Güvenle yardım iste</h2><p>Uygulama sürümünü, işletim sistemini, dili, adımları, beklenen sonucu ve özel olmayan tam hata mesajını ekle. API anahtarlarını, ChatGPT belirteçlerini, gerçek soru görsellerini veya sansürsüz yedekleri paylaşma. <a href="../privacy-and-consent/">Gizlilik</a> ve <a href="../contributing/">Katkı</a> sayfalarına bak.</p>
"""),
    },
    "contributing": {
        "en": ("Contributing", "Improve Hamartia or adapt its exam workflow for another format.", """
<p class="lead">Hamartia is MIT-licensed. Contributions can improve a shared workflow or adapt a different exam structure, provided scoring and data behavior are explicit.</p>
<h2 id="before">Before changing code</h2><p>Read the repository <code>AGENTS.md</code>, <code>notes.md</code>, backlog, and latest reports. Preserve existing user records and old backups. Keep local-model execution and quality out of CI tests/benchmarks; use mocks for provider error paths.</p>
<h2 id="exam">Adapting exam formats</h2><p>Describe exam/session types, section relationships, scoring formula, validation boundaries, trends, and compatibility with old records/backups. Keep curriculum references separate from scoring. Include an explicit correctness oracle for score calculations and update English/Turkish UI and docs together.</p>
<h2 id="docs">Documentation changes</h2><p>Update both language versions with the same page IDs, links, factual scope, and cross-links. Run <code>python3 scripts/build_docs.py</code>, the frontend docs browser smoke, and link/accessibility checks. Describe only behavior in the shipped app; record manual OS/account gates separately from automated evidence.</p>
<h2 id="submit">Submit a report</h2><p>Include a concise problem statement, user-visible change, tests and commands, limits, and report path. Use fictional data in screenshots. Never include personal student records, API keys, or ChatGPT credentials.</p>
"""),
        "tr": ("Katkı", "Hamartia'yı geliştir veya sınav akışını başka bir biçime uyarla.", """
<p class="lead">Hamartia MIT lisanslıdır. Katkılar ortak akışı geliştirebilir veya puanlama ve veri davranışını açıkça belirterek başka bir sınav yapısını uyarlayabilir.</p>
<h2 id="before">Kodu değiştirmeden önce</h2><p>Depodaki <code>AGENTS.md</code>, <code>notes.md</code>, backlog ve son raporları oku. Kullanıcı kayıtlarını ve eski yedekleri koru. Yerel model çalıştırma ve kaliteyi CI testi/benchmark dışında tut; sağlayıcı hata akışlarında sahte sağlayıcı kullan.</p>
<h2 id="exam">Sınav biçimlerini uyarlama</h2><p>Sınav/oturum türlerini, bölüm ilişkilerini, puanlama formülünü, doğrulama sınırlarını, eğilimleri ve eski kayıt/yedek uyumluluğunu açıkla. Program referanslarını puan hesabından ayrı tut. Puan hesapları için açık doğruluk oracle'ı ekle; İngilizce/Türkçe arayüzü ve dokümanları birlikte güncelle.</p>
<h2 id="docs">Dokümantasyon değişikliği</h2><p>Her iki dil sürümünü aynı sayfa kimlikleri, bağlantılar, olgusal kapsam ve çapraz bağlantılarla güncelle. <code>python3 scripts/build_docs.py</code>, frontend doküman tarayıcı smoke'u ve link/erişilebilirlik kontrollerini çalıştır. Yalnızca yayımlanan uygulamadaki davranışı açıkla; elle doğrulanacak OS/hesap kapılarını otomatik kanıtlardan ayrı kaydet.</p>
<h2 id="submit">Rapor gönder</h2><p>Kısa sorun tanımı, öğrenciye görünen değişiklik, testler ve komutlar, sınırlar ve rapor yolunu ekle. Ekran görüntülerinde uydurma veri kullan. Kişisel öğrenci kayıtlarını, API anahtarlarını veya ChatGPT kimlik bilgilerini ekleme.</p>
"""),
    },
}

NAV = {
    "en": ["Getting Started", "System architecture", "Purpose and scope", "Study workflows", "Cosmos and progression", "Mistakes and review", "Exam formats and Maarif", "Install by operating system", "Study Agent and providers", "Privacy and consent", "Backup and restore", "Clock and reminders", "Accessibility and language", "Learning evidence and claims", "FAQ", "Troubleshooting", "Contributing"],
    "tr": ["Başlarken", "Sistem mimarisi", "Amaç ve kapsam", "Çalışma akışları", "Cosmos ve ilerleme", "Yanlışlar ve tekrar", "Sınav biçimleri ve Maarif", "İşletim sistemine göre kurulum", "Çalışma Asistanı ve sağlayıcılar", "Gizlilik ve onay", "Yedekleme ve geri yükleme", "Saat ve hatırlatıcılar", "Erişilebilirlik ve dil", "Öğrenme kanıtı ve iddialar", "Sık sorulan sorular", "Sorun giderme", "Katkı"],
}
ORDER = list(PAGES)
SLUG_BY_LABEL = {lang: dict(zip(NAV[lang], ORDER)) for lang in ("en", "tr")}


def route(lang: str, slug: str) -> str:
    prefix = "tr/" if lang == "tr" else ""
    return f"{prefix}{slug}/" if slug != "getting-started" else prefix


def relative_href(current_lang: str, current_slug: str, target_lang: str, target_slug: str) -> str:
    current_depth = 0 if current_slug == "getting-started" else 1
    target_depth = 0 if target_slug == "getting-started" else 1
    target = route(target_lang, target_slug)
    if current_lang == target_lang:
        return ("../" if current_depth else "./") + (target.split("tr/", 1)[-1] if target_lang == "tr" else target)
    if target_lang == "tr":
        return ("../tr/" if current_depth else "./tr/") + ("" if target_slug == "getting-started" else f"{target_slug}/")
    return ("../../" if current_lang == "tr" and current_depth else "../" if current_lang == "tr" else "./") + ("" if target_slug == "getting-started" else f"{target_slug}/")


def render(lang: str, slug: str) -> str:
    title, description, body = PAGES[slug][lang]
    current_depth = 0 if slug == "getting-started" else 1
    if current_depth == 0:
        body = body.replace('href="../', 'href="./')
    root_prefix = "../" if current_depth else "./"
    if lang == "tr":
        root_prefix = ("../../" if current_depth else "../")
    nav_items = []
    for label in NAV[lang]:
        target = SLUG_BY_LABEL[lang][label]
        href = relative_href(lang, slug, lang, target)
        current = ' aria-current="page"' if target == slug else ""
        nav_items.append(f'<li><a href="{escape(href)}"{current}>{escape(label)}</a></li>')
    other = "tr" if lang == "en" else "en"
    language_label = "Türkçe" if other == "tr" else "English"
    language_href = relative_href(lang, slug, other, slug)
    canonical_path = route(lang, slug)
    canonical = BASE + canonical_path
    lang_name = "English" if lang == "en" else "Türkçe"
    return f'''<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{escape(description)}"><link rel="canonical" href="{escape(canonical)}">
  <link rel="icon" type="image/svg+xml" href="{root_prefix}assets/hamartia-favicon.svg">
  <link rel="stylesheet" href="{root_prefix}styles.css"><title>{escape(title)} · Hamartia</title>
</head>
<body>
  <a class="skip-link" href="#content">{'Skip to content' if lang == 'en' else 'İçeriğe geç'}</a>
  <header class="site-header"><a class="brand" href="{relative_href(lang, slug, lang, 'getting-started')}" aria-label="Hamartia"><img src="{root_prefix}assets/hamartia-mark.svg" alt=""><span>Hamartia</span></a>
    <div class="header-actions"><span class="edition">{'User guide' if lang == 'en' else 'Kullanım kılavuzu'}</span><a class="language-link" href="{escape(language_href)}" lang="{other}" hreflang="{other}">{language_label}</a></div>
  </header>
  <div class="page-layout">
    <aside class="sidebar"><p class="sidebar-title">{'Documentation' if lang == 'en' else 'Dokümantasyon'}</p><nav aria-label="{'Documentation pages' if lang == 'en' else 'Dokümantasyon sayfaları'}"><ol>{''.join(nav_items)}</ol></nav>
      <div class="sidebar-footer"><a href="https://github.com/Nec0ti/hamartia/releases/latest">{'Latest release ↗' if lang == 'en' else 'En son sürüm ↗'}</a><a href="https://github.com/Nec0ti/hamartia">{'Source code ↗' if lang == 'en' else 'Kaynak kod ↗'}</a></div>
    </aside>
    <main id="content" class="article"><p class="breadcrumb">{lang_name} / {escape(title)}</p><h1>{escape(title)}</h1><p class="page-description">{escape(description)}</p><article>{body}</article>
      <nav class="page-switch" aria-label="{'Language versions' if lang == 'en' else 'Dil sürümleri'}"><a href="{escape(language_href)}" lang="{other}" hreflang="{other}">{'Read this page in' if lang == 'en' else 'Bu sayfayı şu dilde oku'} {language_label}</a></nav>
    </main>
  </div>
  <footer class="site-footer"><span>Hamartia · MIT License</span><a href="https://github.com/Nec0ti/hamartia/blob/master/LICENSE">{'License' if lang == 'en' else 'Lisans'}</a><span>{'Docs updated' if lang == 'en' else 'Doküman güncellemesi'}: 2026-11-15</span></footer>
</body></html>
'''


def main() -> None:
    for lang in ("en", "tr"):
        for slug in ORDER:
            route_path = route(lang, slug)
            path = DOCS / route_path / "index.html"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render(lang, slug), encoding="utf-8")


if __name__ == "__main__":
    main()
