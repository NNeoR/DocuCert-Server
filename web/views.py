# routes.py
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import io
import os
import smtplib
from flask import Blueprint, abort, current_app, flash, render_template, redirect, request, send_file, session, url_for
from flask_wtf.csrf import generate_csrf
from flask_login import current_user, login_required, logout_user
import numpy as np
from web.auth import determine_gender, validate_id_number
from .forms import UpdateProfileForm, MessageForm, ProfileForm, SignupForm, DocumentCertificationForm
from werkzeug.security import check_password_hash, generate_password_hash
from .models import User , db, UserProfile, DocumentCertificationRequest, CertifiedDocument, Message
import logging
from PIL import Image
import cv2
from skimage.metrics import structural_similarity as ssim
from pdf2image import convert_from_bytes

logger = logging.getLogger(__name__)

views = Blueprint('views', __name__)

@views.route('/')
def home():
    return render_template('home.html')


@views.route('/dashboard')
@login_required
def dashboard():
    
    user = User.query.filter_by(username=current_user.username).first()
    user_profile = UserProfile.query.filter_by(user_id=user.id).first()
    #concate user first name and last name
    full_name = f'{user_profile.first_name} {user_profile.last_name}'
    user_name = user.username
    total_users = User.query.count()
    total_requests = DocumentCertificationRequest.query.count()
    messages_sent_count = Message.query.filter_by(sender_id=user.id).count()

    certified_requests = DocumentCertificationRequest.query.filter_by(user_id=user.id,is_certified=True).count()
    requests = DocumentCertificationRequest.query.filter_by(user_id=user.id).count()
    request_ids = DocumentCertificationRequest.query.filter_by(user_id=user.id).all()
    certified_documents = CertifiedDocument.query.filter(CertifiedDocument.certification_request_id.in_([request.id for request in request_ids])).count()
    unread_messages_count = Message.query.filter_by(recipient_id=user.id, is_read=False).count()

    context = {
        'user': user,
        'total_users': total_users,
        'total_requests': total_requests,
        'certified_requests': certified_requests,
        'certified_documents': certified_documents,
        'user_name': full_name,
        'requests': requests,
        'unread_messages_count': unread_messages_count,
        'messages_sent_count': messages_sent_count
    }
    return render_template('dashboard.html', **context)

#Certify Document
@views.route('/document_certification', methods=['GET', 'POST'])
@login_required
def document_certification():
    form = DocumentCertificationForm()
    
    if form.validate_on_submit():
        document_copy = form.document_copy.data
        original_document = form.original_document.data
        
        if not document_copy.filename.endswith('.pdf'):
            flash('The document copy must be a PDF', 'error')
            return redirect(url_for('document_certification_view'))
        
        #RETRIEVE THE DATA FROM THE FILES
        document_copy_data = document_copy.read()
        original_document_data = original_document.read()
        
        # CREATE A NEW DOCUMENT CERTIFICATION REQUEST
        certification_request = DocumentCertificationRequest(
            user_id=current_user.id, 
            document_copy=document_copy_data,
            original_document=original_document_data,
            is_certified=False
        )
        #ADD AND COMMIT THE REQUEST
        db.session.add(certification_request)
        db.session.commit()
        
        if original_document.filename.endswith('.png'):
            if not is_pdf_png_similar(document_copy_data, original_document_data):
                return document_certification_subview()
        elif original_document.filename.endswith('.pdf'):
            if not is_pdf_similar(document_copy_data, original_document_data):
                return document_certification_subview()
        else:
            flash('The original document must be a PDF or a PNG', 'error')
            return redirect(url_for('views.document_certification_view'))
        
        stamp_image_path = os.path.join(current_app.root_path, 'static', 'certifiedStamp.png')
        stamp_image = Image.open(stamp_image_path)
        output_image = apply_stamp_to_image(document_copy_data, stamp_image)
        output_image_io = io.BytesIO()
        output_image.save(output_image_io, format='PNG')
        
        #set request as certified
        certification_request.is_certified = True
        db.session.commit()
        #get user email
        user = User.query.filter_by(id=current_user.id).first()
        userprofile = UserProfile.query.filter_by(user_id=user.id).first()
        user_email = userprofile.email
        #create a certified document
        certified_document = CertifiedDocument(
            certification_request_id=certification_request.id,
            stamped_document=output_image_io.getvalue(),
            name=document_copy.filename
        )
        #add and commit the certified document
        db.session.add(certified_document)
        db.session.commit()
        
        # Send the certified document to the user's email
        output_image_io.seek(0) # Reset the file pointer to the beginning
        send_document_to_email(user_email, output_image_io)

        flash('Document certified successfully!', 'success')
        flash('A copy of the certified document has been sent to your email.', 'success')
        return redirect(url_for('views.dashboard'))

    return render_template('document_certification.html', form=form)


