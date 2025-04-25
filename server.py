from flask import Flask, request, jsonify, render_template  # add render_template
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
ws_server = None
clients = []  # Store connected clients

def new_client(client, server):
    """Called when a new client connects to the WebSocket server"""
    print(f"New client connected and was given id {client['id']}")
    clients.append(client)

def client_left(client, server):
    """Called when a client disconnects from the WebSocket server"""
    print(f"Client {client['id']} disconnected")
    if client in clients:
        clients.remove(client)

def message_received(client, server, message):
    """Called when a client sends a message to the server"""
    try:
        data = json.loads(message)
        if data.get("type") == "waypoint_result":
            print(f"Received Fibonacci result: {data['sequence']}")
        else:
            print("Received unrecognized message type")

    except Exception as e:
        print(f"Error handling message: {e}")

def start_websocket_server():
    global ws_server
    port = 48236
    max_retries = 10
    
    for attempt in range(max_retries):
        try:
            ws_server = websocket_server.WebsocketServer(host='0.0.0.0', port=port)
            # ws_server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            ws_server.set_fn_new_client(new_client)
            ws_server.set_fn_client_left(client_left)
            ws_server.set_fn_message_received(message_received)
            print(f"WebSocket server started on port {port}")
            ws_server.run_forever(threaded=True)
            break
        except OSError as e:
            if attempt == max_retries - 1:
                print(f"Failed to start WebSocket server after {max_retries} attempts: {e}")
                raise
            print(f"Port {port} in use, retrying with port {port + 1}...")
            port += 1
            time.sleep(1)

# Start WebSocket server in a separate thread
websocket_thread = threading.Thread(target=start_websocket_server, daemon=True)
websocket_thread.start()

@app.route('/get-table-array', methods=['POST'])
def get_table_array():
    data = request.get_json()
    trays = data.get('trays', {})
    print(trays)
    tray_array = [f"T{value}" for value in trays.values()]
    
    # Send data to all connected WebSocket clients
    if ws_server and clients:
        ws_message = json.dumps({
            "order": 10 ,
            "tray": tray_array
        })
        
        for client in clients:
            ws_server.send_message(client, ws_message)
        print(f"Sent WebSocket message to {len(clients)} clients: {ws_message}")
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stats-page')
def stats_page():
    return render_template('stats.html')


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
        os.system("shutdown /r /t 1")
    elif system == "Linux":
        os.system("sudo /usr/sbin/reboot")
    return jsonify({"message": "Rebooting..."})



if __name__ == '__main__':
    # Start background thread for sending stats
    stats_thread = threading.Thread(target=background_task)
    stats_thread.daemon = True
    stats_thread.start()
    
    socketio.run(app, debug=True)
