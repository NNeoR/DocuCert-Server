from flask import Blueprint, Flask, redirect, flash, render_template, request, session, url_for
from flask_login import LoginManager, current_user, login_user, logout_user
from web.forms import CustomPasswordResetForm, LoginForm, PasswordResetForm, SignupForm
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

@auth.route('/reset_password', methods=['GET', 'POST'])
def password_reset_view():
    # sourcery skip: merge-else-if-into-elif, move-assign-in-block, use-named-expression
    if request.method == 'POST':
        
        form = CustomPasswordResetForm(request.form)
        if form.validate_on_submit():
            # Verify the account here
            user_id = form.id_number.data
            email = form.email.data
            user = User.query.filter_by(username=user_id).first()
            if user:
                
                user_profile = UserProfile.query.filter_by(email=email).first()
                if user_profile:
                    session['user_verified'] = True
                    session['user_id'] = user_id
                    
                    flash('Account verified. Please reset your password.', 'success')
                    return redirect(url_for('auth.update_password'))
                else:
                    flash('Email specified is incorrect.', 'error')
                return redirect(url_for('auth.reset_password'))  # Redirect to the same page to show reset form
            else:
                flash('User ID specified not found. Please create an account.', 'error')
                render_template('reset_password.html', form=form)
        else:
            flash('Invalid input.', 'error')
            render_template('reset_password.html', form=form)

    else:
        form = CustomPasswordResetForm()  # Assuming this is the password reset form
        
    return render_template('reset_password.html', form=form)

@auth.route('/update_password', methods=['GET', 'POST'])
def update_password():
    form = PasswordResetForm(request.form if request.method == 'POST' else None)
    user_id = session.get('user_id')
    user = User.query.filter_by(username=user_id).first()

    context = {
        'form': form
    }

    if request.method == 'POST' and form.validate_on_submit():
        if user:
            new_password = request.form.get('password')
            user.password = generate_password_hash(new_password) 
            db.session.commit()
            flash('Your password has been reset.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('User not found.', 'error')

    return render_template('update_password.html', **context)

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if not form.validate_on_submit():
        return render_template('signup.html', form=form)
    # Validate ID number
    if not validate_id_number(form.id_number.data):
        flash('Invalid ID number', 'error')
        return redirect(url_for('signup'))
    if user_profile := UserProfile.query.filter_by(
        email=form.email.data
    ).first():
        flash('An account with this email already exists. Use a unique email.', 'error')
        return redirect(url_for('auth.signup'))
    else:
        if user := User.query.filter_by(username=form.id_number.data).first():
            flash('An account with this ID already exists. Please login.')
        else:
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
        return redirect(url_for('auth.login'))  # Redirect to login page if ID exists

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