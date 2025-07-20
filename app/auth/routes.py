from datetime import datetime, UTC, timedelta
from flask_mail import Mail, Message
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import User, WordProgress, Word, UserDailyStats, UserStudySession
from db import db
from flask_login import login_user, logout_user, current_user
from sqlalchemy import and_

auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        login_email = request.form['login_email']
        login_password = request.form['login_password']
        email_check = User.query.filter_by(email=login_email).first()
        if email_check and email_check.check_password(login_password):
            login_user(email_check)
            return redirect(url_for('main.index'))
        else:
            flash("E-posta veya şifre hatalı!", "error")
    return render_template("login.html")


@auth.route('/logout')
def logout():
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for('main.index'))


@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        forgot_email = request.form.get('forgot_email')
        check_email = User.query.filter_by(email=forgot_email).first()
        if not check_email:
            flash("Böyle bir kullanıcı yok", "error")
            return redirect(url_for('auth.forgot_password'))
        token = check_email.get_reset_password_token()
        reset_url = url_for("auth.reset_password", token=token, _external=True)
        msg = Message(
            subject='Şifre Sıfırlama Talebi - Flashcard App',
            recipients=[check_email.email],
            body=f"""
Merhaba {check_email.username},

Şifre sıfırlama talebinde bulundunuz. Aşağıdaki bağlantıya tıklayarak şifrenizi sıfırlayabilirsiniz:

{reset_url}

Bu bağlantı 1 saat geçerlidir.

İyi günler,
Flashcard App
            """.strip()
        )
        msg.sender = ('Flashcard App', 'colabhesabim3442@gmail.com')

        try:
            from app import mail
            print(f"📧 E-posta gönderiliyor: {check_email.email}")
            print(f"📧 Token: {token}")
            print(f"📧 Reset URL: {reset_url}")
            mail.send(msg)
            print(f"✅ E-posta başarıyla gönderildi: {check_email.email}")
            flash("Şifre sıfırlama bağlantısı e-posta adresinize gönderildi.", "success")
        except Exception as e:
            print(f"❌ E-posta hatası: {type(e).__name__}: {str(e)}")
            flash(f"E-posta gönderilirken bir hata oluştu: {str(e)}", "error")

        return redirect(url_for('auth.forgot_password'))
    return render_template("forgot_password.html")


@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.verify_reset_token(token):
        flash("Geçersiz veya süresi dolmuş token!", "error")
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash("Şifreler eşleşmiyor!", "error")
            return render_template("reset_password.html", token=token)
        
        if len(new_password) < 6:
            flash("Şifre en az 6 karakter olmalıdır!", "error")
            return render_template("reset_password.html", token=token)
        
        user.set_password(new_password)
        user.reset_token = None
        user.reset_token_expiration = None
        db.session.commit()
        
        flash("Şifreniz başarıyla güncellendi! Giriş yapabilirsiniz.", "success")
        return redirect(url_for('auth.login'))
    
    return render_template("reset_password.html", token=token)


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        registerName = request.form['register_name']
        registerEmail = request.form['register_email']
        registerPassword = request.form['register_password']
        email_check = User.query.filter_by(email=registerEmail).first()
        if email_check:
            flash("Bu email zaten kullanılıyor!", "error")
            return redirect(url_for('auth.register'))
        try:
            user = User(username=registerName, email=registerEmail)
            user.set_password(password=registerPassword)
            db.session.add(user)
            db.session.flush()
            
            today = datetime.now(UTC).date()
            print(f"DEBUG: User ID: {user.id}, Date: {today}")
            daily_stats = UserDailyStats(user_id=user.id, date=today)
            db.session.add(daily_stats)
            print(f"DEBUG: Daily stats eklendi: {daily_stats}")
            
            db.session.commit()
            flash("Kayıt başarıyla tamamlandı!", "success")
        except Exception as e:
            db.session.rollback()
            print(f"Kayıt hatası: {e}")
            flash("Kayıt sırasında bir hata oluştu!", "error")
            return redirect(url_for('auth.register'))
        return redirect(url_for('auth.login'))
    return render_template("register.html")


def word_to_dict(word, flashcard_name=None):
    return {
        'id': word.id,
        'word': word.word,
        'front_language': word.front_language,
        'answer': word.answer,
        'back_language': word.back_language,
        'created_at': word.created_at.strftime('%Y-%m-%d') if word.created_at else '',
        'flashcard_name': flashcard_name
    }


