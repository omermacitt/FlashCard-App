from flask import Blueprint, render_template, session, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import User
from db import db

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template("index.html")

@main.route('/profile')
@login_required
def profile():
    # Kullanıcı istatistiklerini al
    total_stats = current_user.get_total_stats()
    today_stats = current_user.get_today_stats()
    weekly_stats = current_user.get_weekly_stats()
    
    # Son 7 günün verilerini düzenle (eksik günleri ekle)
    from datetime import datetime, timedelta, UTC
    end_date = datetime.now(UTC).date()
    start_date = end_date - timedelta(days=6)
    
    # Mevcut istatistikleri tarih bazında düzenle
    stats_dict = {stat.date: stat for stat in weekly_stats}
    weekly_stats = []
    
    for i in range(7):
        current_date = start_date + timedelta(days=i)
        if current_date in stats_dict:
            weekly_stats.append(stats_dict[current_date])
        else:
            # Eksik günler için boş istatistik oluştur
            from models import UserDailyStats
            empty_stat = UserDailyStats(
                user_id=current_user.id,
                date=current_date,
                cards_added=0,
                cards_seen=0,
                words_learned=0,
                study_time_minutes=0,
                correct_answers=0,
                wrong_answers=0,
                points_earned=0
            )
            weekly_stats.append(empty_stat)
    
    # Seviye ilerleme hesapla
    current_level_points = (current_user.level - 1) * 1000
    next_level_points = current_user.level * 1000
    points_in_level = current_user.total_points - current_level_points
    points_to_next_level = next_level_points - current_user.total_points
    level_progress = (points_in_level / 1000) * 100
    
    return render_template('profile.html',
                         total_stats=total_stats,
                         today_stats=today_stats,
                         weekly_stats=weekly_stats,
                         level_progress=level_progress,
                         points_to_next_level=points_to_next_level)

@main.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    username = request.form.get('username')
    email = request.form.get('email')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Kullanıcı adı ve email güncelleme
    if username and username != current_user.username:
        # Kullanıcı adının zaten kullanılıp kullanılmadığını kontrol et
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Bu kullanıcı adı zaten kullanılıyor.', 'error')
            return redirect(url_for('main.profile'))
        current_user.username = username
    
    if email and email != current_user.email:
        # Email'in zaten kullanılıp kullanılmadığını kontrol et
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Bu e-posta adresi zaten kullanılıyor.', 'error')
            return redirect(url_for('main.profile'))
        current_user.email = email
    
    # Şifre değiştirme
    if current_password or new_password or confirm_password:
        if not current_password:
            flash('Şifre değiştirmek için mevcut şifrenizi girmelisiniz.', 'error')
            return redirect(url_for('main.profile'))
        
        if not current_user.check_password(current_password):
            flash('Mevcut şifre yanlış.', 'error')
            return redirect(url_for('main.profile'))
        
        if not new_password:
            flash('Yeni şifre boş olamaz.', 'error')
            return redirect(url_for('main.profile'))
        
        if new_password != confirm_password:
            flash('Yeni şifreler eşleşmiyor.', 'error')
            return redirect(url_for('main.profile'))
        
        if len(new_password) < 6:
            flash('Şifre en az 6 karakter olmalıdır.', 'error')
            return redirect(url_for('main.profile'))
        
        current_user.set_password(new_password)
    
    try:
        db.session.commit()
        flash('Profil başarıyla güncellendi.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Profil güncellenirken bir hata oluştu.', 'error')
    
    return redirect(url_for('main.profile'))
