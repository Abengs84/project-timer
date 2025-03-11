from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
from datetime import datetime
import serial
import time
import threading
import queue
from config import SECRET_KEY, RFID_PORT, RFID_BAUDRATE, DATABASE_PATH, ENABLE_TIMER_DEBUG

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Global variables for RFID reading
rfid_queue = queue.Queue()
is_scanning = False
ser = None
start_times = {}  # Dictionary to track start times for projects

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Create projects table
    conn.execute('''CREATE TABLE IF NOT EXISTS projects
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     name TEXT NOT NULL,
                     tag_id TEXT UNIQUE NOT NULL)''')
    
    # Create time_logs table
    conn.execute('''CREATE TABLE IF NOT EXISTS time_logs
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     tag_id TEXT,
                     start_time REAL,
                     end_time REAL,
                     duration REAL)''')

    # Create finished_projects table
    conn.execute('''CREATE TABLE IF NOT EXISTS finished_projects
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     name TEXT NOT NULL,
                     tag_id TEXT UNIQUE NOT NULL,
                     completion_date REAL,
                     original_id INTEGER)''')
    
    # Create finished_time_logs table
    conn.execute('''CREATE TABLE IF NOT EXISTS finished_time_logs
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     tag_id TEXT,
                     project_name TEXT,
                     start_time REAL,
                     end_time REAL,
                     duration REAL)''')
    
    conn.commit()
    conn.close()

def read_rfid():
    global is_scanning, ser
    print("\n[DEBUG] Starting RFID reader...")
    print("[DEBUG] Waiting for RFID tag...")
    try:
        # Only open serial port if it's not already open
        if not ser or not ser.is_open:
            ser = serial.Serial(RFID_PORT, RFID_BAUDRATE, timeout=1)
        
        while is_scanning:
            try:
                tag_id = ser.readline().decode('utf-8').strip()
                if tag_id:
                    print(f"[DEBUG] RFID Tag detected: {tag_id}")
                    rfid_queue.put(tag_id)
                    is_scanning = False
                else:
                    print("[DEBUG] Scanning...", end='\r')
            except serial.SerialException as e:
                print(f"\n[DEBUG] Serial error while reading: {e}")
                break
            except Exception as e:
                print(f"\n[DEBUG] Error while reading: {e}")
                break
    except Exception as e:
        print(f"\n[DEBUG] Error opening RFID reader: {e}")
    finally:
        try:
            if ser and ser.is_open:
                ser.close()
                print("[DEBUG] RFID reader closed")
        except Exception as e:
            print(f"[DEBUG] Error closing serial port: {e}")

def get_project_total_hours(tag_id, conn):
    result = conn.execute('''
        SELECT COALESCE(SUM(duration), 0) as total_hours
        FROM time_logs
        WHERE tag_id = ?
    ''', (tag_id,)).fetchone()
    return float(result['total_hours'])

def log_time(tag_id, start_time, end_time):
    """Log the time spent on a project in the database"""
    duration = (end_time - start_time) / 3600  # Convert to hours
    conn = get_db_connection()
    try:
        # Get project name for debugging
        project = conn.execute('SELECT name FROM projects WHERE tag_id = ?', (tag_id,)).fetchone()
        project_name = project['name'] if project else 'Unknown Project'
        
        conn.execute("INSERT INTO time_logs (tag_id, start_time, end_time, duration) VALUES (?, ?, ?, ?)",
                    (tag_id, start_time, end_time, duration))
        conn.commit()
        print(f"[DEBUG] Logged time for {project_name}: {duration:.2f} hours")
        return True
    except Exception as e:
        print(f"[DEBUG] Error logging time: {e}")
        return False
    finally:
        conn.close()

def get_active_timers():
    """Get information about currently active timers"""
    active_timers = []
    conn = get_db_connection()
    try:
        for tag_id, start_time in start_times.items():
            project = conn.execute('SELECT name FROM projects WHERE tag_id = ?', (tag_id,)).fetchone()
            if project:
                active_timers.append({
                    'project_name': project['name'],
                    'start_time': start_time
                })
    finally:
        conn.close()
    return active_timers

