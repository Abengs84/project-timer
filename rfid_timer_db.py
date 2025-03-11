import serial
import sqlite3
import time

# Open serial connection
ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)

# SQLite database setup
conn = sqlite3.connect('rfid_time_tracker.db')
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS time_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_id TEXT,
                    start_time REAL,
                    end_time REAL,
                    duration REAL
                )''')
conn.commit()

# Dictionary to track start times
start_times = {}

def log_time(tag_id, start_time, end_time):
    """Log the time spent on a project in the database"""
    duration = (end_time - start_time) / 3600  # Convert to hours
    cursor.execute("INSERT INTO time_logs (tag_id, start_time, end_time, duration) VALUES (?, ?, ?, ?)",
                   (tag_id, start_time, end_time, duration))
    conn.commit()
    print(f"Logged {tag_id}: {duration:.2f} hours")

print("Waiting for RFID scan...")

try:
    while True:
        # Read RFID data
        tag_id = ser.readline().decode('utf-8').strip()
        
        if tag_id:
            print(f"Scanned RFID: {tag_id}")
            
            if tag_id in start_times:
                # Stop timer and log time
                start_time = start_times.pop(tag_id)
                end_time = time.time()
                log_time(tag_id, start_time, end_time)
            else:
                # Start timer
                start_times[tag_id] = time.time()
                print(f"Started tracking time for {tag_id}")
                
        time.sleep(0.5)  # Prevent spamming

except KeyboardInterrupt:
    print("\nExiting...")
    conn.close()
    ser.close()
