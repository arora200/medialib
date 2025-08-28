import pytest
import requests
import json
import os

API_BASE_URL = "http://localhost:5000/api"
DUMMY_MEDIA_PATH = "E:\AppDevelopment\medialib\dummy_media.txt"

@pytest.fixture(scope="module")
def authenticated_session():
    session = requests.Session()
    login_url = f"{API_BASE_URL}/auth/login"
    username = "admin"
    password = "admin"
    try:
        response = session.post(login_url, json={'username': username, 'password': password})
        response.raise_for_status()
        print("\nLogin successful for tests.")
        yield session
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Login failed during test setup: {e}")

@pytest.fixture(scope="module")
def dummy_media_item(authenticated_session):
    # Create a dummy media item for testing
    media_url = f"{API_BASE_URL}/media"
    files = {'file': (os.path.basename(DUMMY_MEDIA_PATH), open(DUMMY_MEDIA_PATH, 'rb'), 'text/plain')}
    data = {
        'title': 'Test Media Item',
        'description': 'This is a test media item for CRUD operations.',
        'file_type': 'other',
        'category': 'test',
        'subcategory': 'crud',
        'tags': 'test,crud'
    }
    response = authenticated_session.post(media_url, files=files, data=data)
    response.raise_for_status()
    media_id = response.json()['id']
    print(f"\nCreated dummy media item with ID: {media_id}")
    yield media_id
    # Clean up the dummy media item after tests
    delete_url = f"{API_BASE_URL}/media/{media_id}"
    authenticated_session.delete(delete_url)
    print(f"Deleted dummy media item with ID: {media_id}")

def test_create_media(authenticated_session):
    media_url = f"{API_BASE_URL}/media"
    files = {'file': (os.path.basename(DUMMY_MEDIA_PATH), open(DUMMY_MEDIA_PATH, 'rb'), 'text/plain')}
    data = {
        'title': 'Another Test Media Item',
        'description': 'This is another test media item for creation.',
        'file_type': 'other',
        'category': 'test',
        'subcategory': 'create',
        'tags': 'test,create'
    }
    response = authenticated_session.post(media_url, files=files, data=data)
    assert response.status_code == 201
    assert 'id' in response.json()
    # Clean up this specific item
    authenticated_session.delete(f"{API_BASE_URL}/media/{response.json()['id']}")

def test_get_all_media(authenticated_session, dummy_media_item):
    media_url = f"{API_BASE_URL}/media"
    response = authenticated_session.get(media_url)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert any(item['id'] == dummy_media_item for item in response.json())

def test_get_single_media(authenticated_session, dummy_media_item):
    media_url = f"{API_BASE_URL}/media/{dummy_media_item}"
    response = authenticated_session.get(media_url)
    assert response.status_code == 200
    assert response.json()['id'] == dummy_media_item
    assert response.json()['title'] == 'Test Media Item'

def test_update_media(authenticated_session, dummy_media_item):
    media_url = f"{API_BASE_URL}/media/{dummy_media_item}"
    updated_data = {
        'title': 'Updated Test Media Item',
        'description': 'This item has been updated.',
        'tags': 'test,crud,updated'
    }
    response = authenticated_session.put(media_url, json=updated_data)
    assert response.status_code == 200
    assert response.json()['title'] == 'Updated Test Media Item'
    assert response.json()['description'] == 'This item has been updated.'

    # Verify the update by getting the item again
    verify_response = authenticated_session.get(media_url)
    assert verify_response.status_code == 200
    assert verify_response.json()['title'] == 'Updated Test Media Item'

def test_download_media(authenticated_session, dummy_media_item):
    download_url = f"{API_BASE_URL}/media/{dummy_media_item}/download"
    response = authenticated_session.get(download_url, stream=True)
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'text/plain'
    # Read content and verify
    downloaded_content = b""
    for chunk in response.iter_content(chunk_size=8192):
        downloaded_content += chunk
    
    with open(DUMMY_MEDIA_PATH, 'rb') as f:
        original_content = f.read()
    
    assert downloaded_content == original_content

def test_delete_media(authenticated_session):
    # Create a media item specifically for deletion test
    media_url = f"{API_BASE_URL}/media"
    files = {'file': (os.path.basename(DUMMY_MEDIA_PATH), open(DUMMY_MEDIA_PATH, 'rb'), 'text/plain')}
    data = {
        'title': 'Media to be deleted',
        'description': 'This item will be deleted.',
        'file_type': 'other',
        'category': 'test',
        'subcategory': 'delete',
        'tags': 'test,delete'
    }
    response = authenticated_session.post(media_url, files=files, data=data)
    response.raise_for_status()
    media_id_to_delete = response.json()['id']

    delete_url = f"{API_BASE_URL}/media/{media_id_to_delete}"
    delete_response = authenticated_session.delete(delete_url)
    assert delete_response.status_code == 204 # No Content for successful deletion

    # Verify deletion by trying to get the item
    verify_delete_response = authenticated_session.get(delete_url)
    assert verify_delete_response.status_code == 404 # Not Found after deletion
