from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from datetime import datetime
from flask import jsonify


app = Flask(__name__)
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

@app.route('/', methods=['GET', 'POST'])
def index():
    products_with_users = db.session.query(Product, User).join(User).all()
    return render_template('index.html', products_with_users=products_with_users)


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
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            if user.role == 'seller':
                return redirect(url_for('seller_dashboard'))
            elif user.role == 'customer':
                return redirect(url_for('customer_dashboard'))
            else:
                flash('Invalid user role.', 'error')
                return redirect(url_for('login'))
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
@app.route('/search_products', methods=['POST'])
def search_products():
    data = request.get_json()
    search_term = data['searchTerm']
    filtered_products = db.session.query(Product, User).join(User).filter(Product.name.ilike(f'%{search_term}%')).all()
    products_data = [{
        'name': product.name,
        'quantity': product.quantity,
        'price': product.price,
        'user': {
            'name': user.name,
            'phonenumber': user.phonenumber
        },
        'photo': product.photo
    } for product, user in filtered_products]
    return jsonify(products_data)
@app.route('/search')
def search():
    query = request.args.get('q')
    # Implement your search logic here
    # You can query your database or perform any search operation
    # For demonstration, let's just return a dummy response
    search_results = [
        {'name': 'Product 1', 'price': 10},
        {'name': 'Product 2', 'price': 20},
        # Add more search results as needed
    ]
    return jsonify(search_results)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
