# Burada bütün yapı birleşecek
from app import create_app
from db import db
import os
from models import User, Word, Flashcard
from dotenv import load_dotenv
load_dotenv()

app = create_app()

def initialize_database():
    """Veritabanını başlat ve gerekli default verileri oluştur"""
    with app.app_context():
        # Tabloları oluştur
        db.create_all()
        print("📊 Veritabanı tabloları oluşturuldu")
        
        # Admin kullanıcısını kontrol et
        admin_user = User.query.filter_by(username="admin").first()
        if not admin_user:
            print("🔧 Admin kullanıcısı oluşturuluyor...")
            from werkzeug.security import generate_password_hash
            admin_user = User(
                username="admin",
                email="admin@flashcard.com",
                password=generate_password_hash("admin")
            )
            db.session.add(admin_user)
            db.session.commit()
            print("✅ Admin kullanıcısı oluşturuldu (Kullanıcı: admin, Şifre: admin)")
        
        # Default flashcard'lar var mı kontrol et (AUTO_SEED env var ile kontrol edilebilir)
        auto_seed = os.getenv('AUTO_SEED', 'true').lower() == 'true'
        
        if auto_seed:
            # Admin kullanıcısının ID'sini al
            admin_id = admin_user.id
            default_flashcards = Flashcard.query.filter_by(user_id=admin_id, visibility="public").count()
            if default_flashcards == 0:
                print("📚 Default flashcard'lar bulunamadı, oluşturuluyor...")
                try:
                    from create_admin_flashcards import create_admin_flashcards
                    create_admin_flashcards()
                except Exception as e:
                    print(f"⚠️ Default flashcard'lar oluşturulamadı: {e}")
                    print("💡 Manuel olarak 'python create_admin_flashcards.py' çalıştırabilirsiniz")
            else:
                print(f"✅ {default_flashcards} default flashcard mevcut")
        else:
            print("🔕 AUTO_SEED=false, default flashcard kontrolü atlandı")

# Veritabanını başlat
initialize_database()

if __name__ == '__main__':
    app.run(debug=True, port=5005)
