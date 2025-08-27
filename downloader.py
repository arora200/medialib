import os
import requests
import json

API_BASE_URL = "http://localhost:5000/api"
DOWNLOAD_DIR = "downloads"

def login(session, username, password):
    login_url = f"{API_BASE_URL}/login"
    try:
        response = session.post(login_url, json={'username': username, 'password': password})
        response.raise_for_status()
        print("Login successful!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Login failed: {e}")
        if response and response.status_code == 401:
            print("Invalid username or password.")
        return False

def download_media(session, search_params):
    """Search for media with given parameters and download them"""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    search_url = f"{API_BASE_URL}/media"
    try:
        response = session.get(search_url, params=search_params)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error searching for media: {e}")
        if response and response.status_code == 401:
            print("Authentication required. Please log in.")
        return

    media_list = response.json()

    if not media_list:
        print(f"No media found with the given criteria.")
        return

    print(f"Found {len(media_list)} media items.")

    for media_item in media_list:
        file_id = media_item['id']
        filename = media_item['filename']
        download_url = f"{API_BASE_URL}/media/{file_id}/download"
        file_path = os.path.join(DOWNLOAD_DIR, filename)

        print(f"Downloading {filename}...")
        try:
            download_response = session.get(download_url, stream=True)
            download_response.raise_for_status()

            with open(file_path, 'wb') as f:
                for chunk in download_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Successfully downloaded {filename}")

        except requests.exceptions.RequestException as e:
            print(f"Error downloading {filename}: {e}")

if __name__ == "__main__":
    session = requests.Session()

    username = input("Enter username: ")
    password = input("Enter password: ")

    if not login(session, username, password):
        print("Exiting due to failed login.")
    else:
        print("\n--- Search Options ---")
        title = input("Enter title (optional): ")
        tags = input("Enter tags (comma-separated, optional): ")
        file_type = input("Enter file type (image, audio, video, ebook, other - optional): ")
        category = input("Enter category (optional): ")
        subcategory = input("Enter subcategory (optional): ")

        search_params = {}
        if title: search_params['title'] = title
        if tags: search_params['tags'] = tags
        if file_type: search_params['file_type'] = file_type
        if category: search_params['category'] = category
        if subcategory: search_params['subcategory'] = subcategory

        download_media(session, search_params)