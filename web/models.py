# models/user.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin,db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    password = db.Column(db.String(256))
    type = db.Column(db.String(50))
    active = db.Column(db.Boolean, default=True)# True if user is active, False if user is inactive(Developer's choice)
    UserProfile = db.relationship('UserProfile', backref='user')# Access UserProfile from User model
    
    @property
    def is_active(self):
        return self.active
    
    def get_id(self):
        return str(self.id)


class UserProfile(UserMixin, db.Model):
    __tablename__ = 'user_profile'
    id = db.Column(db.String(255), primary_key=True)
    gender = db.Column(db.String(1))
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    contact_number = db.Column(db.String(255))
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Link to User model

class DocumentCertificationRequest(db.Model):
    __tablename__ = 'document_certification_request'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    document_copy = db.Column(db.LargeBinary)
    original_document = db.Column(db.LargeBinary)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_certified = db.Column(db.Boolean, default=False)

class CertifiedDocument(db.Model):
    __tablename__ = 'certified_document'
    id = db.Column(db.Integer, primary_key=True)
    certification_request_id = db.Column(db.Integer, db.ForeignKey('document_certification_request.id'))
    document_certification_request = db.relationship('DocumentCertificationRequest', backref='certified_document')  # Access CertifiedDocument from DocumentCertificationRequest    
    stamped_document = db.Column(db.LargeBinary)
    name = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    expire_date = db.Column(db.DateTime)

class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender = db.relationship('User', foreign_keys=[sender_id], backref=db.backref('sent_messages', lazy='dynamic'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref=db.backref('received_messages', lazy='dynamic'))
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    send_to_all = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"Message from {self.sender} to {self.recipient or 'all users'}"
    
    