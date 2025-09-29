-- Complete MySQL Database Schema for Temple Pilgrimage Management System
-- Created for SIH Temple Pilgrim Project

CREATE DATABASE IF NOT EXISTS temple_db;
USE temple_db;

-- =====================================================
-- 1. USER TABLE - Authentication & User Management
-- =====================================================
CREATE TABLE user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(200) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'pilgrim',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_role (role)
);

-- =====================================================
-- 2. TEMPLE TABLE - Temple Information
-- =====================================================
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
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_active (is_active),
    INDEX idx_location (location),
    INDEX idx_name (name)
);

-- =====================================================
-- 3. BOOKING TABLE - Temple Visit Bookings
-- =====================================================
CREATE TABLE booking (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    temple_id INT NOT NULL,
    date DATE NOT NULL,
    time_slot VARCHAR(20) NOT NULL,
    persons INT NOT NULL,
    confirmation_id VARCHAR(20) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    payment_status VARCHAR(20) DEFAULT 'pending',
    transaction_id VARCHAR(50),
    total_amount FLOAT NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (temple_id) REFERENCES temple(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_temple_id (temple_id),
    INDEX idx_date (date),
    INDEX idx_confirmation_id (confirmation_id),
    INDEX idx_status (status),
    INDEX idx_payment_status (payment_status)
);

-- =====================================================
-- 4. CROWD TABLE - AI Crowd Detection Data
-- =====================================================
CREATE TABLE crowd (
    id INT AUTO_INCREMENT PRIMARY KEY,
    temple_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Low',
    count INT DEFAULT 0,
    accuracy FLOAT DEFAULT 0.0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (temple_id) REFERENCES temple(id) ON DELETE CASCADE,
    INDEX idx_temple_id (temple_id),
    INDEX idx_status (status),
    INDEX idx_updated_at (updated_at)
);

-- =====================================================
-- 5. PRASAD TABLE - Temple Offerings
-- =====================================================
CREATE TABLE prasad (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    price FLOAT NOT NULL,
    temple_id INT NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (temple_id) REFERENCES temple(id) ON DELETE CASCADE,
    INDEX idx_temple_id (temple_id),
    INDEX idx_available (is_available)
);

-- =====================================================
-- 6. POOJA TABLE - Special Religious Services
-- =====================================================
CREATE TABLE pooja (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    price FLOAT NOT NULL,
    duration INT DEFAULT 30,
    temple_id INT NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (temple_id) REFERENCES temple(id) ON DELETE CASCADE,
    INDEX idx_temple_id (temple_id),
    INDEX idx_available (is_available)
);

-- =====================================================
-- 7. ORDER TABLE - QR Code Orders for Services
-- =====================================================
CREATE TABLE `order` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    total_amount FLOAT NOT NULL,
    qr_code VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES booking(id) ON DELETE CASCADE,
    INDEX idx_booking_id (booking_id),
    INDEX idx_qr_code (qr_code),
    INDEX idx_status (status)
);

-- =====================================================
-- 8. ORDER_ITEM TABLE - Individual Prasad & Pooja Items
-- =====================================================
CREATE TABLE order_item (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    item_type VARCHAR(20) NOT NULL,
    item_id INT NOT NULL,
    quantity INT DEFAULT 1,
    price FLOAT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES `order`(id) ON DELETE CASCADE,
    INDEX idx_order_id (order_id),
    INDEX idx_item_type (item_type)
);

-- =====================================================
-- SAMPLE DATA INSERTION
-- =====================================================

-- Insert Admin User
INSERT INTO user (name, email, password_hash, role) VALUES 
('Admin', 'admin@temple.com', 'pbkdf2:sha256:260000$salt$hash', 'admin');

-- Insert Sample Temples
INSERT INTO temple (name, location, latitude, longitude, capacity, description, image_url) VALUES 
('Somnath Temple', 'Somnath, Gujarat', 20.8880, 70.4017, 150, 'First among the twelve Jyotirlinga shrines of Shiva.', 'https://example.com/somnath.jpg'),
('Dwarka Temple', 'Dwarka, Gujarat', 22.2394, 68.9678, 200, 'Sacred city of Lord Krishna, one of the Char Dham pilgrimage sites.', 'https://example.com/dwarka.jpg'),
('Ambaji Temple', 'Ambaji, Gujarat', 24.2167, 72.8667, 100, 'One of the 51 Shakti Peethas, dedicated to Goddess Amba.', 'https://example.com/ambaji.jpg'),
('Pavagadh Temple', 'Pavagadh, Gujarat', 22.4833, 73.5333, 120, 'Kalika Mata temple atop Pavagadh hill.', 'https://example.com/pavagadh.jpg');

-- Insert Sample Prasad Items
INSERT INTO prasad (name, price, temple_id) VALUES 
('Laddu', 25, 1), ('Coconut', 15, 1), ('Flowers Garland', 20, 1),
('Modak', 30, 2), ('Tulsi Leaves', 10, 2), ('Butter', 35, 2),
('Chunri', 50, 3), ('Sindoor', 25, 3), ('Coconut', 15, 3),
('Prasad Box', 40, 4), ('Flowers', 20, 4), ('Incense', 15, 4);

-- Insert Sample Pooja Services
INSERT INTO pooja (name, price, duration, temple_id) VALUES 
('Abhishek', 101, 30, 1), ('Aarti', 51, 15, 1), ('Rudrabhishek', 251, 45, 1),
('Mangal Aarti', 75, 20, 2), ('Bhog Offering', 151, 25, 2), ('Krishna Aarti', 101, 30, 2),
('Mata ki Aarti', 101, 30, 3), ('Durga Path', 201, 45, 3), ('Devi Aarti', 75, 20, 3),
('Kalika Aarti', 101, 25, 4), ('Special Pooja', 151, 35, 4);

