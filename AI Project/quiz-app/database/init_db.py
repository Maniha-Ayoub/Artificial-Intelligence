import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'quizora.db')

def init_db():
    print(f"Initializing database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Drop existing tables
    c.execute('DROP TABLE IF EXISTS users')
    c.execute('DROP TABLE IF EXISTS exams')
    c.execute('DROP TABLE IF EXISTS questions')
    c.execute('DROP TABLE IF EXISTS quiz_results')
    c.execute('DROP TABLE IF EXISTS badges')
    c.execute('DROP TABLE IF EXISTS user_badges')

    # Create users table
    c.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            points INTEGER DEFAULT 0,
            current_streak INTEGER DEFAULT 0,
            longest_streak INTEGER DEFAULT 0,
            last_quiz_date DATE
        )
    ''')

    # Create exams table
    c.execute('''
        CREATE TABLE exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            total_marks INTEGER NOT NULL,
            passing_marks INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create questions table
    c.execute('''
        CREATE TABLE questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            category TEXT NOT NULL,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            difficulty_level TEXT DEFAULT 'Medium',
            FOREIGN KEY(exam_id) REFERENCES exams(id)
        )
    ''')

    # Create quiz_results table
    c.execute('''
        CREATE TABLE quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exam_id INTEGER,
            type TEXT DEFAULT 'learning', 
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            category TEXT NOT NULL,
            ai_feedback TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(exam_id) REFERENCES exams(id)
        )
    ''')

    # Create badges table
    c.execute('''
        CREATE TABLE badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            icon_path TEXT
        )
    ''')

    # Create user_badges table
    c.execute('''
        CREATE TABLE user_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_id INTEGER NOT NULL,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(badge_id) REFERENCES badges(id)
        )
    ''')

    # Insert default badges
    badges = [
        ('First Steps', 'Completed your first quiz!', 'fa-shoe-prints'),
        ('Quick Learner', 'Scored 100% on a quiz.', 'fa-bolt'),
        ('Steady Scholar', 'Maintained a 3-day streak.', 'fa-fire'),
        ('Knowledge Seeker', 'Uploaded and completed a PDF quiz.', 'fa-book'),
        ('Master Mind', 'Passed a formal exam with 90% or higher.', 'fa-brain')
    ]
    c.executemany('INSERT INTO badges (name, description, icon_path) VALUES (?, ?, ?)', badges)

    # Insert default admin user
    admin_pw = generate_password_hash('mn909')
    c.execute('INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)',
              ('Admin', 'manihaayoub9@gmail.com', admin_pw, 'admin'))
              
    # Insert default student user
    student_pw = generate_password_hash('student123')
    c.execute('INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)',
              ('Student User', 'student@quizora.com', student_pw, 'student'))

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == '__main__':
    init_db()