def format_duration(hours):
    """Convert hours to HH:MM:SS format"""
    total_seconds = int(hours * 3600)  # Convert hours to seconds
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

@app.route('/')
def index():
    conn = get_db_connection()
    
    # Get projects with their total hours
    projects = []
    base_projects = conn.execute('SELECT * FROM projects').fetchall()
    
    for project in base_projects:
        total_hours = get_project_total_hours(project['tag_id'], conn)
        projects.append({
            'id': project['id'],
            'name': project['name'],
            'tag_id': project['tag_id'],
            'total_hours': total_hours
        })
    
    # Get time logs with project names (only for active projects)
    time_logs = conn.execute('''
        SELECT time_logs.*, p.name as project_name 
        FROM time_logs 
        INNER JOIN projects p ON time_logs.tag_id = p.tag_id 
        ORDER BY start_time DESC
    ''').fetchall()
    
    conn.close()

    # Get active timers
    active_timers = get_active_timers()
    
    return render_template('index.html', 
                         projects=projects, 
                         time_logs=time_logs,
                         active_timers=active_timers,
                         datetime=datetime,
                         format_duration=format_duration)

@app.route('/start_project', methods=['POST'])
def start_project():
    name = request.form['name']
    if not name:
        flash('Project name is required!', 'error')
        return redirect(url_for('index'))
    
    print(f"\n[DEBUG] Starting new project setup: {name}")
    return render_template('scan_rfid.html', project_name=name)

@app.route('/start_rfid_scan', methods=['POST'])
def start_rfid_scan():
    global is_scanning
    # If already scanning, don't start a new thread
    if not is_scanning:
        is_scanning = True
        print("\n[DEBUG] RFID scanning initiated")
        
        # Clear any existing items in the queue
        while not rfid_queue.empty():
            rfid_queue.get()
        
        # Start RFID reading thread
        thread = threading.Thread(target=read_rfid)
        thread.daemon = True
        thread.start()
    
    return jsonify({'status': 'scanning'})

@app.route('/check_rfid_scan')
def check_rfid_scan():
    try:
        # Non-blocking queue check
        tag_id = rfid_queue.get_nowait()
        print(f"[DEBUG] RFID tag retrieved from queue: {tag_id}")
        return jsonify({'status': 'success', 'tag_id': tag_id})
    except queue.Empty:
        return jsonify({'status': 'waiting'})

@app.route('/complete_project', methods=['POST'])
def complete_project():
    name = request.form['name']
    tag_id = request.form['tag_id']
    
    print(f"\n[DEBUG] Completing project setup:")
    print(f"[DEBUG] Project Name: {name}")
    print(f"[DEBUG] RFID Tag ID: {tag_id}")
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO projects (name, tag_id) VALUES (?, ?)',
                    (name, tag_id))
        conn.commit()
        print("[DEBUG] Project successfully added to database")
        flash('Project added successfully!', 'success')
    except sqlite3.IntegrityError:
        print("[DEBUG] Error: RFID tag already in use")
        flash('Error: RFID tag already assigned to a project!', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('index'))

@app.route('/delete_project/<int:project_id>', methods=['POST'])
def delete_project(project_id):
    print(f"\n[DEBUG] Attempting to delete project {project_id}")
    
    conn = get_db_connection()
    try:
        # Get project info for debugging
        project = conn.execute('SELECT name, tag_id FROM projects WHERE id = ?', (project_id,)).fetchone()
        if project:
            print(f"[DEBUG] Deleting project: {project['name']} (Tag: {project['tag_id']})")
            
            # Delete associated time logs first
            conn.execute('DELETE FROM time_logs WHERE tag_id = ?', (project['tag_id'],))
            # Then delete the project
            conn.execute('DELETE FROM projects WHERE id = ?', (project_id,))
            
            conn.commit()
            print("[DEBUG] Project and associated time logs deleted successfully")
            flash('Project deleted successfully!', 'success')
        else:
            print("[DEBUG] Project not found")
            flash('Project not found!', 'error')
    except Exception as e:
        print(f"[DEBUG] Error deleting project: {e}")
        flash('Error deleting project!', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('index'))

