# from flask import Flask, request, jsonify, render_template
# from flask_cors import CORS
# from flask_socketio import SocketIO, emit
# import psutil
# import os
# import platform
# import time
# import threading
# import mysql.connector
# import traceback

# # Initialize Flask app
# app = Flask(__name__)
# CORS(app)
# socketio = SocketIO(app, cors_allowed_origins="*")

# # MySQL connection setup
# def get_db_connection():
#     return mysql.connector.connect(
#         host="rovers.cjc26ma2u8ql.us-east-1.rds.amazonaws.com",         # Replace with your DB host
#         user="admin",              # Replace with your DB user
#         password="password",      # Replace with your DB password
#         database="rovers"  # Replace with your DB name
#     )

# @app.route('/logHealthCheckRPI', methods=['POST'])
# def log_health_check_rpi():
#     try:
#         data = request.get_json()
#         print("Received data:", data)

#         if not data:
#             return jsonify({"message": "No JSON data received"}), 400

#         # Extract values with fallback defaults (for debugging phase)
#         rover_id = data.get('rover_id')
#         rpi_id = data.get('rpi_id')
#         device_id = data.get('device_id')
#         check_status = data.get('check_status')
#         check_value = data.get('check_value')
#         date_time = data.get('date_time')
#         location_x = data.get('location_x')
#         location_y = data.get('location_y')
#         location_z = data.get('location_z')
#         remarks = data.get('remarks')

#         # Basic validation (optional)
#         required_fields = ['rover_id', 'rpi_id', 'device_id', 'check_status', 'check_value', 'date_time']
#         for field in required_fields:
#             if data.get(field) is None:
#                 return jsonify({"message": f"Missing field: {field}"}), 400

#         # Insert into database
#         conn = get_db_connection()
#         cursor = conn.cursor()

#         insert_query = """
#             INSERT INTO loghealthcheckrpi (
#                 rover_id, rpi_id, device_id, check_status, check_value, 
#                 date_time, location_x, location_y, location_z, remarks
#             ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#         """

#         cursor.execute(insert_query, (
#             rover_id, rpi_id, device_id, check_status, check_value,
#             date_time, location_x, location_y, location_z, remarks
#         ))
#         conn.commit()
#         cursor.close()
#         conn.close()

#         return jsonify({"message": "Health check log inserted successfully"}), 201

#     except Exception as e:
#         print("Error:", e)
#         traceback.print_exc()  # Logs full stack trace
#         return jsonify({"message": "Server error", "error": str(e)}), 500


# # Route to fetch system stats (used in the stats page)
# def get_system_stats():
#     # Gather system info
#     cpu_overall_percent = psutil.cpu_percent(interval=1)
#     cpu_per_core_percent = psutil.cpu_percent(interval=1, percpu=True)
#     cpu_count_logical = psutil.cpu_count(logical=True)
#     cpu_count_physical = psutil.cpu_count(logical=False)
#     cpu_freq = psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {}
#     load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else [None, None, None]
#     memory = psutil.virtual_memory()._asdict()

#     # Gather top 10 processes by CPU usage
#     processes = []
#     for proc in psutil.process_iter(attrs=['pid', 'name', 'cpu_percent', 'memory_percent', 'cmdline']):
#         try:
#             processes.append(proc.info)
#         except (psutil.NoSuchProcess, psutil.AccessDenied):
#             continue

#     # Sort processes by CPU usage, descending and get top 10
#     top_processes = sorted(processes, key=lambda p: p['cpu_percent'], reverse=True)[:10]

#     # Format command line nicely
#     for p in top_processes:
#         p['cmdline'] = ' '.join(p['cmdline']) if p['cmdline'] else ''

#     return {
#         "cpu_overall_percent": cpu_overall_percent,
#         "cpu_per_core_percent": cpu_per_core_percent,
#         "cpu_count_logical": cpu_count_logical,
#         "cpu_count_physical": cpu_count_physical,
#         "cpu_freq": cpu_freq,
#         "load_avg": load_avg,
#         "memory": memory,
#         "top_processes": top_processes
#     }

# # Route to display index.html
# @app.route('/')
# def index():
#     return render_template('index.html')

# @app.route('/tray_mgmt')
# def tray_mgmt():
#     return render_template('tray_mgmt.html')

