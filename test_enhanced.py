#!/usr/bin/env python3
"""
Test script for Enhanced Temple Management System
"""
import requests
import json

BASE_URL = 'http://localhost:5000'

def test_api_endpoints():
    """Test basic API endpoints"""
    print("Testing Enhanced Temple Management System...")
    
    # Test temples API
    try:
        response = requests.get(f'{BASE_URL}/api/temples')
        if response.status_code == 200:
            temples = response.json()
            print(f"✓ Temples API working - Found {len(temples)} temples")
        else:
            print(f"✗ Temples API failed - Status: {response.status_code}")
    except Exception as e:
        print(f"✗ Temples API error: {e}")
    
    # Test crowd status API
    try:
        response = requests.get(f'{BASE_URL}/crowd-status')
        if response.status_code == 200:
            crowd = response.json()
            print(f"✓ Crowd API working - Status: {crowd['status']}, Count: {crowd['count']}")
        else:
            print(f"✗ Crowd API failed - Status: {response.status_code}")
    except Exception as e:
        print(f"✗ Crowd API error: {e}")
    
    # Test chatbot API
    try:
        response = requests.post(f'{BASE_URL}/api/chatbot', 
                               json={'message': 'booking help'})
        if response.status_code == 200:
            bot_response = response.json()
            print(f"✓ Chatbot API working - Response: {bot_response['response'][:50]}...")
        else:
            print(f"✗ Chatbot API failed - Status: {response.status_code}")
    except Exception as e:
        print(f"✗ Chatbot API error: {e}")

def test_web_pages():
    """Test web page accessibility"""
    pages = ['/', '/temples', '/login', '/register']
    
    for page in pages:
        try:
            response = requests.get(f'{BASE_URL}{page}')
            if response.status_code == 200:
                print(f"✓ Page {page} accessible")
            else:
                print(f"✗ Page {page} failed - Status: {response.status_code}")
        except Exception as e:
            print(f"✗ Page {page} error: {e}")

if __name__ == '__main__':
    print("Enhanced Temple Management System Test")
    print("=" * 50)
    print("Make sure the server is running with: python enhanced_app.py")
    print()
    
    test_api_endpoints()
    print()
    test_web_pages()
    print()
    print("Test completed!")