@app.route('/track_time')
def track_time():
    global is_scanning
    is_scanning = True
    
    # Start RFID reading thread
    thread = threading.Thread(target=read_rfid)
    thread.daemon = True
    thread.start()
    
    return render_template('track_time.html')

@app.route('/check_card_scan')
def check_card_scan():
    global is_scanning
    try:
        # Non-blocking queue check
        tag_id = rfid_queue.get_nowait()
        print(f"[DEBUG] Card scanned for time tracking: {tag_id}")
        
        # Check if this is a valid project
        conn = get_db_connection()
        project = conn.execute('SELECT name FROM projects WHERE tag_id = ?', (tag_id,)).fetchone()
        conn.close()
        
        if not project:
            # Restart scanning
            is_scanning = True
            thread = threading.Thread(target=read_rfid)
            thread.daemon = True
            thread.start()
            return jsonify({
                'status': 'error',
                'message': 'Unknown RFID tag. Please register this tag with a project first.'
            })
        
        if tag_id in start_times:
            # Stop timer and log time
            start_time = start_times.pop(tag_id)
            end_time = time.time()
            if log_time(tag_id, start_time, end_time):
                # Get the new log entry
                conn = get_db_connection()
                new_log = conn.execute('''
                    SELECT time_logs.*, projects.name as project_name 
                    FROM time_logs 
                    LEFT JOIN projects ON time_logs.tag_id = projects.tag_id 
                    WHERE time_logs.tag_id = ? 
                    AND time_logs.start_time = ?
                ''', (tag_id, start_time)).fetchone()
                conn.close()

                # Restart scanning
                is_scanning = True
                thread = threading.Thread(target=read_rfid)
                thread.daemon = True
                thread.start()
                
                return jsonify({
                    'status': 'success',
                    'message': f'Timer stopped for {project["name"]}',
                    'action': 'stopped',
                    'new_log': {
                        'project_name': project['name'],
                        'start_time': start_time,
                        'end_time': end_time,
                        'duration': (end_time - start_time) / 3600  # Convert to hours
                    }
                })
            else:
                # Restart scanning
                is_scanning = True
                thread = threading.Thread(target=read_rfid)
                thread.daemon = True
                thread.start()
                return jsonify({
                    'status': 'error',
                    'message': 'Error logging time'
                })
        else:
            # Start timer
            start_times[tag_id] = time.time()
            # Restart scanning
            is_scanning = True
            thread = threading.Thread(target=read_rfid)
            thread.daemon = True
            thread.start()
            return jsonify({
                'status': 'success',
                'message': f'Timer started for {project["name"]}',
                'action': 'started'
            })
            
    except queue.Empty:
        return jsonify({'status': 'waiting'})
    except Exception as e:
        print(f"[DEBUG] Error in check_card_scan: {e}")
        # Restart scanning even on error
        is_scanning = True
        thread = threading.Thread(target=read_rfid)
        thread.daemon = True
        thread.start()
        return jsonify({
            'status': 'error',
            'message': 'Error processing card scan'
        })

@app.route('/check_active_timers')
def check_active_timers():
    """API endpoint to get active timer information"""
    if ENABLE_TIMER_DEBUG:
        print("[DEBUG] Checking active timers")
    active_timers = get_active_timers()
    return jsonify({
        'active_timers': active_timers,
        'current_time': time.time()
    })

