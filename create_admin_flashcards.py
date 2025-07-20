#!/usr/bin/env python3
"""
Admin flashcard'ları oluştur - Excel dosyalarından admin kullanıcısı için public flashcard'lar
"""

import pandas as pd
import os
from datetime import datetime, UTC

def create_admin_flashcards():
    """Excel dosyalarından admin kullanıcısı için public flashcard'lar oluştur"""
    
    print("📚 Admin flashcard'ları oluşturuluyor...")
    
    # Uygulama context'i içinde çalıştır
    from app import create_app
    from db import db
    from models import Flashcard, Word, FlashcardWords, User
    
    app = create_app()
    with app.app_context():
        
        # Admin kullanıcısını bul
        admin_user = User.query.filter_by(username="admin").first()
        if not admin_user:
            print("❌ Admin kullanıcısı bulunamadı! Önce admin kullanıcısı oluşturun.")
            return
        
        print(f"✅ Admin kullanıcısı bulundu (ID: {admin_user.id})")
        
        words_directory = "words"
        
        # Seviye bilgileri
        level_info = {
            "a1": {"name": "A1 Seviye", "description": "Temel seviye - Günlük hayatta en sık kullanılan kelimeler"},
            "a2": {"name": "A2 Seviye", "description": "Temel seviye - Günlük konuşmalarda kullanılan kelimeler"},
            "b1": {"name": "B1 Seviye", "description": "Orta seviye - Konuşma ve yazma becerileri geliştiren kelimeler"},
            "b2": {"name": "B2 Seviye", "description": "Orta-üst seviye - Akademik ve profesyonel kelimeler"},
            "c1": {"name": "C1 Seviye", "description": "İleri seviye - Karmaşık konuları anlama ve ifade etme"},
            "c2": {"name": "C2 Seviye", "description": "İleri seviye - Ana dili konuşanlar seviyesinde kelime hazinesi"}
        }
        
        # Her dosyayı ayrı ayrı işle
        for filename in sorted(os.listdir(words_directory)):
            if filename.endswith('.xlsx'):
                print(f"\n📖 {filename} dosyası işleniyor...")
                
                # Seviye bilgisini dosya adından çıkar
                level_key = filename.split(' ')[0].lower()
                
                if level_key not in level_info:
                    print(f"⚠️  Bilinmeyen seviye: {level_key}, atlanıyor...")
                    continue
                
                try:
                    # Excel dosyasını oku
                    file_path = os.path.join(words_directory, filename)
                    
                    # Dosya boyutunu kontrol et
                    file_size = os.path.getsize(file_path)
                    if file_size == 0:
                        print(f"   ⚠️  Dosya boş, atlanıyor...")
                        continue
                    
                    df = pd.read_excel(file_path, engine='openpyxl')
                    
                    if df.empty:
                        print(f"   ⚠️  Dosyada veri yok, atlanıyor...")
                        continue
                        
                    print(f"   📊 {len(df)} kelime bulundu")
                    
                    # Bu seviye için flashcard var mı kontrol et
                    existing_flashcard = Flashcard.query.filter_by(
                        name=level_info[level_key]["name"],
                        user_id=admin_user.id
                    ).first()
                    
                    if existing_flashcard:
                        print(f"   ⚠️  '{level_info[level_key]['name']}' zaten mevcut, atlanıyor...")
                        continue
                    
                    # Flashcard oluştur
                    flashcard = Flashcard(
                        name=level_info[level_key]["name"],
                        category="Dil Öğrenme",
                        description=level_info[level_key]["description"],
                        visibility="public",  # Herkese açık
                        front_language="en",
                        back_language="tr",
                        user_id=admin_user.id  # Admin kullanıcısına ait
                    )
                    
                    db.session.add(flashcard)
                    db.session.commit()  # Flashcard'ı hemen kaydet
                    
                    print(f"   ✅ Flashcard oluşturuldu (ID: {flashcard.id})")
                    
                    # Kelimeleri ekle
                    word_count = 0
                    for index, row in df.iterrows():
                        try:
                            english_word = str(row.iloc[0]).strip()
                            turkish_word = str(row.iloc[1]).strip()
                            difficulty = str(row.iloc[4]).strip().lower()
                            if turkish_word and english_word and turkish_word != 'nan' and english_word != 'nan':
                                
                                try:
                                    # EN->TR yönü için kelime oluştur
                                    existing_word_en_tr = Word.query.filter_by(
                                        word=english_word,
                                        answer=turkish_word,
                                        front_language="en",
                                        back_language="tr",
                                        user_id=admin_user.id
                                    ).first()
                                    
                                    if not existing_word_en_tr:
                                        # EN->TR kelime oluştur
                                        word_en_tr = Word(
                                            word=english_word,
                                            answer=turkish_word,
                                            front_language="en",
                                            back_language="tr",
                                            difficulty=difficulty,
                                            user_id=admin_user.id
                                        )
                                        db.session.add(word_en_tr)
                                        try:
                                            db.session.commit()  # Kelimeyi hemen kaydet
                                            word_en_tr_id = word_en_tr.id
                                        except Exception as commit_error:
                                            # Duplicate key hatası, rollback yap ve mevcut kelimeyi bul
                                            db.session.rollback()
                                            existing_word_en_tr = Word.query.filter_by(
                                                word=english_word,
                                                answer=turkish_word,
                                                front_language="en",
                                                back_language="tr",
                                                user_id=admin_user.id
                                            ).first()
                                            word_en_tr_id = existing_word_en_tr.id if existing_word_en_tr else None
                                            if not word_en_tr_id:
                                                continue  # Kelime bulunamazsa atla
                                    else:
                                        word_en_tr_id = existing_word_en_tr.id
                                    
                                    # TR->EN yönü için kelime oluştur
                                    existing_word_tr_en = Word.query.filter_by(
                                        word=turkish_word,
                                        answer=english_word,
                                        front_language="tr",
                                        back_language="en",
                                        user_id=admin_user.id
                                    ).first()
                                    
                                    if not existing_word_tr_en:
                                        # TR->EN kelime oluştur
                                        word_tr_en = Word(
                                            word=turkish_word,
                                            answer=english_word,
                                            front_language="tr",
                                            back_language="en",
                                            difficulty=difficulty,
                                            user_id=admin_user.id
                                        )
                                        db.session.add(word_tr_en)
                                        try:
                                            db.session.commit()  # Kelimeyi hemen kaydet
                                            word_tr_en_id = word_tr_en.id
                                        except Exception as commit_error:
                                            # Duplicate key hatası, rollback yap ve mevcut kelimeyi bul
                                            db.session.rollback()
                                            existing_word_tr_en = Word.query.filter_by(
                                                word=turkish_word,
                                                answer=english_word,
                                                front_language="tr",
                                                back_language="en",
                                                user_id=admin_user.id
                                            ).first()
                                            word_tr_en_id = existing_word_tr_en.id if existing_word_tr_en else None
                                            if not word_tr_en_id:
                                                continue  # Kelime bulunamazsa atla
                                    else:
                                        word_tr_en_id = existing_word_tr_en.id
                                    
                                    # Her iki kelime için flashcard ilişkisi kontrol et ve ekle
                                    word_ids = [word_en_tr_id, word_tr_en_id]
                                    added_words = 0
                                    
                                    for word_id in word_ids:
                                        if word_id:
                                            # Flashcard-Word ilişkisi var mı kontrol et
                                            existing_relation = FlashcardWords.query.filter_by(
                                                flashcard_id=flashcard.id,
                                                word_id=word_id
                                            ).first()
                                            
                                            if not existing_relation:
                                                flashcard_word = FlashcardWords(
                                                    flashcard_id=flashcard.id,
                                                    word_id=word_id
                                                )
                                                db.session.add(flashcard_word)
                                                try:
                                                    db.session.commit()  # İlişkiyi hemen kaydet
                                                    added_words += 1
                                                except Exception:
                                                    # İlişki zaten varsa rollback yap ve devam et
                                                    db.session.rollback()
                                                    continue
                                    
                                    word_count += added_words
                                            
                                except Exception as word_error:
                                    # Herhangi bir beklenmedik hata
                                    db.session.rollback()
                                    continue
                        
                        except Exception as e:
                            print(f"      ⚠️  Satır {index + 1} hatası: {str(e)[:100]}...")
                            db.session.rollback()  # Session'ı temizle
                            continue
                    
                    print(f"   ✅ {word_count} kelime eklendi")
                    
                except Exception as e:
                    print(f"   ❌ Dosya işleme hatası: {e}")
                    db.session.rollback()  # Session'ı temizle
                    continue
        
        print("\n🎉 Tüm admin flashcard'ları başarıyla oluşturuldu!")
        print("💡 Bu flashcard'lar public olarak tüm kullanıcılar tarafından görülebilir.")

if __name__ == "__main__":
    create_admin_flashcards()