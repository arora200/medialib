import os
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_restx import Api, Resource, fields, reqparse
from flask_login import login_required, current_user
from functools import wraps
from models import db, Media, Playlist, PlaylistMedia, User # Import SQLAlchemy db and models
from werkzeug.utils import secure_filename
import uuid
from utils import allowed_file, get_file_type # Import from utils.py

# Create a Blueprint for the API
api_bp = Blueprint('api', __name__, url_prefix='/api')
api = Api(api_bp,
          version='1.0',
          title='Media Library API',
          description='A simple API for managing media items and playlists.',
          doc='/doc/')

# Custom decorator for API authentication
def api_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            api.abort(401, "Authentication required")
        return f(*args, **kwargs)
    return decorated_function

# Define API models for serialization/deserialization
media_model = api.model('Media', {
    'id': fields.Integer(readOnly=True, description='The unique identifier of the media item'),
    'title': fields.String(required=True, description='The title of the media item'),
    'description': fields.String(description='A brief description of the media item'),
    'tags': fields.String(description='Comma-separated tags for the media item'),
    'filename': fields.String(readOnly=True, description='The stored filename on the server'),
    'file_type': fields.String(readOnly=True, description='The type of media (e.g., image, video, audio, document)'),
    'category': fields.String(description='Category of the media'),
    'subcategory': fields.String(description='Subcategory of the media'),
    'uploaded_at': fields.DateTime(readOnly=True, description='Timestamp of when the media was uploaded'),
    'user_id': fields.Integer(readOnly=True, description='ID of the user who uploaded the media'),
})

playlist_model = api.model('Playlist', {
    'id': fields.Integer(readOnly=True, description='The unique identifier of the playlist'),
    'name': fields.String(required=True, description='The name of the playlist'),
    'description': fields.String(description='A brief description of the playlist'),
    'playlist_type': fields.String(required=True, description='The type of playlist (e.g., audio, video, ebook)'),
    'created_at': fields.DateTime(readOnly=True, description='Timestamp of when the playlist was created'),
    'user_id': fields.Integer(readOnly=True, description='ID of the user who owns the playlist'),
})

playlist_media_model = api.model('PlaylistMedia', {
    'media_id': fields.Integer(required=True, description='ID of the media item to add/remove'),
    'order_index': fields.Integer(description='Order of the media item in the playlist'),
})

# Request parsers for filtering/pagination
media_list_parser = reqparse.RequestParser()
media_list_parser.add_argument('title', type=str, help='Filter by title', location='args')
media_list_parser.add_argument('tags', type=str, help='Filter by tags', location='args')
media_list_parser.add_argument('file_type', type=str, help='Filter by media type', location='args')
media_list_parser.add_argument('category', type=str, help='Filter by category', location='args')
media_list_parser.add_argument('subcategory', type=str, help='Filter by subcategory', location='args')
media_list_parser.add_argument('limit', type=int, help='Limit the number of results', default=20, location='args')
media_list_parser.add_argument('offset', type=int, help='Offset for pagination', default=0, location='args')

from werkzeug.exceptions import HTTPException # Added import

# Error Handlers for Flask-RESTX API
@api.errorhandler(HTTPException)
def handle_http_exception(e):
    return {'message': e.description, 'code': e.code}, e.code

@api.errorhandler
def generic_error(error):
    current_app.logger.error(f"An unhandled API error occurred: {error}")
    return {'message': 'An unexpected error occurred', 'details': str(error)}, 500

# Media Namespace
media_ns = api.namespace('media', description='Media operations')

auth_ns = api.namespace('auth', description='Authentication operations')

@auth_ns.route('/login')
class UserLogin(Resource):
    @api.expect(api.model('UserAuth', {'username': fields.String(required=True), 'password': fields.String(required=True)}))
    def post(self):
        data = request.json
        username = data.get('username')
        password = data.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            from flask_login import login_user
            login_user(user)
            return {'message': 'Login successful'}, 200
        return {'message': 'Invalid credentials'}, 401

@auth_ns.route('/logout')
class UserLogout(Resource):
    @api_login_required
    def post(self):
        from flask_login import logout_user
        logout_user()
        return {'message': 'Logout successful'}, 200


