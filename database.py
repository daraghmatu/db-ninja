import mysql.connector
from mysql.connector import pooling, Error
from config import Config
from werkzeug.security import generate_password_hash
import json

# Initialize Connection Pool
# Allows multiple users to query the DB simultaneously more efficiently
try:
    db_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="game_pool",
        pool_size=5, # 5 connections
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        autocommit=True
    )
    print(f"Connection pool created for: {Config.DB_NAME}")
except Error as e:
    print(f"Error creating pool: {e}")
    db_pool = None

def get_connection():
    """Fetches a connection from the pool."""
    if db_pool:
        return db_pool.get_connection()
    return None

def db_health_check():
    """A simple test function to verify the DB is reachable."""
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DATABASE();")
            db_name = cursor.fetchone()
            print(f"Connected to database: {db_name[0]}")
            return True
        except Error as e:
            print(f"Health check failed: {e}")
        finally:
            cursor.close()
            conn.close()
    return False

def verify_enrollment_pin(pin):
    """Checks PIN is correct"""
    conn = get_connection()
    if not conn: return False
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT is_active FROM enrollment_pin WHERE pin_code = %s"
        cursor.execute(query, (pin,))
        result = cursor.fetchone()
        return result and result['is_active']
    finally:
        cursor.close()
        conn.close()

def create_user(username, password):
    """Hash password and insert new usr"""
    conn = get_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        # Hash password
        hashed_pw = generate_password_hash(password)
        
        query = "INSERT INTO users (username, password_hash) VALUES (%s, %s)"
        cursor.execute(query, (username, hashed_pw))
        conn.commit()
        return True
    except Error as e:
        print(f"Error creating user: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_user_by_username(username):
    """Fetch user record for authentication."""
    conn = get_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
                select  u.user_id, u.username, u.password_hash
                from    users u 
                where   username = %s
                """
        cursor.execute(query, (username,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def get_level_map():
    conn = get_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            select  level_id, level_name 
            from    levels
            order by level_id
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        return {row['level_id']: row['level_name'] for row in rows}
    finally:
        cursor.close()
        conn.close()

def get_level_info(level_id):
    conn = get_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            select  level_id, level_name, is_available 
            from    levels 
            where   level_id = %s
        """
        cursor.execute(query, (level_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def get_user_levels(user_id):
    conn = get_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
                select  u.current_level, u.highest_level
                from    users u 
                where   user_id = %s
                """
        cursor.execute(query, (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def get_active_session(user_id):
    conn = get_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT  * 
            FROM    user_session 
            WHERE   user_id = %s 
            AND     is_active = 1
            ORDER BY start_time DESC LIMIT 1
        """
        cursor.execute(query, (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def create_session(user_id, target_level_id):
    level_info = get_level_info(target_level_id)
    if not level_info:
        return None
    
    if not level_info['is_available']:
        return "LOCKED"
    
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        # Pick 6 random questions for level
        q_query = """
            select  *
            from    question 
            where   level_id = %s 
            order by rand() limit 6
            """
        cursor.execute(q_query, (target_level_id,))
        questions = cursor.fetchall()

        # Get the correct answer key
        correct_key = "".join([q['correct_option'] for q in questions]).upper()

        # Serialize the full objects into JSON
        questions_json = json.dumps(questions)

        insert_sql = """
            insert into user_session 
            (user_id, level_id, questions_data, correct_key)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(insert_sql, (user_id, target_level_id, questions_json, correct_key))
        conn.commit()

        # Return the newly created session        
        cursor.execute("select * from user_session where session_id = %s", (cursor.lastrowid,))
        return cursor.fetchone()
        
    finally:
        cursor.close()
        conn.close()

def get_leaderboard(limit=100):
    conn = get_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            select 	username, total_score 
            from 	users 
            order by total_score desc, username 
            limit 	%s
        """
        cursor.execute(query, (limit,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def process_level_win(user_id, session_id, score):
    conn = get_connection()
    if not conn: return []
    conn.start_transaction()

    try:
        cursor = conn.cursor(dictionary=True)
        # Update overall game stats in users table
        query = """
            update  users 
            set     total_score = total_score + %s,
                    highest_level = 
                        CASE 
                            WHEN current_level + 1 > highest_level THEN current_level + 1 
                            ELSE highest_level 
                        END,
                    current_level = current_level + 1
            where   user_id = %s
        """
        cursor.execute(query, (score, user_id))
        
        # Update level stats in user_session table
        query = """
            update  user_session
            set     is_active = 0, 
                    session_score = %s
            where   session_id = %s
        """
        cursor.execute(query, (score, session_id))

        # Commit the transaction
        conn.commit() 
    
    except Error as e:
        print(f"DATABASE ERROR: {e}")
        conn.rollback()

    finally:
        cursor.close()
        conn.close()

def process_level_fail(session_id):
    conn = get_connection()
    if not conn: return []
    conn.start_transaction()
    try:
        cursor = conn.cursor(dictionary=False)
        # Check current no. lives       
        query = """
            select	lives_remaining
            from	user_session
            where	session_id = %s
            for update;
        """
        cursor.execute(query, (session_id,))
        lives = cursor.fetchone()
        if lives[0] == 1:
            # Game Over
            query = """
                update  user_session
                set     is_active = 0, 
                        session_score = 0,
                        lives_remaining = 0
                where   session_id = %s
            """
            cursor.execute(query, (session_id,))

            # Commit the transaction
            conn.commit()

            return True

        else:
            # Dock a life
            query = """
                update  user_session
                set     lives_remaining = lives_remaining - 1
                where   session_id = %s
            """
            cursor.execute(query, (session_id,))

            # Commit the transaction
            conn.commit()

            return False 
    
    except Error as e:
        print(f"DATABASE ERROR: {e}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()
    
if __name__ == "__main__":
    # Test the connection when running this file directly
    db_health_check()