def document_certification_subview():
    flash('Documents do not match or have been tampered with', 'error')
    return redirect(url_for('views.dashboard'))

def is_pdf_png_similar(pdf_data, png_data):
    try:
        pdf_image = convert_pdf_to_png(io.BytesIO(pdf_data))
        with Image.open(io.BytesIO(png_data)) as png_image:
            width = min(pdf_image.width, png_image.width)
            height = min(pdf_image.height, png_image.height)
            if pdf_image.width != width or pdf_image.height != height:
                pdf_image = pdf_image.resize((width, height))
            if png_image.width != width or png_image.height != height:
                png_image = png_image.resize((width, height))

            pdf_data_array = cv2.cvtColor(np.array(pdf_image), cv2.COLOR_RGB2BGR)
            png_data_array = cv2.cvtColor(np.array(png_image), cv2.COLOR_RGB2BGR)

        win_size = min(width, height)
        if win_size % 2 == 0:
            win_size -= 1

        similarity_score = ssim(pdf_data_array, png_data_array, multichannel=True, win_size=win_size, channel_axis=2)
        return similarity_score > 0.50
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def is_pdf_similar(pdf1_data, pdf2_data):
    pdf1_image = convert_pdf_to_png(io.BytesIO(pdf1_data))
    pdf2_image = convert_pdf_to_png(io.BytesIO(pdf2_data))

    width = min(pdf1_image.width, pdf2_image.width)
    height = min(pdf1_image.height, pdf2_image.height)
    if pdf1_image.width != width or pdf1_image.height != height:
        pdf1_image = pdf1_image.resize((width, height))
    if pdf2_image.width != width or pdf2_image.height != height:
        pdf2_image = pdf2_image.resize((width, height))

    pdf1_data_array = cv2.cvtColor(np.array(pdf1_image), cv2.COLOR_RGB2BGR)
    pdf2_data_array = cv2.cvtColor(np.array(pdf2_image), cv2.COLOR_RGB2BGR)

    win_size = min(width, height)
    if win_size % 2 == 0:
        win_size -= 1

    similarity_score = ssim(pdf1_data_array, pdf2_data_array, multichannel=True, win_size=win_size, channel_axis=2)
    return similarity_score > 0.80

def convert_pdf_to_png(pdf_file_io):
    file_content = pdf_file_io.read()
    images = convert_from_bytes(file_content)
    return images[0]

def apply_stamp_to_image(document_copy_data, stamp_image):
    input_image = convert_pdf_to_png(io.BytesIO(document_copy_data))
    stamp_width, stamp_height = stamp_image.size
    input_width, input_height = input_image.size
    stamp_ratio = min(input_width / 4 / stamp_width, input_height / 4 / stamp_height)
    new_stamp_width = int(stamp_width * stamp_ratio)
    new_stamp_height = int(stamp_height * stamp_ratio)
    resized_stamp_image = stamp_image.resize((new_stamp_width, new_stamp_height))

    position = (input_width - new_stamp_width, input_height - new_stamp_height)
    if resized_stamp_image.mode in ('RGBA', 'LA') or (resized_stamp_image.mode == 'P' and 'transparency' in resized_stamp_image.info):
        input_image.paste(resized_stamp_image, position, resized_stamp_image)
    else:
        input_image.paste(resized_stamp_image, position)
    return input_image

