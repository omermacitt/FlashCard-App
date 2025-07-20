# 📚 FlashCard App

Modern ve interaktif bir dil öğrenme uygulaması. Flask web framework kullanılarak geliştirilmiş bu uygulama, kullanıcıların kelime kartları oluşturmasına, çalışmasına ve ilerleme kaydetmesine olanak tanır.

## ✨ Özellikler

### 🔐 Kullanıcı Yönetimi
- Güvenli kullanıcı kaydı ve girişi
- E-posta doğrulaması ve şifre sıfırlama
- Kişisel profil yönetimi

### 📖 Flashcard Sistemi
- Özel flashcard setleri oluşturma
- Çoklu dil desteği (Türkçe, İngilizce, Almanca, vb.)
- Zorluk seviyesi belirleme (A1-C2)
- Halka açık ve özel flashcard'lar

### 🎯 Çalışma Modları
- **Flashcard Modu**: Klasik kart çevirme
- **Quiz Modu**: Çoktan seçmeli sorular
- **Yazma Modu**: Manuel cevap yazma
- **Toplu Yazma**: Birden fazla kelime testi

### 📊 İlerleme Takibi
- Günlük, haftalık ve aylık istatistikler
- Başarı oranları ve doğruluk yüzdeleri
- Seviye sistemi ve puan kazanma
- Günlük çalışma serileri (streak)
- Çalışma süresi takibi

### 🎨 Kullanıcı Deneyimi
- Responsive tasarım (mobil uyumlu)
- Modern ve temiz arayüz
- PWA desteği (uygulama gibi yüklenebilir)
- Dark/Light mod desteği

## 🛠️ Teknolojiler

### Backend
- **Flask** - Web framework
- **SQLAlchemy** - ORM ve veritabanı yönetimi
- **PostgreSQL** - Ana veritabanı
- **Flask-Login** - Kullanıcı oturum yönetimi
- **Flask-Mail** - E-posta gönderimi
- **Werkzeug** - Şifre hashleme ve güvenlik

### Frontend
- **HTML5/CSS3** - Yapı ve stil
- **JavaScript** - İnteraktif özellikler
- **Bootstrap** - Responsive tasarım
- **PWA** - Progressive Web App desteği

### AI/ML
- **SentenceTransformers** - Kelime benzerlik analizi
- **distiluse-base-multilingual-cased-v2** - Çok dilli embedding modeli

## 📁 Proje Yapısı

```
FlashCard-App/
├── app/
│   ├── __init__.py              # Flask uygulaması factory
│   ├── auth/                    # Kimlik doğrulama modülü
│   │   ├── __init__.py
│   │   └── routes.py           # Login, register, password reset
│   ├── flashcards/             # Flashcard yönetimi
│   │   ├── __init__.py
│   │   └── routes.py           # CRUD işlemleri, çalışma modları
│   ├── main/                   # Ana uygulama rotaları
│   │   ├── __init__.py
│   │   └── routes.py           # Dashboard, profil, istatistikler
│   ├── static/                 # Statik dosyalar
│   │   ├── css/
│   │   │   └── style.css       # Ana stil dosyası
│   │   └── favicon.*           # Favicon dosyaları
│   └── templates/              # HTML şablonları
│       ├── base.html           # Ana şablon
│       ├── dashboard.html      # Ana sayfa
│       ├── flashcards.html     # Flashcard listesi
│       └── ...                 # Diğer sayfalar
├── words/                      # Excel kelime listeleri
│   ├── a1 kelimeler.xlsx
│   ├── a2 kelimeler.xlsx
│   └── ...
├── models.py                   # Veritabanı modelleri
├── config.py                   # Uygulama konfigürasyonu
├── db.py                       # Veritabanı bağlantısı
├── run.py                      # Uygulama başlatıcı
├── create_admin_flashcards.py  # Admin kartları oluşturucu
└── requirements.txt            # Python bağımlılıkları
```

## 🚀 Kurulum

### Gereksinimler
- Python 3.8+
- PostgreSQL
- pip (Python paket yöneticisi)

### Adım 1: Projeyi İndirin
```bash
git clone https://github.com/omermacitt/FlashCard-App.git
cd FlashCard-App
```

### Adım 2: Sanal Ortam Oluşturun
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# veya
venv\Scripts\activate     # Windows
```

### Adım 3: Bağımlılıkları Yükleyin
```bash
pip install -r requirements.txt
```

### Adım 4: Çevre Değişkenlerini Ayarlayın
`.env` dosyası oluşturun:
```env
# Veritabanı
USERNAME_=your_db_username
PASSWORD=your_db_password
HOST=localhost
PORT=5432
DATABASE_NAME=flashcard_db

# Flask
FLASK_SECRET_KEY=your_secret_key

# E-posta (opsiyonel)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_DEFAULT_SENDER=your_email@gmail.com

# Ayarlar
AUTO_SEED=true
```

### Adım 5: Veritabanını Oluşturun
```bash
# PostgreSQL'de veritabanı oluşturun
createdb flashcard_db

# Uygulamayı çalıştırın (veritabanı otomatik oluşturulur)
python run.py
```

### Adım 6: Uygulamayı Başlatın
```bash
python run.py
```

Uygulama `http://localhost:5005` adresinde çalışacaktır.

## 👤 Varsayılan Kullanıcı

Uygulama ilk çalıştırıldığında otomatik olarak bir admin kullanıcısı oluşturulur:
- **Kullanıcı adı**: admin
- **Şifre**: admin
- **E-posta**: admin@flashcard.com

## 📝 Kullanım

1. **Kayıt Olun/Giriş Yapın**: Ana sayfadan hesap oluşturun veya giriş yapın
2. **Flashcard Oluşturun**: "Flashcard Ekle" bölümünden yeni setler oluşturun
3. **Kelime Ekleyin**: Flashcard'lara kelimeler ekleyin
4. **Çalışmaya Başlayın**: Farklı çalışma modlarını deneyin
5. **İlerlemenizi Takip Edin**: Dashboard'dan istatistiklerinizi görün

## 🤝 Katkıda Bulunma

1. Projeyi fork edin
2. Feature branch oluşturun (`git checkout -b feature/AmazingFeature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add some AmazingFeature'`)
4. Branch'inizi push edin (`git push origin feature/AmazingFeature`)
5. Pull Request oluşturun

## 🐛 Hata Bildirimi

Bir hata bulduysanız veya öneriniz varsa, lütfen [issues](https://github.com/yourusername/FlashCard-App/issues) bölümünden bildirin.

## 📞 İletişim

Proje sahibi: [Ömer Macit TÜRK](mailto:your.email@example.com)

Proje Linki: [https://github.com/omermacitt/FlashCard-App](https://github.com/yourusername/FlashCard-App)