@media_ns.route('/')
class MediaList(Resource):
    @api.doc('list_media_items')
    @api.expect(media_list_parser)
    @api.marshal_list_with(media_model)
    @api_login_required
    def get(self):
        '''List all media items uploaded by the current user'''
        args = media_list_parser.parse_args()
        query = Media.query.filter_by(user_id=current_user.id)

        if args['title']:
            query = query.filter(Media.title.like(f"%{args['title']}% "))
        if args['tags']:
            tag_list = [t.strip() for t in args['tags'].split(',') if t.strip()]
            if tag_list:
                or_conditions = [Media.tags.like(f'%{tag}%') for tag in tag_list]
                query = query.filter(db.or_(*or_conditions))
        if args['file_type']:
            query = query.filter_by(file_type=args['file_type'])
        if args['category']:
            query = query.filter_by(category=args['category'])
        if args['subcategory']:
            query = query.filter_by(subcategory=args['subcategory'])

        media_items = query.offset(args['offset']).limit(args['limit']).all()
        return media_items

    @api.doc('upload_media')
    @api.marshal_with(media_model, code=201)
    @api_login_required
    def post(self):
        '''Upload a new media item'''
        parser = reqparse.RequestParser()
        parser.add_argument('title', type=str, required=True, help='Title of the media item')
        parser.add_argument('description', type=str, help='Description of the media item')
        parser.add_argument('tags', type=str, help='Comma-separated tags')
        parser.add_argument('file_type', type=str, help='Type of the file (e.g., image, audio)')
        parser.add_argument('category', type=str, help='Category of the media')
        parser.add_argument('subcategory', type=str, help='Subcategory of the media')
        
        args = parser.parse_args()

        if 'file' not in request.files:
            api.abort(400, "No file part in the request")
        file = request.files['file']
        if file.filename == '':
            api.abort(400, "No selected file")

        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            file_extension = os.path.splitext(original_filename)[1].lower()
            new_filename = f"{uuid.uuid4().hex}{file_extension}"
            file_path = os.path.join(current_app.config['MEDIA_DIR'], new_filename)
            file.save(file_path)

            current_app.logger.info(f"Attempting to create Media with title: {args['title']}, file_type: {args['file_type'] or get_file_type(original_filename)}, category: {args['category'] or get_file_type(original_filename)}, subcategory: {args['subcategory']}")
            current_app.logger.info(f"MEDIA_DIR: {current_app.config['MEDIA_DIR']}")

            new_media = Media(
                title=args['title'],
                description=args['description'],
                tags=args['tags'],
                filename=new_filename,
                file_type=args['file_type'] or get_file_type(original_filename),
                category=args['category'] or get_file_type(original_filename),
                subcategory=args['subcategory'],
                user_id=current_user.id
            )
            db.session.add(new_media)
            db.session.commit()
            return new_media, 201
        else:
            api.abort(400, "File type not allowed")

