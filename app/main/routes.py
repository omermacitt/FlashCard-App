from flask import Blueprint, render_template, session, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import User
from db import db
import os
from werkzeug.utils import secure_filename
from PIL import Image
import uuid

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

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_profile_image(file):
    if file and allowed_file(file.filename):
        # Güvenli dosya adı oluştur
        filename = secure_filename(file.filename)
        unique_filename = str(uuid.uuid4()) + '_' + filename
        
        # Upload klasörü oluştur
        upload_folder = os.path.join('app', 'static', 'uploads', 'profile_images')
        os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, unique_filename)
        
        # Resmi kaydet ve boyutlandır
        try:
            # PIL ile resmi aç
            image = Image.open(file)
            
            # EXIF verilerini koru ve otomatik rotasyonu düzelt
            if hasattr(image, '_getexif'):
                exif = image._getexif()
                if exif is not None:
                    from PIL.ExifTags import ORIENTATION
                    for tag, value in exif.items():
                        if tag == ORIENTATION:
                            if value == 3:
                                image = image.rotate(180, expand=True)
                            elif value == 6:
                                image = image.rotate(270, expand=True)
                            elif value == 8:
                                image = image.rotate(90, expand=True)
            
            # Resmi kare yap ve boyutlandır
            size = min(image.size)
            left = (image.width - size) / 2
            top = (image.height - size) / 2
            right = (image.width + size) / 2
            bottom = (image.height + size) / 2
            
            image = image.crop((left, top, right, bottom))
            image = image.resize((300, 300), Image.Resampling.LANCZOS)
            
            # RGB moduna çevir (PNG için)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Kaydet
            image.save(filepath, 'JPEG', quality=85, optimize=True)
            return unique_filename
            
        except Exception as e:
            print(f"Resim kaydetme hatası: {e}")
            return None
    return None

@main.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    username = request.form.get('username')
    email = request.form.get('email')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Profil resmi silme kontrolü
    delete_profile_image = request.form.get('delete_profile_image')
    if delete_profile_image == 'true':
        if current_user.profile_image:
            # Dosyayı sil
            old_image_path = os.path.join('app', 'static', 'uploads', 'profile_images', current_user.profile_image)
            if os.path.exists(old_image_path):
                os.remove(old_image_path)
            
            # Veritabanından kaldır
            current_user.profile_image = None
            flash('Profil resminiz silindi.', 'success')
    
    # Profil resmi yükleme (silme işlemi yapılmadıysa)
    elif not delete_profile_image or delete_profile_image == 'false':
        profile_image = request.files.get('profile_image')
        if profile_image and profile_image.filename:
            # Dosya boyutu kontrolü (5MB)
            profile_image.seek(0, os.SEEK_END)
            file_size = profile_image.tell()
            profile_image.seek(0)
            
            if file_size > 5 * 1024 * 1024:  # 5MB
                flash('Dosya boyutu 5MB\'den büyük olamaz.', 'error')
                return redirect(url_for('main.profile'))
            
            # Eski profil resmini sil
            if current_user.profile_image:
                old_image_path = os.path.join('app', 'static', 'uploads', 'profile_images', current_user.profile_image)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
            
            # Yeni resmi kaydet
            saved_filename = save_profile_image(profile_image)
            if saved_filename:
                current_user.profile_image = saved_filename
            else:
                flash('Resim yüklenirken bir hata oluştu. Geçerli bir resim dosyası seçin.', 'error')
                return redirect(url_for('main.profile'))
    
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
