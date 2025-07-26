from datetime import datetime, UTC
import random

import pandas as pd
from flask import session
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import current_user
from db import db
from sentence_transformers import SentenceTransformer, util
from models import Word, User, WordProgress, Flashcard, UserStudySession, UserDailyStats

flashcards = Blueprint('flashcards', __name__)
model = SentenceTransformer("distiluse-base-multilingual-cased-v2")


@flashcards.route("/flashcard/<int:flashcard_id>/words/add", methods=['GET', 'POST'])
def add_word_to_flashcard(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return "Flashcard bulunamadı", 404
    method = request.form.get('method')
    if request.method == "POST":
        return redirect(url_for('flashcards.add_word_to_flashcard', flashcard_id=flashcard_id))

    return render_template('add_word_to_flashcard.html', flashcard=flashcard)


@flashcards.route("/flashcard/<int:flashcard_id>/words/add/single", methods=["POST"])
def add_single_word(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    front_word = request.form['front_word'].strip()
    back_word = request.form['back_word'].strip()
    difficulty = request.form.get('difficulty', 'medium')

    # Check if the exact word-meaning pair already exists in this flashcard
    existing_word_in_flashcard = db.session.query(Word).filter(
        Word.flashcards.any(id=flashcard_id),
        Word.word.ilike(front_word),
        Word.answer.ilike(back_word)
    ).first()

    if existing_word_in_flashcard:
        # Bu kelime zaten bu flashcard'da var - mevcut anlamı göster ve güncelleme seçeneği sun
        return render_template('add_word_to_flashcard.html', 
                             flashcard=flashcard, 
                             existing_word=existing_word_in_flashcard,
                             searched_front_word=front_word,
                             searched_back_word=back_word)

    # Check if the same front word exists with different meaning in this flashcard
    existing_front_word_in_flashcard = db.session.query(Word).filter(
        Word.flashcards.any(id=flashcard_id),
        Word.word.ilike(front_word),
        ~Word.answer.ilike(back_word)
    ).first()

    if existing_front_word_in_flashcard:
        # Aynı kelime var ama farklı anlam - kullanıcıya seçenek sun
        return render_template('add_word_to_flashcard.html', 
                             flashcard=flashcard, 
                             existing_word=existing_front_word_in_flashcard,
                             searched_front_word=front_word,
                             searched_back_word=back_word,
                             different_meaning=True)

    # Word tablosunda mevcut kelimeyi ara (case-insensitive)
    existing_word = Word.query.filter(
        Word.word.ilike(front_word),
        Word.answer.ilike(back_word),
        Word.front_language == flashcard.front_language,
        Word.back_language == flashcard.back_language
    ).first()

    # Ters kelimeyi de ara
    existing_word_reverse = Word.query.filter(
        Word.word.ilike(back_word),
        Word.answer.ilike(front_word),
        Word.front_language == flashcard.back_language,
        Word.back_language == flashcard.front_language
    ).first()

    # İleri yönlü kelime
    if existing_word:
        word = existing_word
    else:
        try:
            word = Word(
                word=front_word,
                answer=back_word,
                front_language=flashcard.front_language,
                back_language=flashcard.back_language,
                difficulty=difficulty,
                user_id=current_user.id
            )
            db.session.add(word)
            db.session.flush()  # ID'yi almak için
        except Exception as word_error:
            db.session.rollback()
            # Başka bir session tarafından eklenmiş olabilir, tekrar ara
            existing_word = Word.query.filter(
                Word.word.ilike(front_word),
                Word.answer.ilike(back_word),
                Word.front_language == flashcard.front_language,
                Word.back_language == flashcard.back_language
            ).first()
            if existing_word:
                word = existing_word
            else:
                flash(f'Kelime ekleme hatası: {str(word_error)}', 'error')
                return render_template('add_word_to_flashcard.html', flashcard=flashcard)

    # Geri yönlü kelime (ters çeviri için)
    if existing_word_reverse:
        word_reverse = existing_word_reverse
    else:
        try:
            word_reverse = Word(
                word=back_word,
                answer=front_word,
                front_language=flashcard.back_language,
                back_language=flashcard.front_language,
                difficulty=difficulty,
                user_id=current_user.id
            )
            db.session.add(word_reverse)
            db.session.flush()  # ID'yi almak için
        except Exception as reverse_error:
            db.session.rollback()
            # Başka bir session tarafından eklenmiş olabilir, tekrar ara
            existing_word_reverse = Word.query.filter(
                Word.word.ilike(back_word),
                Word.answer.ilike(front_word),
                Word.front_language == flashcard.back_language,
                Word.back_language == flashcard.front_language
            ).first()
            if existing_word_reverse:
                word_reverse = existing_word_reverse
            else:
                flash(f'Ters kelime ekleme hatası: {str(reverse_error)}', 'error')
                return render_template('add_word_to_flashcard.html', flashcard=flashcard)

    # Flashcard'a kelime ekle (many-to-many ilişki)
    if word not in flashcard.words:
        flashcard.words.append(word)
    if word_reverse not in flashcard.words:
        flashcard.words.append(word_reverse)

    # WordProgress kayıtları oluştur (eğer yoksa)
    word_progress = WordProgress.query.filter_by(
        word_id=word.id,
        user_id=current_user.id
    ).first()

    if not word_progress:
        word_progress = WordProgress(
            word_id=word.id,
            user_id=current_user.id,
            is_learned=False,
            flashcard_id=flashcard_id
        )
        db.session.add(word_progress)

    word_progress_reverse = WordProgress.query.filter_by(
        word_id=word_reverse.id,
        user_id=current_user.id
    ).first()

    if not word_progress_reverse:
        word_progress_reverse = WordProgress(
            word_id=word_reverse.id,
            user_id=current_user.id,
            is_learned=False,
            flashcard_id=flashcard_id
        )
        db.session.add(word_progress_reverse)

    db.session.commit()

    # İstatistik tracking - Kelime ekleme
    from datetime import datetime, UTC
    today = datetime.now(UTC).date()
    daily_stats = UserDailyStats.query.filter_by(
        user_id=current_user.id,
        date=today
    ).first()

    if not daily_stats:
        daily_stats = UserDailyStats(
            user_id=current_user.id,
            date=today
        )
        db.session.add(daily_stats)

    # Kelime ekleme sayısını artır (hem ileri hem geri yön için +2)
    daily_stats.cards_added += 2

    # Kullanıcının günlük seri ve istatistiklerini güncelle
    current_user.update_streak()
    current_user.add_points(10)  # Kelime ekleme için 10 puan

    db.session.commit()
    flash('Kelime başarıyla eklendi!', 'success')
    return render_template('add_word_to_flashcard.html', flashcard=flashcard)


@flashcards.route("/flashcard/<int:flashcard_id>/words/update/<int:word_id>", methods=["POST"])
def update_existing_word(flashcard_id, word_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return "Flashcard bulunamadı", 404
    
    word = Word.query.get(word_id)
    if not word or word not in flashcard.words:
        flash('Kelime bulunamadı!', 'error')
        return redirect(url_for('flashcards.add_word_to_flashcard', flashcard_id=flashcard_id))
    
    new_back_word = request.form['new_back_word'].strip()
    
    if new_back_word:
        word.answer = new_back_word
        word.updated_at = datetime.now(UTC)
        db.session.commit()
        flash('Kelime anlamı başarıyla güncellendi!', 'success')
    else:
        flash('Yeni anlam boş olamaz!', 'error')
    
    return redirect(url_for('flashcards.add_word_to_flashcard', flashcard_id=flashcard_id))


@flashcards.route("/flashcard/<int:flashcard_id>/words/add/new-meaning", methods=["POST"])
def add_word_with_new_meaning(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return "Flashcard bulunamadı", 404
    
    front_word = request.form['front_word'].strip()
    back_word = request.form['back_word'].strip()
    difficulty = request.form.get('difficulty', 'medium')
    
    if not front_word or not back_word:
        flash('Kelime ve anlamı boş olamaz!', 'error')
        return redirect(url_for('flashcards.add_word_to_flashcard', flashcard_id=flashcard_id))
    
    # Create new word with different meaning
    try:
        word = Word(
            word=front_word,
            answer=back_word,
            front_language=flashcard.front_language,
            back_language=flashcard.back_language,
            difficulty=difficulty,
            user_id=current_user.id
        )
        db.session.add(word)
        db.session.flush()  # ID'yi almak için
        
        # Add to flashcard
        flashcard.words.append(word)
        
        # Create WordProgress
        word_progress = WordProgress(
            word_id=word.id,
            user_id=current_user.id,
            is_learned=False,
            flashcard_id=flashcard_id
        )
        db.session.add(word_progress)
        
        db.session.commit()
        flash('Kelime yeni anlamıyla başarıyla eklendi!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Kelime ekleme hatası: {str(e)}', 'error')
    
    return redirect(url_for('flashcards.add_word_to_flashcard', flashcard_id=flashcard_id))


@flashcards.route("/flashcard/<int:flashcard_id>/words/add/bulk", methods=["POST"])
def add_bulk_word(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return redirect(url_for('main.index'))
    
    files = request.files.getlist("files")
    
    if not files or all(not file.filename for file in files):
        flash('Dosya seçilmedi!', 'error')
        return redirect(url_for('flashcards.add_word_to_flashcard', flashcard_id=flashcard_id))
    
    added_words_count = 0
    
    for file in files:
        filename = file.filename
        if not filename or filename == '':
            continue
            
        file_ext = filename.split(".")[-1].lower()
        
        try:
            if file_ext == "csv":
                df = pd.read_csv(file, header=None)
            elif file_ext == "xlsx":
                df = pd.read_excel(file, header=None)
            elif file_ext == "txt":
                df = pd.read_csv(file, sep="\t", header=None)
            else:
                flash(f'Desteklenmeyen dosya formatı: {filename}', 'warning')
                continue
            df.columns = ['front_word', 'back_word', 'front_lang', 'back_lang', 'difficulty']
            
            for index, row in df.iterrows():
                try:
                    front_word = str(row['front_word']).strip()
                    back_word = str(row['back_word']).strip()
                    front_lang = str(row['front_lang']).strip()
                    back_lang = str(row['back_lang']).strip()
                    difficulty = str(row['difficulty']).strip()
                    
                    # Bu kelime çiftinin bu flashcard'da zaten var olup olmadığını kontrol et
                    existing_word_in_flashcard = db.session.query(Word).filter(
                        Word.flashcards.any(id=flashcard_id),
                        Word.word.ilike(front_word),
                        Word.answer.ilike(back_word),
                        Word.front_language == front_lang,
                        Word.back_language == back_lang
                    ).first()
                    
                    if existing_word_in_flashcard:
                        # Bu kelime zaten bu flashcard'da var, atla
                        continue
                    
                    # İleri yönlü kelimeyi kontrol et
                    existing_word = Word.query.filter(
                        Word.word == front_word,
                        Word.front_language == front_lang,
                        Word.back_language == back_lang,
                        Word.user_id == current_user.id
                    ).first()
                    
                    if existing_word:
                        word = existing_word
                    else:
                        try:
                            word = Word(
                                word=front_word,
                                answer=back_word,
                                front_language=front_lang,
                                back_language=back_lang,
                                difficulty=difficulty,
                                user_id=current_user.id
                            )
                            db.session.add(word)
                            db.session.flush()  # ID'yi almak için
                        except Exception as word_error:
                            db.session.rollback()
                            # Tekrar mevcut kelimeyi ara (başka bir session tarafından eklenmiş olabilir)
                            existing_word = Word.query.filter(
                                Word.word == front_word,
                                Word.front_language == front_lang,
                                Word.back_language == back_lang,
                                Word.user_id == current_user.id
                            ).first()
                            if existing_word:
                                word = existing_word
                            else:
                                print(f"İleri kelime ekleme hatası: {str(word_error)}")
                                continue
                    
                    # Geri yönlü kelimeyi kontrol et
                    existing_inverse_word = Word.query.filter(
                        Word.word == back_word,
                        Word.front_language == back_lang,
                        Word.back_language == front_lang,
                        Word.user_id == current_user.id
                    ).first()
                    
                    if existing_inverse_word:
                        inverse_word = existing_inverse_word
                    else:
                        try:
                            inverse_word = Word(
                                word=back_word,
                                answer=front_word,
                                front_language=back_lang,
                                back_language=front_lang,
                                difficulty=difficulty,
                                user_id=current_user.id
                            )
                            db.session.add(inverse_word)
                            db.session.flush()  # ID'yi almak için
                        except Exception as inverse_error:
                            db.session.rollback()
                            # Tekrar mevcut kelimeyi ara (başka bir session tarafından eklenmiş olabilir)
                            existing_inverse_word = Word.query.filter(
                                Word.word == back_word,
                                Word.front_language == back_lang,
                                Word.back_language == front_lang,
                                Word.user_id == current_user.id
                            ).first()
                            if existing_inverse_word:
                                inverse_word = existing_inverse_word
                            else:
                                print(f"Ters kelime ekleme hatası: {str(inverse_error)}")
                                continue
                    
                    # Flashcard'a kelimeleri ekle (eğer yoksa)
                    try:
                        word_added = False
                        inverse_word_added = False
                        
                        if word not in flashcard.words:
                            flashcard.words.append(word)
                            added_words_count += 1
                            word_added = True
                            
                        if inverse_word not in flashcard.words:
                            flashcard.words.append(inverse_word)
                            added_words_count += 1
                            inverse_word_added = True
                        
                        # WordProgress kayıtları oluştur (sadece flashcard'a yeni eklenen kelimeler için)
                        if word_added or word in flashcard.words:
                            existing_word_progress = WordProgress.query.filter_by(
                                word_id=word.id,
                                user_id=current_user.id,
                                flashcard_id=flashcard_id
                            ).first()
                            
                            if not existing_word_progress:
                                word_progress = WordProgress(
                                    word_id=word.id,
                                    user_id=current_user.id,
                                    is_learned=False,
                                    flashcard_id=flashcard_id
                                )
                                db.session.add(word_progress)
                        
                        if inverse_word_added or inverse_word in flashcard.words:
                            existing_inverse_progress = WordProgress.query.filter_by(
                                word_id=inverse_word.id,
                                user_id=current_user.id,
                                flashcard_id=flashcard_id
                            ).first()
                            
                            if not existing_inverse_progress:
                                word_progress_inverse = WordProgress(
                                    word_id=inverse_word.id,
                                    user_id=current_user.id,
                                    is_learned=False,
                                    flashcard_id=flashcard_id
                                )
                                db.session.add(word_progress_inverse)
                            
                        # Her kelime çifti için flush yapalım
                        db.session.flush()
                        
                    except Exception as progress_error:
                        db.session.rollback()
                        print(f"Progress ekleme hatası: {str(progress_error)}")
                        continue
                        
                except Exception as row_error:
                    # Tek satır hatası durumunda sadece o satırı atla
                    print(f"Satır {index} işlenirken hata: {str(row_error)}")
                    continue
                
        except Exception as e:
            db.session.rollback()
            flash(f'Dosya işleme hatası ({filename}): {str(e)}', 'error')
            continue
    
    if added_words_count > 0:
        try:
            db.session.commit()
            flash(f'{added_words_count} kelime başarıyla eklendi!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Kelimeler kaydedilirken hata oluştu: {str(e)}', 'error')
    else:
        flash('Hiçbir kelime eklenemedi!', 'warning')
    
    return redirect(url_for('flashcards.flashcard_detail', flashcard_id=flashcard_id))

@flashcards.route("/flashcard/<int:flashcard_id>/delete")
def flashcard_delete(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return {"status": "error", "message": "Flashcard not found"}, 404
    
    # Bu flashcard'a ait tüm WordProgress kayıtlarını sil
    WordProgress.query.filter_by(flashcard_id=flashcard_id, user_id=current_user.id).delete()
    
    # Bu flashcard'a ait tüm UserStudySession kayıtlarını sil
    UserStudySession.query.filter_by(flashcard_id=flashcard_id, user_id=current_user.id).delete()
    
    # Flashcard'ı sil
    db.session.delete(flashcard)
    db.session.commit()
    
    flash('Flashcard başarıyla silindi!', 'success')
    return redirect(url_for('flashcards.add_flashcard'))


@flashcards.route("/add-flashcard", methods=['GET', 'POST'])
def add_flashcard():
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == "POST":
        title = request.form['title']
        category = request.form['category']
        description = request.form['description']
        language_from = request.form['language_from']
        language_to = request.form['language_to']
        is_public = request.form.get('is_public') == 'on'
        visibility = 'public' if is_public else 'private'
        is_there_flashcard = Flashcard.query.filter_by(name=title, category=category, user_id=current_user.id).first()
        if is_there_flashcard:
            flash("Bu isimde bir flashcard var zaten!", "error")
            return redirect(url_for('flashcards.add_flashcard'))
        flashcard = Flashcard(
            name=title, category=category,
            description=description, visibility=visibility,
            user_id=current_user.id, front_language=language_from,
            back_language=language_to
        )
        db.session.add(flashcard)
        db.session.commit()
    flashcards = Flashcard.query.filter_by(user_id=current_user.id).all()

    # Her flashcard için kelime istatistiklerini hesapla
    flashcards_with_stats = []
    global_total_words = 0
    global_mastered_words = 0

    for flashcard in flashcards:
        words = flashcard.words
        total_words = len(words)

        # Bu flashcard'a ait WordProgress'leri al
        mastered_words = 0
        for word in words:
            progress = WordProgress.query.filter_by(
                word_id=word.id,
                user_id=current_user.id,
                flashcard_id=flashcard.id
            ).first()
            if progress and progress.is_learned:
                mastered_words += 1

        learning_words = total_words - mastered_words

        # Flashcard objesine istatistikleri ekle
        flashcard.total_words = total_words
        flashcard.mastered_words = mastered_words
        flashcard.learning_words = learning_words

        # Global istatistikleri güncelle
        global_total_words += total_words
        global_mastered_words += mastered_words

        flashcards_with_stats.append(flashcard)

    global_learning_words = global_total_words - global_mastered_words

    return render_template("add_flashcard.html",
                           flashcards=flashcards_with_stats,
                           total_words=global_total_words,
                           mastered_words=global_mastered_words,
                           learning_words=global_learning_words)


@flashcards.route("/flashcard/<int:flashcard_id>/edit", methods=['GET', 'POST'])
def edit_flashcard(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))
    flashcard = Flashcard.query.filter_by(user_id=current_user.id, id=flashcard_id).first()
    if not flashcard:
        return "Flashcard is not found", 404
    if request.method == "POST":
        title = request.form['title']
        category = request.form['category']
        description = request.form['description']
        language_from = request.form['language_from']
        language_to = request.form['language_to']
        is_public = request.form.get('is_public') == 'on'
        visibility = 'public' if is_public else 'private'
        flashcard.name = title
        flashcard.category = category
        flashcard.description = description
        flashcard.visibility = visibility
        flashcard.front_language = language_from
        flashcard.back_language = language_to
        flashcard.updated_at = datetime.now(UTC)
        db.session.commit()
        return redirect(url_for("flashcards.flashcard_detail", flashcard_id=flashcard_id))
    return render_template("edit_flashcard.html", flashcard=flashcard)


@flashcards.route("/flashcard/<int:flashcard_id>/detail", methods=['GET'])
def flashcard_detail(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))

    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return "Flashcard is not found", 404

    words = flashcard.words

    front_language = flashcard.front_language
    # Her kelime için progress bilgisini ekle
    words_with_progress = []
    for word in words:
        if word.front_language == front_language:
            progress = WordProgress.query.filter_by(
                word_id=word.id,
                user_id=current_user.id,
                flashcard_id=flashcard_id
            ).first()
            word.progress = progress
            words_with_progress.append(word)
    total_words = len(words_with_progress)
    mastered_words = len([w for w in words_with_progress if w.progress and w.progress.is_learned])
    learning_words = total_words - mastered_words

    return render_template('flashcard_detail.html',
                           flashcard=flashcard,
                           words=words_with_progress,
                           total_words=total_words,
                           mastered_words=mastered_words,
                           learning_words=learning_words)


@flashcards.route('/flashcard/<int:flashcard_id>/detail/word/edit/<int:word_id>', methods=['GET', 'POST'])
def edit_word(flashcard_id, word_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # Flashcard'ın kullanıcıya ait olduğunu kontrol et
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return "Flashcard bulunamadı", 404

    # Kelimenin bu flashcard'da olduğunu kontrol et
    word = Word.query.get(word_id)
    if not word or word not in flashcard.words:
        return "Kelime bulunamadı", 404

    if request.method == 'POST':
        word.word = request.form['front_word']
        word.front_language = request.form['front_language']
        word.answer = request.form['back_word']
        word.back_language = request.form['back_language']
        word.difficulty = request.form['difficulty']
        word.updated_at = datetime.now(UTC)
        db.session.commit()
        return redirect(url_for("flashcards.flashcard_detail", flashcard_id=flashcard_id))

    return render_template("edit_word.html", word=word, flashcard=flashcard)


@flashcards.route('/flashcard/<int:flashcard_id>/detail/word/delete/<int:word_id>', methods=['GET', 'POST'])
def delete_word(flashcard_id, word_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))
    word = Word.query.get(word_id)
    if not word:
        return "Kelime bulunamadı", 404
    WordProgress.query.filter_by(word_id=word.id).delete()
    db.session.delete(word)
    db.session.commit()
    return redirect(url_for("flashcards.flashcard_detail", flashcard_id=flashcard_id))


@flashcards.route('/flashcard/<int:flashcard_id>/word/<int:word_id>/mark-learned', methods=['POST'])
def mark_word_learned(flashcard_id, word_id):
    if not current_user.is_authenticated:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    progress = WordProgress.query.filter_by(
        word_id=word_id,
        user_id=current_user.id,
        flashcard_id=flashcard_id
    ).first()

    if not progress:
        return jsonify({"status": "error", "message": "Progress not found"}), 404

    progress.is_learned = True
    progress.last_review_at = datetime.now(UTC)
    db.session.commit()

    return jsonify({"status": "success"})


@flashcards.route('/flashcard/<int:flashcard_id>/word/<int:word_id>/mark-learning', methods=['POST'])
def mark_word_learning(flashcard_id, word_id):
    if not current_user.is_authenticated:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    progress = WordProgress.query.filter_by(
        word_id=word_id,
        user_id=current_user.id,
        flashcard_id=flashcard_id
    ).first()

    if not progress:
        return jsonify({"status": "error", "message": "Progress not found"}), 404

    progress.is_learned = False
    progress.last_review_at = datetime.now(UTC)
    db.session.commit()

    return jsonify({"status": "success"})


@flashcards.route("/flashcard/<int:flashcard_id>/study", methods=['GET'])
def flashcard_study(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # Flashcard'ın kullanıcıya ait olduğunu kontrol et
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return "Flashcard bulunamadı", 404

    # Kelime sayılarını hesapla
    words = flashcard.words
    total_words = len(words)
    mastered_words = len(
        [w for w in words if any(wp.is_learned for wp in w.progresses if wp.user_id == current_user.id)])
    learning_words = total_words - mastered_words

    return render_template("flashcard_study.html",
                           flashcard=flashcard,
                           total_words=total_words,
                           mastered_words=mastered_words,
                           learning_words=learning_words)


@flashcards.route("/flashcard/<int:flashcard_id>/study/flashcard", methods=["GET"])
def flashcard_study_flashcard(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))

    lang_mode = request.args.get('lang_mode')
    word_filter = request.args.get('word_filter', 'all')
    language_modes = {
        'tr_to_en': 'tr',
        'en_to_tr': 'en',
        'mixed': 'mixed'
    }
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return "Flashcard bulunamadı", 404

    # Apply language filter first
    if language_modes.get(lang_mode) == "mixed":
        words = flashcard.words
        front_language = "mixed"
        back_language = "mixed"
    else:
        words = [w for w in flashcard.words if w.front_language == language_modes.get(lang_mode)]
        if words:
            front_language = words[0].front_language
            back_language = words[0].back_language
        else:
            # Fallback to language mode based on selection
            if lang_mode == 'tr_to_en':
                front_language = 'tr'
                back_language = 'en'
            elif lang_mode == 'en_to_tr':
                front_language = 'en'
                back_language = 'tr'
            else:
                front_language = 'mixed'
                back_language = 'mixed'

    # Apply word filter based on learning status
    if word_filter and word_filter != 'all':
        filtered_words = []
        for word in words:
            progress = WordProgress.query.filter_by(
                word_id=word.id,
                user_id=current_user.id,
                flashcard_id=flashcard_id
            ).first()
            
            if word_filter == 'learned' and progress and progress.is_learned:
                filtered_words.append(word)
            elif word_filter == 'not_learned' and (not progress or not progress.is_learned):
                filtered_words.append(word)
        words = filtered_words

    if not words:
        return render_template("flashcard_study_flashcard.html",
                               flashcard=flashcard,
                               words=[],
                               total_words=0,
                               lang_mode=lang_mode,
                               word_filter=word_filter,
                               front_language=front_language,
                               back_language=back_language)

    formatted_words = []
    for word in words:
        formatted_words.append({
            'id': word.id,
            'front_word': word.word,
            'back_word': word.answer,
            'front_language': word.front_language,
            'back_language': word.back_language,
            'difficulty': word.difficulty
        })
    random.shuffle(formatted_words)
    flashcard.last_studied = datetime.now(UTC)
    db.session.commit()
    return render_template("flashcard_study_flashcard.html",
                           flashcard=flashcard,
                           words=formatted_words,
                           total_words=len(formatted_words),
                           lang_mode=lang_mode,
                           word_filter=word_filter,
                           front_language=front_language,
                           back_language=back_language)


@flashcards.route("/flashcard/<int:flashcard_id>/study/flashcard/finish", methods=["POST"])
def flashcard_study_flashcard_finish(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))
    data = request.get_json()
    results = data.get('results', {})
    early_exit = data.get('early_exit', False)
    total_words = data.get('total_words', 0)
    completed_at = data.get('completed_at')
    started_at = data.get('started_at')

    # Eğer results boşsa, hiçbir kelime çalışılmamış demektir
    if not results:
        learned_count = 0
        practice_count = 0
        not_learned_count = 0
    else:
        learned_count = sum(1 for r in results.values() if r['status'] == 'learned')
        practice_count = sum(1 for r in results.values() if r['status'] == 'practice')
        not_learned_count = sum(1 for r in results.values() if r['status'] == 'not_learned')

    # Lang mode bilgisini de al
    lang_mode = request.get_json().get('lang_mode', 'mixed')

    # Flashcard ve language mode'a specific session key kullan
    session_key = f'study_results_{flashcard_id}_{lang_mode}'
    session[session_key] = {
        'learned': learned_count,
        'practice': practice_count,
        'not_learned': not_learned_count,
        'results': results,
        "early_exit": early_exit,
        "total_words": total_words,
        "completed_at": completed_at,
        "flashcard_id": flashcard_id,
        "lang_mode": lang_mode
    }

    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if flashcard:
        flashcard.last_studied = datetime.now(UTC)

    # User'ın last_study_date'ini güncelle
    user = User.query.get(current_user.id)
    user.last_study_date = datetime.now(UTC)

    # UserStudySession oluştur ve tracking yap
    if results:  # Sadece gerçekten çalışma yapıldıysa
        # Çalışma süresini hesapla
        duration_minutes = 1  # Varsayılan değer
        start_time = datetime.now(UTC)
        end_time = datetime.now(UTC)

        if started_at and completed_at:
            try:
                start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                duration_minutes = max(int((end_time - start_time).total_seconds() / 60), 1)
            except:
                duration_minutes = 1

        # Study session oluştur
        study_session = UserStudySession(
            user_id=current_user.id,
            flashcard_id=flashcard_id,
            session_type='flashcard_study',
            started_at=start_time,
            ended_at=end_time,
            duration_minutes=duration_minutes,
            cards_seen=len(results),
            correct_answers=learned_count,
            wrong_answers=practice_count + not_learned_count,
            points_earned=learned_count * 5 + practice_count * 2  # Learned: 5 puan, Practice: 2 puan
        )
        db.session.add(study_session)
        study_session.end_session()  # Bu otomatik olarak daily_stats'ı da güncelleyecek

    db.session.commit()
    return jsonify({"status": "success"})


@flashcards.route("/flashcard/<int:flashcard_id>/study/language-select", methods=["GET"])
def flashcard_study_language_select(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return "Flashcard bulunamadı", 404

    mode = request.args.get('mode')
    if not mode or mode not in ['flashcard', 'quiz', 'writing']:
        return redirect(url_for('flashcards.flashcard_study', flashcard_id=flashcard_id))

    # Kelime sayılarını hesapla
    words = flashcard.words
    total_words = len(words)
    mastered_words = len(
        [w for w in words if any(wp.is_learned for wp in w.progresses if wp.user_id == current_user.id)])
    learning_words = total_words - mastered_words

    return render_template("study_language_select.html",
                           flashcard=flashcard,
                           mode=mode,
                           total_words=total_words,
                           mastered_words=mastered_words,
                           learning_words=learning_words)


@flashcards.route("/flashcard/<int:flashcard_id>/study/results", methods=["GET"])
def flashcard_study_result(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # Lang mode bilgisini al
    lang_mode = request.args.get('lang_mode', 'mixed')

    # Flashcard ve language mode'a specific session key kullan
    session_key = f'study_results_{flashcard_id}_{lang_mode}'
    study_results = session.get(session_key, {})

    # Eğer language-mode specific key yoksa, sadece flashcard-specific key'i dene
    if not study_results:
        fallback_session_key = f'study_results_{flashcard_id}'
        study_results = session.get(fallback_session_key, {})

    # Son çare olarak genel key'i dene
    if not study_results:
        study_results = session.get('study_results', {})

    if not study_results:
        # Eğer session'da veri yoksa study sayfasına yönlendir
        return redirect(url_for('flashcards.flashcard_study', flashcard_id=flashcard_id))

    # Flashcard ID eşleşmesini kontrol et
    if study_results.get('flashcard_id') != flashcard_id:
        return redirect(url_for('flashcards.flashcard_study', flashcard_id=flashcard_id))

    # Session verilerinin kopyasını al
    results_copy = {
        'learned': study_results.get('learned', 0),
        'practice': study_results.get('practice', 0),
        'not_learned': study_results.get('not_learned', 0),
        'results': study_results.get('results', {}),
        'early_exit': study_results.get('early_exit', False),
        'total_words': study_results.get('total_words', 0),
        'completed_at': study_results.get('completed_at', None)
    }

    user = User.query.get(current_user.id)
    user.last_study_date = datetime.now(UTC)

    # Flashcard'ın last_studied tarihini güncelle
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if flashcard:
        flashcard.last_studied = datetime.now(UTC)

    # WordProgress güncellemeleri yap
    if study_results.get('results'):
        for word_id, word_result in study_results.get('results').items():
            status = word_result.get("status")
            wp = WordProgress.query.filter_by(
                word_id=word_id,
                user_id=current_user.id,
                flashcard_id=flashcard_id
            ).first()
            if wp:
                wp.is_learned = True if status == "learned" else False
                wp.times_seen += 1
                wp.last_review_at = datetime.now(UTC)
                if status == "learned":
                    wp.correct_count += 1
                else:
                    wp.wrong_count += 1
        db.session.commit()

    # Kullanıldıktan sonra session'ı temizle
    session.pop(session_key, None)
    session.pop('study_results', None)

    # Diğer eski study_results session'larını da temizle
    keys_to_remove = [key for key in list(session.keys()) if key.startswith('study_results_')]
    for key in keys_to_remove:
        session.pop(key, None)

    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()

    return render_template('study_results.html',
                           flashcard=flashcard,
                           flashcard_id=flashcard_id,
                           learned_count=results_copy['learned'],
                           practice_count=results_copy['practice'],
                           not_learned_count=results_copy['not_learned'],
                           results=results_copy['results'],
                           early_exit=results_copy['early_exit'],
                           total_words=results_copy['total_words'],
                           completed_at=results_copy['completed_at'])


@flashcards.route("/flashcard/<int:flashcard_id>/study/quiz", methods=["GET"])
def flashcard_study_quiz(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # Sadece quiz sonuçlarını temizle (study_results'ları burada temizleme)
    session.pop('quiz_results', None)

    # Flashcard'ın kullanıcıya ait olduğunu kontrol et
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return "Flashcard bulunamadı", 404

    lang_mode = request.args.get('lang_mode')
    word_filter = request.args.get('word_filter', 'all')
    language_modes = {
        'tr_to_en': 'tr',
        'en_to_tr': 'en',
        'mixed': 'mixed'
    }

    quiz_items = prepare_quiz_questions(language_modes.get(lang_mode), flashcard_id, word_filter)

    if not quiz_items:
        flash("Quiz oluşturmak için en az 3 kelimeye ihtiyaç var!", "warning")
        return redirect(url_for('flashcards.flashcard_study', flashcard_id=flashcard_id))
    flashcard.last_studied = datetime.now(UTC)
    db.session.commit()
    return render_template("flashcard_study_quiz.html",
                           flashcard=flashcard,
                           quiz_items=quiz_items,
                           total_questions=len(quiz_items),
                           lang_mode=lang_mode,
                           word_filter=word_filter)


def prepare_quiz_questions(mode, flashcard_id, word_filter='all'):
    user_id = current_user.id
    quiz_items = []
    userwordProgress = WordProgress.query.filter_by(user_id=user_id, flashcard_id=flashcard_id).all()
    print(userwordProgress, user_id,flashcard_id,word_filter,len(userwordProgress))
    # Apply word filter
    if word_filter != 'all':
        filtered_progress = []
        for progress in userwordProgress:
            if word_filter == 'learned' and progress.is_learned:
                filtered_progress.append(progress)
            elif word_filter == 'not_learned' and not progress.is_learned:
                filtered_progress.append(progress)
        userwordProgress = filtered_progress
    
    if len(userwordProgress) < 3:
        return quiz_items
    tr_words = []
    en_words = []
    for p in userwordProgress:
        if p.word.front_language.lower() == "tr":
            tr_words.append(p.word.word)
        if p.word.back_language.lower() == "tr":
            tr_words.append(p.word.answer)
        if p.word.front_language.lower() == "en":
            en_words.append(p.word.word)
        if p.word.back_language.lower() == "en":
            en_words.append(p.word.answer)
    if mode == "tr":
        print("buradayım")
        for p in userwordProgress:
            if p.word.front_language.lower() == "tr" and p.word.back_language.lower() == "en":
                question = p.word.word
                answer = p.word.answer
                pool = [w for w in en_words if w != answer]
                wrong_opts = random.sample(pool, min(3, len(pool)))
                options = wrong_opts + [answer]
                random.shuffle(options)
                quiz_items.append({
                    "id": p.word.id,
                    "question": question,
                    "answer": answer,
                    "options": options
                })
    elif mode == "en":
        for p in userwordProgress:
            if p.word.front_language.lower() == "en" and p.word.back_language.lower() == "tr":
                question = p.word.word
                answer = p.word.answer
                pool = [w for w in tr_words if w != answer]
                wrong_opts = random.sample(pool, min(3, len(pool)))
                options = wrong_opts + [answer]
                random.shuffle(options)
                quiz_items.append({
                    "id": p.word.id,
                    "question": question,
                    "answer": answer,
                    "options": options
                })

    else:  # mixed
        print("sa buradayım")
        for p in userwordProgress:
            if p.word.front_language.lower() == "tr" and p.word.back_language.lower() == "en":
                question = p.word.word
                answer = p.word.answer
                pool = [w for w in en_words if w != answer]
                wrong_opts = random.sample(pool, min(3, len(pool)))
                options = wrong_opts + [answer]
                random.shuffle(options)
                quiz_items.append({
                    "id": p.word.id,
                    "question": question,
                    "answer": answer,
                    "options": options
                })
            if p.word.front_language.lower() == "en" and p.word.back_language.lower() == "tr":
                question = p.word.word
                answer = p.word.answer
                pool = [w for w in tr_words if w != answer]
                wrong_opts = random.sample(pool, min(3, len(pool)))
                options = wrong_opts + [answer]
                random.shuffle(options)
                quiz_items.append({
                    "id": p.word.id,
                    "question": question,
                    "answer": answer,
                    "options": options
                })
    random.shuffle(quiz_items)
    return quiz_items


@flashcards.route('/flashcard/<int:flashcard_id>/study/quiz/finish', methods=['POST'])
def flashcard_quiz_finished(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # JSON formatından veri al
    data = request.get_json()
    answers = data.get('answers', [])

    correct_count = 0
    wrong_count = 0
    results = []

    # Eğer hiç cevap yoksa veya tüm cevaplar boşsa, boş sonuç oluştur
    if not answers or not any(answer.get('user_answer') for answer in answers):
        # Hiç cevap verilmemiş, sadece soruları results'a ekle ama veritabanını güncelleme
        for answer in answers:
            results.append({
                "question": answer.get('question', ''),
                "user_answer": None,
                "correct_answer": answer.get('correct_answer', ''),
                "is_correct": False,
            })

        # Sonuçları session'a kaydet (boş sonuçlar)
        session['quiz_results'] = {
            'results': results,
            'correct_count': 0,
            'wrong_count': 0,
            'total_questions': len(answers),
            'flashcard_id': flashcard_id
        }

        # Flashcard'ın last_studied tarihini güncelle (quiz'e girdi ama cevaplamadı)
        flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
        if flashcard:
            flashcard.last_studied = datetime.now(UTC)

        # User'ın last_study_date'ini güncelle
        user = User.query.get(current_user.id)
        user.last_study_date = datetime.now(UTC)

        db.session.commit()

        return jsonify({"status": "success"})

    # Normal işlem: Cevaplar var
    if answers:
        for answer in answers:
            word_id = answer['id']
            question = answer['question']
            correct_answer = answer['correct_answer']
            user_answer = answer['user_answer']

            # WordProgress'i flashcard_id ile birlikte ara
            progress = WordProgress.query.filter_by(
                word_id=word_id,
                user_id=current_user.id,
                flashcard_id=flashcard_id
            ).first()

            is_correct = correct_answer == user_answer

            if progress:
                progress.times_seen += 1
                progress.last_review_at = datetime.now(UTC)

                if is_correct:
                    progress.correct_count += 1
                    progress.is_learned = True
                    correct_count += 1
                else:
                    progress.wrong_count += 1
                    progress.is_learned = False
                    wrong_count += 1

                db.session.commit()

            results.append({
                "question": question,
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
            })

    # Sonuçları session'a kaydet
    session['quiz_results'] = {
        'results': results,
        'correct_count': correct_count,
        'wrong_count': wrong_count,
        'total_questions': len(answers),
        'flashcard_id': flashcard_id
    }

    # Flashcard'ın last_studied tarihini güncelle
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if flashcard:
        flashcard.last_studied = datetime.now(UTC)

    # User'ın last_study_date'ini güncelle
    user = User.query.get(current_user.id)
    user.last_study_date = datetime.now(UTC)

    # Quiz için UserStudySession oluştur ve tracking yap
    if answers and any(answer.get('user_answer') for answer in answers):
        # Quiz session oluştur
        study_session = UserStudySession(
            user_id=current_user.id,
            flashcard_id=flashcard_id,
            session_type='quiz',
            duration_minutes=max(len(answers) // 4, 1),  # Kelime başına yaklaşık 15 saniye
            cards_seen=len(answers),
            correct_answers=correct_count,
            wrong_answers=wrong_count,
            points_earned=correct_count * 3  # Quiz doğru cevap: 3 puan
        )
        db.session.add(study_session)
        study_session.end_session()

    db.session.commit()

    return jsonify({"status": "success"})


@flashcards.route('/flashcard/<int:flashcard_id>/study/quiz/result', methods=['GET'])
def flashcard_quiz_result(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))

    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return "Flashcard bulunamadı", 404

    quiz_results = session.get('quiz_results', {})
    if not quiz_results or quiz_results.get('flashcard_id') != flashcard_id:
        return redirect(url_for('flashcards.flashcard_study', flashcard_id=flashcard_id))

    # Session verilerini al ve temizle
    results = quiz_results.get('results', [])
    correct_count = quiz_results.get('correct_count', 0)
    wrong_count = quiz_results.get('wrong_count', 0)
    total_questions = quiz_results.get('total_questions', 0)

    # Kullanıldıktan sonra session'ı temizle
    session.pop('quiz_results', None)

    return render_template('flashcard_quiz_result.html',
                           flashcard=flashcard,
                           results=results,
                           correct_count=correct_count,
                           wrong_count=wrong_count,
                           total_questions=total_questions)


@flashcards.route("/flashcard/<int:flashcard_id>/study/writing", methods=["GET"])
def flashcard_study_writing(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))

    lang_mode = request.args.get('lang_mode')
    word_filter = request.args.get('word_filter', 'all')
    language_modes = {
        'tr_to_en': 'tr',
        'en_to_tr': 'en',
        'mixed': 'mixed'
    }
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return "Flashcard bulunamadı", 404

    # Sadece kullanıcının bu flashcard'a ait WordProgress'leri olan kelimeleri al
    user_words = []
    for word in flashcard.words:
        progress = WordProgress.query.filter_by(
            word_id=word.id,
            user_id=current_user.id,
            flashcard_id=flashcard_id
        ).first()
        if progress:
            # Apply word filter
            if word_filter == 'all':
                user_words.append(word)
            elif word_filter == 'learned' and progress.is_learned:
                user_words.append(word)
            elif word_filter == 'not_learned' and not progress.is_learned:
                user_words.append(word)

    # Dil moduna göre filtrele
    if language_modes.get(lang_mode) == "mixed":
        words = user_words
    else:
        words = [w for w in user_words if w.front_language == language_modes.get(lang_mode)]

    if not words:
        import json
        words_json = json.dumps([])
        return render_template("flashcard_study_writing.html",
                               flashcard=flashcard,
                               words=[],
                               words_json=words_json,
                               total_words=0,
                               lang_mode=lang_mode,
                               word_filter=word_filter)

    # Kelimeleri karıştır
    import random
    random.shuffle(words)

    # Session'ı temizle
    session.pop('writing_results', None)

    # Words'ü JSON string'e çevir
    import json
    words_json = json.dumps([{
        'id': word.id,
        'word': word.word,
        'answer': word.answer,
        'front_language': word.front_language,
        'back_language': word.back_language,
        'difficulty': word.difficulty
    } for word in words])
    flashcard.last_studied = datetime.now(UTC)
    db.session.commit()
    return render_template("flashcard_study_writing.html",
                           flashcard=flashcard,
                           words=words,
                           words_json=words_json,
                           total_words=len(words),
                           lang_mode=lang_mode,
                           word_filter=word_filter)


@flashcards.route("/flashcard/<int:flashcard_id>/study/writing/check", methods=["POST"])
def flashcard_study_writing_check(flashcard_id):
    if not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized"}), 401

    # Flashcard kontrolü
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return jsonify({"error": "Flashcard bulunamadı"}), 404

    data = request.get_json()
    user_answer = data.get('user_answer', '').strip()
    correct_answer = data.get('correct_answer', '')
    word_id = data.get('word_id')

    # Cevabı kontrol et (büyük/küçük harf duyarsız)
    is_correct = user_answer.lower() == correct_answer.lower() if user_answer else False

    # Similarity kontrolü (daha esnek)
    if not is_correct and user_answer:
        try:
            similarity = check_with_llm(user_answer, correct_answer)
            is_correct = similarity >= 0.8
        except Exception as e:
            print(f"LLM check error: {e}")
            # LLM hatası durumunda exact match sonucunu kullan
            pass

    return jsonify({
        "is_correct": is_correct,
        "user_answer": user_answer,
        "correct_answer": correct_answer
    })


@flashcards.route("/flashcard/<int:flashcard_id>/study/writing/finish", methods=["POST"])
def flashcard_study_writing_finish(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # JSON verilerini al
    data = request.get_json()
    answers = data.get('answers', [])
    lang_mode = data.get('lang_mode', 'mixed')
    early_exit = data.get('early_exit', False)
    completed_at = data.get('completed_at')

    correct_count = 0
    wrong_count = 0
    results = []

    for answer in answers:
        word_id = answer.get('word_id')
        user_answer = answer.get('user_answer', '').strip()
        correct_answer = answer.get('correct_answer', '')
        question = answer.get('question', '')

        # Cevabı kontrol et (büyük/küçük harf duyarsız)
        is_correct = user_answer.lower() == correct_answer.lower() if user_answer else False

        # Similarity kontrolü (daha esnek)
        if not is_correct and user_answer:
            similarity = check_with_llm(user_answer, correct_answer)
            is_correct = similarity >= 0.8

        if is_correct:
            correct_count += 1
        else:
            wrong_count += 1

        # WordProgress güncelle
        progress = WordProgress.query.filter_by(
            word_id=word_id,
            user_id=current_user.id,
            flashcard_id=flashcard_id
        ).first()

        if progress:
            progress.times_seen += 1
            progress.last_review_at = datetime.now(UTC)

            if is_correct:
                progress.correct_count += 1
                progress.is_learned = True
            else:
                progress.wrong_count += 1
                progress.is_learned = False

        results.append({
            'word_id': word_id,
            'question': question,
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct
        })

    # Flashcard'ın last_studied tarihini güncelle
    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if flashcard:
        flashcard.last_studied = datetime.now(UTC)

    # User'ın last_study_date'ini güncelle
    user = User.query.get(current_user.id)
    user.last_study_date = datetime.now(UTC)

    # Writing için UserStudySession oluştur ve tracking yap
    if answers:
        # Writing session oluştur
        study_session = UserStudySession(
            user_id=current_user.id,
            flashcard_id=flashcard_id,
            session_type='writing',
            duration_minutes=max(len(answers) // 3, 1),  # Kelime başına yaklaşık 20 saniye
            cards_seen=len(answers),
            correct_answers=correct_count,
            wrong_answers=wrong_count,
            points_earned=correct_count * 4  # Writing doğru cevap: 4 puan (daha zor)
        )
        db.session.add(study_session)
        study_session.end_session()

    db.session.commit()

    # Sonuçları session'a kaydet
    session_key = f'writing_results_{flashcard_id}_{lang_mode}'
    session[session_key] = {
        'results': results,
        'correct_count': correct_count,
        'wrong_count': wrong_count,
        'total_questions': len(answers),
        'flashcard_id': flashcard_id,
        'lang_mode': lang_mode,
        'early_exit': early_exit,
        'completed_at': completed_at
    }

    return jsonify({"status": "success"})


@flashcards.route("/flashcard/<int:flashcard_id>/study/writing/result", methods=["GET"])
def flashcard_study_writing_result(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))

    lang_mode = request.args.get('lang_mode', 'mixed')
    session_key = f'writing_results_{flashcard_id}_{lang_mode}'

    writing_results = session.get(session_key, {})

    if not writing_results or writing_results.get('flashcard_id') != flashcard_id:
        return redirect(url_for('flashcards.flashcard_study', flashcard_id=flashcard_id))

    flashcard = Flashcard.query.filter_by(id=flashcard_id, user_id=current_user.id).first()
    if not flashcard:
        return "Flashcard bulunamadı", 404

    # Session verilerini al
    results = writing_results.get('results', [])
    correct_count = writing_results.get('correct_count', 0)
    wrong_count = writing_results.get('wrong_count', 0)
    total_questions = writing_results.get('total_questions', 0)
    early_exit = writing_results.get('early_exit', False)
    completed_at = writing_results.get('completed_at')

    # Session'ı temizle
    session.pop(session_key, None)

    return render_template('flashcard_study_writing_result.html',
                           flashcard=flashcard,
                           results=results,
                           correct_count=correct_count,
                           wrong_count=wrong_count,
                           total_questions=total_questions,
                           early_exit=early_exit,
                           completed_at=completed_at,
                           lang_mode=lang_mode)


@flashcards.route("/flashcards")
def flashcards_list():
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # Pagination parametrelerini al
    page = request.args.get('page', 1, type=int)
    per_page = 9  # Her sayfada 9 flashcard göster

    # Tüm public flashcard'ları al (diğer kullanıcılardan da) - paginate ile
    public_flashcards_pagination = Flashcard.query.filter_by(visibility="public").paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    public_flashcards = public_flashcards_pagination.items
    flashcards_with_stats = []

    for flashcard in public_flashcards:
        words = flashcard.words
        total_words = len(words)

        # Bu kullanıcının bu flashcard'ı kendi koleksiyonuna eklemiş mi kontrol et
        user_has_copy = Flashcard.query.filter_by(
            user_id=current_user.id,
            name=flashcard.name,
            category=flashcard.category,
            front_language=flashcard.front_language,
            back_language=flashcard.back_language
        ).first()

        # Flashcard objesine istatistikleri ekle
        flashcard.total_words = total_words
        flashcard.user_has_copy = bool(user_has_copy)
        flashcard.creator = User.query.get(flashcard.user_id)

        flashcards_with_stats.append(flashcard)

    return render_template("flashcards.html",
                           flashcards=flashcards_with_stats,
                           pagination=public_flashcards_pagination)


@flashcards.route("/flashcard/<int:flashcard_id>/copy", methods=['POST'])
def copy_flashcard(flashcard_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # Kopyalanacak flashcard'ı al (public olmalı)
    original_flashcard = Flashcard.query.filter_by(id=flashcard_id, visibility="public").first()
    if not original_flashcard:
        flash("Flashcard bulunamadı veya public değil!", "error")
        return redirect(url_for('flashcards.flashcards_list'))

    # Kullanıcının zaten bu flashcard'ın bir kopyası var mı kontrol et
    existing_copy = Flashcard.query.filter_by(
        user_id=current_user.id,
        name=original_flashcard.name,
        category=original_flashcard.category,
        front_language=original_flashcard.front_language,
        back_language=original_flashcard.back_language
    ).first()

    if existing_copy:
        flash("Bu flashcard zaten koleksiyonunuzda mevcut!", "warning")
        return redirect(url_for('flashcards.flashcards_list'))

    # Yeni flashcard kopyası oluştur
    new_flashcard = Flashcard(
        name=original_flashcard.name,
        category=original_flashcard.category,
        description=original_flashcard.description,
        visibility="private",  # Kopya private olarak oluşturulur
        user_id=current_user.id,
        front_language=original_flashcard.front_language,
        back_language=original_flashcard.back_language
    )

    db.session.add(new_flashcard)
    db.session.flush()  # ID'yi almak için

    # Orijinal flashcard'daki tüm kelimeleri kopyala
    for original_word in original_flashcard.words:
        # Bu kelimenin zaten Word tablosunda olup olmadığını kontrol et
        existing_word = Word.query.filter_by(
            word=original_word.word,
            answer=original_word.answer,
            front_language=original_word.front_language,
            back_language=original_word.back_language
        ).first()

        if existing_word:
            # Varolan kelimeyi flashcard'a ekle
            new_flashcard.words.append(existing_word)

            # WordProgress oluştur
            existing_progress = WordProgress.query.filter_by(
                word_id=existing_word.id,
                user_id=current_user.id,
                flashcard_id=new_flashcard.id
            ).first()

            if not existing_progress:
                word_progress = WordProgress(
                    word_id=existing_word.id,
                    user_id=current_user.id,
                    is_learned=False,
                    flashcard_id=new_flashcard.id
                )
                db.session.add(word_progress)
        else:
            # Yeni kelime oluştur
            new_word = Word(
                word=original_word.word,
                answer=original_word.answer,
                front_language=original_word.front_language,
                back_language=original_word.back_language,
                difficulty=original_word.difficulty,
                user_id=current_user.id
            )
            db.session.add(new_word)
            db.session.flush()

            # Flashcard'a ekle
            new_flashcard.words.append(new_word)

            # WordProgress oluştur
            word_progress = WordProgress(
                word_id=new_word.id,
                user_id=current_user.id,
                is_learned=False,
                flashcard_id=new_flashcard.id
            )
            db.session.add(word_progress)

    db.session.commit()
    flash(f"'{original_flashcard.name}' flashcard'ı koleksiyonunuza başarıyla eklendi!", "success")
    return redirect(url_for('flashcards.add_flashcard'))


@flashcards.route("/flashcard/<int:flashcard_id>/preview", methods=['GET'])
def flashcard_preview(flashcard_id):
    if not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized"}), 401

    # Public flashcard'ı al
    flashcard = Flashcard.query.filter_by(id=flashcard_id, visibility="public").first()
    if not flashcard:
        return jsonify({"error": "Flashcard bulunamadı veya public değil"}), 404

    # İlk 10 kelimeyi al (önizleme için)
    words = flashcard.words[:10]

    # Kullanıcının bu flashcard'ın kopyasına sahip olup olmadığını kontrol et
    user_has_copy = Flashcard.query.filter_by(
        user_id=current_user.id,
        name=flashcard.name,
        category=flashcard.category,
        front_language=flashcard.front_language,
        back_language=flashcard.back_language
    ).first()

    # Yaratıcı bilgisi
    creator = User.query.get(flashcard.user_id)

    preview_data = {
        "id": flashcard.id,
        "name": flashcard.name,
        "description": flashcard.description,
        "category": flashcard.category,
        "front_language": flashcard.front_language,
        "back_language": flashcard.back_language,
        "total_words": len(flashcard.words),
        "creator": creator.username if creator else "Bilinmeyen",
        "created_at": flashcard.created_at.strftime('%d %B %Y') if flashcard.created_at else 'Tarih yok',
        "user_has_copy": bool(user_has_copy),
        "sample_words": [
            {
                "front": word.word,
                "back": word.answer,
                "difficulty": word.difficulty
            } for word in words
        ]
    }

    return jsonify(preview_data)


def check_with_llm(user_answer, correct_answer):
    user_answer_embedding = model.encode(user_answer)
    correct_answer_embedding = model.encode(correct_answer)
    similarity = util.cos_sim(user_answer_embedding, correct_answer_embedding)
    return float(similarity.item())
