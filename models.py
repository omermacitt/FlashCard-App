# db tablolarının temsilleri burada olacak
from db import db
from datetime import datetime, UTC
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from datetime import datetime, timedelta

class FlashcardWords(db.Model):
    __tablename__ = 'flashcard_words'
    flashcard_id = db.Column(db.Integer, db.ForeignKey('flashcard.id'), primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    last_study_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    
    # Yeni istatistik alanları
    total_study_time = db.Column(db.Integer, default=0)  # Toplam çalışma süresi (dakika)
    current_streak = db.Column(db.Integer, default=0)    # Mevcut günlük seri
    longest_streak = db.Column(db.Integer, default=0)    # En uzun günlük seri
    total_points = db.Column(db.Integer, default=0)      # Toplam puan
    level = db.Column(db.Integer, default=1)             # Kullanıcı seviyesi
    
    # Relationships
    flashcards = db.relationship("Flashcard", back_populates="owner")
    reset_token = db.Column(db.String(128), nullable=True)
    reset_token_expiration = db.Column(db.DateTime, nullable=True)
    word_progresses = db.relationship(
        "WordProgress",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    study_sessions = db.relationship(
        "UserStudySession",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    daily_stats = db.relationship(
        "UserDailyStats",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    def set_password(self, password: str) -> None:
        self.password = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password, password)

    def update_study_date(self) -> None:
        self.last_study_date = datetime.now(UTC)

    def get_reset_password_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiration = datetime.now(UTC) + timedelta(hours=1)
        db.session.commit()
        return self.reset_token

    def verify_reset_token(self, token):
        if (self.reset_token == token and
                self.reset_token_expiration and
                datetime.now(UTC) < self.reset_token_expiration):
            return True
        return False
    
    def add_study_time(self, minutes):
        """Çalışma süresini ekle ve seviye hesapla"""
        self.total_study_time += minutes
        self.calculate_level()
        db.session.commit()
    
    def add_points(self, points):
        """Puan ekle"""
        self.total_points += points
        self.calculate_level()
        db.session.commit()
    
    def calculate_level(self):
        """Toplam puana göre seviye hesapla"""
        # Her seviye için 1000 puan gerekli
        new_level = (self.total_points // 1000) + 1
        self.level = max(self.level, new_level)
    
    def update_streak(self):
        """Günlük seriyi güncelle"""
        from models import UserDailyStats  # Circular import'u önlemek için burada import
        today = datetime.now(UTC).date()
        yesterday = today - timedelta(days=1)
        
        # Bugün çalışma var mı kontrol et
        today_stats = UserDailyStats.query.filter_by(
            user_id=self.id, 
            date=today
        ).first()
        
        # Dün çalışma var mı kontrol et
        yesterday_stats = UserDailyStats.query.filter_by(
            user_id=self.id, 
            date=yesterday
        ).first()
        
        if today_stats and (today_stats.cards_added > 0 or today_stats.cards_seen > 0):
            if yesterday_stats and (yesterday_stats.cards_added > 0 or yesterday_stats.cards_seen > 0):
                # Seriyi devam ettir
                self.current_streak += 1
            else:
                # Yeni seri başlat
                self.current_streak = 1
            
            # En uzun seriyi güncelle
            if self.current_streak > self.longest_streak:
                self.longest_streak = self.current_streak
        else:
            # Seri kırıldı
            self.current_streak = 0
        
        db.session.commit()
    
    def get_today_stats(self):
        """Bugünkü istatistikleri getir"""
        from models import UserDailyStats  # Circular import'u önlemek için burada import
        today = datetime.now(UTC).date()
        stats = UserDailyStats.query.filter_by(
            user_id=self.id,
            date=today
        ).first()
        
        if not stats:
            stats = UserDailyStats(
                user_id=self.id,
                date=today,
                cards_added=0,
                cards_seen=0,
                study_time_minutes=0
            )
            db.session.add(stats)
            db.session.commit()
        
        return stats
    
    def get_weekly_stats(self):
        """Haftalık istatistikleri getir"""
        from models import UserDailyStats  # Circular import'u önlemek için burada import
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=6)  # Son 7 gün
        
        stats = UserDailyStats.query.filter(
            UserDailyStats.user_id == self.id,
            UserDailyStats.date >= start_date,
            UserDailyStats.date <= end_date
        ).order_by(UserDailyStats.date.asc()).all()
        
        return stats
    
    def get_total_stats(self):
        """Toplam istatistikleri hesapla"""
        total_words = len(self.word_progresses)
        learned_words = len([wp for wp in self.word_progresses if wp.is_learned])
        pending_words = total_words - learned_words
        success_rate = (learned_words / total_words * 100) if total_words > 0 else 0
        
        return {
            'total_words': total_words,
            'learned_words': learned_words,
            'pending_words': pending_words,
            'success_rate': round(success_rate, 1),
            'total_study_time': self.total_study_time,
            'current_streak': self.current_streak,
            'longest_streak': self.longest_streak,
            'total_points': self.total_points,
            'level': self.level
        }



class Word(db.Model):
    __tablename__ = 'word'
    __table_args__ = (db.UniqueConstraint('word', 'front_language', 'back_language', 'user_id', name="uq_word_langs_user"),)
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(128), nullable=False)
    answer = db.Column(db.String(128), nullable=False)
    front_language = db.Column(db.String(128), nullable=False)
    back_language = db.Column(db.String(128), nullable=False)
    difficulty = db.Column(db.String(128), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    
    # Relationships
    user = db.relationship("User")
    flashcards = db.relationship("Flashcard", secondary='flashcard_words', back_populates="words")
    progresses = db.relationship("WordProgress", back_populates="word", cascade="all, delete-orphan")

class Flashcard(db.Model):
    __tablename__ = 'flashcard'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    category = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(128))
    visibility = db.Column(db.Enum("public", "private", name="visibility_enum"), default="private")
    front_language = db.Column(db.String(64), nullable=False)
    back_language  = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    last_studied = db.Column(db.DateTime, nullable=True)
    owner = db.relationship("User", back_populates="flashcards")
    words = db.relationship("Word", secondary='flashcard_words', back_populates="flashcards")



class WordProgress(db.Model):
    __tablename__ = 'word_progress'
    __table_args__ = (
        db.UniqueConstraint("user_id", "word_id", "flashcard_id", name="uq_user_word_deck"),
    )
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    flashcard_id = db.Column(db.Integer, db.ForeignKey("flashcard.id"), nullable=True)
    is_learned = db.Column(db.Boolean, default=False)
    times_seen = db.Column(db.Integer, default=0)
    last_review_at = db.Column(db.DateTime, default=datetime.now(UTC))
    correct_count = db.Column(db.Integer, default=0)
    wrong_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    word = db.relationship("Word", back_populates="progresses")
    user = db.relationship("User", back_populates="word_progresses")
    flashcard = db.relationship("Flashcard")

class UserStudySession(db.Model):
    __tablename__ = 'user_study_session'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    flashcard_id = db.Column(db.Integer, db.ForeignKey('flashcard.id'), nullable=True)
    session_type = db.Column(db.String(50), nullable=False, default='study')  # study, quiz, review
    started_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))
    ended_at = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=False, default=0)
    cards_added = db.Column(db.Integer, nullable=False, default=0)
    cards_seen = db.Column(db.Integer, nullable=False, default=0)
    correct_answers = db.Column(db.Integer, nullable=False, default=0)
    wrong_answers = db.Column(db.Integer, nullable=False, default=0)
    points_earned = db.Column(db.Integer, nullable=False, default=0)

    # Relationships
    user = db.relationship("User", back_populates="study_sessions")
    flashcard = db.relationship("Flashcard")

    def end_session(self):
        """Çalışma seansını bitir"""
        self.ended_at = datetime.now(UTC)
        if self.started_at:
            duration = self.ended_at - self.started_at
            self.duration_minutes = int(duration.total_seconds() / 60)

        # Günlük istatistikleri güncelle
        self.update_daily_stats()

        # Kullanıcı istatistiklerini güncelle
        self.user.add_study_time(self.duration_minutes)
        self.user.add_points(self.points_earned)
        self.user.update_study_date()

        db.session.commit()

    def update_daily_stats(self):
        """Günlük istatistikleri güncelle"""
        today = datetime.now(UTC).date()
        daily_stats = UserDailyStats.query.filter_by(
            user_id=self.user_id,
            date=today
        ).first()

        if not daily_stats:
            daily_stats = UserDailyStats(
                user_id=self.user_id,
                date=today
            )
            db.session.add(daily_stats)

        daily_stats.cards_added = (daily_stats.cards_added or 0) + (self.cards_added or 0)
        daily_stats.cards_seen = (daily_stats.cards_seen or 0) + (self.cards_seen or 0)
        daily_stats.study_time_minutes = (daily_stats.study_time_minutes or 0) + (self.duration_minutes or 0)
        daily_stats.correct_answers = (daily_stats.correct_answers or 0) + (self.correct_answers or 0)
        daily_stats.wrong_answers = (daily_stats.wrong_answers or 0) + (self.wrong_answers or 0)
        daily_stats.points_earned = (daily_stats.points_earned or 0) + (self.points_earned or 0)
        
        # Öğrenilen kelime sayısını güncelle (örnek: doğru cevapların %80'i öğrenildi kabul edilir)
        if hasattr(self, 'words_learned'):
            daily_stats.words_learned = (daily_stats.words_learned or 0) + getattr(self, 'words_learned', 0)
        else:
            # Doğru cevapları öğrenilen kelime olarak kabul et
            daily_stats.words_learned = (daily_stats.words_learned or 0) + (self.correct_answers or 0)