def send_document_to_email(email, document):
    msg = MIMEMultipart()
    msg['Subject'] = 'Certified Document'
    msg['From'] = 'neotshivhangani@gmail.com'
    msg['To'] = email

    document.seek(0)

    attachment = MIMEBase('application', 'pdf')
    attachment.set_payload(document.read())
    encoders.encode_base64(attachment)
    attachment.add_header('Content-Disposition', 'attachment', filename='document.pdf')
    msg.attach(attachment)

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login('neotshivhangani@gmail.com', 'jton guvb atbe micl')
        server.sendmail(msg['From'], [msg['To']], msg.as_string())
        
#User Management views
@views.route('/user_management')
@login_required
def user_management():
    
    if current_user.is_authenticated and current_user.type == 'Admin':
        users = UserProfile.query.all()
        #define list of csrf tokens
        csrf_tokens = [generate_csrf(), generate_csrf()]
        context = {
            'csrf_tokens': csrf_tokens,
            'users': users
        }
        return render_template('user_management.html', **context)
    else:
        return redirect(url_for('views.dashboard'))
    
@views.route('/update_user/<string:id_number>/', methods=['GET', 'POST'])
@login_required
def update_user(id_number):
    user_profile = UserProfile.query.filter_by(id=id_number).first()
    form = UpdateProfileForm()
    
    if request.method == 'POST' and form.validate_on_submit():
            form.populate_obj(user_profile)
            db.session.commit()
            flash('User updated successfully.', 'success')
            return redirect(url_for('views.user_management'))
        
    user_profile = UserProfile.query.filter_by(id=id_number).first()
    form.id.data = user_profile.id
    form.first_name.data = user_profile.first_name
    form.last_name.data = user_profile.last_name
    form.email.data = user_profile.email
    form.contact_number.data = user_profile.contact_number
    
    context = {
        'form': form,
        'user_profile': user_profile
    }
    return render_template('update_user.html', **context)

