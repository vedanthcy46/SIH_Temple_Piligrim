-- Temple Pilgrimage Crowd Management System Database Schema (3NF)
-- MySQL Database Schema

CREATE DATABASE IF NOT EXISTS temple_management_system;
USE temple_management_system;

-- Users table (1NF, 2NF, 3NF compliant)
CREATE TABLE user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(15),
    password_hash VARCHAR(200) NOT NULL,
    role ENUM('user', 'admin', 'rescue') NOT NULL DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_role (role)
);

-- Temples table (1NF, 2NF, 3NF compliant)
CREATE TABLE temple (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    location VARCHAR(200) NOT NULL,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    capacity INT DEFAULT 1000,
    opening_time TIME DEFAULT '06:00:00',
    closing_time TIME DEFAULT '20:00:00',
    description TEXT,
    image_url VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_active (is_active),
    INDEX idx_location (latitude, longitude)
);

-- Bookings table (1NF, 2NF, 3NF compliant)
CREATE TABLE booking (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    temple_id INT NOT NULL,
    date DATE NOT NULL,
    time_slot VARCHAR(20) NOT NULL,
    persons INT NOT NULL,
    status ENUM('confirmed', 'cancelled', 'completed') DEFAULT 'confirmed',
    payment_id VARCHAR(100),
    amount DECIMAL(10, 2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (temple_id) REFERENCES temple(id) ON DELETE CASCADE,
    INDEX idx_user_date (user_id, date),
    INDEX idx_temple_date (temple_id, date),
    INDEX idx_status (status)
);

-- Payments table (1NF, 2NF, 3NF compliant)
CREATE TABLE payment (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    payment_method ENUM('upi', 'card', 'wallet', 'cash') DEFAULT 'upi',
    transaction_id VARCHAR(100) UNIQUE,
    gateway_response TEXT,
    status ENUM('pending', 'success', 'failed', 'refunded') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES booking(id) ON DELETE CASCADE,
    INDEX idx_transaction (transaction_id),
    INDEX idx_status (status)
);

-- Crowd Data table (1NF, 2NF, 3NF compliant)
CREATE TABLE crowd_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    temple_id INT NOT NULL,
    zone VARCHAR(50) DEFAULT 'main',
    status ENUM('Low', 'Medium', 'High') NOT NULL DEFAULT 'Low',
    count INT DEFAULT 0,
    ai_confidence DECIMAL(5, 2) DEFAULT 0.00,
    detection_method ENUM('manual', 'ai', 'sensor') DEFAULT 'manual',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (temple_id) REFERENCES temple(id) ON DELETE CASCADE,
    INDEX idx_temple_zone (temple_id, zone),
    INDEX idx_updated (updated_at)
);

-- Incidents table (1NF, 2NF, 3NF compliant)
CREATE TABLE incident (
    id INT AUTO_INCREMENT PRIMARY KEY,
    temple_id INT NOT NULL,
    reported_by INT,
    assigned_to INT,
    type ENUM('medical', 'security', 'crowd', 'fire', 'structural') NOT NULL,
    severity ENUM('low', 'medium', 'high', 'critical') DEFAULT 'medium',
    status ENUM('open', 'assigned', 'in_progress', 'resolved', 'closed') DEFAULT 'open',
    title VARCHAR(200),
    description TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    FOREIGN KEY (temple_id) REFERENCES temple(id) ON DELETE CASCADE,
    FOREIGN KEY (reported_by) REFERENCES user(id) ON DELETE SET NULL,
    FOREIGN KEY (assigned_to) REFERENCES user(id) ON DELETE SET NULL,
    INDEX idx_temple_status (temple_id, status),
    INDEX idx_severity (severity),
    INDEX idx_assigned (assigned_to)
);

-- Notifications table (1NF, 2NF, 3NF compliant)
CREATE TABLE notification (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    temple_id INT,
    type ENUM('booking', 'crowd', 'emergency', 'general') NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (temple_id) REFERENCES temple(id) ON DELETE SET NULL,
    INDEX idx_user_read (user_id, is_read),
    INDEX idx_type (type)
);