class UserDailyStats(db.Model):
    __tablename__ = 'user_daily_stats'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'date', name='uq_user_daily_stats'),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=lambda: datetime.now(UTC).date())
    cards_added = db.Column(db.Integer, nullable=False, default=0)
    cards_seen = db.Column(db.Integer, nullable=False, default=0)
    words_learned = db.Column(db.Integer, nullable=False, default=0)
    study_time_minutes = db.Column(db.Integer, nullable=False, default=0)
    correct_answers = db.Column(db.Integer, nullable=False, default=0)
    wrong_answers = db.Column(db.Integer, nullable=False, default=0)
    points_earned = db.Column(db.Integer, nullable=False, default=0)
    study_sessions_count = db.Column(db.Integer, nullable=False, default=0)

    # Relationships
    user = db.relationship("User", back_populates="daily_stats")

    @property
    def accuracy_rate(self):
        """Doğruluk oranını hesapla"""
        total_answers = self.correct_answers + self.wrong_answers
        if total_answers == 0:
            return 0
        return round((self.correct_answers / total_answers) * 100, 1)

    @property
    def words_per_minute(self):
        """Dakikada kelime sayısını hesapla"""
        if self.study_time_minutes == 0:
            return 0
        return round(self.cards_seen / self.study_time_minutes, 1)