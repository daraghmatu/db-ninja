import mysql.connector
from mysql.connector import pooling, Error
from config import Config
from werkzeug.security import generate_password_hash

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
        query = "SELECT user_id, username, password_hash, current_level FROM users WHERE username = %s"
        cursor.execute(query, (username,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def get_all_levels():
    """Fetches the release status for all 10 levels."""
    conn = get_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT level_id, name, is_available FROM level ORDER BY level_id")
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    # Test the connection when running this file directly
    db_health_check()