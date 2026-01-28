from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import Config
import database as db
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.config.from_object(Config)

# Ensure the DB is up before starting the server
'''@app.before_first_request
def check_db():
    if not db.db_health_check():
        print("Warning: Database health check failed at startup!")
'''
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
    
    levels = db.get_all_levels() 
    
    progress = session.get('current_level', 1)

    return render_template('dashboard.html', 
                           username=session['username'], 
                           user_level=progress, 
                           levels=levels)

@app.route('/game/<int:level_id>')
def game(level_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    
    level_info = db.get_level_info(level_id)
    if not level_info or not level_info['is_available'] or level_id > (session['current_level']+1):
        flash("Level currently locked!")
        return redirect(url_for('dashboard'))

    game_session = db.get_or_create_session(user_id, level_id)
    if not game_session:
        flash("Could not start session. Is the level open?")
        return redirect(url_for('dashboard'))

    question_data = db.get_current_question(game_session['session_id'])

    leaderboard = db.get_leaderboard()

    return render_template('game.html', 
                           question_num=game_session['current_question_index'] + 1,
                           lives=game_session['lives_remaining'],
                           level_id=level_id,
                           session_id=game_session['session_id'],
                           question=question_data,
                           leaderboard=leaderboard)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 3. Main Method
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)