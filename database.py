import mysql.connector
from mysql.connector import pooling, Error
from config import Config

# Initialize Connection Pool
# Allows multiple users to query the DB simultaneously more efficiently
try:
    db_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="game_pool",
        pool_size=5, # Start with 5 connections
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

if __name__ == "__main__":
    # Test the connection when running this file directly
    db_health_check()