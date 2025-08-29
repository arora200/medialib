import requests
import os
import json
import uuid
from dotenv import load_dotenv
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Media, db # Assuming db is already initialized in models.py
from utils import allowed_file, get_file_type # Re-using utility functions

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
PIXABAY_BASE_URL = "https://pixabay.com/api/videos/"

MEDIA_DIR = "media_library"
DB_PATH = "instance/media.db"
LOG_FILE = "pixabay_downloads_log.json"

# Ensure media directory exists
os.makedirs(MEDIA_DIR, exist_ok=True)

# --- Database Setup (for this script's independent use) ---
# This part ensures the script can interact with the database directly
# without running the full Flask app. If the Flask app is always running
# when this script is used, some of this might be redundant.
engine = create_engine(f'sqlite:///{DB_PATH}')
Base.metadata.bind = engine
DB_Session = sessionmaker(bind=engine)

# --- Pixabay API Interaction ---

def get_pixabay_videos(keywords, per_page=10, min_width=1080, min_height=1920):
    """
    Searches Pixabay for videos based on keywords and returns mapped metadata.
    Targets vertical videos suitable for shorts.
    """
    if not PIXABAY_API_KEY:
        print("Error: PIXABAY_API_KEY not found in .env file. Please set it up.")
        return []

    params = {
        "key": PIXABAY_API_KEY,
        "q": " ".join(keywords), # Pixabay API expects space-separated keywords
        "video_type": "film", # or "animation", "all"
        "orientation": "vertical", # Target vertical videos
        "per_page": per_page,
        "min_width": min_width,
        "min_height": min_height
    }

    print(f"Searching Pixabay for videos with keywords: '{keywords}'...")
    try:
        response = requests.get(PIXABAY_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        mapped_videos = []
        for hit in data.get('hits', []):
            # Pixabay provides various video qualities, pick a suitable one
            # For shorts, we want high quality vertical video
            video_url = None
            if 'videos' in hit:
                # Prioritize large or medium quality for download
                if 'large' in hit['videos'] and 'url' in hit['videos']['large']:
                    video_url = hit['videos']['large']['url']
                elif 'medium' in hit['videos'] and 'url' in hit['videos']['medium']:
                    video_url = hit['videos']['medium']['url']
                elif 'small' in hit['videos'] and 'url' in hit['videos']['small']:
                    video_url = hit['videos']['small']['url']

            if video_url:
                # --- Mapping Pixabay fields to Media model schema ---
                # Pixabay 'tags' field is comma-separated
                tags_str = hit.get('tags', '')
                
                # Generate a secure filename
                file_extension = ".mp4" # Assuming all Pixabay videos are mp4
                new_filename = f"{uuid.uuid4().hex}{file_extension}"

                mapped_videos.append({
                    "pixabay_id": hit.get('id'),
                    "title": hit.get('tags').split(',')[0].strip() if hit.get('tags') else f"Video {hit.get('id')}",
                    "description": hit.get('tags', ''), # Using tags as description for simplicity
                    "tags": tags_str,
                    "filename": new_filename,
                    "file_type": "video",
                    "category": "video",
                    "subcategory": "", # Pixabay doesn't provide direct subcategory
                    "pixabay_video_url": video_url,
                    "duration": hit.get('duration'),
                    "user_id": 1 # Assuming user_id 1 is admin or a default user
                })
        print(f"Found {len(mapped_videos)} videos on Pixabay matching criteria.")
        return mapped_videos
    except requests.exceptions.RequestException as e:
        print(f"Error searching Pixabay: {e}")
        if response is not None:
            print(f"Response content: {response.text}")
        return []

def download_pixabay_video(video_url, filename):
    """Downloads a video from a given URL to the media_library directory."""
    local_filepath = os.path.join(MEDIA_DIR, filename)
    print(f"Downloading {video_url} to {local_filepath}...")
    try:
        response = requests.get(video_url, stream=True)
        response.raise_for_status()
        with open(local_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Successfully downloaded {filename}.")
        return local_filepath
    except requests.exceptions.RequestException as e:
        print(f"Download failed for {filename}: {e}")
        return None

def create_db_entry(video_metadata):
    """Creates a new entry in the SQLite database for the downloaded video."""
    session = DB_Session()
    try:
        new_media = Media(
            title=video_metadata['title'],
            description=video_metadata['description'],
            tags=video_metadata['tags'],
            filename=video_metadata['filename'],
            file_type=video_metadata['file_type'],
            category=video_metadata['category'],
            subcategory=video_metadata['subcategory'],
            user_id=video_metadata['user_id']
        )
        session.add(new_media)
        session.commit()
        print(f"Created DB entry for '{new_media.title}' (ID: {new_media.id}).")
        return new_media.id
    except Exception as e:
        session.rollback()
        print(f"Error creating DB entry for '{video_metadata['title']}': {e}")
        return None
    finally:
        session.close()

def record_pixabay_download(log_data):
    """Appends a JSON record of the Pixabay download to the log file."""
    try:
        data = []
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
            with open(LOG_FILE, 'r') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    # Handle case where file is empty or malformed, start fresh
                    data = []
        
        data.append(log_data)
        
        with open(LOG_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Recorded Pixabay download to {LOG_FILE}")
    except Exception as e:
        print(f"Error recording Pixabay download to log file: {e}")

# --- Main Execution ---

if __name__ == "__main__":
    # Ensure the database schema is created if it doesn't exist
    # This is important if running this script independently of app.py's init_db
    # from models import Base # Import Base from models.py
    # Base.metadata.create_all(engine) # Create tables if they don't exist

    # User input for keywords
    # keywords_input = input("Enter keywords to search for on Pixabay (comma-separated, e.g., 'nature,city'): ")
    # query_keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
    query_keywords = ['girl', 'award', 'homework'] # Default keywords for automated testing

    if not query_keywords:
        print("No keywords provided. Exiting.")
        exit()

    # 1. Get videos from Pixabay
    found_videos_meta = get_pixabay_videos(query_keywords)

    if not found_videos_meta:
        print("No videos found on Pixabay matching your criteria.")
        exit()

    download_count = 0
    for video_meta in found_videos_meta:
        downloaded_path = download_pixabay_video(video_meta['pixabay_video_url'], video_meta['filename'])
        if downloaded_path:
            video_meta['local_path'] = downloaded_path
            db_id = create_db_entry(video_meta)
            if db_id:
                video_meta['db_id'] = db_id
                download_count += 1
                
                # Record the download in the log
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "keywords_searched": query_keywords,
                    "pixabay_video_id": video_meta['pixabay_id'],
                    "downloaded_filename": video_meta['filename'],
                    "title": video_meta['title'],
                    "tags": video_meta['tags'],
                    "api_base_url": PIXABAY_BASE_URL, # Log the API used
                    "local_db_id": db_id
                }
                record_pixabay_download(log_entry)

    if download_count > 0:
        print(f"Successfully downloaded and recorded {download_count} videos from Pixabay.")
    else:
        print("No new videos were downloaded and recorded from Pixabay.")
