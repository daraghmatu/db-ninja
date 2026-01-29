import mysql.connector
from mysql.connector import pooling, Error
from config import Config
from werkzeug.security import generate_password_hash
import json
import random

# Initialize Connection Pool
# Allows multiple users to query the DB simultaneously more efficiently
try:
    db_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="game_pool",
        pool_size=5, # 5 connections
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME
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
                select  u.user_id, u.username, u.password_hash, u.current_level, l.name as level_name 
                from    users u 
                inner join level l 
                where   current_level = l.level_id 
                and     username = %s
                """
        cursor.execute(query, (username,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def get_all_levels():
    """Fetches the release status for all 10 levels."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
                select  level_id, name, is_available 
                from    level 
                where   level_id > 0 
                order by level_id
                """
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_level_info(level_id):
    conn = get_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            select  level_id, name, is_available 
            from    level 
            where   level_id = %s
        """
        cursor.execute(query, (level_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def get_or_create_session(user_id, level_id):
    level_info = get_level_info(level_id)
    if not level_info or not level_info['is_available']:
        print(f"Access Denied: Level not open.")
        return None
    
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Check if active session for this user and level
        query = """
                select  * 
                from    user_session 
                where   user_id = %s 
                and     level_id = %s 
                and     is_active = 1
                """
        cursor.execute(query, (user_id, level_id))
        existing_session = cursor.fetchone()
        
        if existing_session:
            return existing_session

        # Pick 6 random questions if no current session
        # get questions for level
        q_query = """
            select  *
            from    question 
            where   level_id = %s 
            order by rand() limit 6
            """
        cursor.execute(q_query, (level_id,))
        questions = cursor.fetchall()

        # Serialize the full objects into JSON
        questions_json = json.dumps(questions)

        insert_sql = """
            insert into user_session 
            (user_id, level_id, questions_data, current_question_index, lives_remaining, is_active)
            VALUES (%s, %s, %s, 0, 3, 1)
        """
        cursor.execute(insert_sql, (user_id, level_id, questions_json))
        conn.commit()

        # Return the newly created session        
        cursor.execute("select * from user_session where session_id = %s", (cursor.lastrowid,))
        return cursor.fetchone()
        
    finally:
        cursor.close()
        conn.close()

def get_leaderboard(limit=10):
    """Calculates total scores for the top players"""
    conn = get_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT username, total_score FROM users ORDER BY total_score DESC LIMIT %s
        """
        cursor.execute(query, (limit,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    # Test the connection when running this file directly
    db_health_check()