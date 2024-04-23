from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from datetime import datetime
from random import *

app = Flask(__name__)
mail = Mail(app)

# Configuration for email
app.config["MAIL_SERVER"] = 'smtp.fastmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'b2twob@fastmail.com'
app.config['MAIL_PASSWORD'] = 'f56p3j9cx38p279p'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_DEBUG'] = True


app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Create the uploads directory if it doesn't exist
uploads_dir = os.path.join('static', 'uploads')
os.makedirs(uploads_dir, exist_ok=True)

# Configure the UPLOAD_FOLDER
UPLOAD_FOLDER = uploads_dir
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='customer')
    phonenumber = db.Column(db.String(20), nullable=True)
    verified = db.Column(db.Boolean, default=False)

    def set_email(self, email):
        self.email = email.lower()

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    photo = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].lower()
        password = request.form['password']
        role = request.form['role']
        phonenumber = request.form['phonenumber']

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already exists. Please choose a different one.', 'error')
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(name=name, email=email, password=hashed_password, role=role, phonenumber=phonenumber)
            db.session.add(new_user)
            db.session.commit()
            
            # Generate OTP and send verification email
            otp = randint(1000, 9999)
            session['otp'] = otp
            if send_verification_email(email, otp):
                flash('Registration successful! Please check your email for verification.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Failed to send verification email. Please try again later.', 'error')
    return render_template('register.html')

def send_verification_email(email, otp):
    try:
        msg = Message('Email Verification', sender='b2twob@fastmail.com', recipients=[email])
        msg.body = f'Your verification code is: {otp}'
        mail.send(msg)
        return True
    except Exception as e:
        print("Error sending verification email:", e)
        return False

@app.route('/verify_email', methods=['POST'])
def verify_email():
    email = request.form.get('email')
    otp = session.get('otp')
    if email and otp:
        if send_verification_email(email, otp):
            flash('Verification email resent. Please check your email.', 'success')
        else:
            flash('Failed to resend verification email. Please try again later.', 'error')
    else:
        flash('Email address or OTP is missing.', 'error')
    return redirect(url_for('login'))

@app.route('/verify', methods=['POST'])
def verify():
    user_otp = request.form["otp"]
    stored_otp = session.get('otp')
    if user_otp == str(stored_otp):
        email = request.form["email"]
        user = User.query.filter_by(email=email).first()
        user.verified = True
        db.session.commit()
        return jsonify({"message": "Email verified successfully!"})
    else:
        return jsonify({"message": "Invalid OTP!"})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            if user.verified:
                login_user(user)
                flash('Login successful!', 'success')
                if user.role == 'seller':
                    return redirect(url_for('seller_dashboard'))
                elif user.role == 'customer':
                    return redirect(url_for('customer_dashboard'))
            else:
                flash('Email not verified. Please verify your email.', 'error')
        else:
            flash('Invalid email or password. Please try again.', 'error')
    return render_template('login.html')

@app.route('/seller_dashboard')
@login_required
def seller_dashboard():
    if current_user.role == 'seller':
        seller_products = Product.query.filter_by(user_id=current_user.id).all()
        return render_template('seller_dashboard.html', products=seller_products)
    else:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('login'))

@app.route('/customer_dashboard')
@login_required
def customer_dashboard():
    if current_user.role == 'customer':
        products_with_users = db.session.query(Product, User).join(User).all()
        return render_template('customer_dashboard.html', products_with_users=products_with_users)
    else:
        flash('Please log in first', 'info')
        return redirect(url_for('login'))

@app.route('/guest_dashboard', methods=['GET', 'POST'])
def guest_dashboard():
    products_with_users = db.session.query(Product, User).join(User).all()
    return render_template('guest_dashboard.html', products_with_users=products_with_users)

@app.route('/add_product', methods=['POST'])
@login_required
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        quantity = int(request.form['quantity'])
        price = float(request.form['price'])

        if 'photo' in request.files:
            photo = request.files['photo']
            filename = secure_filename(photo.filename)

            # Generate a unique filename
            unique_filename = generate_unique_filename(filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            photo.save(filepath)
        else:
            filepath = None

        user_id = current_user.id if current_user.is_authenticated else None
        new_product = Product(name=name, quantity=quantity, price=price, photo=unique_filename, user_id=user_id)
        db.session.add(new_product)
        db.session.commit()
        flash('Product added successfully!', 'success')

    return redirect(url_for('seller_dashboard'))

def generate_unique_filename(filename):
    # Append a timestamp to the filename to make it unique
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    basename, extension = os.path.splitext(filename)
    return f"{basename}_{timestamp}{extension}"

@app.route('/delete_product/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    if current_user.role == 'seller':
        product = Product.query.get(product_id)
        if product:
            # Delete the product image from the server if it exists
            if product.photo:
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], product.photo)
                if os.path.exists(image_path):
                    os.remove(image_path)

            db.session.delete(product)
            db.session.commit()
            flash('Product deleted successfully!', 'success')
        else:
            flash('Product not found.', 'error')
    else:
        flash('Unauthorized access!', 'error')
    return redirect(url_for('seller_dashboard'))

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/guest_exit', methods=['POST'])
def guest_exit():
    logout_user()
    flash('Exited', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
