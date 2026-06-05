from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from ai_logic import (
    generate_personalized_feedback, 
    determine_next_difficulty, 
    generate_dynamic_question, 
    generate_batch_questions,
    generate_questions_from_text,
    generate_hint,
    generate_explanation
)
import pypdf
import io
import base64
from datetime import datetime, date, timedelta

load_dotenv()

app = Flask(__name__, 
            template_folder='../frontend/templates',
            static_folder='../frontend/static')

app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_secret_key")
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), '../database/quizora.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def update_gamification(user_id, score, total, quiz_type, category):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if not user:
        conn.close()
        return []

    points_earned = score * 10
    new_points = (user['points'] or 0) + points_earned
    
    # Streak logic
    today = date.today()
    last_date_str = user['last_quiz_date']
    current_streak = user['current_streak'] or 0
    longest_streak = user['longest_streak'] or 0
    
    if last_date_str:
        try:
            last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
        except:
            last_date = None
            
        if last_date == today:
            pass
        elif last_date == today - timedelta(days=1):
            current_streak += 1
        else:
            current_streak = 1
    else:
        current_streak = 1
        
    if current_streak > longest_streak:
        longest_streak = current_streak
        
    conn.execute('''
        UPDATE users SET points = ?, current_streak = ?, longest_streak = ?, last_quiz_date = ?
        WHERE id = ?
    ''', (new_points, current_streak, longest_streak, today.isoformat(), user_id))
    
    # Badge check
    new_badges = []
    
    def award_badge(badge_name):
        badge = conn.execute('SELECT id FROM badges WHERE name = ?', (badge_name,)).fetchone()
        if badge:
            exists = conn.execute('SELECT id FROM user_badges WHERE user_id = ? AND badge_id = ?', (user_id, badge['id'])).fetchone()
            if not exists:
                conn.execute('INSERT INTO user_badges (user_id, badge_id) VALUES (?, ?)', (user_id, badge['id']))
                new_badges.append(badge_name)

    award_badge('First Steps')
    if score == total and total > 0:
        award_badge('Quick Learner')
    if current_streak >= 3:
        award_badge('Steady Scholar')
    
    if quiz_type == 'exam' and score/total >= 0.9 if total > 0 else False:
        award_badge('Master Mind')
        
    conn.commit()
    conn.close()
    return new_badges

# --- HTML ROUTES ---

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
            
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    db_categories = conn.execute('SELECT DISTINCT category FROM questions WHERE exam_id IS NULL').fetchall()
    exams = conn.execute('SELECT * FROM exams ORDER BY id DESC').fetchall()
    conn.close()
    
    category_list = [row['category'] for row in db_categories]
    exams_list = [dict(row) for row in exams]
        
    return render_template('dashboard.html', name=session.get('user_name', 'Student'), role=session.get('role', 'student'), categories=category_list, exams=exams_list)

@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    return render_template('admin_dashboard.html', name=session.get('user_name', 'Admin'))

@app.route('/manage_exams')
def manage_exams_page():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    return render_template('manage_exams.html')

@app.route('/student_records')
def student_records_page():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    return render_template('student_records.html')

