import os

# Flask configuration
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-key-please-change-in-production')

# RFID configuration
RFID_PORT = os.environ.get('RFID_PORT', '/dev/ttyUSB0')
RFID_BAUDRATE = int(os.environ.get('RFID_BAUDRATE', '9600'))

# Database configuration
DATABASE_PATH = os.environ.get('DATABASE_PATH', 'rfid_time_tracker.db')

# Debug configuration
ENABLE_TIMER_DEBUG = os.environ.get('ENABLE_TIMER_DEBUG', 'False').lower() == 'true' 