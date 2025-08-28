
import pytest
from app import app as flask_app



def test_index(client):
    """Test the index page."""
    res = client.get('/')
    assert res.status_code == 200