-- Audit Log table (1NF, 2NF, 3NF compliant)
CREATE TABLE audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(100) NOT NULL,
    table_name VARCHAR(50) NOT NULL,
    record_id INT,
    old_values JSON,
    new_values JSON,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE SET NULL,
    INDEX idx_user_action (user_id, action),
    INDEX idx_table_record (table_name, record_id)
);

-- Temple Zones table (1NF, 2NF, 3NF compliant)
CREATE TABLE temple_zone (
    id INT AUTO_INCREMENT PRIMARY KEY,
    temple_id INT NOT NULL,
    zone_name VARCHAR(50) NOT NULL,
    capacity INT DEFAULT 100,
    zone_type ENUM('entry', 'exit', 'darshan', 'prasadam', 'parking', 'general') DEFAULT 'general',
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (temple_id) REFERENCES temple(id) ON DELETE CASCADE,
    UNIQUE KEY unique_temple_zone (temple_id, zone_name),
    INDEX idx_temple_type (temple_id, zone_type)
);

-- Festival Calendar table (1NF, 2NF, 3NF compliant)
CREATE TABLE festival_calendar (
    id INT AUTO_INCREMENT PRIMARY KEY,
    temple_id INT,
    festival_name VARCHAR(100) NOT NULL,
    festival_date DATE NOT NULL,
    expected_crowd_multiplier DECIMAL(3, 2) DEFAULT 1.00,
    special_arrangements TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (temple_id) REFERENCES temple(id) ON DELETE SET NULL,
    INDEX idx_temple_date (temple_id, festival_date)
);

-- Sample Data Insertion
INSERT INTO temple (name, location, latitude, longitude, capacity, description, image_url) VALUES
('Somnath Temple', 'Somnath, Gujarat', 20.8880, 70.4017, 2000, 'First Jyotirlinga temple dedicated to Lord Shiva', '/static/images/somnath.jpg'),
('Dwarka Temple', 'Dwarka, Gujarat', 22.2394, 68.9678, 1500, 'Sacred temple of Lord Krishna', '/static/images/dwarka.jpg'),
('Ambaji Temple', 'Ambaji, Gujarat', 24.2167, 72.8667, 1200, 'Famous Shakti Peetha temple', '/static/images/ambaji.jpg'),
('Pavagadh Temple', 'Pavagadh, Gujarat', 22.4833, 73.5333, 800, 'Kalika Mata temple on Pavagadh hill', '/static/images/pavagadh.jpg');

INSERT INTO user (name, email, password_hash, role) VALUES
('System Admin', 'admin@temple.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/RK.PmvlG.', 'admin'),
('Rescue Team Lead', 'rescue@temple.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/RK.PmvlG.', 'rescue'),
('Demo User', 'user@temple.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/RK.PmvlG.', 'user');

INSERT INTO temple_zone (temple_id, zone_name, capacity, zone_type, latitude, longitude) VALUES
(1, 'Main Entry', 200, 'entry', 20.8875, 70.4015),
(1, 'Darshan Hall', 500, 'darshan', 20.8880, 70.4017),
(1, 'Prasadam Counter', 100, 'prasadam', 20.8885, 70.4019),
(1, 'Parking Area', 300, 'parking', 20.8870, 70.4010);

INSERT INTO crowd_data (temple_id, zone, status, count, detection_method) VALUES
(1, 'main', 'Low', 45, 'ai'),
(2, 'main', 'Medium', 120, 'ai'),
(3, 'main', 'Low', 30, 'manual'),
(4, 'main', 'High', 200, 'ai');

INSERT INTO festival_calendar (temple_id, festival_name, festival_date, expected_crowd_multiplier) VALUES
(1, 'Maha Shivratri', '2024-03-08', 3.50),
(2, 'Janmashtami', '2024-08-26', 4.00),
(3, 'Navratri', '2024-10-03', 2.50),
(4, 'Dussehra', '2024-10-12', 2.00);