@auth.route('/dashboard', methods=['GET'])
def dashboard():
    if not current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    # Kullanıcı istatistiklerini al
    user_stats = current_user.get_total_stats()
    today_stats = current_user.get_today_stats()
    weekly_stats = current_user.get_weekly_stats()
    
    # Son eklenen kelimeler
    threshold = datetime.now(UTC) - timedelta(days=7)  # Son 7 gün
    last_added_words = (
        Word.query
        .filter(
            and_(
                Word.user_id == current_user.id,
                Word.created_at >= threshold
            )
        )
        .order_by(Word.created_at.desc())
        .limit(10)
        .all()
    )
    
    # Öğrenilmemiş kelimeler (flashcard bilgisiyle)
    unlearned_words = []
    for wp in current_user.word_progresses:
        if not wp.is_learned:
            flashcard_name = wp.flashcard.name if wp.flashcard else "Genel"
            word_dict = word_to_dict(wp.word, flashcard_name)
            unlearned_words.append(word_dict)
    
    # Haftalık chart verisi hazırla (güncel günden geriye doğru)
    chart_data = []
    today = datetime.now(UTC).date()
    for i in range(7):
        date = today - timedelta(days=6-i)
        day_stats = next((s for s in weekly_stats if s.date == date), None)
        
        # Bu günde öğrenilen kelimeler (UserDailyStats'ten)
        daily_learned = 0
        if day_stats:
            # words_learned alanını kullan, yoksa correct_answers'ı kullan
            daily_learned = getattr(day_stats, 'words_learned', day_stats.correct_answers)
        
        chart_data.append({
            'date': date,
            'cards_seen': day_stats.cards_seen if day_stats else 0,
            'cards_learned': daily_learned,
            'study_time': day_stats.study_time_minutes if day_stats else 0,
            'day_name': ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar'][date.weekday()],
            'day_short': ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'][date.weekday()]
        })
    
    # Haftalık istatistikleri hesapla
    weekly_total_cards = sum(s.cards_seen for s in weekly_stats)
    weekly_total_time = sum(s.study_time_minutes for s in weekly_stats)
    weekly_active_days = len([s for s in weekly_stats if s.cards_seen > 0 or s.study_time_minutes > 0])
    weekly_avg_cards = round(weekly_total_cards / 7, 1) if weekly_total_cards > 0 else 0
    
    # Bugünkü yeni eklenen kelimeler (sadece bugün)
    today = datetime.now(UTC).date()
    today_added_words = (
        Word.query
        .filter(
            and_(
                Word.user_id == current_user.id,
                Word.created_at >= datetime.combine(today, datetime.min.time().replace(tzinfo=UTC)),
                Word.created_at < datetime.combine(today + timedelta(days=1), datetime.min.time().replace(tzinfo=UTC))
            )
        )
        .order_by(Word.created_at.desc())
        .limit(5)
        .all()
    )
    
    # Bu hafta öğrenilen kelimeler
    week_start = today - timedelta(days=6)
    weekly_learned_words = []
    for wp in current_user.word_progresses:
        if (wp.is_learned and wp.last_review_at and 
            wp.last_review_at.date() >= week_start):
            weekly_learned_words.append(wp.word)
    
    return render_template(
        "dashboard.html",
        # Temel istatistikler
        toplam_kelime=user_stats['total_words'],
        ogrenilen_kelime=user_stats['learned_words'],
        ogrenilmesi_beklenen=user_stats['pending_words'],
        son_calistigi_tarih=current_user.last_study_date.strftime("%d.%m.%Y %H:%M") if current_user.last_study_date else None,
        
        # Gamification verileri
        streak_days=current_user.current_streak,
        total_points=current_user.total_points,
        level=current_user.level,
        longest_streak=current_user.longest_streak,
        
        # Günlük veriler
        today_cards_added=today_stats.cards_added,
        today_cards_seen=today_stats.cards_seen,
        today_study_time=today_stats.study_time_minutes,
        today_accuracy=today_stats.accuracy_rate,
        
        # Haftalık veriler
        weekly_total_cards=weekly_total_cards,
        weekly_total_time=weekly_total_time,
        weekly_active_days=weekly_active_days,
        weekly_avg_cards=weekly_avg_cards,
        
        # Listeler
        son_eklenenler=[word_to_dict(w) for w in last_added_words],
        ogrenilmemisler=unlearned_words[:10],
        today_added_words=[word_to_dict(w) for w in today_added_words],
        weekly_learned_words=[word_to_dict(w) for w in weekly_learned_words],
        
        # Chart verileri
        weekly_chart_data=chart_data,
        
        # Toplam istatistikler
        total_study_time=current_user.total_study_time,
        success_rate=user_stats['success_rate']
    )
