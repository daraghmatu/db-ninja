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
            session['current_level'] = user['current_level']
            session['level_name'] = user['level_name']
            return redirect(url_for('dashboard'))
        
        flash("Invalid username or password.")
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    current_level = session['current_level']
    next_level = session['current_level'] + 1 

    game_session = db.get_active_session(user_id)

    if not game_session:
        game_session = db.create_session(user_id, next_level)

    questions = json.loads(game_session['questions_data'])

    leaders = db.get_leaderboard()

    return render_template('dashboard.html', 
                           username=session['username'],
                           user_level=current_level,
                           leaderboard=leaders,
                           questions=questions,
                           lives=game_session['lives_remaining'],
                           session_id=game_session['session_id'])

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
        
        # Calculate Score: (Lives * 100) + (3600 / duration)
        # Use max(1, duration) to ensure never division by zero
        base_score = game_session['lives_remaining'] * 100
        speed_bonus = int(3600 / max(1, duration))
        session_score = base_score + speed_bonus
        
        db.process_level_win(user_id, game_session['session_id'], session_score)
        
        flash(f"STRIKE TRUE! You are now a {session.get('level_name')}!")
		
    else:
        is_game_over = db.process_level_fail(user_id, game_session['session_id'])
        
        if is_game_over:
            flash("GAME OVER. Your journey ends here.")
            return redirect(url_for('game_over'))
        else:
            flash("MISSED! One life lost.")

    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 3. Main Method
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)