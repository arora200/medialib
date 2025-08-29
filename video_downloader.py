import requests
import os
import json
import time
from moviepy.editor import VideoFileClip, concatenate_videoclips
from datetime import datetime

# --- Configuration ---
API_BASE_URL = "http://localhost:5000/api"  # Adjust if your Flask app runs on a different port/host
USERNAME = "admin"  # Your API username
PASSWORD = "admin"  # Your API password

DOWNLOAD_DIR = "downloads"
OUTPUT_DIR = "output_shorts"
LOG_FILE = "shorts_log.json"

# Ensure download and output directories exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- API Interaction Functions ---

def login(username, password):
    """Logs into the API and returns an authenticated requests.Session object."""
    session = requests.Session()
    login_url = f"{API_BASE_URL}/auth/login"
    headers = {"Content-Type": "application/json"}
    payload = {"username": username, "password": password}
    
    try:
        response = session.post(login_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        print("Login successful.")
        return session
    except requests.exceptions.RequestException as e:
        print(f"Login failed: {e}")
        if response is not None:
            print(f"Response content: {response.text}")
        return None

def search_videos(session, query_keywords, title_only=False):
    """
    Searches for videos based on keywords in title or tags.
    Returns a list of dictionaries, each representing a media item.
    """
    search_url = f"{API_BASE_URL}/media"
    params = {}
    if title_only:
        params['title'] = query_keywords
    else:
        params['tags'] = query_keywords # Assuming tags search is broader

    print(f"Searching for videos with keywords: '{query_keywords}' (title_only: {title_only})...")
    try:
        response = session.get(search_url, params=params)
        response.raise_for_status()
        media_items = response.json()
        print(f"Found {len(media_items)} video(s).")
        return media_items
    except requests.exceptions.RequestException as e:
        print(f"Video search failed: {e}")
        if response is not None:
            print(f"Response content: {response.text}")
        return []

def download_video(session, media_id, original_filename):
    """Downloads a single video file and returns its local path."""
    download_url = f"{API_BASE_URL}/media/{media_id}/download"
    local_filepath = os.path.join(DOWNLOAD_DIR, original_filename)
    
    print(f"Downloading video {media_id} to {local_filepath}...")
    try:
        response = session.get(download_url, stream=True)
        response.raise_for_status()
        with open(local_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Successfully downloaded {original_filename}.")
        return local_filepath
    except requests.exceptions.RequestException as e:
        print(f"Download failed for {original_filename}: {e}")
        if response is not None:
            print(f"Response content: {response.text}")
        return None

# --- Video Processing Functions ---

def process_videos_for_shorts(video_data, output_filename="y_short.mp4", max_duration=60):
    """
    Loads video clips, resizes them for YouTube Shorts (9:16 aspect ratio),
    concatenates them, and exports the final video.
    video_data is a list of dictionaries with 'path' and 'metadata'.
    """
    clips = []
    total_duration = 0
    processed_video_details = []

    print("Processing video clips for YouTube Shorts...")
    for item in video_data:
        path = item['path']
        metadata = item['metadata']
        try:
            clip = VideoFileClip(path)
            
            # Resize to 9:16 aspect ratio (e.g., 1080x1920)
            # First, scale the smaller dimension to fit, then crop the larger dimension
            width, height = clip.size
            target_aspect_ratio = 9 / 16
            clip_aspect_ratio = width / height

            if clip_aspect_ratio > target_aspect_ratio: # Clip is wider than 9:16, need to crop width
                new_width = int(height * target_aspect_ratio)
                clip = clip.crop(x_center=width/2, width=new_width)
            elif clip_aspect_ratio < target_aspect_ratio: # Clip is taller than 9:16, need to crop height
                new_height = int(width / target_aspect_ratio)
                clip = clip.crop(y_center=height/2, height=new_height)
            
            # Ensure final resolution is suitable, e.g., 1080p vertical
            # If the original video is very low resolution, scaling up might look bad.
            # For simplicity, let's target 1080x1920 if possible, maintaining aspect ratio.
            if clip.size[0] != 1080 or clip.size[1] != 1920:
                clip = clip.resize(newsize=(1080, 1920)) # Force to 1080x1920 after cropping

            # Trim clip if total duration exceeds max_duration
            remaining_duration = max_duration - total_duration
            if remaining_duration <= 0:
                clip.close() # Close the clip to free resources
                break
            
            if clip.duration > remaining_duration:
                clip = clip.subclip(0, remaining_duration)
            
            clips.append(clip)
            total_duration += clip.duration
            print(f"Added '{os.path.basename(path)}', duration: {clip.duration:.2f}s. Total duration: {total_duration:.2f}s")
            
            processed_video_details.append({
                "media_id": metadata.get('id'),
                "title": metadata.get('title'),
                "original_filename": metadata.get('filename'),
                "tags": metadata.get('tags'),
                "duration_used_in_short": clip.duration
            })

        except Exception as e:
            print(f"Error processing video clip '{path}': {e}")
            if 'clip' in locals() and clip is not None:
                clip.close() # Ensure clip is closed even on error
            continue

    if not clips:
        print("No valid video clips to process.")
        return None, None

    final_clip = concatenate_videoclips(clips)
    output_filepath = os.path.join(OUTPUT_DIR, output_filename)
    
    print(f"Exporting final video to {output_filepath}...")
    final_clip.write_videofile(output_filepath, codec="libx264", audio_codec="aac", fps=24)
    print("Video processing complete.")
    
    # Close all clips to free resources
    for clip in clips:
        clip.close()
    final_clip.close()
    
    return output_filepath, processed_video_details

# --- Logging Function ---

def record_short_creation(log_data):
    """Appends a JSON record of the short creation to the log file."""
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
        print(f"Recorded short creation to {LOG_FILE}")
    except Exception as e:
        print(f"Error recording short creation to log file: {e}")

# --- Main Execution ---

if __name__ == "__main__":
    # User input for keywords
    # keywords_input = input("Enter keywords to search for (comma-separated, e.g., 'girl,award,homework'): ")
    # query_keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
    query_keywords = ['girl', 'award', 'homework'] # Default keywords for automated testing
    
    # Decide whether to search by title only or tags (broader)
    # search_type = input("Search by 'title' or 'tags' (default: tags)? ").lower()
    title_only_search = False # Default to searching by tags for automated testing

    # 1. Login to the API
    auth_session = login(USERNAME, PASSWORD)
    if not auth_session:
        print("Authentication failed. Exiting.")
        exit()

    # 2. Search for videos
    # Join keywords for the API query if searching by tags
    api_query_string = ",".join(query_keywords) if not title_only_search else query_keywords[0]
    
    found_videos = search_videos(auth_session, api_query_string, title_only=title_only_search)

    if not found_videos:
        print("No videos found matching your criteria.")
        exit()

    downloaded_video_data = [] # Store path and metadata
    for video_meta in found_videos:
        # Assuming 'filename' is available in the metadata and is the original name
        # You might need to adjust this based on your actual API response structure
        if 'filename' in video_meta and 'id' in video_meta:
            downloaded_path = download_video(auth_session, video_meta['id'], video_meta['filename'])
            if downloaded_path:
                downloaded_video_data.append({'path': downloaded_path, 'metadata': video_meta})
        else:
            print(f"Skipping video due to missing 'filename' or 'id' in metadata: {video_meta}")

    if not downloaded_video_data:
        print("No videos were successfully downloaded. Exiting.")
        exit()

    # 3. Process and join videos for YouTube Shorts
    output_short_filename = f"youtube_short_{'_'.join(query_keywords)}.mp4"
    final_video_path, processed_video_details = process_videos_for_shorts(downloaded_video_data, output_short_filename)

    if final_video_path:
        print(f"YouTube Short created successfully: {final_video_path}")
        
        # 4. Record the short creation
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "keywords_searched": query_keywords,
            "api_base_url": API_BASE_URL,
            "output_short_filename": output_short_filename,
            "total_duration_seconds": sum(item['duration_used_in_short'] for item in processed_video_details),
            "videos_included": processed_video_details
        }
        record_short_creation(log_entry)

    else:
        print("Failed to create YouTube Short.")

    # Clean up downloaded files
    print("Cleaning up downloaded video files...")
    for item in downloaded_video_data:
        path = item['path']
        try:
            os.remove(path)
            print(f"Removed {path}")
        except OSError as e:
            print(f"Error removing {path}: {e}")
    print("Cleanup complete.")