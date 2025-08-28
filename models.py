from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    media = db.relationship('Media', backref='uploader', lazy=True)
    playlists = db.relationship('Playlist', backref='owner', lazy=True)
    bookmarks = db.relationship('Bookmark', backref='owner', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    tags = db.Column(db.String(255))
    filename = db.Column(db.String(255), nullable=False, unique=True)
    file_type = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(100))
    subcategory = db.Column(db.String(100))
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Media {self.title}>'

class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    playlist_type = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    media_items = db.relationship('PlaylistMedia', backref='playlist', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Playlist {self.name}>'

class PlaylistMedia(db.Model):
    __tablename__ = 'playlist_media' # Explicit table name to avoid conflict with PlaylistMedia class name
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlist.id'), nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey('media.id'), nullable=False)
    order_index = db.Column(db.Integer, nullable=False)

    db.UniqueConstraint('playlist_id', 'media_id', name='_playlist_media_uc')
    db.UniqueConstraint('playlist_id', 'order_index', name='_playlist_order_uc')

    media = db.relationship('Media', backref='playlist_associations')

    def __repr__(self):
        return f'<PlaylistMedia Playlist:{self.playlist_id} Media:{self.media_id}>'

class Bookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    tags = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Bookmark {self.title}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
