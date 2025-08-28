
import pytest
from app import app as flask_app



def test_api_doc(client):
    """Test the api doc page."""
    res = client.get('/api/doc/')
    assert res.status_code == 200
