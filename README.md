# RFID Project Time Tracker

A Python-based time tracking system that uses RFID cards to track time spent on different projects. Perfect for freelancers, small teams, or anyone who needs to track time across multiple projects.

## Features

- **RFID-based Time Tracking**: Start and stop timers by simply scanning an RFID card
- **Project Management**: Create, finish, and reactivate projects
- **Real-time Updates**: Active timers update in real-time without page refresh
- **Time Log History**: View detailed time logs for both active and finished projects
- **Project Statistics**: Track total time spent on each project
- **Clean Interface**: Modern, responsive web interface built with Bootstrap

## Requirements

- Python 3.x
- Flask
- SQLite3
- pyserial (for RFID reader communication)
- RFID Reader (connected via USB)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Abengs84/project-timer.git
cd project-timer
```

2. Create and activate a virtual environment:
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

3. Install required Python packages:
```bash
pip install -r requirements.txt
```

4. Initialize the database:
```bash
python web_interface.py
```

4. Access the application:
- Open a web browser
- Navigate to `http://localhost:5000`

## Usage

1. **Adding a New Project**:
   - Click "Add New Project"
   - Enter project name
   - Scan an RFID card when prompted

2. **Time Tracking**:
   - Scan RFID card to start timer
   - Scan again to stop timer
   - View active timers and time logs in real-time

3. **Managing Projects**:
   - Mark projects as finished
   - Reactivate finished projects
   - View time logs for both active and finished projects

## Hardware Setup

- Connect your RFID reader to USB port
- Default configuration uses `/dev/ttyUSB0` (can be modified in `web_interface.py`)

## Database Structure

The application uses SQLite with the following tables:
- `projects`: Active projects
- `time_logs`: Time entries for active projects
- `finished_projects`: Completed projects
- `finished_time_logs`: Time entries for completed projects

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## Security Note

This is a basic implementation. For production use, consider:
- Adding user authentication
- Implementing HTTPS
- Securing the database
- Adding input validation
- Implementing backup solutions 