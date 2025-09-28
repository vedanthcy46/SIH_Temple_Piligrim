#!/usr/bin/env python3
"""
Run the enhanced Temple Management System
Make sure to run this file instead of app.py to see the new features
"""

from enhanced_app import app, socketio

if __name__ == '__main__':
    print("🕉️ Starting Enhanced Temple Management System...")
    print("📍 Features: Temple Selection + Leaflet Maps + Dynamic Crowd Overlay")
    print("🌐 Access at: http://localhost:5000")
    print("=" * 60)
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)