@views.route('/delete_user/<string:id_number>/', methods=['GET', 'POST'])
@login_required
def delete_user(id_number):
    user_profile = UserProfile.query.filter_by(id_number=id_number).first()
    try:
        user_id = user_profile.user_id
        user = User.query.get(user_id)
        if user_profile and user:
            db.session.delete(user_profile)
            db.session.delete(user)
            db.session.commit()
            # Assuming there's a mechanism to flash messages to the user
            flash('User and profile deleted successfully.', 'success')
        else:
            flash('User or profile not found.', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {str(e)}', 'error')

    return redirect(url_for('views.user_management'))

#certified documents views
@views.route('/certified_documents/')
@login_required
def certified_documents():
    user = current_user
    certification_requests = DocumentCertificationRequest.query.filter_by(user_id=user.id).all()
    certified_documents = CertifiedDocument.query.filter(CertifiedDocument.certification_request_id.in_([request.id for request in certification_requests])).all()
    
    return render_template('certified_documents.html', certified_documents=certified_documents)

@views.route('/certified_documents/download/<int:document_id>/')
def download_document(document_id):
    try:
        document = CertifiedDocument.query.get(document_id)
        if document is None:
            abort(404, description="Document does not exist")

        file_stream = io.BytesIO(document.stamped_document)  # Assuming 'stamped_document' is the binary column
        file_name = document.name
        return send_file(file_stream, as_attachment=True, download_name=file_name, mimetype='application/octet-stream')
    except Exception as e:
        abort(404, description=str(e))

@views.route('/send_message', methods=['GET', 'POST'])
@login_required
def send_message():
    if current_user.type != 'Admin':
        return redirect(url_for('views.dashboard'))

    form = MessageForm()
    if form.validate_on_submit():
        recipient = form.recipient.data
        subject = form.subject.data
        body = form.body.data
        if send_to_all := form.send_to_all.data:
            users = User.query.all()
            for user in users:
                message = Message(
                    sender_id=User.query.filter_by(id=current_user.id).first().id,
                    recipient_id=User.query.filter_by(id=user.id).first().id,
                    subject=subject,
                    body=body,
                    send_to_all=True
                )
                db.session.add(message)
                email = user.UserProfile.email
                send_message_to_email(email, subject, body)
        else:
            if recipient:
                user = User.query.get(recipient.id)
                message = Message(
                    sender_id=User.query.filter_by(id=current_user.id).first().id,
                    recipient_id=User.query.filter_by(id=user.id).first().id,
                    subject=subject,
                    body=body,
                    send_to_all=False
                )
                db.session.add(message)
                user_profile = UserProfile.query.filter_by(user_id=user.id).first()
                send_message_to_email(user_profile.email, subject, body)
            else:
                flash('Recipient not found.', 'error')
                return redirect(url_for('send_message_view'))

        db.session.commit()
        flash('Message sent successfully!', 'success')
        return redirect(url_for('views.dashboard'))

    return render_template('send_message.html', form=form)

def send_message_to_email(email, subject, message):
    msg = MIMEMultipart()
    msg['From'] = 'neotshivhangani@gmail.com'
    msg['To'] = email
    msg['Subject'] = subject
    
    body = message
    msg.attach(MIMEText(body, 'plain'))
    
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login('neotshivhangani@gmail.com', 'jton guvb atbe micl')
        server.send_message(msg)
        
        
@views.route('/inbox')
@login_required
def inbox():
    # Get all messages for the current user descending by timestamp
    messages = Message.query.filter_by(recipient_id=current_user.id).order_by(Message.timestamp.desc()).all()
    context = {
        'messages': messages
    }
    
    return render_template('inbox.html', **context)

@views.route('/message/<int:message_id>')
@login_required
def message_detail(message_id):
    if message := Message.query.filter_by(
        id=message_id, recipient_id=current_user.id
    ).first():
        message.is_read = True
        db.session.commit()
        return render_template('message_detail.html', message=message)
    else:
        # Handle message not found or unauthorized access
        return redirect(url_for('views.inbox'))
    
#Profile View
@views.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    user = User.query.filter_by(id=current_user.id).first()
    print(request.form)  # Print POST data for debugging
    if request.method == 'POST':
        profile_form = ProfileForm(request.form, obj=user_profile)
        if profile_form.validate_on_submit():
            profile_form.populate_obj(user_profile)
            if(request.form.get('updatePasswordCheck') =='on'):

                if 'existing_password' in request.form and not check_password_hash(user.password, request.form['existing_password']):
                    flash('Incorrect password', 'error')
                    return redirect(url_for('views.profile'))
                if 'new_password' in request.form and request.form['new_password']:
                    user.password = generate_password_hash(request.form['new_password'])
                    db.session.add(user)

            db.session.commit()
            flash('Profile updated successfully.', 'success')
            return redirect(url_for('views.profile'))
        else:
            print(profile_form.errors)  # Print form errors for debugging
    else:
        profile_form = ProfileForm(obj=user_profile)

    gender = user_profile.gender
    title = 'Welcome Mr.' if gender == 'M' else 'Welcome Ms.'
    context = {
        'form': profile_form,
        'profile_form': profile_form,
        'user_profile': user_profile,
        'title': title,
    }

    return render_template('profile.html', **context)

#Create User
@views.route('/create_user', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.type != 'Admin':
        return redirect(url_for('views.dashboard'))
    form = SignupForm()
    if request.method == 'POST' and form.validate_on_submit():

        if not validate_id_number(form.id_number.data):
            flash('Invalid ID number', 'error')
            return render_template('create_user.html', form=form)

        new_user = User(username=form.id_number.data, password=generate_password_hash(form.password.data), type='Client')
        db.session.add(new_user)
        db.session.commit()

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
        flash('User created successfully!', 'success')
        return redirect(url_for('views.user_management'))
    return render_template('create_user.html', form=form)

#Error handling
#@views.app_errorhandler(404)
#def page_not_found(error):
    #return render_template('404.html'), 404
