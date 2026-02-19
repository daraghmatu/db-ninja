from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import Config
import database as db
from werkzeug.security import check_password_hash
import json
import datetime

app = Flask(__name__)
app.config.from_object(Config)

# Ensure the DB is up before starting the server
with app.app_context():
    if not db.db_health_check():
        print("Warning: Database health check failed at startup!")

# Global variables
level_map = db.get_level_map()

# Routes
@app.route('/')
def index():
    """Redirect to login if not authenticated, otherwise dashboard."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        pin = request.form.get('pin')
        username = request.form.get('username')
        password = request.form.get('password')

        if not db.verify_enrollment_pin(pin):
            flash("Invalid or inactive Enrollment PIN.")
            return redirect(url_for('register'))

        if db.create_user(username, password):
            flash("Account created successfully! Please log in.")
            return redirect(url_for('login'))
        else:
            flash("Username already exists")
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = db.get_user_by_username(username)
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        
        flash("Invalid username or password.")
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    
    user_levels = db.get_user_levels(user_id) 
    current_level = user_levels['current_level']
    target_level = user_levels['highest_level'] + 1

    level_name = level_map.get(current_level)
    target_level_name = level_map.get(target_level)     # will return None when target_level = 11
    
    if current_level == 10:
        page_state = "COMPLETE"
    
    else:
        page_state = "ACTIVE"

    # Check sent arg
    arg_state = request.args.get('status')
    if arg_state == 'failed':
        page_state = "FAILED"
        active_game = None

    else:
        active_game = db.get_active_session(user_id)
        
        if arg_state == 'missed':
            page_state = "MISSED"

        if not active_game:
            active_game = db.create_session(user_id, target_level)
            
            if active_game == "LOCKED":
                page_state = "LOCKED"
                active_game = None

    lives = 0
    sid = 0
    questions = []
    if active_game:
        questions = json.loads(active_game['questions_data'])
        lives = active_game['lives_remaining']
        sid = active_game['session_id']

    leaders = db.get_leaderboard()

    return render_template('dashboard.html', 
                           username=session['username'],
                           user_level=current_level,
                           current_level_name=level_name,
                           target_level_name=target_level_name,
                           leaderboard=leaders,
                           questions=questions,
                           page_state=page_state,
                           lives=lives,
                           session_id=sid)

@app.route('/submit', methods=['POST'])
def submit():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_input = request.form.get('submission_key', '').strip().upper()

    game_session = db.get_active_session(user_id)
    if not game_session:
        return redirect(url_for('dashboard'))
    
    if user_input == game_session['correct_key']:
        # Calculate time taken
        start_time = game_session['start_time']
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Calculate Score: (Lives * 100) + (36000 / duration)
        # Use max(1, duration) to ensure never division by zero
        base_score = game_session['lives_remaining'] * 100
        speed_bonus = int(36000 / max(1, duration))
        session_score = base_score + speed_bonus
        
        db.process_level_win(user_id, game_session['session_id'], session_score)
        
        level_name = level_map.get(game_session['level_id'])
        flash(f"STRIKE TRUE! You are now a {level_name}!")
		
    else:
        is_game_over = db.process_level_fail(game_session['session_id'])
        
        if is_game_over:
            return redirect(url_for('dashboard', status='failed'))
        else:
            flash("MISSED! One life lost.")
            return redirect(url_for('dashboard', status='missed'))

    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 3. Main Method
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)