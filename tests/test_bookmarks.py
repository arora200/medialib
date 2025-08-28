import pytest
from models import db, User, Bookmark
from werkzeug.security import generate_password_hash

@pytest.fixture
def user(app):
    with app.app_context():
        user = User(username='testuser', password_hash=generate_password_hash('password'))
        db.session.add(user)
        db.session.commit()
        yield user
        db.session.delete(user)
        db.session.commit()

def test_bookmarks_page(client, user):
    # Login as the user
    with client.session_transaction() as session:
        session['_user_id'] = user.id
        session['_fresh'] = True

    # Access the bookmarks page
    res = client.get('/bookmarks')
    assert res.status_code == 200

    # Add a new bookmark
    res = client.post('/bookmarks', data={
        'title': 'Google',
        'url': 'https://google.com',
        'description': 'Search engine'
    }, follow_redirects=True)
    assert res.status_code == 200

    # Check if the bookmark is in the database
    bookmark = Bookmark.query.filter_by(title='Google').first()
    assert bookmark is not None
    assert bookmark.owner == user

    # Check if the bookmark is on the page
    assert b'Google' in res.data