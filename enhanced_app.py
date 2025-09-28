from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit
from flask_mail import Mail, Message
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os, json, random
try:
    from detect import detect_crowd, get_crowd_status
except ImportError:
    def detect_crowd(source): return 0
    def get_crowd_status(count): return 'Low'
from sqlalchemy import text

app = Flask(__name__)
app.config.from_object('config.Config')
app.config['JWT_SECRET_KEY'] = 'temple-jwt-secret'

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")
mail = Mail(app)
jwt = JWTManager(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Enhanced Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='pilgrim')  # pilgrim, admin, rescue
    bookings = db.relationship('Booking', backref='user', lazy=True)

class Temple(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    capacity = db.Column(db.Integer, default=1000)
    opening_time = db.Column(db.Time, default=datetime.strptime('06:00', '%H:%M').time())
    closing_time = db.Column(db.Time, default=datetime.strptime('20:00', '%H:%M').time())
    description = db.Column(db.Text)
    image_url = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)


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

# Additional models can be added later when database is extended

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# API Routes
@app.route('/api/temples')
def api_temples():
    temples = Temple.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': t.id, 'name': t.name, 'location': t.location,
        'latitude': t.latitude, 'longitude': t.longitude,
        'capacity': t.capacity, 'image_url': t.image_url
    } for t in temples])

@app.route('/api/temple/<int:temple_id>/crowd')
def api_temple_crowd(temple_id):
    crowd = Crowd.query.order_by(Crowd.updated_at.desc()).first()
    if crowd:
        return jsonify({'status': crowd.status, 'count': crowd.count})
    return jsonify({'status': 'Low', 'count': 0})

@app.route('/api/book', methods=['POST'])
@login_required
def api_book():
    data = request.json
    booking = Booking(
        user_id=current_user.id,
        date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
        time_slot=data['time_slot'],
        persons=data['persons']
    )
    db.session.add(booking)
    db.session.commit()
    
    # Emit real-time update
    socketio.emit('new_booking', {
        'id': booking.id,
        'user': current_user.name,
        'date': data['date'],
        'time_slot': data['time_slot'],
        'persons': data['persons']
    })
    
    return jsonify({'success': True, 'booking_id': booking.id})

# Enhanced Routes
@app.route('/')
def index():
    # Create sample temples if none exist
    if not Temple.query.first():
        temples_data = [
            {'name': 'Somnath Temple', 'location': 'Somnath, Gujarat', 'lat': 20.8880, 'lng': 70.4017},
            {'name': 'Dwarka Temple', 'location': 'Dwarka, Gujarat', 'lat': 22.2394, 'lng': 68.9678},
            {'name': 'Ambaji Temple', 'location': 'Ambaji, Gujarat', 'lat': 24.2167, 'lng': 72.8667},
            {'name': 'Pavagadh Temple', 'location': 'Pavagadh, Gujarat', 'lat': 22.4833, 'lng': 73.5333}
        ]
        for t in temples_data:
            temple = Temple(name=t['name'], location=t['location'], latitude=t['lat'], longitude=t['lng'])
            db.session.add(temple)
        db.session.commit()
    
    temples = Temple.query.filter_by(is_active=True).limit(4).all()
    return render_template('enhanced_index.html', temples=temples)

@app.route('/temples')
def temples():
    temples = Temple.query.filter_by(is_active=True).all()
    return render_template('temples.html', temples=temples)

@app.route('/temple/<int:temple_id>')
def temple_detail(temple_id):
    temple = Temple.query.get_or_404(temple_id)
    crowd = Crowd.query.order_by(Crowd.updated_at.desc()).first()
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('temple_detail.html', temple=temple, crowd=crowd, today=today)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    temples = Temple.query.all()
    bookings = Booking.query.order_by(Booking.created_at.desc()).limit(10).all()
    total_users = User.query.filter_by(role='pilgrim').count()
    total_bookings = Booking.query.count()
    
    return render_template('admin_dashboard.html', 
                         temples=temples, bookings=bookings,
                         total_users=total_users, total_bookings=total_bookings)

# Rescue and incident management routes can be added when database is extended

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'rescue_dashboard' if user.role == 'rescue' else 'index'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return render_template('register.html')
        
        user = User(name=name, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/my-bookings')
@login_required
def my_bookings():
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()
    return render_template('my_bookings.html', bookings=bookings)

@app.route('/crowd-status')
def crowd_status():
    crowd = Crowd.query.order_by(Crowd.updated_at.desc()).first()
    if crowd:
        return jsonify({'status': crowd.status, 'count': crowd.count})
    return jsonify({'status': 'Low', 'count': 0})

@app.route('/update-crowd', methods=['POST'])
@login_required
def update_crowd():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    status = request.form.get('status', 'Low')
    count = int(request.form.get('count', 0))
    
    crowd = Crowd.query.first()
    if crowd:
        crowd.status = status
        crowd.count = count
        crowd.updated_at = datetime.utcnow()
    else:
        crowd = Crowd(status=status, count=count)
        db.session.add(crowd)
    
    db.session.commit()
    socketio.emit('crowd_update', {'status': status, 'count': count})
    return jsonify({'success': True})

# Chatbot API
@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    data = request.json
    message = data.get('message', '').lower()
    
    responses = {
        'booking': 'To book a darshan slot, select your temple, choose date and time, then proceed with payment.',
        'crowd': 'Current crowd status is updated in real-time. Check the temple page for live updates.',
        'payment': 'We accept UPI, cards, and digital wallets. All payments are secure and encrypted.',
        'timings': 'Most temples are open from 6:00 AM to 8:00 PM. Check individual temple pages for specific timings.',
        'cancel': 'You can cancel bookings up to 2 hours before your slot time for a full refund.'
    }
    
    for key, response in responses.items():
        if key in message:
            return jsonify({'response': response})
    
    return jsonify({'response': 'I can help you with bookings, crowd status, payments, timings, and cancellations. What would you like to know?'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create sample data
        if not Temple.query.first():
            temples = [
                Temple(name='Somnath Temple', location='Somnath, Gujarat', latitude=20.8880, longitude=70.4017, 
                      description='First Jyotirlinga temple', image_url='/static/images/somnath.jpg'),
                Temple(name='Dwarka Temple', location='Dwarka, Gujarat', latitude=22.2394, longitude=68.9678,
                      description='Krishna temple', image_url='/static/images/dwarka.jpg'),
                Temple(name='Ambaji Temple', location='Ambaji, Gujarat', latitude=24.2167, longitude=72.8667,
                      description='Shakti Peetha temple', image_url='/static/images/ambaji.jpg'),
                Temple(name='Pavagadh Temple', location='Pavagadh, Gujarat', latitude=22.4833, longitude=73.5333,
                      description='Kalika Mata temple', image_url='/static/images/pavagadh.jpg')
            ]
            for temple in temples:
                db.session.add(temple)
            
            # Create admin user if not exists
            if not User.query.filter_by(email='admin@temple.com').first():
                admin = User(name='Admin', email='admin@temple.com', 
                            password_hash=generate_password_hash('admin123'), role='admin')
                db.session.add(admin)
            
            if not User.query.filter_by(email='rescue@temple.com').first():
                rescue = User(name='Rescue Team', email='rescue@temple.com',
                             password_hash=generate_password_hash('rescue123'), role='rescue')
                db.session.add(rescue)
            db.session.commit()
    
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)