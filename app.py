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

class Prasad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    temple_id = db.Column(db.Integer, db.ForeignKey('temple.id'), nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    temple = db.relationship('Temple', backref='prasads')

class Pooja(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    duration = db.Column(db.Integer, default=30)  # minutes
    temple_id = db.Column(db.Integer, db.ForeignKey('temple.id'), nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    temple = db.relationship('Temple', backref='poojas')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    qr_code = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, collected
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    booking = db.relationship('Booking', backref='orders')

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    item_type = db.Column(db.String(20), nullable=False)  # prasad, pooja
    item_id = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)
    order = db.relationship('Order', backref='items')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def generate_confirmation_id():
    """Generate unique confirmation ID"""
    return 'TMP' + ''.join(random.choices(string.digits, k=8))

def generate_qr_code():
    """Generate unique QR code for orders"""
    return 'QR' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

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

def send_booking_confirmation_email(booking, qr_code, order_amount):
    """Send booking confirmation email with QR code"""
    try:
        temple = booking.temple
        user = booking.user
        
        # Get order items if any
        prasad_items = []
        pooja_items = []
        
        if qr_code:
            order = Order.query.filter_by(qr_code=qr_code).first()
            if order:
                for item in order.items:
                    if item.item_type == 'prasad':
                        prasad = Prasad.query.get(item.item_id)
                        if prasad:
                            prasad_items.append(f'{prasad.name} x{item.quantity} - ₹{item.price}')
                    elif item.item_type == 'pooja':
                        pooja = Pooja.query.get(item.item_id)
                        if pooja:
                            pooja_items.append(f'{pooja.name} ({pooja.duration}min) - ₹{item.price}')
        
        # Create email content
        email_body = f"""Dear {user.name},

Your temple booking has been confirmed! 🙏

📍 Temple: {temple.name}
📅 Date: {booking.date.strftime('%d %B %Y')}
⏰ Time Slot: {booking.time_slot}
👥 Number of People: {booking.persons}
🎫 Booking ID: {booking.id}
🔖 Confirmation ID: {booking.confirmation_id}

💰 Darshan Fee: ₹{booking.persons * 50}"""
        
        # Always include QR code section with image URL
        qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={qr_code}"
        email_body += f"\n\n📱 Your QR Code: {qr_code}"
        email_body += f"\n\n🖼️ QR Code Image: {qr_image_url}"
        email_body += "\n\n⚡ IMPORTANT: Show this QR code at temple entrance for verification!"
        email_body += "\n(You can scan the QR code image above or show this email to temple staff)"
        
        if prasad_items or pooja_items:
            email_body += f"\n\n🛍️ Pre-booked Services (₹{order_amount}):"
            if prasad_items:
                email_body += "\n\n📦 Prasad Items:"
                for item in prasad_items:
                    email_body += f"\n• {item}"
            if pooja_items:
                email_body += "\n\n🕯️ Pooja Services:"
                for item in pooja_items:
                    email_body += f"\n• {item}"
            email_body += "\n\n⚡ Show QR code at Pre-booked Collection counter for services!"
        else:
            email_body += "\n\n🙏 This QR code is for darshan entry verification."
        
        email_body += f"""\n\n📋 Instructions:
1. Arrive at {temple.name} on {booking.date.strftime('%d %B %Y')}
2. Report to the temple between {booking.time_slot}
3. Show this email and QR code (if applicable) for verification
4. Enjoy your divine darshan! 🙏

🏛️ Temple Timings: {temple.opening_time or '6:00 AM'} - {temple.closing_time or '8:00 PM'}
📍 Location: {temple.location}

Thank you for choosing Divine Darshan!

Blessings,
Temple Management Team"""
        
        # Create HTML version with embedded QR code image
        html_body = email_body.replace('\n', '<br>').replace(f'QR Code Image: {qr_image_url}', f'<br><img src="{qr_image_url}" alt="QR Code" style="width:200px;height:200px;"><br>')
        
        msg = Message(
            subject=f'🕉️ Booking Confirmed - {temple.name} | {booking.confirmation_id}',
            recipients=[user.email],
            body=email_body,
            html=html_body
        )
        mail.send(msg)
        
    except Exception as e:
        print(f'Booking confirmation email failed: {e}')

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
    prasads = Prasad.query.filter_by(temple_id=temple_id, is_available=True).all()
    poojas = Pooja.query.filter_by(temple_id=temple_id, is_available=True).all()
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('temple_detail.html', temple=temple, crowd=crowd, prasads=prasads, poojas=poojas, today=today)

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
        db.session.flush()  # Get booking ID
        
        # Process prasad and pooja orders if any
        total_order_amount = 0
        order_items = []
        
        if 'prasads' in data and data['prasads']:
            for prasad_data in data['prasads']:
                prasad = Prasad.query.get(prasad_data['id'])
                if prasad:
                    quantity = prasad_data['quantity']
                    total_order_amount += prasad.price * quantity
                    order_items.append({
                        'type': 'prasad',
                        'id': prasad.id,
                        'quantity': quantity,
                        'price': prasad.price * quantity
                    })
        
        if 'poojas' in data and data['poojas']:
            for pooja_data in data['poojas']:
                pooja = Pooja.query.get(pooja_data['id'])
                if pooja:
                    total_order_amount += pooja.price
                    order_items.append({
                        'type': 'pooja',
                        'id': pooja.id,
                        'quantity': 1,
                        'price': pooja.price
                    })
        
        # Always create order with QR code for every booking
        qr_code = generate_qr_code()
        order = Order(
            booking_id=booking.id,
            total_amount=total_order_amount,
            qr_code=qr_code
        )
        db.session.add(order)
        db.session.flush()
        
        # Add order items if any
        for item in order_items:
            order_item = OrderItem(
                order_id=order.id,
                item_type=item['type'],
                item_id=item['id'],
                quantity=item['quantity'],
                price=item['price']
            )
            db.session.add(order_item)
        
        db.session.commit()
        
        # Send confirmation email with QR code
        try:
            send_booking_confirmation_email(booking, qr_code, total_order_amount)
        except Exception as e:
            print(f'Email sending failed: {e}')
        
        # Emit real-time update
        socketio.emit('new_booking', {
            'id': booking.id,
            'user': current_user.name,
            'date': data['date'],
            'time_slot': data['time_slot'],
            'persons': data['persons'],
            'confirmation_id': confirmation_id,
            'order_amount': total_order_amount,
            'qr_code': qr_code
        })
        
        return jsonify({
            'success': True,
            'booking_id': booking.id,
            'confirmation_id': confirmation_id,
            'qr_code': qr_code,
            'order_amount': total_order_amount if total_order_amount > 0 else 0
        })
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

@app.route('/qr-scan')
@login_required
def qr_scan():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    return render_template('qr_scan.html')

@app.route('/api/verify-qr', methods=['POST'])
@login_required
def verify_qr():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    qr_code = request.json.get('qr_code')
    if not qr_code:
        return jsonify({'error': 'QR code is required'}), 400
    
    print(f'Verifying QR code: {qr_code}')  # Debug log
    
    order = Order.query.filter_by(qr_code=qr_code).first()
    
    if not order:
        print(f'QR code not found: {qr_code}')  # Debug log
        return jsonify({'error': 'Invalid QR code'}), 404
    
    if order.status == 'collected':
        return jsonify({'error': 'Order already collected'}), 400
    
    # Get order details
    prasads = []
    poojas = []
    
    for item in order.items:
        if item.item_type == 'prasad':
            prasad = Prasad.query.get(item.item_id)
            if prasad:
                prasads.append({
                    'name': prasad.name,
                    'quantity': item.quantity,
                    'price': item.price
                })
        elif item.item_type == 'pooja':
            pooja = Pooja.query.get(item.item_id)
            if pooja:
                poojas.append({
                    'name': pooja.name,
                    'duration': pooja.duration,
                    'price': item.price
                })
    
    print(f'QR verification successful for order: {order.id}')  # Debug log
    
    return jsonify({
        'success': True,
        'order_id': order.id,
        'booking_id': order.booking_id,
        'user_name': order.booking.user.name,
        'temple_name': order.booking.temple.name,
        'booking_date': order.booking.date.strftime('%d %B %Y'),
        'time_slot': order.booking.time_slot,
        'persons': order.booking.persons,
        'total_amount': order.total_amount,
        'darshan_fee': order.booking.persons * 50,
        'prasads': prasads,
        'poojas': poojas,
        'status': order.status
    })

@app.route('/api/collect-order', methods=['POST'])
@login_required
def collect_order():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    order_id = request.json.get('order_id')
    order = Order.query.get(order_id)
    
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    order.status = 'collected'
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Order marked as collected'})

@app.route('/pilgrim-dashboard')
@login_required
def pilgrim_dashboard():
    if current_user.role != 'pilgrim':
        return redirect(url_for('admin'))
    return render_template('pilgrim_dashboard.html')

@app.route('/temple-dashboard')
@login_required
def temple_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    temples = Temple.query.filter_by(is_active=True).all()
    today = datetime.now().date()
    
    # Today's bookings
    today_bookings = Booking.query.filter(
        db.func.date(Booking.created_at) == today
    ).join(Temple).join(User).all()
    
    # Today's orders with QR codes
    today_orders = Order.query.join(Booking).filter(
        db.func.date(Booking.created_at) == today
    ).all()
    
    # Revenue stats
    today_revenue = db.session.query(db.func.sum(Order.total_amount)).join(Booking).filter(
        db.func.date(Booking.created_at) == today
    ).scalar() or 0
    
    pending_orders = Order.query.filter_by(status='pending').count()
    collected_orders = Order.query.filter_by(status='collected').count()
    
    return render_template('temple_dashboard.html', 
                         temples=temples, today_bookings=today_bookings, 
                         today_orders=today_orders, today_revenue=today_revenue,
                         pending_orders=pending_orders, collected_orders=collected_orders)

@app.route('/camera-scanner')
@login_required
def camera_scanner():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    return render_template('camera_scanner.html')

@app.route('/admin/prasad-pooja')
@login_required
def manage_prasad_pooja():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    temples = Temple.query.filter_by(is_active=True).all()
    prasads = Prasad.query.join(Temple).all()
    poojas = Pooja.query.join(Temple).all()
    
    # Revenue statistics
    total_revenue = db.session.query(db.func.sum(Order.total_amount)).scalar() or 0
    prasad_revenue = db.session.query(db.func.sum(OrderItem.price)).filter(OrderItem.item_type == 'prasad').scalar() or 0
    pooja_revenue = db.session.query(db.func.sum(OrderItem.price)).filter(OrderItem.item_type == 'pooja').scalar() or 0
    
    return render_template('manage_prasad_pooja.html', 
                         temples=temples, prasads=prasads, poojas=poojas,
                         total_revenue=total_revenue, prasad_revenue=prasad_revenue, pooja_revenue=pooja_revenue)

@app.route('/api/prasad', methods=['POST', 'PUT', 'DELETE'])
@login_required
def manage_prasad_api():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    if request.method == 'POST':
        data = request.json
        prasad = Prasad(
            name=data['name'],
            price=float(data['price']),
            temple_id=int(data['temple_id'])
        )
        db.session.add(prasad)
        db.session.commit()
        return jsonify({'success': True, 'id': prasad.id})
    
    elif request.method == 'PUT':
        data = request.json
        prasad = Prasad.query.get(data['id'])
        if prasad:
            prasad.name = data['name']
            prasad.price = float(data['price'])
            prasad.is_available = data.get('is_available', True)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'error': 'Prasad not found'}), 404
    
    elif request.method == 'DELETE':
        prasad_id = request.json.get('id')
        prasad = Prasad.query.get(prasad_id)
        if prasad:
            db.session.delete(prasad)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'error': 'Prasad not found'}), 404

