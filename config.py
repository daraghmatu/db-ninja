import os
from dotenv import load_dotenv

# Load variables from .env into the environment
load_dotenv()

class Config:
    """Base configuration."""
    # Database Settings
    DB_HOST = os.getenv('DB_HOST')
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME')

    # Flask Settings
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
    
    # This checks if we actually loaded the required DB info
    @staticmethod
    def validate():
        missing = [k for k, v in {
            "DB_USER": Config.DB_USER,
            "DB_PASSWORD": Config.DB_PASSWORD,
            "DB_NAME": Config.DB_NAME
        }.items() if v is None]
        
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")

# Test the config
if __name__ == "__main__":
    try:
        Config.validate()
        print("Configuration loaded successfully.")
    except ValueError as e:
        print(f"Configuration error: {e}")