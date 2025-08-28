import os

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.mp3', '.wav', '.mp4', '.mov', '.pdf', '.docx', '.txt'}

def allowed_file(filename):
    return '.' in filename and \
           os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif']:
        return 'image'
    elif ext in ['.mp3', '.wav']:
        return 'audio'
    elif ext in ['.mp4', '.mov']:
        return 'video'
    elif ext in ['.pdf', '.docx', '.txt']:
        return 'ebook'
    return 'other'