@app.route('/manage_questions')
def manage_questions_page():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    conn = get_db_connection()
    questions = conn.execute('SELECT * FROM questions ORDER BY id DESC').fetchall()
    exams = conn.execute('SELECT * FROM exams ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('manage_questions.html', questions=questions, exams=exams)

@app.route('/quiz')
def quiz():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    session['asked_questions'] = []
    return render_template('quiz.html')

@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('settings.html', name=session.get('user_name'), role=session.get('role'))

@app.route('/exam/<int:exam_id>')
def exam(exam_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    conn = get_db_connection()
    exam_data = conn.execute('SELECT * FROM exams WHERE id = ?', (exam_id,)).fetchone()
    conn.close()
    if not exam_data:
        return redirect(url_for('dashboard'))
    return render_template('exam.html', exam=dict(exam_data))

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    if session.get('role') == 'admin':
        # Admin only sees Exam history as per requirements
        results = conn.execute('''
            SELECT quiz_results.id, users.name, quiz_results.score, quiz_results.total, quiz_results.category, quiz_results.date, quiz_results.type
            FROM quiz_results 
            JOIN users ON quiz_results.user_id = users.id 
            WHERE quiz_results.type = 'exam'
            ORDER BY quiz_results.date DESC
        ''').fetchall()
    else:
        results = conn.execute('''
            SELECT quiz_results.id, users.name, quiz_results.score, quiz_results.total, quiz_results.category, quiz_results.date, quiz_results.type
            FROM quiz_results 
            JOIN users ON quiz_results.user_id = users.id 
            WHERE quiz_results.user_id = ?
            ORDER BY quiz_results.date DESC
        ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('history.html', results=results)

# --- API ROUTES ---

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    
    if not name or not email or not password:
        return jsonify({"success": False, "error": "All fields required"}), 400
        
    hashed_pw = generate_password_hash(password)
    
    conn = get_db_connection()
    try:
        cursor = conn.execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)', (name, email, hashed_pw))
        conn.commit()
        session['user_id'] = cursor.lastrowid
        session['user_name'] = name
        session['role'] = 'student'
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Email already exists"}), 400
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    
    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['role'] = user['role']
        return jsonify({"success": True, "role": user['role']})
    else:
        return jsonify({"success": False, "error": "Invalid email or password"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True})

# --- EXAM ENDPOINTS ---
@app.route('/api/exams', methods=['GET', 'POST'])
def manage_exams():
    conn = get_db_connection()
    if request.method == 'POST':
        if session.get('role') != 'admin':
            return jsonify({"error": "Unauthorized"}), 403
        data = request.json
        conn.execute(
            'INSERT INTO exams (title, category, duration_minutes, total_marks, passing_marks) VALUES (?, ?, ?, ?, ?)',
            (data['title'], data['category'], data['duration_minutes'], data['total_marks'], data['passing_marks'])
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    else:
        exams = conn.execute('SELECT * FROM exams ORDER BY id DESC').fetchall()
        conn.close()
        return jsonify([dict(row) for row in exams])

@app.route('/api/exams/<int:exam_id>', methods=['DELETE'])
def delete_exam(exam_id):
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db_connection()
    conn.execute('DELETE FROM exams WHERE id = ?', (exam_id,))
    conn.execute('DELETE FROM questions WHERE exam_id = ?', (exam_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/exams/<int:exam_id>/questions', methods=['GET'])
def get_exam_questions(exam_id):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db_connection()
    questions = conn.execute('SELECT * FROM questions WHERE exam_id = ?', (exam_id,)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in questions])

# --- QUESTIONS ENDPOINTS ---
@app.route('/api/questions', methods=['GET'])
def get_questions():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    category = request.args.get('category', 'Python')
    difficulty = request.args.get('difficulty', 'Easy')
    
    asked_qs = session.get('asked_questions', [])
    
    conn = get_db_connection()
    db_questions = conn.execute(
        'SELECT * FROM questions WHERE category = ? AND difficulty_level = ? AND exam_id IS NULL', 
        (category, difficulty)
    ).fetchall()
    conn.close()
    
    available_db_qs = [q for q in db_questions if q['question'] not in asked_qs]
    
    if available_db_qs:
        import random
        selected_q = dict(random.choice(available_db_qs))
        asked_qs.append(selected_q['question'])
        session['asked_questions'] = asked_qs
        session.modified = True
        return jsonify(selected_q)
        
    ai_q = generate_dynamic_question(category, difficulty, asked_qs)
    if ai_q:
        asked_qs.append(ai_q['question'])
        session['asked_questions'] = asked_qs
        session.modified = True
        return jsonify(ai_q)
    
    return jsonify({"error": "Failed to generate AI question or out of questions."}), 500

@app.route('/api/generate_quiz_from_pdf', methods=['POST'])
def generate_quiz_from_pdf():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if file and file.filename.endswith('.pdf'):
        try:
            pdf_reader = pypdf.PdfReader(io.BytesIO(file.read()))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            if not text.strip():
                return jsonify({"error": "Could not extract text from PDF."}), 400
            
            category = os.path.splitext(file.filename)[0]
            import random
            question_count = random.choice([10, 15, 20])
            result = generate_questions_from_text(text, question_count)
            
            if isinstance(result, dict) and 'error' in result:
                return jsonify({"error": f"AI Error: {result['error']}"}), 500
            
            questions = result
            if not questions:
                return jsonify({"error": "Failed to generate questions. AI returned empty response."}), 500
                
            conn = get_db_connection()
            for q in questions:
                conn.execute(
                    '''INSERT INTO questions (category, question, option_a, option_b, option_c, option_d, correct_answer, difficulty_level) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (category, q.get('question'), q.get('option_a'), q.get('option_b'), q.get('option_c'), q.get('option_d'), q.get('correct_answer'), q.get('difficulty', 'Easy'))
                )
            conn.commit()
            conn.close()
            
            return jsonify({"success": True, "category": category})
            
        except Exception as e:
            return jsonify({"error": f"Error processing PDF: {str(e)}"}), 500
    else:
        return jsonify({"error": "Only PDF files are supported."}), 400


@app.route('/api/submit', methods=['POST'])
def submit_quiz():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    score = data.get('score', 0)
    total = data.get('total', 0)
    category = data.get('category', 'General')
    details = data.get('details', '')
    exam_id = data.get('exam_id')
    quiz_type = data.get('type', 'learning')
    
    user_id = session.get('user_id')
    
    ai_feedback = ""
    if quiz_type == 'learning':
        ai_feedback = generate_personalized_feedback(score, total, category, details)
    else:
        # In exam mode, we can provide formal feedback
        ai_feedback = f"Exam Completed. You scored {score}/{total}. "
        if score >= data.get('passing_marks', 0):
            ai_feedback += "Status: PASS"
        else:
            ai_feedback += "Status: FAIL"
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO quiz_results (user_id, exam_id, type, score, total, category, ai_feedback) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (user_id, exam_id, quiz_type, score, total, category, ai_feedback)
    )
    conn.commit()
    conn.close()
    
    new_badges = update_gamification(user_id, score, total, quiz_type, category)
    
    session['asked_questions'] = []
    
    return jsonify({
        "success": True,
        "score": score,
        "total": total,
        "ai_feedback": ai_feedback,
        "new_badges": new_badges
    })

@app.route('/api/proctoring_log', methods=['POST'])
def proctoring_log():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    # Here you could save cheating attempts to the DB. For now, just logging.
    print(f"PROCTORING ALERT - User {session['user_id']} during Exam {data.get('exam_id')}: {data.get('violation')}")
    return jsonify({"success": True})

@app.route('/api/next_difficulty', methods=['POST'])
def get_next_difficulty():
    data = request.json
    current_difficulty = data.get('current_difficulty', 'Easy')
    is_correct = data.get('is_correct', False)
    
    next_diff = determine_next_difficulty(current_difficulty, is_correct)
    return jsonify({"next_difficulty": next_diff})

@app.route('/api/hint', methods=['POST'])
def get_hint():
    data = request.json
    question = data.get('question')
    options = data.get('options')
    
    hint = generate_hint(question, options)
    return jsonify({"hint": hint})

@app.route('/api/explanation', methods=['POST'])
def get_explanation():
    data = request.json
    question = data.get('question')
    correct_answer = data.get('correct_answer')
    selected_answer = data.get('selected_answer')
    options_map = data.get('options_map')
    
    explanation = generate_explanation(question, correct_answer, selected_answer, options_map)
    return jsonify({"explanation": explanation})

@app.route('/api/history/clear_all', methods=['DELETE'])
def clear_all_history():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_db_connection()
    if session.get('role') == 'admin':
        conn.execute('DELETE FROM quiz_results')
    else:
        conn.execute('DELETE FROM quiz_results WHERE user_id = ?', (session['user_id'],))
        
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/history/<int:id>', methods=['DELETE'])
def delete_history_item(id):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_db_connection()
    if session.get('role') == 'admin':
        conn.execute('DELETE FROM quiz_results WHERE id = ?', (id,))
    else:
        # Check ownership
        record = conn.execute('SELECT user_id FROM quiz_results WHERE id = ?', (id,)).fetchone()
        if not record or record['user_id'] != session['user_id']:
            conn.close()
            return jsonify({"error": "Unauthorized"}), 403
        conn.execute('DELETE FROM quiz_results WHERE id = ?', (id,))
        
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    new_name = data.get('name')
    new_email = data.get('email')
    new_password = data.get('password')
    
    conn = get_db_connection()
    try:
        if new_password:
            hashed_pw = generate_password_hash(new_password)
            conn.execute('UPDATE users SET name = ?, email = ?, password = ? WHERE id = ?', (new_name, new_email, hashed_pw, session['user_id']))
        else:
            conn.execute('UPDATE users SET name = ?, email = ? WHERE id = ?', (new_name, new_email, session['user_id']))
        
        conn.commit()
        session['user_name'] = new_name
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Email already exists"}), 400
    finally:
        conn.close()

@app.route('/api/manage_questions', methods=['POST'])
def add_question():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
        
    data = request.json
    conn = get_db_connection()
    conn.execute(
        '''INSERT INTO questions (exam_id, category, question, option_a, option_b, option_c, option_d, correct_answer, difficulty_level) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (data.get('exam_id'), data['category'], data['question'], data['option_a'], data['option_b'], data['option_c'], data['option_d'], data['correct_answer'], data['difficulty'])
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/manage_questions/<int:id>', methods=['DELETE'])
def delete_question(id):
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db_connection()
    conn.execute('DELETE FROM questions WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/student_records', methods=['GET'])
def get_student_records():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
        
    conn = get_db_connection()
    # Average and count only for EXAMS as per requirements
    records = conn.execute('''
        SELECT users.id, users.name, users.email, 
               COUNT(CASE WHEN quiz_results.type = 'exam' THEN quiz_results.id END) as quizzes_taken, 
               AVG(CASE WHEN quiz_results.type = 'exam' THEN quiz_results.score END) as avg_score
        FROM users
        LEFT JOIN quiz_results ON users.id = quiz_results.user_id
        WHERE users.role = 'student'
        GROUP BY users.id
    ''').fetchall()
    conn.close()
    return jsonify([dict(row) for row in records])

@app.route('/api/delete_category', methods=['DELETE'])
def delete_category():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    category = request.args.get('category')
    if not category:
        return jsonify({"error": "Category required"}), 400
        
    conn = get_db_connection()
    # Delete learning materials (non-exam questions) for this category
    conn.execute('DELETE FROM questions WHERE category = ? AND exam_id IS NULL', (category,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    conn = get_db_connection()
    users = conn.execute('''
        SELECT name, points, current_streak, longest_streak 
        FROM users 
        WHERE role = 'student'
        ORDER BY points DESC 
        LIMIT 10
    ''').fetchall()
    conn.close()
    return jsonify([dict(row) for row in users])

@app.route('/api/user_stats', methods=['GET'])
def get_user_stats():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    user = conn.execute('SELECT points, current_streak, longest_streak FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    badges = conn.execute('''
        SELECT b.name, b.description, b.icon_path 
        FROM badges b
        JOIN user_badges ub ON b.id = ub.badge_id
        WHERE ub.user_id = ?
    ''', (session['user_id'],)).fetchall()
    conn.close()
    
    return jsonify({
        "stats": dict(user) if user else {},
        "badges": [dict(b) for b in badges]
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