@app.route('/api/pooja', methods=['POST', 'PUT', 'DELETE'])
@login_required
def manage_pooja_api():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    if request.method == 'POST':
        data = request.json
        pooja = Pooja(
            name=data['name'],
            price=float(data['price']),
            duration=int(data['duration']),
            temple_id=int(data['temple_id'])
        )
        db.session.add(pooja)
        db.session.commit()
        return jsonify({'success': True, 'id': pooja.id})
    
    elif request.method == 'PUT':
        data = request.json
        pooja = Pooja.query.get(data['id'])
        if pooja:
            pooja.name = data['name']
            pooja.price = float(data['price'])
            pooja.duration = int(data['duration'])
            pooja.is_available = data.get('is_available', True)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'error': 'Pooja not found'}), 404
    
    elif request.method == 'DELETE':
        pooja_id = request.json.get('id')
        pooja = Pooja.query.get(pooja_id)
        if pooja:
            db.session.delete(pooja)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'error': 'Pooja not found'}), 404

@app.route('/api/revenue-stats')
@login_required
def revenue_stats():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Daily revenue
    today = datetime.now().date()
    daily_revenue = db.session.query(db.func.sum(Order.total_amount)).filter(
        db.func.date(Order.created_at) == today
    ).scalar() or 0
    
    # Monthly revenue
    month_start = today.replace(day=1)
    monthly_revenue = db.session.query(db.func.sum(Order.total_amount)).filter(
        Order.created_at >= month_start
    ).scalar() or 0
    
    # Total bookings today
    daily_bookings = Booking.query.filter(
        db.func.date(Booking.created_at) == today
    ).count()
    
    return jsonify({
        'daily_revenue': daily_revenue,
        'monthly_revenue': monthly_revenue,
        'daily_bookings': daily_bookings
    })

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
            
            # Add prasad and pooja tables
            try:
                db.session.execute(text("SELECT 1 FROM prasad LIMIT 1"))
            except:
                db.session.execute(text("""
                    CREATE TABLE prasad (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        price FLOAT NOT NULL,
                        temple_id INT NOT NULL,
                        is_available BOOLEAN DEFAULT TRUE
                    )
                """))
                db.session.execute(text("""
                    CREATE TABLE pooja (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        price FLOAT NOT NULL,
                        duration INT DEFAULT 30,
                        temple_id INT NOT NULL,
                        is_available BOOLEAN DEFAULT TRUE
                    )
                """))
                db.session.execute(text("""
                    CREATE TABLE `order` (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        booking_id INT NOT NULL,
                        total_amount FLOAT NOT NULL,
                        qr_code VARCHAR(100) UNIQUE NOT NULL,
                        status VARCHAR(20) DEFAULT 'pending',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                db.session.execute(text("""
                    CREATE TABLE order_item (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        order_id INT NOT NULL,
                        item_type VARCHAR(20) NOT NULL,
                        item_id INT NOT NULL,
                        quantity INT DEFAULT 1,
                        price FLOAT NOT NULL
                    )
                """))
                db.session.commit()
                print("Added prasad and pooja tables")
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
            
            # Add sample prasads and poojas for all temples
            prasads = [
                # Somnath Temple (ID: 1)
                Prasad(name='Laddu', price=25, temple_id=1),
                Prasad(name='Coconut', price=15, temple_id=1),
                Prasad(name='Flowers Garland', price=20, temple_id=1),
                # Dwarka Temple (ID: 2)
                Prasad(name='Modak', price=30, temple_id=2),
                Prasad(name='Tulsi Leaves', price=10, temple_id=2),
                Prasad(name='Butter', price=35, temple_id=2),
                # Ambaji Temple (ID: 3)
                Prasad(name='Chunri', price=50, temple_id=3),
                Prasad(name='Sindoor', price=25, temple_id=3),
                Prasad(name='Coconut', price=15, temple_id=3),
                # Pavagadh Temple (ID: 4)
                Prasad(name='Prasad Box', price=40, temple_id=4),
                Prasad(name='Flowers', price=20, temple_id=4),
                Prasad(name='Incense', price=15, temple_id=4)
            ]
            
            poojas = [
                # Somnath Temple (ID: 1)
                Pooja(name='Abhishek', price=101, duration=30, temple_id=1),
                Pooja(name='Aarti', price=51, duration=15, temple_id=1),
                Pooja(name='Rudrabhishek', price=251, duration=45, temple_id=1),
                # Dwarka Temple (ID: 2)
                Pooja(name='Mangal Aarti', price=75, duration=20, temple_id=2),
                Pooja(name='Bhog Offering', price=151, duration=25, temple_id=2),
                Pooja(name='Krishna Aarti', price=101, duration=30, temple_id=2),
                # Ambaji Temple (ID: 3)
                Pooja(name='Mata ki Aarti', price=101, duration=30, temple_id=3),
                Pooja(name='Durga Path', price=201, duration=45, temple_id=3),
                Pooja(name='Devi Aarti', price=75, duration=20, temple_id=3),
                # Pavagadh Temple (ID: 4)
                Pooja(name='Kalika Aarti', price=101, duration=25, temple_id=4),
                Pooja(name='Special Pooja', price=151, duration=35, temple_id=4)
            ]
            
            for prasad in prasads:
                db.session.add(prasad)
            for pooja in poojas:
                db.session.add(pooja)
            
            db.session.commit()
            print('Sample temples, prasads, and poojas created')
        else:
            # Add prasad and pooja data if not exists
            if not Prasad.query.first():
                # Get actual temple IDs
                temples = Temple.query.all()
                if len(temples) >= 4:
                    temple_ids = [t.id for t in temples[:4]]
                    
                    prasads = [
                        # First Temple
                        Prasad(name='Laddu', price=25, temple_id=temple_ids[0]),
                        Prasad(name='Coconut', price=15, temple_id=temple_ids[0]),
                        Prasad(name='Flowers Garland', price=20, temple_id=temple_ids[0]),
                        # Second Temple
                        Prasad(name='Modak', price=30, temple_id=temple_ids[1]),
                        Prasad(name='Tulsi Leaves', price=10, temple_id=temple_ids[1]),
                        Prasad(name='Butter', price=35, temple_id=temple_ids[1]),
                        # Third Temple
                        Prasad(name='Chunri', price=50, temple_id=temple_ids[2]),
                        Prasad(name='Sindoor', price=25, temple_id=temple_ids[2]),
                        Prasad(name='Coconut', price=15, temple_id=temple_ids[2]),
                        # Fourth Temple
                        Prasad(name='Prasad Box', price=40, temple_id=temple_ids[3]),
                        Prasad(name='Flowers', price=20, temple_id=temple_ids[3]),
                        Prasad(name='Incense', price=15, temple_id=temple_ids[3])
                    ]
                    
                    poojas = [
                        # First Temple
                        Pooja(name='Abhishek', price=101, duration=30, temple_id=temple_ids[0]),
                        Pooja(name='Aarti', price=51, duration=15, temple_id=temple_ids[0]),
                        Pooja(name='Rudrabhishek', price=251, duration=45, temple_id=temple_ids[0]),
                        # Second Temple
                        Pooja(name='Mangal Aarti', price=75, duration=20, temple_id=temple_ids[1]),
                        Pooja(name='Bhog Offering', price=151, duration=25, temple_id=temple_ids[1]),
                        Pooja(name='Krishna Aarti', price=101, duration=30, temple_id=temple_ids[1]),
                        # Third Temple
                        Pooja(name='Mata ki Aarti', price=101, duration=30, temple_id=temple_ids[2]),
                        Pooja(name='Durga Path', price=201, duration=45, temple_id=temple_ids[2]),
                        Pooja(name='Devi Aarti', price=75, duration=20, temple_id=temple_ids[2]),
                        # Fourth Temple
                        Pooja(name='Kalika Aarti', price=101, duration=25, temple_id=temple_ids[3]),
                        Pooja(name='Special Pooja', price=151, duration=35, temple_id=temple_ids[3])
                    ]
                    
                    for prasad in prasads:
                        db.session.add(prasad)
                    for pooja in poojas:
                        db.session.add(pooja)
                    
                    db.session.commit()
                    print('Prasad and Pooja data added')
                else:
                    print('Not enough temples found to add prasad/pooja data')
        
        os.makedirs('uploads', exist_ok=True)
    
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)