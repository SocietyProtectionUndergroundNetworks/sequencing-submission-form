"""
A sample Hello World server.
"""
import os
import secrets

from flask import Flask, render_template, redirect, url_for
from flask_bootstrap import Bootstrap5

from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length


# pylint: disable=C0103
app = Flask(__name__)
foo = secrets.token_urlsafe(16)
app.secret_key = foo

# Bootstrap-Flask requires this line
bootstrap = Bootstrap5(app)
# Flask-WTF requires this line
csrf = CSRFProtect(app)

class NameForm(FlaskForm):
    name = StringField('Name a character from the book', validators=[DataRequired(), Length(4, 40)])
    submit = SubmitField('Submit')


@app.route('/', methods=['GET', 'POST'])
def hello():
    """Return a friendly HTTP greeting."""
    message = "Test Form for uploading data"
    form = NameForm()
    names = ["darrow", "servo", "virga", "the poet", "mastang", "ragnar"]
    if form.validate_on_submit():
        name = form.name.data
        if name.lower() in names:
            # empty the form field
            form.name.data = ""
            message = "We found the character " + name
        else:
            message = "That character is not in our list."    

    return render_template('index.html', names=names, form=form, message=message)

if __name__ == '__main__':
    server_port = os.environ.get('PORT', '8080')
    app.run(debug=True, port=server_port, host='0.0.0.0')
