
import pytest
from app import app as flask_app
from models import db, Media # Import Media model for test data

# Existing test_index function
def test_index(client):
    """Test the index page."""
    res = client.get('/')
    assert res.status_code == 200

# NEW TEST: Test index page with tag filtering
def test_index_tag_filter(client, test_user):
    """Test the index page with tag filtering."""
    # Create some dummy media for testing, associated with test_user
    media1 = Media(title="Test Media 1", filename="test1.jpg", file_type="image", tags="nature,landscape", user_id=test_user.id, description="")
    media2 = Media(title="Test Media 2", filename="test2.mp3", file_type="audio", tags="music,pop", user_id=test_user.id, description="")
    media3 = Media(title="Test Media 3", filename="test3.pdf", file_type="ebook", tags="science,nature", user_id=test_user.id, description="")
    db.session.add_all([media1, media2, media3])
    db.session.commit()

    # Test with a tag that should match media1 and media3
    res = client.get('/?tags=nature')
    assert res.status_code == 200
    assert b'Test Media 1' in res.data
    assert b'Test Media 3' in res.data
    assert b'Test Media 2' not in res.data

    # Test with a tag that should match media2
    res = client.get('/?tags=music')
    assert res.status_code == 200
    assert b'Test Media 2' in res.data
    assert b'Test Media 1' not in res.data
    assert b'Test Media 3' not in res.data

    # Clean up test data (important!)
    db.session.delete(media1)
    db.session.delete(media2)
    db.session.delete(media3)
    db.session.commit()