-- Insert Initial Crowd Status for All Temples
INSERT INTO crowd (temple_id, status, count, accuracy) VALUES 
(1, 'Low', 0, 1.0), (2, 'Low', 0, 1.0), (3, 'Low', 0, 1.0), (4, 'Low', 0, 1.0);

-- =====================================================
-- DATABASE CONSTRAINTS & VALIDATIONS
-- =====================================================
ALTER TABLE booking ADD CONSTRAINT chk_persons CHECK (persons > 0 AND persons <= 10);
ALTER TABLE temple ADD CONSTRAINT chk_capacity CHECK (capacity > 0);
ALTER TABLE prasad ADD CONSTRAINT chk_prasad_price CHECK (price > 0);
ALTER TABLE pooja ADD CONSTRAINT chk_pooja_price CHECK (price > 0);
ALTER TABLE `order` ADD CONSTRAINT chk_order_amount CHECK (total_amount >= 0);

-- =====================================================
-- PERFORMANCE OPTIMIZATION INDEXES
-- =====================================================
CREATE INDEX idx_booking_date_temple ON booking(date, temple_id);
CREATE INDEX idx_order_created_status ON `order`(created_at, status);
CREATE INDEX idx_crowd_temple_updated ON crowd(temple_id, updated_at);
CREATE INDEX idx_user_role_created ON user(role, created_at);

-- =====================================================
-- DATABASE VIEWS FOR ANALYTICS
-- =====================================================

-- Temple Revenue Summary View
CREATE VIEW temple_revenue_summary AS
SELECT 
    t.id,
    t.name AS temple_name,
    COUNT(DISTINCT b.id) AS total_bookings,
    COALESCE(SUM(b.total_amount), 0) AS total_revenue,
    COALESCE(SUM(CASE WHEN b.payment_status = 'completed' THEN b.total_amount ELSE 0 END), 0) AS collected_revenue,
    COALESCE(SUM(CASE WHEN b.payment_status = 'pending' THEN b.total_amount ELSE 0 END), 0) AS pending_revenue
FROM temple t
LEFT JOIN booking b ON t.id = b.temple_id
WHERE t.is_active = TRUE
GROUP BY t.id, t.name;

-- Daily Booking Summary View
CREATE VIEW daily_booking_summary AS
SELECT 
    DATE(b.created_at) AS booking_date,
    t.name AS temple_name,
    COUNT(b.id) AS total_bookings,
    SUM(b.persons) AS total_persons,
    COALESCE(SUM(CASE WHEN b.payment_status = 'completed' THEN b.total_amount ELSE 0 END), 0) AS total_revenue
FROM booking b
JOIN temple t ON b.temple_id = t.id
GROUP BY DATE(b.created_at), t.id, t.name
ORDER BY booking_date DESC;

-- =====================================================
-- STORED PROCEDURES
-- =====================================================

-- Get Temple Statistics Procedure
DELIMITER //
CREATE PROCEDURE GetTempleStats(IN temple_id INT)
BEGIN
    SELECT 
        t.name,
        t.capacity,
        COUNT(DISTINCT b.id) AS total_bookings,
        COUNT(DISTINCT CASE WHEN DATE(b.created_at) = CURDATE() THEN b.id END) AS today_bookings,
        COALESCE(SUM(CASE WHEN b.payment_status = 'completed' THEN b.total_amount ELSE 0 END), 0) AS total_revenue,
        COALESCE(c.status, 'Low') AS current_crowd_status,
        COALESCE(c.count, 0) AS current_crowd_count
    FROM temple t
    LEFT JOIN booking b ON t.id = b.temple_id
    LEFT JOIN crowd c ON t.id = c.temple_id
    WHERE t.id = temple_id
    GROUP BY t.id, t.name, t.capacity, c.status, c.count;
END //
DELIMITER ;

-- Update Crowd Status Procedure
DELIMITER //
CREATE PROCEDURE UpdateCrowdStatus(
    IN temple_id INT, 
    IN new_status VARCHAR(20), 
    IN new_count INT, 
    IN detection_accuracy FLOAT
)
BEGIN
    INSERT INTO crowd (temple_id, status, count, accuracy, updated_at)
    VALUES (temple_id, new_status, new_count, detection_accuracy, NOW())
    ON DUPLICATE KEY UPDATE
        status = new_status,
        count = new_count,
        accuracy = detection_accuracy,
        updated_at = NOW();
END //
DELIMITER ;

-- =====================================================
-- TRIGGERS FOR DATA INTEGRITY
-- =====================================================

-- Auto-update crowd timestamp trigger
DELIMITER //
CREATE TRIGGER crowd_update_timestamp 
BEFORE UPDATE ON crowd
FOR EACH ROW
BEGIN
    SET NEW.updated_at = NOW();
END //
DELIMITER ;

-- =====================================================
-- SUMMARY OF TABLES
-- =====================================================
/*
TABLES CREATED:
1. user - User authentication and roles
2. temple - Temple information and details
3. booking - Darshan bookings with payment info
4. crowd - AI crowd detection data
5. prasad - Temple offerings/prasad items
6. pooja - Special religious services
7. order - QR code orders for services
8. order_item - Individual items in orders

FEATURES SUPPORTED:
- User registration and authentication
- Temple management (CRUD operations)
- Booking system with payment integration
- QR code generation and verification
- Crowd monitoring with AI detection
- Prasad and Pooja service management
- Revenue tracking and analytics
- Real-time crowd status updates
- Admin dashboard with statistics
*/