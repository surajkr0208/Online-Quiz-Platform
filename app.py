from flask import Flask, render_template, request, session, redirect, url_for, jsonify, flash
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
import re
import uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'quizplatform_secret_key_2024'

# ─── Config ───────────────────────────────────────────────────────────────────

ADMIN_PASSWORD = 'admin123'
DATA_DIR       = os.path.join(os.path.dirname(__file__), 'data')
DATA_FILE      = os.path.join(DATA_DIR, 'quizzes.json')
USERS_FILE     = os.path.join(DATA_DIR, 'users.json')
SCORES_FILE    = os.path.join(DATA_DIR, 'scores.json')

# ─── Data Helpers ─────────────────────────────────────────────────────────────

def load_quizzes():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_quizzes(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_users():
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_users(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_scores():
    try:
        with open(SCORES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_scores(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SCORES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')

def build_leaderboard():
    """Aggregate scores into a ranked leaderboard list."""
    scores = load_scores()
    if not scores:
        return []
    # Group by username
    user_data = {}
    for s in scores:
        u = s['username']
        if u not in user_data:
            user_data[u] = {'username': u, 'quizzes': 0, 'total_pct': 0, 'best_pct': 0}
        user_data[u]['quizzes'] += 1
        user_data[u]['total_pct'] += s['percentage']
        user_data[u]['best_pct'] = max(user_data[u]['best_pct'], s['percentage'])
    # Compute average and sort
    board = []
    for u, d in user_data.items():
        avg = round(d['total_pct'] / d['quizzes']) if d['quizzes'] > 0 else 0
        board.append({
            'username': u,
            'avg_score': avg,
            'best_score': d['best_pct'],
            'quizzes': d['quizzes'],
        })
    board.sort(key=lambda x: (-x['avg_score'], -x['quizzes']))
    # Assign ranks and badges
    badges = ['🥇', '🥈', '🥉']
    for i, entry in enumerate(board):
        entry['rank'] = i + 1
        entry['badge'] = badges[i] if i < 3 else '⭐'
    return board

# ─── Jinja2 Globals ────────────────────────────────────────────────────────────
app.jinja_env.globals.update(enumerate=enumerate, load_quizzes=load_quizzes)

# ─── Auth Decorators ──────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user'):
            flash('Please log in to access that page.', 'error')
            return redirect(url_for('user_login', next=request.path))
        return f(*args, **kwargs)
    return decorated

# ─── User Auth Routes ──────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('user'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append('Username can only contain letters, numbers, and underscores.')
        if not email or '@' not in email:
            errors.append('A valid email address is required.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')

        if not errors:
            users = load_users()
            if username.lower() in {k.lower() for k in users}:
                errors.append('That username is already taken.')
            elif email in {u['email'] for u in users.values()}:
                errors.append('An account with that email already exists.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('auth/register.html',
                                   form_data=request.form)

        users = load_users()
        users[username] = {
            'username': username,
            'email': email,
            'password_hash': generate_password_hash(password),
            'created_at': datetime.utcnow().isoformat()
        }
        save_users(users)
        session['user'] = username
        flash(f'Welcome to QuizMaster, {username}! 🎉', 'success')
        return redirect(request.args.get('next') or url_for('index'))

    return render_template('auth/register.html', form_data={})


@app.route('/login', methods=['GET', 'POST'])
def user_login():
    if session.get('user'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        users = load_users()
        user = users.get(username)
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid username or password.', 'error')
            return render_template('auth/login.html', form_data=request.form)
        session['user'] = username
        flash(f'Welcome back, {username}! 👋', 'success')
        return redirect(request.args.get('next') or url_for('index'))
    return render_template('auth/login.html', form_data={})


@app.route('/logout')
def user_logout():
    username = session.pop('user', None)
    if username:
        flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

# ─── Public Routes ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    quizzes = load_quizzes()
    total_questions = sum(len(q['questions']) for q in quizzes.values())
    return render_template('index.html', quizzes=quizzes, total_questions=total_questions)

@app.route('/quiz/<quiz_id>')
def quiz_intro(quiz_id):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        return redirect(url_for('index'))
    return render_template('quiz_intro.html', quiz=quiz)

@app.route('/quiz/<quiz_id>/start')
def start_quiz(quiz_id):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        return redirect(url_for('index'))
    session['quiz_id'] = quiz_id
    session['current_question'] = 0
    session['score'] = 0
    session['answers'] = []
    session['total'] = len(quiz['questions'])
    return redirect(url_for('play_quiz', quiz_id=quiz_id))

@app.route('/quiz/<quiz_id>/play')
def play_quiz(quiz_id):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        return redirect(url_for('index'))
    if session.get('quiz_id') != quiz_id:
        return redirect(url_for('start_quiz', quiz_id=quiz_id))
    current_q_index = session.get('current_question', 0)
    questions = quiz['questions']
    if current_q_index >= len(questions):
        return redirect(url_for('quiz_results', quiz_id=quiz_id))
    question = questions[current_q_index]
    progress = (current_q_index / len(questions)) * 100
    return render_template('play_quiz.html',
                           quiz=quiz, question=question,
                           question_number=current_q_index + 1,
                           total_questions=len(questions),
                           progress=progress)

@app.route('/quiz/<quiz_id>/answer', methods=['POST'])
def submit_answer(quiz_id):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        return jsonify({'error': 'Quiz not found'}), 404
    data = request.get_json()
    selected = data.get('answer')
    current_q_index = session.get('current_question', 0)
    questions = quiz['questions']
    if current_q_index >= len(questions):
        return jsonify({'error': 'No more questions'}), 400
    question = questions[current_q_index]
    correct = question['answer']
    is_correct = selected == correct
    if is_correct:
        session['score'] = session.get('score', 0) + 1
    answers = session.get('answers', [])
    answers.append({
        'question': question['question'],
        'selected': selected,
        'correct': correct,
        'is_correct': is_correct,
        'explanation': question['explanation'],
        'options': question['options']
    })
    session['answers'] = answers
    session['current_question'] = current_q_index + 1
    return jsonify({
        'is_correct': is_correct,
        'correct_answer': correct,
        'explanation': question['explanation'],
        'is_last': (current_q_index + 1) >= len(questions)
    })

@app.route('/quiz/<quiz_id>/results')
def quiz_results(quiz_id):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz or session.get('quiz_id') != quiz_id:
        return redirect(url_for('index'))
    score      = session.get('score', 0)
    total      = session.get('total', len(quiz['questions']))
    answers    = session.get('answers', [])
    percentage = round((score / total) * 100) if total > 0 else 0

    if percentage >= 80:
        grade, grade_color, grade_icon = "Excellent", "#4ade80", "🏆"
        message = "Outstanding performance! You've mastered this topic."
    elif percentage >= 60:
        grade, grade_color, grade_icon = "Good", "#60a5fa", "⭐"
        message = "Great job! A little more practice and you'll be an expert."
    elif percentage >= 40:
        grade, grade_color, grade_icon = "Fair", "#f59e0b", "📚"
        message = "Not bad! Review the topics and try again."
    else:
        grade, grade_color, grade_icon = "Needs Work", "#f87171", "💪"
        message = "Keep practicing! Every expert was once a beginner."

    # ── Save score to leaderboard if user is logged in ──
    score_saved = False
    username = session.get('user')
    if username:
        scores = load_scores()
        scores.append({
            'id':         str(uuid.uuid4()),
            'username':   username,
            'quiz_id':    quiz_id,
            'quiz_title': quiz['title'],
            'score':      score,
            'total':      total,
            'percentage': percentage,
            'timestamp':  datetime.utcnow().isoformat()
        })
        save_scores(scores)
        score_saved = True

    return render_template('results.html', quiz=quiz, score=score, total=total,
                           percentage=percentage, grade=grade, grade_color=grade_color,
                           grade_icon=grade_icon, message=message, answers=answers,
                           score_saved=score_saved)

@app.route('/leaderboard')
def leaderboard():
    board = build_leaderboard()
    current_user = session.get('user')
    return render_template('leaderboard.html', leaders=board, current_user=current_user)

@app.route('/about')
def about():
    return render_template('about.html')

# ─── Admin Auth Routes ─────────────────────────────────────────────────────────

@app.route('/admin')
def admin_root():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('admin_login'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    error = None
    if request.method == 'POST':
        pwd = request.form.get('password', '')
        if pwd == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session.permanent = False
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Incorrect password. Please try again.'
    return render_template('admin/login.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# ─── Admin Dashboard ───────────────────────────────────────────────────────────

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    quizzes = load_quizzes()
    total_questions = sum(len(q['questions']) for q in quizzes.values())
    users  = load_users()
    scores = load_scores()
    return render_template('admin/dashboard.html', quizzes=quizzes,
                           total_questions=total_questions,
                           total_users=len(users),
                           total_attempts=len(scores))

# ─── Admin: Create / Edit Quiz ─────────────────────────────────────────────────

@app.route('/admin/quiz/new', methods=['GET', 'POST'])
@admin_required
def admin_new_quiz():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Quiz title is required.', 'error')
            return render_template('admin/quiz_form.html', quiz=None, action='new')
        quizzes = load_quizzes()
        quiz_id = slugify(title)
        if quiz_id in quizzes:
            quiz_id = quiz_id + '-' + str(uuid.uuid4())[:4]
        new_quiz = {
            'id':                quiz_id,
            'title':             title,
            'description':       request.form.get('description', '').strip(),
            'category':          request.form.get('category', 'General').strip(),
            'difficulty':        request.form.get('difficulty', 'Beginner'),
            'icon':              request.form.get('icon', '📝').strip() or '📝',
            'color':             request.form.get('color', '#6366f1'),
            'time_per_question': int(request.form.get('time_per_question', 30)),
            'questions':         []
        }
        quizzes[quiz_id] = new_quiz
        save_quizzes(quizzes)
        flash(f'Quiz "{title}" created successfully!', 'success')
        return redirect(url_for('admin_quiz_questions', quiz_id=quiz_id))
    return render_template('admin/quiz_form.html', quiz=None, action='new')

@app.route('/admin/quiz/<quiz_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_quiz(quiz_id):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        flash('Quiz not found.', 'error')
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        quiz['title']             = request.form.get('title', quiz['title']).strip()
        quiz['description']       = request.form.get('description', '').strip()
        quiz['category']          = request.form.get('category', '').strip()
        quiz['difficulty']        = request.form.get('difficulty', 'Beginner')
        quiz['icon']              = request.form.get('icon', quiz.get('icon', '📝')).strip() or '📝'
        quiz['color']             = request.form.get('color', '#6366f1')
        quiz['time_per_question'] = int(request.form.get('time_per_question', 30))
        quizzes[quiz_id] = quiz
        save_quizzes(quizzes)
        flash(f'Quiz "{quiz["title"]}" updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/quiz_form.html', quiz=quiz, action='edit')

@app.route('/admin/quiz/<quiz_id>/delete', methods=['POST'])
@admin_required
def admin_delete_quiz(quiz_id):
    quizzes = load_quizzes()
    quiz = quizzes.pop(quiz_id, None)
    if quiz:
        save_quizzes(quizzes)
        flash(f'Quiz "{quiz["title"]}" deleted.', 'success')
    else:
        flash('Quiz not found.', 'error')
    return redirect(url_for('admin_dashboard'))

# ─── Admin: Manage Questions ───────────────────────────────────────────────────

@app.route('/admin/quiz/<quiz_id>/questions')
@admin_required
def admin_quiz_questions(quiz_id):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        flash('Quiz not found.', 'error')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/questions.html', quiz=quiz)

@app.route('/admin/quiz/<quiz_id>/question/add', methods=['GET', 'POST'])
@admin_required
def admin_add_question(quiz_id):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        flash('Quiz not found.', 'error')
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        q_text      = request.form.get('question', '').strip()
        options     = [request.form.get(f'option_{i}', '').strip() for i in range(4)]
        answer      = int(request.form.get('answer', 0))
        explanation = request.form.get('explanation', '').strip()
        errors = []
        if not q_text:             errors.append('Question text is required.')
        if any(not o for o in options): errors.append('All four answer options are required.')
        if not explanation:        errors.append('Explanation is required.')
        if errors:
            for e in errors: flash(e, 'error')
            return render_template('admin/question_form.html', quiz=quiz, question=None,
                                   action='add', form_data=request.form)
        questions = quiz.get('questions', [])
        new_id = max((q['id'] for q in questions), default=0) + 1
        questions.append({'id': new_id, 'question': q_text,
                          'options': options, 'answer': answer, 'explanation': explanation})
        quiz['questions'] = questions
        quizzes[quiz_id] = quiz
        save_quizzes(quizzes)
        flash('Question added successfully!', 'success')
        if request.form.get('add_another'):
            return redirect(url_for('admin_add_question', quiz_id=quiz_id))
        return redirect(url_for('admin_quiz_questions', quiz_id=quiz_id))
    return render_template('admin/question_form.html', quiz=quiz, question=None,
                           action='add', form_data={})

@app.route('/admin/quiz/<quiz_id>/question/<int:q_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_question(quiz_id, q_id):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        flash('Quiz not found.', 'error')
        return redirect(url_for('admin_dashboard'))
    questions = quiz.get('questions', [])
    question  = next((q for q in questions if q['id'] == q_id), None)
    if not question:
        flash('Question not found.', 'error')
        return redirect(url_for('admin_quiz_questions', quiz_id=quiz_id))
    if request.method == 'POST':
        q_text      = request.form.get('question', '').strip()
        options     = [request.form.get(f'option_{i}', '').strip() for i in range(4)]
        answer      = int(request.form.get('answer', 0))
        explanation = request.form.get('explanation', '').strip()
        errors = []
        if not q_text:             errors.append('Question text is required.')
        if any(not o for o in options): errors.append('All four answer options are required.')
        if not explanation:        errors.append('Explanation is required.')
        if errors:
            for e in errors: flash(e, 'error')
            return render_template('admin/question_form.html', quiz=quiz, question=question,
                                   action='edit', form_data=request.form)
        question['question']    = q_text
        question['options']     = options
        question['answer']      = answer
        question['explanation'] = explanation
        quizzes[quiz_id] = quiz
        save_quizzes(quizzes)
        flash('Question updated successfully!', 'success')
        return redirect(url_for('admin_quiz_questions', quiz_id=quiz_id))
    return render_template('admin/question_form.html', quiz=quiz, question=question,
                           action='edit', form_data={})

@app.route('/admin/quiz/<quiz_id>/question/<int:q_id>/delete', methods=['POST'])
@admin_required
def admin_delete_question(quiz_id, q_id):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        flash('Quiz not found.', 'error')
        return redirect(url_for('admin_dashboard'))
    original_len = len(quiz.get('questions', []))
    quiz['questions'] = [q for q in quiz.get('questions', []) if q['id'] != q_id]
    if len(quiz['questions']) < original_len:
        quizzes[quiz_id] = quiz
        save_quizzes(quizzes)
        flash('Question deleted.', 'success')
    else:
        flash('Question not found.', 'error')
    return redirect(url_for('admin_quiz_questions', quiz_id=quiz_id))

# ─── Run ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True, port=5000)
