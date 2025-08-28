import shutil
import logging
import os
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, abort, render_template, redirect, url_for, flash, session
from functools import wraps
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename # Added import
from models import db, User, Media, Playlist, PlaylistMedia, login_manager, Bookmark # Import db, models, and login_manager from models.py
from forms import BookmarkForm

# Configuration
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
MEDIA_DIR = os.environ.get("MEDIA_DIR", "media_library")
DB_PATH = os.environ.get("DB_PATH", "media.db")
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.mp3', '.wav', '.mp4', '.mov', '.pdf', '.docx', '.txt'}

app = Flask(__name__)
app.config['MEDIA_DIR'] = MEDIA_DIR
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload
app.config['SECRET_KEY'] = 'admin'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize db and login_manager with app
db.init_app(app)
login_manager.init_app(app)

# Configure logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
app.logger.info('Media Library App starting up...')

# Ensure media directory exists
os.makedirs(MEDIA_DIR, exist_ok=True)

# --- Database Initialization ---
def init_db():
    with app.app_context():
        db.create_all()
        # Create an admin user if one doesn't exist
        if not User.query.filter_by(username=ADMIN_USERNAME).first():
            admin_user = User(username=ADMIN_USERNAME)
            admin_user.set_password(ADMIN_PASSWORD)
            db.session.add(admin_user)
            db.session.commit()
            app.logger.info(f"Admin user '{ADMIN_USERNAME}' created.")
        else:
            app.logger.info(f"Admin user '{ADMIN_USERNAME}' already exists.")

# --- Routes (Web Interface) ---

def allowed_file(filename):
    return '.' in filename and \
           os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif']:
        return 'image'
    elif ext in ['.mp3', '.wav']:
        return 'audio'
    elif ext in ['.mp4', '.mov']:
        return 'video'
    elif ext in ['.pdf', '.docx', '.txt']:
        return 'ebook'
    return 'other'

