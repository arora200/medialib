
import pytest
from models import User

def test_user_model():
    """Test User model."""
    user = User(username='testuser')
    assert user.username == 'testuser'
