# init_db_script.py (in project root or scripts folder)
from src.db import init_db

if __name__ == "__main__":
    init_db()
    print("Database tables created!")
