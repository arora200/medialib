import pytest
from app import app as flask_app
from models import db, User
from werkzeug.security import generate_password_hash

@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:" # Use in-memory SQLite for tests
    })
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def test_user(app):
    user = User(username='testuser', password_hash=generate_password_hash('password'))
    db.session.add(user)
    db.session.commit()
    # Removed db.session.expunge(user) to keep the user bound to the session
    yield user
    # Clean up after test
    db.session.delete(user)
    db.session.commit()