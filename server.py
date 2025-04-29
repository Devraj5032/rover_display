from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import psutil
import os
import platform
import time
import threading
import mysql.connector

# Initialize Flask app
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# MySQL connection setup
def get_db_connection():
    return mysql.connector.connect(
        host="rovers.cjc26ma2u8ql.us-east-1.rds.amazonaws.com",         # Replace with your DB host
        user="admin",              # Replace with your DB user
        password="password",      # Replace with your DB password
        database="rovers"  # Replace with your DB name
    )

# Route to insert health check logs into MySQL
@app.route('/logHealthCheckRPI', methods=['POST'])
def log_health_check_rpi():
    try:
        data = request.get_json()  # Get JSON data from the request

        # Parse the data from the request
        rover_id = data.get('rover_id')
        rpi_id = data.get('rpi_id')
        device_id = data.get('device_id')
        check_status = data.get('check_status')
        check_value = data.get('check_value')
        date_time = data.get('date_time')
        location_x = data.get('location_x')
        location_y = data.get('location_y')
        location_z = data.get('location_z')
        remarks = data.get('remarks')

        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create the SQL insert query
        insert_query = """
            INSERT INTO loghealthcheckrpi (
                rover_id, rpi_id, device_id, check_status, check_value, 
                date_time, location_x, location_y, location_z, remarks
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        # Insert the data into the database
        cursor.execute(insert_query, (rover_id, rpi_id, device_id, check_status, check_value, date_time, location_x, location_y, location_z, remarks))

        # Commit the transaction
        conn.commit()

        # Close the cursor and connection
        cursor.close()
        conn.close()

        # Return a success response
        return jsonify({"message": "Health check log inserted successfully"}), 201

    except Exception as e:
        # In case of an error, return a failure response
        return jsonify({"message": str(e)}), 500


# Route to fetch system stats (used in the stats page)
def get_system_stats():
    # Gather system info
    cpu_overall_percent = psutil.cpu_percent(interval=1)
    cpu_per_core_percent = psutil.cpu_percent(interval=1, percpu=True)
    cpu_count_logical = psutil.cpu_count(logical=True)
    cpu_count_physical = psutil.cpu_count(logical=False)
    cpu_freq = psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {}
    load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else [None, None, None]
    memory = psutil.virtual_memory()._asdict()

    # Gather top 10 processes by CPU usage
    processes = []
    for proc in psutil.process_iter(attrs=['pid', 'name', 'cpu_percent', 'memory_percent', 'cmdline']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sort processes by CPU usage, descending and get top 10
    top_processes = sorted(processes, key=lambda p: p['cpu_percent'], reverse=True)[:10]

    # Format command line nicely
    for p in top_processes:
        p['cmdline'] = ' '.join(p['cmdline']) if p['cmdline'] else ''

    return {
        "cpu_overall_percent": cpu_overall_percent,
        "cpu_per_core_percent": cpu_per_core_percent,
        "cpu_count_logical": cpu_count_logical,
        "cpu_count_physical": cpu_count_physical,
        "cpu_freq": cpu_freq,
        "load_avg": load_avg,
        "memory": memory,
        "top_processes": top_processes
    }

# Route to display index.html
@app.route('/')
def index():
    return render_template('index.html')

# Route to display stats page
@app.route('/stats-page')
def stats_page():
    return render_template('stats.html')

# Keep the REST endpoint for backward compatibility
@app.route("/stats")
def stats():
    return jsonify(get_system_stats())

# Socket.io events
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('request_stats')
def handle_request_stats():
    emit('stats_update', get_system_stats())

# Background task to emit system stats every second
def background_task():
    """Background task to emit system stats every second"""
    while True:
        socketio.emit('stats_update', get_system_stats())
        time.sleep(1)  # Send updates every second

# Route to trigger system reboot
@app.route("/reboot", methods=["POST"])
def reboot():
    system = platform.system()
    if system == "Windows":
        os.system("shutdown /r /t 1")
    elif system == "Linux":
        os.system("sudo /usr/sbin/reboot")
    return jsonify({"message": "Rebooting..."})

if __name__ == '__main__':
    # Start background thread for sending stats
    stats_thread = threading.Thread(target=background_task)
    stats_thread.daemon = True
    stats_thread.start()

    # Run the Flask app with SocketIO
    socketio.run(app, debug=True)
