import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'temple-management-secret-key'
    
    # MySQL Configuration
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'root'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or 'vrvedanth46'
    MYSQL_DB = os.environ.get('MYSQL_DB') or 'temple_db'
    
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Mail Configuration
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'vedanthh46@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'zcfrdrpgxalygkrp'
    MAIL_DEFAULT_SENDER = 'piligrim@temple.com'