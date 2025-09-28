-- Core Database Schema for Temple Pilgrimage Management System
CREATE DATABASE IF NOT EXISTS temple_db;
USE temple_db;

-- 1. User Table
CREATE TABLE user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(200) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'pilgrim'
);

-- 2. Temple Table
CREATE TABLE temple (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    location VARCHAR(200) NOT NULL,
    latitude FLOAT,
    longitude FLOAT,
    capacity INT DEFAULT 100,
    opening_time VARCHAR(10) DEFAULT '06:00',
    closing_time VARCHAR(10) DEFAULT '20:00',
    description TEXT,
    image_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE
);

-- 3. Booking Table
CREATE TABLE booking (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    temple_id INT NOT NULL,
    date DATE NOT NULL,
    time_slot VARCHAR(20) NOT NULL,
    persons INT NOT NULL,
    confirmation_id VARCHAR(20) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'confirmed',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (temple_id) REFERENCES temple(id)
);

-- 4. Crowd Table
CREATE TABLE crowd (
    id INT AUTO_INCREMENT PRIMARY KEY,
    temple_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Low',
    count INT DEFAULT 0,
    accuracy FLOAT DEFAULT 0.0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (temple_id) REFERENCES temple(id)
);

-- 5. Prasad Table
CREATE TABLE prasad (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    price FLOAT NOT NULL,
    temple_id INT NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (temple_id) REFERENCES temple(id)
);

-- 6. Pooja Table
CREATE TABLE pooja (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    price FLOAT NOT NULL,
    duration INT DEFAULT 30,
    temple_id INT NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (temple_id) REFERENCES temple(id)
);

-- 7. Order Table
CREATE TABLE `order` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    total_amount FLOAT NOT NULL,
    qr_code VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES booking(id)
);

-- 8. Order Item Table
CREATE TABLE order_item (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    item_type VARCHAR(20) NOT NULL,
    item_id INT NOT NULL,
    quantity INT DEFAULT 1,
    price FLOAT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES `order`(id)
);

-- Sample Data
INSERT INTO user (name, email, password_hash, role) VALUES 
('Admin', 'admin@temple.com', 'pbkdf2:sha256:260000$salt$hash', 'admin');

INSERT INTO temple (name, location, latitude, longitude, capacity, description) VALUES 
('Somnath Temple', 'Somnath, Gujarat', 20.8880, 70.4017, 150, 'First Jyotirlinga shrine'),
('Dwarka Temple', 'Dwarka, Gujarat', 22.2394, 68.9678, 200, 'Sacred city of Krishna'),
('Ambaji Temple', 'Ambaji, Gujarat', 24.2167, 72.8667, 100, 'Shakti Peetha temple'),
('Pavagadh Temple', 'Pavagadh, Gujarat', 22.4833, 73.5333, 120, 'Kalika Mata temple');