@media_ns.route('/<int:media_id>')
@api.param('media_id', 'The unique identifier of the media item')
class MediaItem(Resource):
    @api.doc('get_media_item')
    @api.marshal_with(media_model)
    @api_login_required
    def get(self, media_id):
        '''Fetch a media item given its identifier'''
        media_item = Media.query.filter_by(id=media_id, user_id=current_user.id).first()
        if media_item:
            return media_item
        api.abort(404, f"Media item {media_id} not found or not authorized")

    @api.doc('update_media_item')
    @api.expect(media_model, validate=True)
    @api.marshal_with(media_model)
    @api_login_required
    def put(self, media_id):
        '''Update a media item'''
        media_item = Media.query.filter_by(id=media_id, user_id=current_user.id).first()
        if not media_item:
            api.abort(404, f"Media item {media_id} not found or not authorized")

        data = api.payload
        media_item.title = data.get('title', media_item.title)
        media_item.description = data.get('description', media_item.description)
        media_item.tags = data.get('tags', media_item.tags)
        media_item.category = data.get('category', media_item.category)
        media_item.subcategory = data.get('subcategory', media_item.subcategory)
        db.session.commit()
        return media_item

    @api.doc('delete_media_item')
    @api.response(204, 'Media item deleted')
    @api_login_required
    def delete(self, media_id):
        '''Delete a media item'''
        media_item = Media.query.filter_by(id=media_id, user_id=current_user.id).first()
        if not media_item:
            api.abort(404, f"Media item {media_id} not found or not authorized")

        # Delete file from filesystem
        file_path = os.path.join(current_app.config['MEDIA_DIR'], media_item.filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                current_app.logger.error(f"Error deleting file {file_path}: {e}")
                api.abort(500, "Failed to delete media file from filesystem")

        db.session.delete(media_item)
        db.session.commit()
        return '', 204

@media_ns.route('/<int:media_id>/download')
@api.param('media_id', 'The unique identifier of the media item')
class MediaDownload(Resource):
    @api.doc('download_media_item')
    @api_login_required
    def get(self, media_id):
        '''Download a media item'''
        media_item = Media.query.filter_by(id=media_id, user_id=current_user.id).first()
        if not media_item:
            api.abort(404, f"Media item {media_id} not found or not authorized")

        directory = current_app.config['MEDIA_DIR']
        filename = media_item.filename
        return send_from_directory(directory, filename, as_attachment=True)

# Playlist Namespace
playlist_ns = api.namespace('playlists', description='Playlist operations')

@playlist_ns.route('/')
class PlaylistList(Resource):
    @api.doc('list_playlists')
    @api.marshal_list_with(playlist_model)
    @api_login_required
    def get(self):
        '''List all playlists owned by the current user'''
        playlists = Playlist.query.filter_by(user_id=current_user.id).all()
        return playlists

    @api.doc('create_playlist')
    @api.expect(playlist_model, validate=True)
    @api.marshal_with(playlist_model, code=201)
    @api_login_required
    def post(self):
        '''Create a new playlist'''
        data = api.payload
        new_playlist = Playlist(
            name=data['name'],
            description=data.get('description'),
            playlist_type=data['playlist_type'],
            user_id=current_user.id
        )
        db.session.add(new_playlist)
        db.session.commit()
        return new_playlist, 201

@playlist_ns.route('/<int:playlist_id>')
@api.param('playlist_id', 'The unique identifier of the playlist')
class PlaylistItem(Resource):
    @api.doc('get_playlist')
    @api.marshal_with(playlist_model)
    @api_login_required
    def get(self, playlist_id):
        '''Fetch a playlist given its identifier'''
        playlist = Playlist.query.filter_by(id=playlist_id, user_id=current_user.id).first()
        if playlist:
            return playlist
        api.abort(404, f"Playlist {playlist_id} not found or not authorized")

    @api.doc('update_playlist')
    @api.expect(playlist_model, validate=True)
    @api.marshal_with(playlist_model)
    @api_login_required
    def put(self, playlist_id):
        '''Update a playlist'''
        playlist = Playlist.query.filter_by(id=playlist_id, user_id=current_user.id).first()
        if not playlist:
            api.abort(404, f"Playlist {playlist_id} not found or not authorized")

        data = api.payload
        playlist.name = data.get('name', playlist.name)
        playlist.description = data.get('description', playlist.description)
        playlist.playlist_type = data.get('playlist_type', playlist.playlist_type)
        db.session.commit()
        return playlist

    @api.doc('delete_playlist')
    @api.response(204, 'Playlist deleted')
    @api_login_required
    def delete(self, playlist_id):
        '''Delete a playlist'''
        playlist = Playlist.query.filter_by(id=playlist_id, user_id=current_user.id).first()
        if not playlist:
            api.abort(404, f"Playlist {playlist_id} not found or not authorized")

        db.session.delete(playlist)
        db.session.commit()
        return '', 204

@playlist_ns.route('/<int:playlist_id>/add_media')
@api.param('playlist_id', 'The unique identifier of the playlist')
class PlaylistAddMedia(Resource):
    @api.doc('add_media_to_playlist')
    @api.expect(playlist_media_model, validate=True)
    @api.response(200, 'Media added to playlist')
    @api_login_required
    def post(self, playlist_id):
        '''Add a media item to a playlist'''
        playlist = Playlist.query.filter_by(id=playlist_id, user_id=current_user.id).first()
        if not playlist:
            api.abort(404, f"Playlist {playlist_id} not found or not authorized")

        data = api.payload
        media_id = data['media_id']
        media_item = Media.query.get(media_id)
        if not media_item:
            api.abort(404, f"Media item {media_id} not found")

        # Check if media type matches playlist type (if playlist type is specific)
        if playlist.playlist_type != 'all' and media_item.file_type != playlist.playlist_type:
            api.abort(400, f"Cannot add {media_item.file_type} to a {playlist.playlist_type} playlist.")

        existing_playlist_media = PlaylistMedia.query.filter_by(playlist_id=playlist_id, media_id=media_id).first()
        if existing_playlist_media:
            return {'message': 'Media already in playlist'}, 200 # Not an error, just informative

        max_order = db.session.query(db.func.max(PlaylistMedia.order_index)).filter_by(playlist_id=playlist_id).scalar()
        next_order = (max_order or 0) + 1

        new_playlist_media = PlaylistMedia(playlist_id=playlist_id, media_id=media_id, order_index=next_order)
        db.session.add(new_playlist_media)
        db.session.commit()
        return {'message': 'Media added to playlist successfully'}, 200

@playlist_ns.route('/<int:playlist_id>/remove_media')
@api.param('playlist_id', 'The unique identifier of the playlist')
class PlaylistRemoveMedia(Resource):
    @api.doc('remove_media_from_playlist')
    @api.expect(playlist_media_model, validate=True)
    @api.response(200, 'Media removed from playlist')
    @api_login_required
    def post(self, playlist_id):
        '''Remove a media item from a playlist'''
        playlist = Playlist.query.filter_by(id=playlist_id, user_id=current_user.id).first()
        if not playlist:
            api.abort(404, f"Playlist {playlist_id} not found or not authorized")

        data = api.payload
        media_id = data['media_id']

        playlist_media_item = PlaylistMedia.query.filter_by(playlist_id=playlist_id, media_id=media_id).first()
        if not playlist_media_item:
            api.abort(404, "Media not found in playlist")

        db.session.delete(playlist_media_item)
        db.session.commit()
        return {'message': 'Media removed from playlist successfully'}, 200

@playlist_ns.route('/<int:playlist_id>/media')
@api.param('playlist_id', 'The unique identifier of the playlist')
class PlaylistMediaList(Resource):
    @api.doc('list_media_in_playlist')
    @api.marshal_list_with(media_model)
    @api_login_required
    def get(self, playlist_id):
        '''List all media items in a specific playlist'''
        playlist = Playlist.query.filter_by(id=playlist_id, user_id=current_user.id).first()
        if not playlist:
            api.abort(404, f"Playlist {playlist_id} not found or not authorized")

        media_items = []
        for pm in PlaylistMedia.query.filter_by(playlist_id=playlist_id).order_by(PlaylistMedia.order_index).all():
            media_items.append(pm.media)
        return media_items