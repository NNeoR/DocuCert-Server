# forms.py
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, SubmitField, TextAreaField, FileField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from wtforms_sqlalchemy.fields import QuerySelectField
from .models import User

class CustomPasswordResetForm(FlaskForm):
    id_number = StringField('ID Number', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=254)])

class PasswordResetForm(FlaskForm):
    password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=5, max=100),  # Adjust min and max values based on your security policy
        EqualTo('confirm', message='Passwords must match')
    ])
    confirm = PasswordField('Repeat Password', validators=[DataRequired()])

class SignupForm(FlaskForm):
    id_number = StringField('ID Number', validators=[DataRequired()])
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    contact_number = StringField('Contact Number', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class ProfileForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    contact_number = StringField('Contact Number', validators=[DataRequired()])
    existing_password = PasswordField('Existing Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired()])

class UpdateProfileForm(FlaskForm):
    id = StringField('ID Number',render_kw={'readonly': True}, validators=[DataRequired()])
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    contact_number = StringField('Contact Number', validators=[DataRequired()])

class EmailForm(FlaskForm):
    subject = StringField('Subject', validators=[DataRequired(), Length(max=255)])
    message = TextAreaField('Message', validators=[DataRequired()])
    recipient = QuerySelectField('Recipient', query_factory=lambda: User.query.all(), allow_blank=True)
    send_to_all = BooleanField('Send to all users')

class MessageForm(FlaskForm):
    send_to_all = BooleanField('Send to all users', default=False, false_values=(False, 'false', 0, '0'))
    subject = StringField('Subject', validators=[DataRequired()])
    body = TextAreaField('Body', validators=[DataRequired()], render_kw={"rows": 10, "cols": 50})
    recipient = QuerySelectField(
        'Recipient (leave empty to send to all users)',
        query_factory=lambda: User.query.filter(User.id != current_user.id).all(), allow_blank=True, 
        get_label='username')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    
class DocumentCertificationForm(FlaskForm):
    document_copy = FileField('Copy Document', validators=[DataRequired()])
    original_document = FileField('Original Document', validators=[DataRequired()])

