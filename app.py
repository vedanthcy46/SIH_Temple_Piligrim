from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from detect import detect_crowd, get_crowd_status
from sqlalchemy import text

app = Flask(__name__)
app.config.from_object('config.Config')

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='pilgrim')
    bookings = db.relationship('Booking', backref='user', lazy=True)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(20), nullable=False)
    persons = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Crowd(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), nullable=False, default='Low')
    count = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'pilgrim')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('register'))
        
        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role=role
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('book'))
        else:
            flash('Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/book', methods=['GET', 'POST'])
@login_required
def book():
    if current_user.role != 'pilgrim':
        return redirect(url_for('admin'))
    
    if request.method == 'POST':
        date_str = request.form['date']
        time_slot = request.form['time_slot']
        persons = int(request.form['persons'])
        
        booking = Booking(
            user_id=current_user.id,
            date=datetime.strptime(date_str, '%Y-%m-%d').date(),
            time_slot=time_slot,
            persons=persons
        )
        db.session.add(booking)
        db.session.commit()
        
        # Emit real-time booking update
        socketio.emit('new_booking', {
            'id': booking.id,
            'user': current_user.name,
            'date': date_str,
            'time_slot': time_slot,
            'persons': persons,
            'created_at': booking.created_at.strftime('%Y-%m-%d %H:%M')
        })
        
        flash('Booking confirmed!')
        return redirect(url_for('my_bookings'))
    
    return render_template('book.html')

@app.route('/my-bookings')
@login_required
def my_bookings():
    if current_user.role != 'pilgrim':
        return redirect(url_for('admin'))
    
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()
    return render_template('my_bookings.html', bookings=bookings)

@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        return redirect(url_for('book'))
    
    bookings = Booking.query.join(User).order_by(Booking.created_at.desc()).all()
    crowd = Crowd.query.order_by(Crowd.updated_at.desc()).first()
    if not crowd:
        crowd = Crowd(status='Low', count=0)
        db.session.add(crowd)
        db.session.commit()
    
    return render_template('admin.html', bookings=bookings, crowd_status=crowd.status, crowd_count=crowd.count)

@app.route('/update-crowd', methods=['POST'])
@login_required
def update_crowd():
    if current_user.role != 'admin':
        return redirect(url_for('book'))
    
    status = request.form['status']
    crowd = Crowd(status=status, count=0, updated_at=datetime.utcnow())
    db.session.add(crowd)
    db.session.commit()
    
    # Emit real-time crowd update
    socketio.emit('crowd_update', {'status': status, 'count': 0})
    
    # Send email if status is High
    if status == 'High':
        send_crowd_alert()
    
    flash(f'Crowd status updated to {status}')
    return redirect(url_for('admin'))

@app.route('/crowd-status')
def crowd_status():
    crowd = Crowd.query.order_by(Crowd.updated_at.desc()).first()
    if crowd:
        return jsonify({'status': crowd.status, 'count': crowd.count})
    return jsonify({'status': 'Low', 'count': 0})

@app.route('/detect-crowd', methods=['GET', 'POST'])
@login_required
def detect_crowd_route():
    if current_user.role != 'admin':
        return redirect(url_for('book'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join('uploads', filename)
            
            # Create uploads directory if not exists
            os.makedirs('uploads', exist_ok=True)
            
            try:
                file.save(filepath)
                
                # Detect crowd
                count = detect_crowd(filepath)
                status = get_crowd_status(count)
                
                # Save to database
                crowd = Crowd(status=status, count=count, updated_at=datetime.utcnow())
                db.session.add(crowd)
                db.session.commit()
                
                # Emit real-time crowd update
                socketio.emit('crowd_update', {'status': status, 'count': count})
                
                # Send email if status is High
                if status == 'High':
                    send_crowd_alert()
                
                return jsonify({'count': count, 'status': status})
                
            except Exception as e:
                return jsonify({'error': f'Detection failed: {str(e)}'}), 500
            
            finally:
                # Clean up uploaded file if it exists
                if os.path.exists(filepath):
                    os.remove(filepath)
    
    return render_template('detect_crowd.html')

def send_crowd_alert():
    """Send email alert to all pilgrims when crowd status is High"""
    try:
        pilgrims = User.query.filter_by(role='pilgrim').all()
        for pilgrim in pilgrims:
            msg = Message(
                subject='Temple Alert - High Crowd',
                recipients=[pilgrim.email],
                body=f'Dear {pilgrim.name}, please note the temple is currently overcrowded. Estimated wait time is 30 mins.'
            )
            mail.send(msg)
    except Exception as e:
        print(f'Email sending failed: {e}')

@app.route('/crowd')
def crowd():
    return render_template('crowd.html')

@app.route('/pilgrim-dashboard')
@login_required
def pilgrim_dashboard():
    if current_user.role != 'pilgrim':
        return redirect(url_for('admin'))
    return render_template('pilgrim_dashboard.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Migrate database to add count column
        try:
            from sqlalchemy import text
            result = db.session.execute(text("SHOW COLUMNS FROM crowd LIKE 'count'"))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE crowd ADD COLUMN count INT DEFAULT 0"))
                db.session.commit()
                print("Added count column to crowd table")
        except Exception as e:
            print(f"Migration handled: {e}")
        
        # Create admin user if not exists
        if not User.query.filter_by(email='admin@temple.com').first():
            admin = User(
                name='Admin',
                email='admin@temple.com',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
        
        # Create uploads directory
        os.makedirs('uploads', exist_ok=True)
    
    socketio.run(app, debug=True)