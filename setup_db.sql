-- MySQL Database Setup for Temple Management System

CREATE DATABASE IF NOT EXISTS temple_db;
USE temple_db;

-- Create tables will be handled by SQLAlchemy
-- This file is for reference and manual setup if needed

-- Users table structure (created by SQLAlchemy)
-- CREATE TABLE user (
--     id INT AUTO_INCREMENT PRIMARY KEY,
--     name VARCHAR(100) NOT NULL,
--     email VARCHAR(100) UNIQUE NOT NULL,
--     password_hash VARCHAR(200) NOT NULL,
--     role VARCHAR(20) NOT NULL DEFAULT 'pilgrim'
-- );

-- Bookings table structure (created by SQLAlchemy)
-- CREATE TABLE booking (
--     id INT AUTO_INCREMENT PRIMARY KEY,
--     user_id INT NOT NULL,
--     date DATE NOT NULL,
--     time_slot VARCHAR(20) NOT NULL,
--     persons INT NOT NULL,
--     created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
--     FOREIGN KEY (user_id) REFERENCES user(id)
-- );

-- Crowd table structure (created by SQLAlchemy)
-- CREATE TABLE crowd (
--     id INT AUTO_INCREMENT PRIMARY KEY,
--     status VARCHAR(20) NOT NULL DEFAULT 'Low',
--     updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
-- );