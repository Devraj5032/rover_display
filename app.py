from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import psutil
import os
import platform
import time
import threading

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/get-table-array', methods=['POST'])
def get_table_array():
    data = request.get_json()
    trays = data.get('trays', {})
    print(trays)
    tray_array = [trays.get(i, None) for i in range(1, 4)]
    return jsonify(tray_array)

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

# Keep the REST endpoint for backward compatibility
@app.route("/stats")
def stats():
    return jsonify(get_system_stats())

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('request_stats')
def handle_request_stats():
    emit('stats_update', get_system_stats())

def background_task():
    """Background task to emit system stats every second"""
    while True:
        socketio.emit('stats_update', get_system_stats())
        time.sleep(1)  # Send updates every second

@app.route("/reboot", methods=["POST"])
def reboot():
    system = platform.system()
    if system == "Windows":
        os.system("shutdown /r /t 1")  # /r = reboot, /t 1 = after 1 second
    elif system == "Linux":
        os.system("sudo reboot")  # 'reboot' is the standard reboot command
    return jsonify({"message": "Rebooting..."})


if __name__ == '__main__':
    # Start background thread for sending stats
    stats_thread = threading.Thread(target=background_task)
    stats_thread.daemon = True
    stats_thread.start()
    
    socketio.run(app, debug=True)