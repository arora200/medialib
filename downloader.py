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

    title_search = search_params.pop('title', None)

    if title_search:
        search_url = f"{API_BASE_URL}/media/search_by_title"
        params = {'q': title_search}
    else:
        search_url = f"{API_BASE_URL}/media"
        params = search_params

    try:
        response = session.get(search_url, params=params)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error searching for media: {e}")
        if response is not None and response.status_code == 401:
            print("Authentication required. Please log in.")
        elif response is not None and response.status_code == 404:
            print("Search endpoint not found. Check API_BASE_URL.")
        elif response is not None and response.status_code == 500:
            print("Server error during search.")
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
        title = input("Enter title (optional): ").strip()
        tags = input("Enter tags (comma-separated, optional): ").strip()
        
        allowed_file_types = ['image', 'audio', 'video', 'ebook', 'other', '']
        file_type = input(f"Enter file type ({', '.join(allowed_file_types[:-1])}, or other - optional): ").strip().lower()
        if file_type and file_type not in allowed_file_types:
            print(f"Invalid file type. Allowed types are: {', '.join(allowed_file_types)}.")
            file_type = '' # Reset to empty if invalid

        category = input("Enter category (optional): ").strip()
        subcategory = input("Enter subcategory (optional): ").strip()

        search_params = {}
        if title: search_params['title'] = title
        if tags: search_params['tags'] = tags
        if file_type: search_params['file_type'] = file_type
        if category: search_params['category'] = category
        if subcategory: search_params['subcategory'] = subcategory

        if not search_params:
            print("No search criteria entered. Searching for all media.")

        download_media(session, search_params)