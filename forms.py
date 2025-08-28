
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, URL

class BookmarkForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    url = StringField('URL', validators=[DataRequired(), URL()])
    description = TextAreaField('Description')
    tags = StringField('Tags')
    submit = SubmitField('Add Bookmark')
