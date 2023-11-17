"""
A sample Hello World server.
"""
import os
import secrets

from flask import Flask, render_template, redirect, url_for
from flask_bootstrap import Bootstrap5

# Libraries regarding forms handling
from flask_wtf import FlaskForm, CSRFProtect
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length

# Library about google cloud storage
from google.cloud import storage

#load the .env variables
# PLACEHOLDER: If I decide to go with .env files (depending on cloud run implementation)
# Then I will need to load the .env variables with the two commands bellow
# For now I load them directly on the docker container with the flag --env-file=.env
#from dotenv import load_dotenv
#load_dotenv()


# pylint: disable=C0103
app = Flask(__name__)
foo = secrets.token_urlsafe(16)
app.secret_key = foo
print (os.environ.get('GOOGLE_STORAGE_BUCKET_NAME'))
# Configure Google Cloud Storage
bucket_name = os.environ.get('GOOGLE_STORAGE_BUCKET_NAME')
project_id = os.environ.get('GOOGLE_STORAGE_PROJECT_ID')
bucket_location = os.environ.get('GOOGLE_STORAGE_BUCKET_LOCATION')

# Bootstrap-Flask requires this line
bootstrap = Bootstrap5(app)
# Flask-WTF requires this line
csrf = CSRFProtect(app)

def upload_file_to_storage(file, filename):
    client = storage.Client(project=project_id)
    bucket = client.get_bucket(bucket_name)
    blob = bucket.blob(f'uploads/{filename}')
    blob.upload_from_file(file)

class NameForm(FlaskForm):
    name = StringField('Name a character from the book', validators=[DataRequired(), Length(4, 40)])
    gzfile = FileField('Upload a gz file with all the data', validators=[
            DataRequired(),
            FileAllowed(['gz'], 'Only .gz files allowed!')
        ])
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

        # Handle the gz file
        uploaded_gz_file = form.gzfile.data
        filename = uploaded_gz_file.filename
        upload_file_to_storage(uploaded_gz_file, filename)


    return render_template('index.html', names=names, form=form, message=message)

if __name__ == '__main__':
    server_port = os.environ.get('PORT', '8080')
    app.run(debug=True, port=server_port, host='0.0.0.0')