# # Route to display stats page
# @app.route('/stats-page')
# def stats_page():
#     return render_template('stats.html')

# # Keep the REST endpoint for backward compatibility
# @app.route("/stats")
# def stats():
#     return jsonify(get_system_stats())

# # Socket.io events
# @socketio.on('connect')
# def handle_connect():
#     print('Client connected')

# @socketio.on('disconnect')
# def handle_disconnect():
#     print('Client disconnected')

# @socketio.on('request_stats')
# def handle_request_stats():
#     emit('stats_update', get_system_stats())

# # Background task to emit system stats every second
# def background_task():
#     """Background task to emit system stats every second"""
#     while True:
#         socketio.emit('stats_update', get_system_stats())
#         time.sleep(1)  # Send updates every second

# # Route to trigger system reboot
# @app.route("/reboot", methods=["POST"])
# def reboot():
#     system = platform.system()
#     if system == "Windows":
#         os.system("shutdown /r /t 1")
#     elif system == "Linux":
#         os.system("sudo /usr/sbin/reboot")
#     return jsonify({"message": "Rebooting..."})

# if __name__ == '__main__':
#     # Start background thread for sending stats
#     stats_thread = threading.Thread(target=background_task)
#     stats_thread.daemon = True
#     stats_thread.start()

#     # Run the Flask app with SocketIO
#     socketio.run(app, debug=True)


from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import psutil
import os
import platform
import time
import threading
import mysql.connector
import sqlite3
import json
import shortuuid
import traceback
from websocket_server import WebsocketServer

# Initialize Flask app
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ---------- DATABASE CONNECTIONS ----------

# MySQL connection setup
# def get_db_connection():
#     return mysql.connector.connect(
#         host="rovers.cjc26ma2u8ql.us-east-1.rds.amazonaws.com",
#         user="admin",
#         password="password",
#         database="rovers"
#     )

# # SQLite initialization
# def init_sqlite_db():
#     with sqlite3.connect('tray_orders.db') as conn:
#         c = conn.cursor()
#         c.execute('''CREATE TABLE IF NOT EXISTS tray_orders (
#             id TEXT PRIMARY KEY,
#             timestamp DATETIME DEFAULT (DATETIME('now', 'localtime')),
#             tray1_table_id INTEGER,
#             tray1_reached BOOLEAN DEFAULT 0,
#             tray2_table_id INTEGER,
#             tray2_reached BOOLEAN DEFAULT 0,
#             tray3_table_id INTEGER,
#             tray3_reached BOOLEAN DEFAULT 0,
#             success BOOLEAN DEFAULT 0,
#             chef_table INTEGER DEFAULT 0
#         )''')
#         conn.commit()

# init_sqlite_db()

# ---------- WEBSOCKET SERVER HANDLING ----------

ws_server = None
clients = []

def new_client(client, server):
    print(f"New client connected: {client['id']}")
    clients.append(client)

def client_left(client, server):
    print(f"Client {client['id']} disconnected")
    if client in clients:
        clients.remove(client)

def message_received(client, server, message):
    try:
        data = json.loads(message)
        if data.get("type") == "waypoint_result" and data.get("sequence"):
            print(f"Received sequence for order {data['order']}: {data['sequence']}")
            with sqlite3.connect('tray_orders.db') as conn:
                c = conn.cursor()
                c.execute('SELECT tray1_table_id, tray2_table_id, tray3_table_id FROM tray_orders WHERE id = ?', (data['order'],))
                row = c.fetchone()
                if row:
                    tray1_reached = 0 if row[0] in data['sequence'] else 1
                    tray2_reached = 0 if row[1] in data['sequence'] else 1
                    tray3_reached = 0 if row[2] in data['sequence'] else 1
                    c.execute('''UPDATE tray_orders 
                                 SET tray1_reached = ?, tray2_reached = ?, tray3_reached = ? 
                                 WHERE id = ?''', 
                              (tray1_reached, tray2_reached, tray3_reached, data['order']))
                    conn.commit()
        else:
            print("Unrecognized message type")
    except Exception as e:
        print(f"Error handling message: {e}")