@app.route('/finish_project/<int:project_id>', methods=['POST'])
def finish_project(project_id):
    print(f"\n[DEBUG] Moving project {project_id} to finished projects")
    conn = get_db_connection()
    try:
        # Get project info
        project = conn.execute('SELECT name, tag_id FROM projects WHERE id = ?', (project_id,)).fetchone()
        if project:
            # Move time logs to finished_time_logs
            conn.execute('''
                INSERT INTO finished_time_logs (tag_id, project_name, start_time, end_time, duration)
                SELECT tag_id, ?, start_time, end_time, duration
                FROM time_logs
                WHERE tag_id = ?
            ''', (project['name'], project['tag_id']))
            
            # Delete from time_logs
            conn.execute('DELETE FROM time_logs WHERE tag_id = ?', (project['tag_id'],))
            
            # Add to finished_projects
            conn.execute('''INSERT INTO finished_projects (name, tag_id, completion_date, original_id)
                          VALUES (?, ?, ?, ?)''', 
                          (project['name'], project['tag_id'], time.time(), project_id))
            
            # Delete from active projects
            conn.execute('DELETE FROM projects WHERE id = ?', (project_id,))
            conn.commit()
            flash('Project marked as finished!', 'success')
        else:
            flash('Project not found!', 'error')
    except Exception as e:
        print(f"[DEBUG] Error finishing project: {e}")
        flash('Error marking project as finished!', 'error')
    finally:
        conn.close()
    return redirect(url_for('index'))

@app.route('/finished_projects')
def finished_projects():
    conn = get_db_connection()
    finished = []
    try:
        # Get finished projects with their total hours
        base_finished = conn.execute('''
            SELECT * FROM finished_projects 
            ORDER BY completion_date DESC''').fetchall()
        
        for project in base_finished:
            total_hours = get_project_total_hours(project['tag_id'], conn)
            
            # Get time logs for this project
            time_logs = conn.execute('''
                SELECT * FROM finished_time_logs
                WHERE tag_id = ?
                ORDER BY start_time DESC
            ''', (project['tag_id'],)).fetchall()
            
            finished.append({
                'id': project['id'],
                'name': project['name'],
                'tag_id': project['tag_id'],
                'completion_date': project['completion_date'],
                'total_hours': total_hours,
                'time_logs': time_logs
            })
    finally:
        conn.close()
    
    return render_template('finished_projects.html', 
                         projects=finished,
                         datetime=datetime,
                         format_duration=format_duration)

@app.route('/reactivate_project/<int:finished_id>', methods=['POST'])
def reactivate_project(finished_id):
    print(f"\n[DEBUG] Reactivating finished project {finished_id}")
    conn = get_db_connection()
    try:
        # Get finished project info
        project = conn.execute('SELECT name, tag_id FROM finished_projects WHERE id = ?', (finished_id,)).fetchone()
        if project:
            # Move time logs back to active time_logs
            conn.execute('''
                INSERT INTO time_logs (tag_id, start_time, end_time, duration)
                SELECT tag_id, start_time, end_time, duration
                FROM finished_time_logs
                WHERE tag_id = ?
            ''', (project['tag_id'],))
            
            # Delete from finished_time_logs
            conn.execute('DELETE FROM finished_time_logs WHERE tag_id = ?', (project['tag_id'],))
            
            # Add back to active projects
            conn.execute('INSERT INTO projects (name, tag_id) VALUES (?, ?)', 
                        (project['name'], project['tag_id']))
            
            # Remove from finished projects
            conn.execute('DELETE FROM finished_projects WHERE id = ?', (finished_id,))
            
            conn.commit()
            flash('Project reactivated successfully!', 'success')
        else:
            flash('Finished project not found!', 'error')
    except Exception as e:
        print(f"[DEBUG] Error reactivating project: {e}")
        flash('Error reactivating project!', 'error')
    finally:
        conn.close()
    return redirect(url_for('finished_projects'))

@app.route('/reset_database', methods=['POST'])
def reset_database():
    conn = get_db_connection()
    try:
        # Clear all tables
        conn.execute('DELETE FROM time_logs')
        conn.execute('DELETE FROM projects')
        conn.execute('DELETE FROM finished_projects')
        conn.execute('DELETE FROM finished_time_logs')
        conn.commit()
        flash('Database has been reset successfully!', 'success')
    except Exception as e:
        flash(f'Error resetting database: {str(e)}', 'error')
    finally:
        conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    print("\n[DEBUG] Database initialized")
    print("[DEBUG] Starting Flask application...")
    app.run(debug=True) 