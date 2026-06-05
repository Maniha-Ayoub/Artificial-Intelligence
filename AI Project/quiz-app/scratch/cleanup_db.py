import sqlite3
import os

DB_PATH = r'c:\Users\Maniha\OneDrive\Desktop\AI Project\quiz-app\database\quizora.db'

def cleanup():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM questions WHERE category IN ('Python', 'AI')")
    rows_deleted = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"Successfully deleted {rows_deleted} questions from 'Python' and 'AI' categories.")

if __name__ == '__main__':
    cleanup()