def start_websocket_server():
    global ws_server
    port = 48236
    for attempt in range(10):
        try:
            ws_server = WebsocketServer(host='0.0.0.0', port=port)
            ws_server.set_fn_new_client(new_client)
            ws_server.set_fn_client_left(client_left)
            ws_server.set_fn_message_received(message_received)
            print(f"WebSocket server started on port {port}")
            ws_server.run_forever(threaded=True)
            break
        except OSError:
            print(f"Port {port} in use, retrying...")
            port += 1
            time.sleep(1)

# Run WebSocket server in background
threading.Thread(target=start_websocket_server, daemon=True).start()

# ---------- SYSTEM STATS LOGIC ----------

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

# ---------- ROUTES ----------

# Route to display index.html
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/tray_mgmt')
def tray_mgmt():
    return render_template('tray_mgmt.html')

# Route to display stats page
@app.route('/stats-page')
def stats_page():
    return render_template('stats.html')

# Keep the REST endpoint for backward compatibility
@app.route("/stats")
def stats():
    return jsonify(get_system_stats())

# Health check logging route
# @app.route('/logHealthCheckRPI', methods=['POST'])
# def log_health_check_rpi():
#     try:
#         data = request.get_json()
#         print("Received data:", data)

#         if not data:
#             return jsonify({"message": "No JSON data received"}), 400

#         # Extract values with fallback defaults (for debugging phase)
#         rover_id = data.get('rover_id')
#         rpi_id = data.get('rpi_id')
#         device_id = data.get('device_id')
#         check_status = data.get('check_status')
#         check_value = data.get('check_value')
#         date_time = data.get('date_time')
#         location_x = data.get('location_x')
#         location_y = data.get('location_y')
#         location_z = data.get('location_z')
#         remarks = data.get('remarks')

#         # Basic validation (optional)
#         required_fields = ['rover_id', 'rpi_id', 'device_id', 'check_status', 'check_value', 'date_time']
#         for field in required_fields:
#             if data.get(field) is None:
#                 return jsonify({"message": f"Missing field: {field}"}), 400

#         # Insert into database
#         conn = get_db_connection()
#         cursor = conn.cursor()

#         insert_query = """
#             INSERT INTO loghealthcheckrpi (
#                 rover_id, rpi_id, device_id, check_status, check_value, 
#                 date_time, location_x, location_y, location_z, remarks
#             ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#         """

#         cursor.execute(insert_query, (
#             rover_id, rpi_id, device_id, check_status, check_value,
#             date_time, location_x, location_y, location_z, remarks
#         ))
#         conn.commit()
#         cursor.close()
#         conn.close()

#         return jsonify({"message": "Health check log inserted successfully"}), 201

#     except Exception as e:
#         print("Error:", e)
#         traceback.print_exc()  # Logs full stack trace
#         return jsonify({"message": "Server error", "error": str(e)}), 500

# Tray management route
@app.route('/get-table-array', methods=['POST'])
def get_table_array():
    data = request.get_json()
    trays = data.get('trays', {})
    tray_array = [f"T{value}" for value in trays.values()]
    order_id = shortuuid.uuid()

    try:
        with sqlite3.connect('tray_orders.db') as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO tray_orders 
                         (id, tray1_table_id, tray2_table_id, tray3_table_id) 
                         VALUES (?, ?, ?, ?)''',
                      (order_id, trays.get('1'), trays.get('2'), trays.get('3')))
            conn.commit()
    except Exception as e:
        print(f"Error inserting into database: {e}")

    # Notify all WebSocket clients
    if ws_server and clients:
        ws_message = json.dumps({
            "order": order_id,
            "tray": tray_array
        })
        for client in clients:
            ws_server.send_message(client, ws_message)
        print(f"Sent tray order to {len(clients)} WebSocket clients.")

    return jsonify(tray_array)

# Route to trigger system reboot
@app.route("/reboot", methods=["POST"])
def reboot():
    system = platform.system()
    if system == "Windows":
        os.system("shutdown /r /t 1")
    elif system == "Linux":
        os.system("sudo /usr/sbin/reboot")
    return jsonify({"message": "Rebooting..."})

# ---------- SOCKET.IO EVENTS ----------

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

# ---------- RUN THE APP ----------

if __name__ == '__main__':
    # Start background thread for sending stats
    stats_thread = threading.Thread(target=background_task)
    stats_thread.daemon = True
    stats_thread.start()

    # Run the Flask app with SocketIO
    socketio.run(app, debug=True)