@app.route('/')
def index():
    tags = request.args.get('tags', '').strip()
    file_type = request.args.get('type', '').strip()
    category = request.args.get('category', '').strip()
    subcategory = request.args.get('subcategory', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 8

    query = Media.query

    if tags:
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
        if tag_list:
            # Use ORM for LIKE queries
            or_conditions = [Media.tags.like(f'%{tag}%') for tag in tag_list]
            query = query.filter(db.or_(*or_conditions))

    if file_type:
        query = query.filter_by(file_type=file_type)

    if category:
        query = query.filter_by(category=category)

    if subcategory:
        query = query.filter_by(subcategory=subcategory)

    total_media = query.count()
    media_list = query.paginate(page=page, per_page=per_page, error_out=False).items

    return render_template('index.html', media_list=media_list, page=page, per_page=per_page, total_media=total_media, tags=tags, file_type=file_type, category=category, subcategory=subcategory)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_form():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        tags = request.form.get('tags', '').strip()
        category = request.form.get('category', '').strip()
        subcategory = request.form.get('subcategory', '').strip()

        # File validation
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        if not allowed_file(file.filename):
            flash('File type not allowed', 'danger')
            return redirect(request.url)

        # Form field validation
        if not title:
            flash("Title is required.", "danger")
            return redirect(request.url)

        # Validate category and subcategory if provided
        valid_categories = ['image', 'audio', 'video', 'ebook', 'other', '']
        if category and category not in valid_categories:
            flash("Invalid category selected.", "danger")
            return redirect(request.url)

        valid_subcategories = ['songs', 'movies', 'short_clip', 'music', 'study', 'reference', 'fiction', 'non_fiction', '']
        if subcategory and subcategory not in valid_subcategories:
            flash("Invalid subcategory selected.", "danger")
            return redirect(request.url)

        original_filename = secure_filename(file.filename)
        file_extension = os.path.splitext(original_filename)[1].lower()
        new_filename = f"{uuid.uuid4().hex}{file_extension}"
        file_path = os.path.join(app.config['MEDIA_DIR'], new_filename)

        try:
            file.save(file_path)

            file_type = get_file_type(original_filename)

            new_media = Media(
                title=title,
                description=description,
                tags=tags,
                filename=new_filename,
                file_type=file_type,
                category=category or file_type, # Use file_type as default category
                subcategory=subcategory,
                user_id=current_user.id
            )
            db.session.add(new_media)
            db.session.commit()
            flash('Media uploaded successfully!', 'success')
            return redirect(url_for('media_page', media_id=new_media.id))
        except Exception as e:
            app.logger.error(f"Error uploading media: {e}")
            flash("Failed to upload media.", "danger")
            # Clean up partially uploaded file if any
            if os.path.exists(file_path):
                os.remove(file_path)
            return redirect(request.url)

    return render_template('upload.html')

@app.route('/media/<int:media_id>')
def media_page(media_id):
    media_item = Media.query.get_or_404(media_id)
    return render_template('media.html', media_item=media_item)

@app.route('/media/<int:media_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_media(media_id):
    media_item = Media.query.get_or_404(media_id)

    # Ensure only the uploader can edit media
    if media_item.user_id != current_user.id:
        flash("You are not authorized to edit this media.", "danger")
        return redirect(url_for('media_page', media_id=media_id))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        tags = request.form.get('tags', '').strip()
        category = request.form.get('category', '').strip()
        subcategory = request.form.get('subcategory', '').strip()

        if not title:
            flash("Title is required.", "danger")
            return render_template('edit.html', media_item=media_item)

        # Validate category and subcategory if provided
        valid_categories = ['image', 'audio', 'video', 'ebook', 'other', '']
        if category and category not in valid_categories:
            flash("Invalid category selected.", "danger")
            return render_template('edit.html', media_item=media_item)

        valid_subcategories = ['songs', 'movies', 'short_clip', 'music', 'study', 'reference', 'fiction', 'non_fiction', '']
        if subcategory and subcategory not in valid_subcategories:
            flash("Invalid subcategory selected.", "danger")
            return render_template('edit.html', media_item=media_item)

        try:
            media_item.title = title
            media_item.description = description
            media_item.tags = tags
            media_item.category = category
            media_item.subcategory = subcategory
            db.session.commit()
            flash("Media updated successfully!", "success")
        except Exception as e:
            app.logger.error(f"Error updating media ID {media_id}: {e}")
            flash("Failed to update media.", "danger")
            return render_template('edit.html', media_item=media_item)
        return redirect(url_for('media_page', media_id=media_id))

    return render_template('edit.html', media_item=media_item)

@app.route('/media/<int:media_id>/delete', methods=['POST'])
@login_required
def delete_media_page(media_id):
    media_item = Media.query.get_or_404(media_id)

    # Ensure only the uploader can delete media
    if media_item.user_id != current_user.id:
        flash("You are not authorized to delete this media.", "danger")
        return redirect(url_for('media_page', media_id=media_id))

    # Delete file from filesystem
    file_path = os.path.join(app.config['MEDIA_DIR'], media_item.filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            app.logger.info(f"File {file_path} deleted from filesystem.")
        except Exception as e:
            app.logger.error(f"Error deleting file {file_path}: {e}")
            flash("Failed to delete media file.", "danger")
            return redirect(url_for('media_page', media_id=media_id))
    else:
        app.logger.warning(f"File {file_path} not found on filesystem for media ID {media_id}.")

    # Delete from database
    try:
        db.session.delete(media_item)
        db.session.commit()
        app.logger.info(f"Media item with ID {media_id} deleted from database by user {current_user.username}.")
        flash("Media deleted successfully!", "success")
    except Exception as e:
        app.logger.error(f"Error deleting media ID {media_id} from database: {e}")
        flash("Failed to delete media metadata.", "danger")
        return redirect(url_for('media_page', media_id=media_id))

    return redirect(url_for('index'))

@app.route('/api/media/search_by_title', methods=['GET'])
def search_media_by_title():
    query_str = request.args.get('q', '').strip()
    media_list = []
    if query_str:
        media_list = Media.query.filter(Media.title.like(f'%{query_str}%')).limit(10).all()

    results = [{
        "id": m.id,
        "title": m.title,
        "file_type": m.file_type
    } for m in media_list]

    return jsonify(results)

# Playlist Management
@app.route('/playlists')
@login_required
def playlists():
    playlists = Playlist.query.filter_by(user_id=current_user.id).all()
    return render_template('playlists.html', playlists=playlists)

@app.route('/playlists/create', methods=['GET', 'POST'])
@login_required
def create_playlist():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        playlist_type = request.form.get('playlist_type', '').strip()

        if not name:
            flash("Playlist Name is required.", "danger")
            return render_template('create_playlist.html')

        valid_playlist_types = ['audio', 'video', 'ebook', 'all', '']
        if not playlist_type or playlist_type not in valid_playlist_types:
            flash("Valid Playlist Type is required.", "danger")
            return render_template('create_playlist.html')

        try:
            new_playlist = Playlist(name=name, description=description, playlist_type=playlist_type, user_id=current_user.id)
            db.session.add(new_playlist)
            db.session.commit()
            flash("Playlist created successfully!", "success")
            return redirect(url_for('playlists'))
        except Exception as e:
            app.logger.error(f"Error creating playlist: {e}")
            flash("Failed to create playlist.", "danger")

    return render_template('create_playlist.html')

@app.route('/playlists/<int:playlist_id>')
@login_required
def view_playlist(playlist_id):
    playlist = Playlist.query.filter_by(id=playlist_id, user_id=current_user.id).first_or_404()
    app.logger.debug(f"Viewing playlist: {playlist.name}, Type: {playlist.playlist_type}")

    # Eager load media for playlist items
    playlist_items = PlaylistMedia.query.filter_by(playlist_id=playlist_id).order_by(PlaylistMedia.order_index).all()

    return render_template('view_playlist.html', playlist=playlist, playlist_items=playlist_items)

@app.route('/playlists/add_media', methods=['POST'])
@login_required
def add_media_to_playlist():
    media_id = request.form.get('media_id', type=int)
    playlist_id = request.form.get('playlist_id', type=int)

    app.logger.debug(f"Attempting to add media_id: {media_id} to playlist_id: {playlist_id}")

    if not media_id or not playlist_id:
        flash("Media ID and Playlist ID are required.", "danger")
        app.logger.warning(f"Missing media_id ({media_id}) or playlist_id ({playlist_id}) for add_media_to_playlist.")
        return redirect(url_for('index'))

    playlist = Playlist.query.filter_by(id=playlist_id, user_id=current_user.id).first_or_404()
    media_item = Media.query.get(media_id)

    if not media_item:
        flash("Media item not found.", "danger")
        app.logger.warning(f"Media item {media_id} not found when trying to add to playlist {playlist_id}.")
        return redirect(url_for('view_playlist', playlist_id=playlist_id))

    if playlist.playlist_type != 'all' and media_item.file_type != playlist.playlist_type:
        flash(f"Cannot add {media_item.file_type} to a {playlist.playlist_type} playlist.", "danger")
        app.logger.warning(f"Media type mismatch: {media_item.file_type} vs {playlist.playlist_type} for media {media_id} in playlist {playlist_id}.")
        return redirect(url_for('view_playlist', playlist_id=playlist_id))

    try:
        existing_playlist_media = PlaylistMedia.query.filter_by(playlist_id=playlist_id, media_id=media_id).first()
        if existing_playlist_media:
            flash("Media item is already in this playlist.", "warning")
            app.logger.warning(f"Attempted to add duplicate media {media_id} to playlist {playlist_id}.")
            return redirect(url_for('view_playlist', playlist_id=playlist_id))

        max_order = db.session.query(db.func.max(PlaylistMedia.order_index)).filter_by(playlist_id=playlist_id).scalar()
        next_order = (max_order or 0) + 1

        new_playlist_media = PlaylistMedia(playlist_id=playlist_id, media_id=media_id, order_index=next_order)
        db.session.add(new_playlist_media)
        db.session.commit()
        flash("Media added to playlist successfully!", "success")
        app.logger.info(f"Successfully added media {media_id} to playlist {playlist_id} at order {next_order}.")
    except Exception as e:
        app.logger.error(f"Error adding media {media_id} to playlist {playlist_id}: {e}")
        flash("Failed to add media to playlist.", "danger")

    return redirect(url_for('view_playlist', playlist_id=playlist_id))

@app.route('/playlists/<int:playlist_id>/remove_media', methods=['POST'])
@login_required
def remove_media_from_playlist(playlist_id):
    playlist = Playlist.query.filter_by(id=playlist_id, user_id=current_user.id).first_or_404()
    media_id = request.form.get('media_id', type=int)

    if not media_id:
        flash("Media ID is required.", "danger")
        return redirect(url_for('view_playlist', playlist_id=playlist_id))

    try:
        playlist_media_item = PlaylistMedia.query.filter_by(playlist_id=playlist_id, media_id=media_id).first()
        if playlist_media_item:
            db.session.delete(playlist_media_item)
            db.session.commit()
            flash("Media removed from playlist successfully!", "success")
        else:
            flash("Media not found in this playlist.", "warning")
    except Exception as e:
        app.logger.error(f"Error removing media from playlist: {e}")
        flash("Failed to remove media from playlist.", "danger")

    return redirect(url_for('view_playlist', playlist_id=playlist_id))

@app.route('/playlists/<int:playlist_id>/reorder_media', methods=['POST'])
@login_required
def reorder_media_in_playlist(playlist_id):
    playlist = Playlist.query.filter_by(id=playlist_id, user_id=current_user.id).first_or_404()
    media_ids_order = request.json.get('media_ids')

    if not media_ids_order or not isinstance(media_ids_order, list):
        return jsonify({"error": "Invalid media order provided."}), 400

    try:
        db.session.begin_nested() # Start a nested transaction
        for index, media_id in enumerate(media_ids_order):
            playlist_media_item = PlaylistMedia.query.filter_by(playlist_id=playlist_id, media_id=media_id).first()
            if playlist_media_item:
                playlist_media_item.order_index = index
            else:
                # If a media_id in the list is not part of the playlist, something is wrong
                db.session.rollback()
                return jsonify({"error": f"Media ID {media_id} not found in playlist {playlist_id}."}), 400
        db.session.commit()
        flash("Playlist reordered successfully!", "success")
        return jsonify({"message": "Playlist reordered successfully!"}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error reordering playlist: {e}")
        flash("Failed to reorder playlist.", "danger")
        return jsonify({"error": "Failed to reorder playlist."}), 500

@app.route('/playlists/<int:playlist_id>/delete', methods=['POST'])
@login_required
def delete_playlist(playlist_id):
    playlist = Playlist.query.filter_by(id=playlist_id, user_id=current_user.id).first_or_404()

    try:
        db.session.delete(playlist)
        db.session.commit()
        flash("Playlist deleted successfully!", "success")
    except Exception as e:
        app.logger.error(f"Error deleting playlist: {e}")
        flash("Failed to delete playlist.", "danger")
    return redirect(url_for('playlists'))

@app.route('/media/<int:media_id>/add_to_playlist_form')
@login_required
def add_to_playlist_form(media_id):
    media_item = Media.query.get_or_404(media_id)
    playlists = Playlist.query.filter_by(user_id=current_user.id).all()
    return render_template('add_to_playlist_form.html', media_item=media_item, playlists=playlists)

def perform_bulk_import(folder_path, default_title, default_description, default_tags, user_id):
    imported_count = 0
    skipped_count = 0

    if not os.path.isdir(folder_path):
        app.logger.error(f"Bulk import failed: Invalid folder path provided: {folder_path}")
        return 0, 0 # Return 0,0 if folder path is invalid

    for root, _, files in os.walk(folder_path):
        for filename in files:
            file_full_path = os.path.join(root, filename)
            ext = os.path.splitext(filename)[1].lower()

            if ext in ALLOWED_EXTENSIONS:
                existing_media = Media.query.filter_by(filename=filename).first()
                if existing_media:
                    skipped_count += 1
                    app.logger.info(f"Skipping duplicate file: {filename}")
                    continue

                new_filename = f"{uuid.uuid4().hex}{ext}"
                destination_path = os.path.join(app.config['MEDIA_DIR'], new_filename)

                try:
                    shutil.copy2(file_full_path, destination_path)
                    file_type = get_file_type(filename)

                    new_media = Media(
                        title=default_title or os.path.splitext(filename)[0],
                        description=default_description,
                        tags=default_tags,
                        filename=new_filename,
                        file_type=file_type,
                        category=file_type,
                        subcategory='',
                        user_id=user_id
                    )
                    db.session.add(new_media)
                    db.session.commit()
                    imported_count += 1
                    app.logger.info(f"Imported: {filename} as {new_filename} by user {user_id}")
                except Exception as e:
                    app.logger.error(f"Error importing {filename}: {e}")
                    if os.path.exists(destination_path):
                        os.remove(destination_path)
                    db.session.rollback() # Rollback in case of DB error
    return imported_count, skipped_count

@app.route('/bulk_import', methods=['GET', 'POST'])
@login_required
def bulk_import():
    if request.method == 'POST':
        folder_path = request.form.get('folder_path', '').strip()
        default_title = request.form.get('default_title', '').strip()
        default_description = request.form.get('default_description', '').strip()
        default_tags = request.form.get('default_tags', '').strip()

        if not folder_path:
            flash("Folder path is required.", "danger")
            return render_template('bulk_import.html')

        # The os.path.isdir check is now inside perform_bulk_import
        imported_count, skipped_count = perform_bulk_import(
            folder_path, default_title, default_description, default_tags, current_user.id
        )

        if imported_count == 0 and skipped_count == 0 and os.path.isdir(folder_path):
            flash("No supported media files found in the specified folder, or an error occurred.", "warning")
        elif imported_count == 0 and skipped_count == 0 and not os.path.isdir(folder_path):
            flash("Invalid folder path. Please provide a valid directory.", "danger")
        else:
            flash(f"Bulk import complete. Imported {imported_count} files, skipped {skipped_count} duplicates/unsupported.", "success")
        return redirect(url_for('bulk_import'))

    return render_template('bulk_import.html')

@app.errorhandler(401)
def unauthorized(e):
    app.logger.error(f"Unauthorized access attempt: {e}")
    flash("Unauthorized access. Please log in.", "danger")
    return redirect(url_for('login'))

@app.errorhandler(404)
def page_not_found(e):
    app.logger.error(f"Page not found: {e}")
    return render_template('404.html'), 404 # Assuming you have a 404.html template

@app.errorhandler(413)
def request_entity_too_large(e):
    app.logger.error(f"File upload too large: {e}")
    flash("File too large. Maximum size is 100MB.", "danger")
    return jsonify(error="File too large (max 100MB)"), 413

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/bookmarks', methods=['GET', 'POST'])
@login_required
def bookmarks():
    form = BookmarkForm()
    if form.validate_on_submit():
        new_bookmark = Bookmark(
            title=form.title.data,
            url=form.url.data,
            description=form.description.data,
            tags=form.tags.data,
            owner=current_user
        )
        db.session.add(new_bookmark)
        db.session.commit()
        flash('Bookmark added successfully!', 'success')
        return redirect(url_for('bookmarks'))

    page = request.args.get('page', 1, type=int)
    per_page = 10
    search_query = request.args.get('q', '')

    query = Bookmark.query.filter_by(user_id=current_user.id)

    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Bookmark.title.like(search_term),
                Bookmark.description.like(search_term),
                Bookmark.tags.like(search_term)
            )
        )

    bookmarks = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('bookmarks.html', form=form, bookmarks=bookmarks)

@app.route('/about-us')
def about_us():
    return render_template('about_us.html')

@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html')

from api import api_bp
app.register_blueprint(api_bp)

if __name__ == '__main__':
    init_db()
    app.logger.debug(f"Admin password: {ADMIN_PASSWORD}")
    app.logger.info("Web Interface:")
    app.logger.info("  GET    /                    - View all media")
    app.logger.info("  GET    /upload              - Upload new media")
    app.logger.info("  GET    /media/<id>          - View a specific media item")
    app.logger.info("API Endpoints:")
    app.logger.info("  POST   /api/upload          - Upload media (requires password)") # This comment is outdated, will be fixed in api.py
    app.logger.info("  GET    /api/media/<id>      - Get media metadata")
    app.logger.info("  GET    /api/media/<id>/download - Download media file")
    app.logger.info("  GET    /api/media           - Search media (tags, type)")
    app.logger.info("  DELETE /api/media/<id>      - Delete media (requires password)") # This comment is outdated, will be fixed in api.py
    app.run(host='0.0.0.0', port=5000, debug=True)
