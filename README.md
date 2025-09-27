# Temple Pilgrimage Crowd Management System

Flask web application for managing temple visits and crowd control.

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. MySQL Database Setup
```sql
CREATE DATABASE temple_db;
```

### 3. Configure Database
Update `config.py` with your MySQL credentials:
- MYSQL_HOST (default: localhost)
- MYSQL_USER (default: root)
- MYSQL_PASSWORD (default: password)
- MYSQL_DB (default: temple_db)

### 4. Run Application
```bash
python app.py
```

## Features

### Pilgrim Features
- Register/Login
- Book temple visit slots
- View personal bookings
- Check live crowd status

### Admin Features
- View all bookings
- Update crowd status
- Dashboard with statistics

## Default Admin Account
- Email: admin@temple.com
- Password: admin123

## API Endpoints
- `/crowd-status` - Returns current crowd status as JSON
- `/update-crowd` - Admin endpoint to update crowd status

## Database Tables
- `user` - User accounts (pilgrims and admins)
- `booking` - Temple visit bookings
- `crowd` - Current crowd status