from flask import Blueprint, Flask, redirect, flash, render_template, session, url_for
from flask_login import LoginManager, current_user, login_user, logout_user
from web.forms import LoginForm, SignupForm
from werkzeug.security import check_password_hash
from .models import User, UserProfile, db
from werkzeug.security import generate_password_hash

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('views.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)  # This logs in the user
            flash('Login successful!', 'success')
            return redirect(url_for('views.dashboard'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html', form=form)

@auth.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('views.home'))

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        # Validate ID number
        if not validate_id_number(form.id_number.data):
            flash('Invalid ID number', 'error')
            return redirect(url_for('signup'))
        #check if email is already in use
        user_profile = UserProfile.query.filter_by(email=form.email.data).first()
        if user_profile:
            flash('An account with this email already exists. Use a unique email.', 'error')
            return redirect(url_for('auth.signup'))
        else:
            user = User.query.filter_by(username=form.id_number.data).first()
            if user:
                flash('An account with this ID already exists. Please login.')
                return redirect(url_for('auth.login'))  # Redirect to login page if ID exists
            else:
                # Create a new User object

                # Rest of the code...
                new_user = User(username=form.id_number.data, password=generate_password_hash(form.password.data), type='Client')
                db.session.add(new_user)
                db.session.commit()

                # Create a new UserProfile object
                gender = determine_gender(form.id_number.data)
                user_profile = UserProfile(
                    id=form.id_number.data,
                    gender=gender,
                    first_name=form.first_name.data,
                    last_name=form.last_name.data,
                    email=form.email.data,
                    contact_number=form.contact_number.data,
                    user_id=new_user.id
                )
                db.session.add(user_profile)
                db.session.commit()

                flash('Signup successful!')
                return redirect(url_for('auth.login'))
    else:
        return render_template('signup.html', form=form)

def validate_id_number(id_number):
    # Return True if the ID/Passport number is valid, False otherwise
    # Check if the ID number is 13 digits long
    if len(id_number) != 13:
        return False

    # Extract the date of birth digits (YYMMDD)
    date_of_birth = id_number[:6]

    # Extract the citizenship status digit (C)
    citizenship_status = id_number[10]

    # Validate the date of birth digits
    try:
        year = int(date_of_birth[:2])
        month = int(date_of_birth[2:4])
        day = int(date_of_birth[4:6])
        # Implement additional validation logic for the date of birth if needed
    except ValueError:
        return False

    # Validate the citizenship status digit
    return citizenship_status in ['0', '1']

def determine_gender(id_number):
    # Return the determined gender ('M', 'F', 'O')
    # Extract the gender digits (SSSS)
    gender_digits = id_number[6:10]

    # Validate the gender digits
    try:
        gender_digits = int(gender_digits)
        if gender_digits < 0 or gender_digits > 9999:
            return None
    except ValueError:
        return None

    # Determine the gender based on the gender digits
    return 'F' if gender_digits < 5000 else 'M'