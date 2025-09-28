from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, timezone
import os, random, string, json
try:
    from detect import detect_crowd, get_crowd_status
except ImportError:
    def detect_crowd(source): return 0
    def get_crowd_status(count): return 'Low'
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

class Temple(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    capacity = db.Column(db.Integer, default=100)
    opening_time = db.Column(db.String(10), default='06:00')
    closing_time = db.Column(db.String(10), default='20:00')
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    temple_id = db.Column(db.Integer, db.ForeignKey('temple.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(20), nullable=False)
    persons = db.Column(db.Integer, nullable=False)
    confirmation_id = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(20), default='confirmed')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    temple = db.relationship('Temple', backref='bookings')

class Crowd(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    temple_id = db.Column(db.Integer, db.ForeignKey('temple.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Low')
    count = db.Column(db.Integer, default=0)
    accuracy = db.Column(db.Float, default=0.0)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    temple = db.relationship('Temple', backref='crowd_data')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def generate_confirmation_id():
    """Generate unique confirmation ID"""
    return 'TMP' + ''.join(random.choices(string.digits, k=8))

def get_crowd_prediction(temple_id, date_str):
    """Dummy crowd prediction API"""
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    day_of_week = date_obj.weekday()
    
    if day_of_week in [0, 5, 6]:  # Monday, Saturday, Sunday
        crowd_levels = ['Medium', 'High', 'High', 'Medium', 'Low']
    else:
        crowd_levels = ['Low', 'Medium', 'Low', 'Low', 'Medium']
    
    return {
        'morning': crowd_levels[0],
        'afternoon': crowd_levels[1],
        'evening': crowd_levels[2]
    }

def generate_time_slots(temple, crowd_prediction):
    """Generate available time slots based on crowd prediction"""
    base_slots = [
        {'time': '06:00-08:00', 'period': 'morning', 'label': '6:00 AM - 8:00 AM'},
        {'time': '08:00-10:00', 'period': 'morning', 'label': '8:00 AM - 10:00 AM'},
        {'time': '10:00-12:00', 'period': 'morning', 'label': '10:00 AM - 12:00 PM'},
        {'time': '12:00-14:00', 'period': 'afternoon', 'label': '12:00 PM - 2:00 PM'},
        {'time': '14:00-16:00', 'period': 'afternoon', 'label': '2:00 PM - 4:00 PM'},
        {'time': '16:00-18:00', 'period': 'afternoon', 'label': '4:00 PM - 6:00 PM'},
        {'time': '18:00-20:00', 'period': 'evening', 'label': '6:00 PM - 8:00 PM'}
    ]
    
    for slot in base_slots:
        period = slot['period']
        crowd_level = crowd_prediction.get(period, 'Low')
        
        if crowd_level == 'Low':
            slot['available'] = True
            slot['capacity'] = temple.capacity
            slot['crowd_status'] = 'Low'
        elif crowd_level == 'Medium':
            slot['available'] = True
            slot['capacity'] = temple.capacity // 2
            slot['crowd_status'] = 'Medium'
        else:  # High
            slot['available'] = False
            slot['capacity'] = 0
            slot['crowd_status'] = 'High'
    
    return base_slots

def enhanced_detect_crowd(filepath):
    """Enhanced crowd detection with better accuracy"""
    try:
        count = detect_crowd(filepath)
        # Simulate accuracy based on detection confidence
        if count > 0:
            accuracy = min(0.95, 0.7 + (count / 100) * 0.2)  # Higher accuracy for more people
        else:
            accuracy = 0.8  # Base accuracy for empty detection
        return count, round(accuracy, 2)
    except:
        return 0, 0.0

def get_enhanced_crowd_status(count, temple_id):
    """Get crowd status based on temple capacity"""
    temple = Temple.query.get(temple_id)
    if not temple:
        return get_crowd_status(count)
    
    capacity_ratio = count / temple.capacity
    if capacity_ratio < 0.3:
        return 'Low'
    elif capacity_ratio < 0.7:
        return 'Medium'
    else:
        return 'High'

def send_crowd_alert(temple_id=None):
    """Send email alert to pilgrims when crowd status is High"""
    try:
        temple_name = 'the temple'
        if temple_id:
            temple = Temple.query.get(temple_id)
            temple_name = temple.name if temple else 'the temple'
        
        pilgrims = User.query.filter_by(role='pilgrim').all()
        for pilgrim in pilgrims:
            msg = Message(
                subject=f'Temple Alert - High Crowd at {temple_name}',
                recipients=[pilgrim.email],
                body=f'Dear {pilgrim.name}, please note {temple_name} is currently overcrowded. Consider visiting at a different time.'
            )
            mail.send(msg)
    except Exception as e:
        print(f'Email sending failed: {e}')

# Routes
@app.route('/')
def index():
    temples = Temple.query.filter_by(is_active=True).limit(4).all()
    return render_template('index.html', temples=temples)

@app.route('/index')
def old_index():
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

@app.route('/temples')
def temples():
    temples = Temple.query.filter_by(is_active=True).all()
    return render_template('temples.html', temples=temples)

@app.route('/temple/<int:temple_id>')
def temple_detail(temple_id):
    temple = Temple.query.get_or_404(temple_id)
    crowd = Crowd.query.filter_by(temple_id=temple_id).order_by(Crowd.updated_at.desc()).first()
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('temple_detail.html', temple=temple, crowd=crowd, today=today)

@app.route('/book', methods=['GET', 'POST'])
@login_required
def book():
    if current_user.role != 'pilgrim':
        return redirect(url_for('admin'))
    
    temples = Temple.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        temple_id = int(request.form['temple_id'])
        date_str = request.form['date']
        time_slot = request.form['time_slot']
        persons = int(request.form['persons'])
        
        confirmation_id = generate_confirmation_id()
        
        booking = Booking(
            user_id=current_user.id,
            temple_id=temple_id,
            date=datetime.strptime(date_str, '%Y-%m-%d').date(),
            time_slot=time_slot,
            persons=persons,
            confirmation_id=confirmation_id
        )
        db.session.add(booking)
        db.session.commit()
        
        socketio.emit('new_booking', {
            'id': booking.id,
            'user': current_user.name,
            'temple': booking.temple.name,
            'date': date_str,
            'time_slot': time_slot,
            'persons': persons,
            'confirmation_id': confirmation_id
        })
        
        return redirect(url_for('booking_confirmation', booking_id=booking.id))
    
    return render_template('book.html', temples=temples)

@app.route('/booking-confirmation/<int:booking_id>')
@login_required
def booking_confirmation(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash('Unauthorized access')
        return redirect(url_for('my_bookings'))
    return render_template('booking_confirmation.html', booking=booking)

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
    
    bookings = Booking.query.join(User).join(Temple).order_by(Booking.created_at.desc()).limit(20).all()
    temples = Temple.query.all()
    total_bookings = Booking.query.count()
    crowd = Crowd.query.order_by(Crowd.updated_at.desc()).first()
    if not crowd:
        crowd = Crowd(status='Low', count=0)
        db.session.add(crowd)
        db.session.commit()
    
    return render_template('admin.html', bookings=bookings, temples=temples, 
                         total_bookings=total_bookings, crowd_status=crowd.status, crowd_count=crowd.count)

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

@app.route('/update-crowd', methods=['POST'])
@login_required
def update_crowd():
    if current_user.role != 'admin':
        if request.is_json:
            return jsonify({'error': 'Unauthorized'}), 403
        return redirect(url_for('book'))
    
    if request.is_json:
        temple_id = request.json.get('temple_id')
        status = request.json.get('status', 'Low')
        count = int(request.json.get('count', 0))
    else:
        temple_id = request.form.get('temple_id')
        status = request.form.get('status', 'Low')
        count = int(request.form.get('count', 0))
    
    if not temple_id:
        return jsonify({'error': 'Temple ID required'}), 400
    
    crowd = Crowd.query.filter_by(temple_id=temple_id).order_by(Crowd.updated_at.desc()).first()
    if crowd:
        crowd.status = status
        crowd.count = count
        crowd.updated_at = datetime.now(timezone.utc)
    else:
        crowd = Crowd(temple_id=temple_id, status=status, count=count, accuracy=1.0)
        db.session.add(crowd)
    
    db.session.commit()
    socketio.emit('crowd_update', {
        'temple_id': temple_id,
        'status': status,
        'count': count,
        'accuracy': crowd.accuracy
    })
    
    if status == 'High':
        send_crowd_alert(temple_id)
    
    if request.is_json:
        return jsonify({'success': True})
    
    flash(f'Crowd status updated to {status}')
    return redirect(url_for('admin'))

# API Routes
@app.route('/api/temples')
def api_temples():
    temples = Temple.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': t.id, 'name': t.name, 'location': t.location,
        'latitude': t.latitude, 'longitude': t.longitude,
        'capacity': t.capacity, 'image_url': t.image_url
    } for t in temples])

@app.route('/api/book', methods=['POST'])
@login_required
def api_book():
    try:
        data = request.json
        confirmation_id = generate_confirmation_id()
        
        booking = Booking(
            user_id=current_user.id,
            temple_id=data.get('temple_id'),
            date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
            time_slot=data['time_slot'],
            persons=data['persons'],
            confirmation_id=confirmation_id
        )
        db.session.add(booking)
        db.session.commit()
        
        # Emit real-time update
        socketio.emit('new_booking', {
            'id': booking.id,
            'user': current_user.name,
            'date': data['date'],
            'time_slot': data['time_slot'],
            'persons': data['persons'],
            'confirmation_id': confirmation_id
        })
        
        return jsonify({'success': True, 'booking_id': booking.id, 'confirmation_id': confirmation_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/temple/<int:temple_id>/crowd')
def api_temple_crowd(temple_id):
    crowd = Crowd.query.filter_by(temple_id=temple_id).order_by(Crowd.updated_at.desc()).first()
    if crowd:
        return jsonify({'status': crowd.status, 'count': crowd.count, 'accuracy': crowd.accuracy})
    return jsonify({'status': 'Low', 'count': 0, 'accuracy': 0.0})

@app.route('/api/available-slots')
def available_slots():
    temple_id = request.args.get('temple_id')
    date_str = request.args.get('date')
    
    if not temple_id or not date_str:
        return jsonify({'error': 'Missing parameters'}), 400
    
    crowd_prediction = get_crowd_prediction(temple_id, date_str)
    temple = Temple.query.get(temple_id)
    if not temple:
        return jsonify({'error': 'Temple not found'}), 404
    
    slots = generate_time_slots(temple, crowd_prediction)
    return jsonify({'slots': slots, 'crowd_prediction': crowd_prediction})

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

@app.route('/crowd-status')
def crowd_status():
    temple_id = request.args.get('temple_id')
    if temple_id:
        crowd = Crowd.query.filter_by(temple_id=temple_id).order_by(Crowd.updated_at.desc()).first()
    else:
        crowd = Crowd.query.order_by(Crowd.updated_at.desc()).first()
    if crowd:
        return jsonify({'status': crowd.status, 'count': crowd.count, 'accuracy': crowd.accuracy})
    return jsonify({'status': 'Low', 'count': 0, 'accuracy': 0.0})

@app.route('/live-detection/<int:temple_id>')
@login_required
def live_detection(temple_id):
    """Simulate live crowd detection for real-time monitoring"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Simulate real-time detection with random but realistic data
    import random
    temple = Temple.query.get_or_404(temple_id)
    
    # Generate realistic crowd data based on time of day
    hour = datetime.now().hour
    if 6 <= hour <= 10:  # Morning rush
        base_count = random.randint(20, 60)
    elif 11 <= hour <= 14:  # Afternoon
        base_count = random.randint(40, 80)
    elif 17 <= hour <= 20:  # Evening rush
        base_count = random.randint(50, 100)
    else:  # Off hours
        base_count = random.randint(5, 25)
    
    count = min(base_count, temple.capacity)
    accuracy = random.uniform(0.85, 0.98)
    status = get_enhanced_crowd_status(count, temple_id)
    
    # Update database
    crowd = Crowd(
        temple_id=temple_id,
        status=status,
        count=count,
        accuracy=accuracy,
        updated_at=datetime.now(timezone.utc)
    )
    db.session.add(crowd)
    db.session.commit()
    
    # Emit real-time update
    socketio.emit('crowd_update', {
        'temple_id': temple_id,
        'status': status,
        'count': count,
        'accuracy': accuracy
    })
    
    return jsonify({
        'count': count,
        'status': status,
        'accuracy': accuracy,
        'temple_id': temple_id,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/detect-crowd', methods=['GET', 'POST'])
@login_required
def detect_crowd_route():
    if current_user.role != 'admin':
        return redirect(url_for('book'))
    
    temples = Temple.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        temple_id = request.form.get('temple_id')
        
        if file.filename == '' or not temple_id:
            return jsonify({'error': 'File and temple selection required'}), 400
        
        filename = secure_filename(file.filename)
        filepath = os.path.join('uploads', filename)
        os.makedirs('uploads', exist_ok=True)
        
        try:
            file.save(filepath)
            count, accuracy = enhanced_detect_crowd(filepath)
            status = get_enhanced_crowd_status(count, int(temple_id))
            
            crowd = Crowd(
                temple_id=temple_id,
                status=status,
                count=count,
                accuracy=accuracy,
                updated_at=datetime.now(timezone.utc)
            )
            db.session.add(crowd)
            db.session.commit()
            
            socketio.emit('crowd_update', {
                'temple_id': temple_id,
                'status': status,
                'count': count,
                'accuracy': accuracy
            })
            
            if status == 'High':
                send_crowd_alert(temple_id)
            
            return jsonify({
                'count': count,
                'status': status,
                'accuracy': accuracy,
                'temple_id': temple_id
            })
            
        except Exception as e:
            return jsonify({'error': f'Detection failed: {str(e)}'}), 500
        
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
    
    return render_template('detect_crowd.html', temples=temples)

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
        
        # Database migrations
        try:
            result = db.session.execute(text("SHOW COLUMNS FROM crowd LIKE 'temple_id'"))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE crowd ADD COLUMN temple_id INT"))
                db.session.execute(text("ALTER TABLE crowd ADD COLUMN accuracy FLOAT DEFAULT 0.0"))
                db.session.commit()
                print("Added temple-specific crowd columns")
            
            result = db.session.execute(text("SHOW COLUMNS FROM booking LIKE 'temple_id'"))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE booking ADD COLUMN temple_id INT"))
                db.session.execute(text("ALTER TABLE booking ADD COLUMN confirmation_id VARCHAR(20)"))
                db.session.execute(text("ALTER TABLE booking ADD COLUMN status VARCHAR(20) DEFAULT 'confirmed'"))
                db.session.commit()
                print("Added temple booking columns")
            
            result = db.session.execute(text("SHOW COLUMNS FROM temple LIKE 'image_url'"))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE temple ADD COLUMN image_url VARCHAR(500)"))
                db.session.execute(text("ALTER TABLE temple ADD COLUMN latitude FLOAT"))
                db.session.execute(text("ALTER TABLE temple ADD COLUMN longitude FLOAT"))
                db.session.execute(text("ALTER TABLE temple ADD COLUMN description TEXT"))
                db.session.commit()
                print("Added enhanced temple columns")
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
        
        # Create sample temples if not exists
        if not Temple.query.first():
            temples = [
                Temple(name='Somnath Temple', location='Somnath, Gujarat', latitude=20.8880, longitude=70.4017,
                      capacity=150, description='First among the twelve Jyotirlinga shrines of Shiva. Located on the western coast of Gujarat.',
                      image_url='https://media.newindianexpress.com/TNIE%2Fimport%2Fuploads%2Fuser%2Fckeditor_images%2Farticle%2F2018%2F3%2F1%2FSoulfula.jpg'),
                Temple(name='Dwarka Temple', location='Dwarka, Gujarat', latitude=22.2394, longitude=68.9678,
                      capacity=200, description='Sacred city of Lord Krishna, one of the Char Dham pilgrimage sites.',
                      image_url='https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Dwarakadheesh_Temple%2C_2014.jpg/500px-Dwarakadheesh_Temple%2C_2014.jpg'),
                Temple(name='Ambaji Temple', location='Ambaji, Gujarat', latitude=24.2167, longitude=72.8667,
                      capacity=100, description='One of the 51 Shakti Peethas, dedicated to Goddess Amba.',
                      image_url='https://rajmandirhotel.com/wp-content/uploads/2024/02/Ambaji-Temple.webp'),
                Temple(name='Pavagadh Temple', location='Pavagadh, Gujarat', latitude=22.4833, longitude=73.5333,
                      capacity=120, description='Kalika Mata temple atop Pavagadh hill, a UNESCO World Heritage site.',
                      image_url='https://www.pavagadhtemple.in/frontend/img/newtemple.jpg')
            ]
            for temple in temples:
                db.session.add(temple)
            db.session.commit()
            print('Sample temples created')
        else:
            # Update existing temple images
            temples_to_update = [
                ('Somnath Temple', 'https://lh3.googleusercontent.com/p/AF1QipMxqKvVzwAr8wKzDxGzqzqzqzqzqzqzqzqzqzqz=s1360-w1360-h1020'),
                ('Dwarka Temple', 'https://dynamic-media-cdn.tripadvisor.com/media/photo-o/0f/4a/4a/4a/dwarkadhish-temple.jpg?w=1200&h=-1&s=1'),
                ('Ambaji Temple', 'https://rajmandirhotel.com/wp-content/uploads/2024/02/Ambaji-Temple.webp'),
                ('Pavagadh Temple', 'https://www.gujarattourism.com/content/dam/gujrattourism/images/heritage-sites/champaner-pavagadh/Champaner-Pavagadh-Archaeological-Park-Banner.jpg')
            ]
            
            temples_to_update = [
                ('Somnath Temple', 'https://media.newindianexpress.com/TNIE%2Fimport%2Fuploads%2Fuser%2Fckeditor_images%2Farticle%2F2018%2F3%2F1%2FSoulfula.jpg'),
                ('Dwarka Temple', 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Dwarakadheesh_Temple%2C_2014.jpg/500px-Dwarakadheesh_Temple%2C_2014.jpg'),
                ('Ambaji Temple', 'https://rajmandirhotel.com/wp-content/uploads/2024/02/Ambaji-Temple.webp'),
                ('Pavagadh Temple', 'https://www.pavagadhtemple.in/frontend/img/newtemple.jpg')
            ]
            
            for temple_name, image_url in temples_to_update:
                temple = Temple.query.filter_by(name=temple_name).first()
                if temple:
                    temple.image_url = image_url
            db.session.commit()
            print('Temple images updated')
        
        os.makedirs('uploads', exist_ok=True)
    
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)