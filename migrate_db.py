from app import app, db
from sqlalchemy import text

def migrate_database():
    """Add count column to crowd table"""
    with app.app_context():
        try:
            # Check if count column exists
            result = db.session.execute(text("SHOW COLUMNS FROM crowd LIKE 'count'"))
            if not result.fetchone():
                # Add count column
                db.session.execute(text("ALTER TABLE crowd ADD COLUMN count INT DEFAULT 0"))
                db.session.commit()
                print("Added count column to crowd table")
            else:
                print("Count column already exists")
        except Exception as e:
            print(f"Migration error: {e}")
            db.session.rollback()

if __name__ == '__main__':
    migrate_database()