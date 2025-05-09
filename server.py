from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import psutil
import os
import platform
import logging
import time
import threading
import sqlite3
import json
import shortuuid
import signal
import sys
import traceback
from websocket_server import WebsocketServer
from logging.handlers import RotatingFileHandler

# ------------------------ Logging Setup ------------------------
logger = logging.getLogger("TrayAppLogger")
logger.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler("tray_app.log", maxBytes=5 * 1024 * 1024, backupCount=2)
file_formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
file_handler.setFormatter(file_formatter)

console_handler = logging.StreamHandler(sys.stdout)
console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
console_handler.setFormatter(console_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ------------------------ Flask Setup ------------------------
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
app.logger.handlers = logger.handlers
app.logger.setLevel(logger.level)


active = 0
# Optional MySQL support (commented out as in original)
import mysql.connector

# ---------- SHUTDOWN HANDLING VARIABLES ----------
shutdown_event = threading.Event()
background_threads = []
ws_server = None

# ---------- DATABASE CONNECTIONS ----------

# MySQL connection setup (commented out as in original)
def get_db_connection():
    return mysql.connector.connect(
        host="rovers.cjc26ma2u8ql.us-east-1.rds.amazonaws.com",
        user="admin",
        password="password",
        database="rovers"
    )

# ---------- DATABASE INITIALIZATION ----------


def init_db():
    with sqlite3.connect("tray_orders.db") as conn:
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS tray_orders (
            id TEXT PRIMARY KEY,
            robot_id TEXT DEFAULT 'R_001',
            timestamp DATETIME DEFAULT (DATETIME('now', 'localtime')),
            tray1_table_id INTEGER,
            tray1_reached BOOLEAN DEFAULT 0,
            tray2_table_id INTEGER,
            tray2_reached BOOLEAN DEFAULT 0,
            tray3_table_id INTEGER,
            tray3_reached BOOLEAN DEFAULT 0,
            success BOOLEAN DEFAULT 0,
            chef_table INTEGER DEFAULT 0,
            total_tables INTEGER DEFAULT 0

        )"""
        )
        conn.commit()


init_db()

# ---------- WEBSOCKET SERVER HANDLING ----------

clients = []


def new_client(client, server):
    print(f"New client connected: {client['id']}")
    global active
    clients.append(client)
    active += 1


def client_left(client, server):
    print(f"Client {client['id']} disconnected")
    if client in clients:
        global active
        clients.remove(client)
        active -= 1


def message_received(client, server, message):
    try:
        data = json.loads(message)
        if data.get("type") == "waypoint_result" and data.get("order"):
            if data["sequence"] is None or len(data["sequence"]) == 0:
                print(f"Empty sequence for order {data['order']}, no updates made")
                return
            with sqlite3.connect("tray_orders.db") as conn:
                c = conn.cursor()
                c.execute(
                    "SELECT total_tables FROM tray_orders WHERE id = ?",
                    (data["order"],),
                )
                row = c.fetchone()
                
                if row:
                    total_tables = row[0]
                    if total_tables == 1:
                        # For 1 table: 0=tray1, 1=chef
                        if 0 in data["sequence"]:
                            tray1_reached = 0
                        if 1 in data["sequence"]:
                            chef_table = 0
                            
                    elif total_tables == 2:
                        # For 2 tables: 0=tray1, 1=tray2, 2=chef
                        if 0 in data["sequence"]:
                            tray1_reached = 0
                        if 1 in data["sequence"]:
                            tray2_reached = 0
                        if 2 in data["sequence"]:
                            chef_table = 0
                            
                    elif total_tables == 3:
                        # For 3 tables: 0=tray1, 1=tray2, 2=tray3, 3=chef
                        if 0 in data["sequence"]:
                            tray1_reached = 0
                        if 1 in data["sequence"]:
                            tray2_reached = 0
                        if 2 in data["sequence"]:
                            tray3_reached = 0
                        if 3 in data["sequence"]:
                            chef_table = 0
                    
                    # Update the database
                    c.execute(
                        """UPDATE tray_orders 
                            SET tray1_reached = ?, tray2_reached = ?, tray3_reached = ?, chef_table = ? 
                            WHERE id = ?""",
                        (tray1_reached, tray2_reached, tray3_reached, chef_table, data["order"]),
                    )
                    conn.commit()
                    print(f"Updated order {data['order']} with tray statuses: tray1={tray1_reached}, tray2={tray2_reached}, tray3={tray3_reached}, chef={chef_table}")
        elif data.get("type") == "current_waypoint":
            try:
               way_log_activity(1005, message=data["content"])
            except Exception as e:
                pass

            with sqlite3.connect("tray_orders.db") as conn:
                c = conn.cursor()
                
                # Get current reached status and total_tables
                c.execute(
                    "SELECT tray1_reached, tray2_reached, tray3_reached, chef_table, total_tables FROM tray_orders WHERE id = ?",
                    (data["order"],),
                )
                row = c.fetchone()
                
                if row:
                    tray1_reached, tray2_reached, tray3_reached, chef_table, total_tables = row
                    
                    # Get current waypoint from data
                    current_waypoint = int(data["content"])
                    
                    # Update reached status based on total_tables and current waypoint
                    if total_tables == 1:
                        # If only 1 table/tray used, waypoint 2 is chef's table
                        if current_waypoint == 1:
                            tray1_reached = 1
                        elif current_waypoint == 2:
                            chef_table = 1
                    elif total_tables == 2:
                        # If 2 tables/trays used, waypoint 3 is chef's table
                        if current_waypoint == 1:
                            tray1_reached = 1
                        elif current_waypoint == 2:
                            tray2_reached = 1
                        elif current_waypoint == 3:
                            chef_table = 1
                    elif total_tables == 3:
                        # If all 3 tables/trays used, waypoint 4 is chef's table
                        if current_waypoint == 1:
                            tray1_reached = 1
                        elif current_waypoint == 2:
                            tray2_reached = 1
                        elif current_waypoint == 3:
                            tray3_reached = 1
                        elif current_waypoint == 4:
                            chef_table = 1
                    
                    # Update the database
                    c.execute(
                        """UPDATE tray_orders
                        SET tray1_reached = ?, tray2_reached = ?, tray3_reached = ?, chef_table = ?
                        WHERE id = ?""",
                        (tray1_reached, tray2_reached, tray3_reached, chef_table, data["order"]),
                    )
                    conn.commit()
        elif data.get("type") == "return_to_chef":
            if data.get("status") == "SUCCEEDED":
                print(f"canceled waypoint and return_to_chef message for order {data['order']}")
                way_log_activity(1006, message="cancel_waypoint return to chef")
            elif data.get("status") == "ABORTED":
                way_log_error(1006, ecode=207, message="cancel_waypoint return to chef")


        else:
            print("Unrecognized message type")
    except Exception as e:
        print(f"Error handling message: {e}")


def start_websocket_server():
    global ws_server
    port = 48236
    for attempt in range(10):
        try:
            ws_server = WebsocketServer(host="0.0.0.0", port=port)
            ws_server.set_fn_new_client(new_client)
            ws_server.set_fn_client_left(client_left)
            ws_server.set_fn_message_received(message_received)
            print(f"WebSocket server started on port {port}")
            ws_server.run_forever(threaded=True)
            break
        except OSError:
            print(f"Port {port} in use, retrying...")
            # port += 1
            time.sleep(1)

    # Keep thread alive until shutdown is requested
    while not shutdown_event.is_set():
        time.sleep(1)

    # Close WebSocket server when shutdown is requested
    if ws_server:
        try:
            print("Closing WebSocket server...")
            ws_server.server_close()
        except Exception as e:
            print(f"Error closing WebSocket server: {e}")

# ----------- ERROR HANDLING FOR ROS  -----
import requests
from datetime import datetime
ROVER_ID = "R_001"
RPI_NO = "Rpi_001"
LOCATION_X = ""
LOCATION_Y = ""
LOCATION_Z = ""
POST_URL = "http://localhost:5000/logHealthCheckRPI"
ACTIVITY_URL = "http://localhost:5000/logActivity"
ERROR_URL = "http://localhost:5000/logError"
IMAGE_SIZE_THRESHOLD_KB = 50


def way_log_activity(activity_id, x=None, y=None, z=None, message=None, description=None):
    # Set activity_type based on inputs
    if message is None and None not in (x, y, z):
        activity_type = f"Sent waypoint {x} {y} {z}"
    elif message is not None:
        activity_type = message
    else:
        activity_type = "Unknown activity"

    # Set description
    if description is None:
        description = "All waypoints sent from server to ros"

    payload = {
        "activity_id": f"act-{activity_id}",
        "rover_id": ROVER_ID,
        "activity_type": activity_type,
        "description": description,
        "location_x": LOCATION_X,
        "location_y": LOCATION_Y,
        "location_z": LOCATION_Z,
        "battery_percentage": 0.0,
        "cpu_usage_percentage": 0.0,
        "memory_usage_percentage": 0.0,
        "temperature": 0.0,
        "created_at": datetime.now().isoformat(),
        "created_by": RPI_NO
    }

    try:
        response = requests.post(ACTIVITY_URL, headers={"Content-Type": "application/json"}, json=payload)
        print(f"✅ Activity Log Sent | Status: {response.status_code} | Message: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to log activity | Error: {e}")

def way_log_error(activity_id, *, ecode=205, x=None, message=None):
    # If message is not given but x is, use default format
    if message is None and x is not None:
        message = f"Not able to reach waypoint {x}"
    elif message is None:
        message = "Unknown error occurred"

    payload = {
        "activity_id": f"act-{activity_id}",
        "activity_type": "Sensor Malfunction",
        "created_by": RPI_NO,
        "error_code": f"E{ecode}",
        "rover_id": ROVER_ID,
        "error_message": message,
        "location_x": LOCATION_X,
        "location_y": LOCATION_Y,
        "location_z": LOCATION_Z,
        "battery_percentage": 0.0,
        "cpu_usage_percentage": 0.0,
        "memory_usage_percentage": 0.0,
        "temperature": 0.0,
        "created_at": datetime.now().isoformat()
    }

    try:
        response = requests.post(ERROR_URL, headers={"Content-Type": "application/json"}, json=payload)
        print(f"✅ Error Log Sent | Status: {response.status_code} | Message: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to log error | Error: {e}")
# ---------- SYSTEM STATS LOGIC -----------


def get_system_stats():
    # Gather system info
    cpu_overall_percent = psutil.cpu_percent(interval=1)
    cpu_per_core_percent = psutil.cpu_percent(interval=1, percpu=True)
    cpu_count_logical = psutil.cpu_count(logical=True)
    cpu_count_physical = psutil.cpu_count(logical=False)
    cpu_freq = psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {}
    load_avg = os.getloadavg() if hasattr(os, "getloadavg") else [None, None, None]
    memory = psutil.virtual_memory()._asdict()

    # Gather top 10 processes by CPU usage
    processes = []
    for proc in psutil.process_iter(
        attrs=["pid", "name", "cpu_percent", "memory_percent", "cmdline"]
    ):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sort processes by CPU usage, descending and get top 10
    top_processes = sorted(processes, key=lambda p: p["cpu_percent"], reverse=True)[:10]

    # Format command line nicely
    for p in top_processes:
        p["cmdline"] = " ".join(p["cmdline"]) if p["cmdline"] else ""

    return {
        "active": active,
        "cpu_overall_percent": cpu_overall_percent,
        "cpu_per_core_percent": cpu_per_core_percent,
        "cpu_count_logical": cpu_count_logical,
        "cpu_count_physical": cpu_count_physical,
        "cpu_freq": cpu_freq,
        "load_avg": load_avg,
        "memory": memory,
        "top_processes": top_processes,
    }


# ---------- ROUTES ----------


# Route to display index.html
@app.route("/")
def index():
    return render_template("index.html")


# Route to display tray management page
@app.route("/tray_mgmt")
def tray_mgmt():
    return render_template("tray_mgmt.html")


# Route to display stats page
@app.route("/stats-page")
def stats_page():
    return render_template("stats.html")


# Keep the REST endpoint for backward compatibility
@app.route("/stats")
def stats():
    return jsonify(get_system_stats())


# Health check logging route (commented out as in original)
@app.route('/logHealthCheckRPI', methods=['POST'])
def log_health_check_rpi():
    try:
        data = request.get_json()
        print("Received data:", data)

        if not data:
            return jsonify({"message": "No JSON data received"}), 400

        # Extract values with fallback defaults (for debugging phase)
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

        # Basic validation (optional)
        required_fields = ['rover_id', 'rpi_id', 'device_id', 'check_status', 'check_value', 'date_time']
        for field in required_fields:
            if data.get(field) is None:
                return jsonify({"message": f"Missing field: {field}"}), 400

        # Insert into database
        conn = get_db_connection()
        cursor = conn.cursor()

        insert_query = """
            INSERT INTO loghealthcheckrpi (
                rover_id, rpi_id, device_id, check_status, check_value,
                date_time, location_x, location_y, location_z, remarks
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(insert_query, (
            rover_id, rpi_id, device_id, check_status, check_value,
            date_time, location_x, location_y, location_z, remarks
        ))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Health check log inserted successfully"}), 201

    except Exception as e:
        print("Error:", e)
        traceback.print_exc()  # Logs full stack trace
        return jsonify({"message": "Server error", "error": str(e)}), 500
    
@app.route('/logActivity', methods=['POST'])
def log_activity():
    try:
        data = request.get_json()
        print("Received log activity data:", data)

        if not data:
            return jsonify({"message": "No JSON data received"}), 400

        # Required fields
        activity_id = data.get('activity_id')
        rover_id = data.get('rover_id')
        activity_type = data.get('activity_type')
        created_by = data.get('created_by')

        # Optional fields
        description = data.get('description')
        location_x = data.get('location_x')
        location_y = data.get('location_y')
        location_z = data.get('location_z')
        battery_percentage = data.get('battery_percentage')
        cpu_usage_percentage = data.get('cpu_usage_percentage')
        memory_usage_percentage = data.get('memory_usage_percentage')
        temperature = data.get('temperature')
        created_at = data.get('created_at')

        # Validation
        required_fields = ['activity_id', 'rover_id', 'activity_type', 'created_by']
        for field in required_fields:
            if data.get(field) is None:
                return jsonify({"message": f"Missing field: {field}"}), 400

        # Insert into DB
        conn = get_db_connection()
        cursor = conn.cursor()

        insert_query = """
            INSERT INTO log_activity (
                activity_id, rover_id, activity_type, description,
                location_x, location_y, location_z,
                battery_percentage, cpu_usage_percentage, memory_usage_percentage,
                temperature, created_at, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(insert_query, (
            activity_id, rover_id, activity_type, description,
            location_x, location_y, location_z,
            battery_percentage, cpu_usage_percentage, memory_usage_percentage,
            temperature, created_at, created_by
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Log activity inserted successfully", "activity_id": activity_id}), 201

    except Exception as e:
        print("Error in /logActivity:", e)
        traceback.print_exc()
        return jsonify({"message": "Server error", "error": str(e)}), 500
    
@app.route('/logError', methods=['POST'])
def log_error():
    try:
        data = request.get_json()
        print("Received error log data:", data)

        if not data:
            return jsonify({"message": "No JSON data received"}), 400

        # Required fields
        activity_id = data.get('activity_id')
        activity_type = data.get('activity_type')
        created_by = data.get('created_by')
        error_code = data.get('error_code')
        rover_id = data.get('rover_id')
        error_message = data.get('error_message')

        # Optional telemetry/context data
        location_x = data.get('location_x')
        location_y = data.get('location_y')
        location_z = data.get('location_z')
        battery_percentage = data.get('battery_percentage')
        cpu_usage_percentage = data.get('cpu_usage_percentage')
        memory_usage_percentage = data.get('memory_usage_percentage')
        temperature = data.get('temperature')
        created_at = data.get('created_at')

        # Basic validation
        required_fields = ['activity_id', 'activity_type', 'created_by', 'error_code', 'rover_id', 'error_message']
        for field in required_fields:
            if data.get(field) is None:
                return jsonify({"message": f"Missing required field: {field}"}), 400

        # Insert into database
        conn = get_db_connection()
        cursor = conn.cursor()

        insert_query = """
            INSERT INTO error_logs (
                activity_id, activity_type, created_by,
                error_code, rover_id, error_message,
                location_x, location_y, location_z,
                battery_percentage, cpu_usage_percentage, memory_usage_percentage,
                temperature, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(insert_query, (
            activity_id, activity_type, created_by,
            error_code, rover_id, error_message,
            location_x, location_y, location_z,
            battery_percentage, cpu_usage_percentage, memory_usage_percentage,
            temperature, created_at
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Error log inserted successfully"}), 201

    except Exception as e:
        print("Error in /logError:", e)
        traceback.print_exc()
        return jsonify({"message": "Server error", "error": str(e)}), 500


# Tray management route
@app.route("/get-table-array", methods=["POST"])
def get_table_array():
    data = request.get_json()
    trays = data.get("trays", {})
    print(data)
    tray_array = [f"T{value}" for value in trays.values() if value is not None]
    tray_value = [int(value) for value in trays.values() if value is not None]
    ACtx, ACTy, ACTz = (tray_value + [0, 0, 0])[:3]
    total_tables = len(tray_array)
    order_id = shortuuid.uuid()

    try:
        with sqlite3.connect("tray_orders.db") as conn:
            c = conn.cursor()
            c.execute(
                """INSERT INTO tray_orders 
                         (id, tray1_table_id, tray2_table_id, tray3_table_id, total_tables) 
                         VALUES (?, ?, ?, ?, ?)""",
                (order_id, trays.get("1"), trays.get("2"), trays.get("3"), total_tables),
            )
            conn.commit()
    except Exception as e:
        print(f"Error inserting into database: {e}")

    # Notify all WebSocket clients
    if ws_server and clients:
        ws_message = json.dumps({"order": order_id, 
                                 "tray": tray_array,
                                 "type": "waypoint_order",
                                 })
        for client in clients:
            try:
                ws_server.send_message(client, ws_message)
                way_log_activity(1004, x=ACtx, y=ACTy, z=ACTz)
            except Exception as e:
                log_error(1004,ecode=205, message="no waypoints sent from server to ros")    
        print(f"Sent tray order to {len(clients)} WebSocket clients.")

    return jsonify({"tray_array": tray_array, "order_id": order_id})

@app.route("/return-to-chef", methods=["POST"])
def return_to_chef():
    try:
        data = request.get_json()
        order_id = data.get("order_id")

        print(f"cancel_waypoint API called for return to chef, order ID {order_id}")

        try:
            if ws_server and clients:
                ws_message = json.dumps(
                    {
                        "type": "waypoint_cancel",
                        "publish": True,
                        "order_id": order_id
                    }
                )
                for client in clients:
                    try:
                        ws_server.send_message(client, ws_message)
                        way_log_activity(1006, message="cancel_waypoint return to chef")
                    except Exception as e:
                        log_error(1006,ecode=206, message="no waypoints cancel request sent from server to ros")
                print(
                    f"Sent table assignment notification to {len(clients)} WebSocket clients"
                )

            return (
                jsonify(
                    {
                        "status": "success",
                        "order_id": order_id,
                        "timestamp": time.time(),
                    }
                ),
                200,
            )

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"status": "error", "message": "Invalid request"}), 400

@app.route("/next-table", methods=["POST"])
def next_table():
    try:
        data = request.get_json()
        order_id = data.get("order_id")

        print(f"Next Table API called for return to chef, order ID {order_id}")

        try:

            if ws_server and clients:
                ws_message = json.dumps(
                    {
                        "type": "waypoint_next",
                        "publish": True,
                        "order_id": order_id
                    }
                )
                for client in clients:
                    ws_server.send_message(client, ws_message)
                print(
                    f"Sent table assignment notification to {len(clients)} WebSocket clients"
                )

            return (
                jsonify(
                    {
                        "status": "success",
                        "order_id": order_id,
                        "timestamp": time.time(),
                    }
                ),
                200,
            )

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"status": "error", "message": "Invalid request"}), 400




# Back to main page
@app.route("/return-home", methods=["POST"])
def return_home():
    try:
        data = request.get_json()
        order_id = data.get("order_id")

        print(f"Next Table API called for return to home, order ID {order_id}")
        try:

            if ws_server and clients:
                ws_message = json.dumps(
                    {
                        "type": "waypoint_next",
                        "publish": True,
                        "order_id": order_id
                    }
                )
                for client in clients:
                    ws_server.send_message(client, ws_message)
                print(
                    f"Sent table assignment notification to {len(clients)} WebSocket clients"
                )

            return (
                jsonify(
                    {
                        "status": "success",
                        "order_id": order_id,
                        "timestamp": time.time(),
                    }
                ),
                200,
            )

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"status": "error", "message": "Invalid request"}), 400


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


@socketio.on("connect")
def handle_connect():
    print("Client connected")


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")


@socketio.on("request_stats")
def handle_request_stats():
    emit("stats_update", get_system_stats())


# Background task to emit system stats every second
def background_task():
    print("Starting background stats task...")
    while not shutdown_event.is_set():
        try:
            socketio.emit("stats_update", get_system_stats())
            # Use a timeout so we can check the shutdown flag regularly
            shutdown_event.wait(1)
        except Exception as e:
            print(f"Error in background task: {e}")
            if not shutdown_event.is_set():
                time.sleep(5)  # Wait before retry if it's not a shutdown


# ---------- SIGNAL HANDLERS ----------


def signal_handler(sig, frame):
    print("\nShutting down gracefully...")

    # Set shutdown event for background threads
    shutdown_event.set()

    # Wait for background threads to finish
    for thread in background_threads:
        if thread.is_alive():
            print(f"Waiting for thread {thread.name} to finish...")
            thread.join(timeout=5)

    print("Shutdown complete.")
    sys.exit(0)


# Register the signal handlers
signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

# ---------- RUN THE APP ----------

if __name__ == "__main__":
    # Start background threads and keep track of them
    stats_thread = threading.Thread(
        target=background_task, daemon=True, name="stats_thread"
    )
    stats_thread.start()
    background_threads.append(stats_thread)

    ws_thread = threading.Thread(
        target=start_websocket_server, daemon=True, name="websocket_thread"
    )
    ws_thread.start()
    background_threads.append(ws_thread)

    # Add heartbeat thread
    # heartbeat_thread = threading.Thread(target=send_heartbeat, daemon=True, name="heartbeat_thread")
    # heartbeat_thread.start()
    # background_threads.append(heartbeat_thread)

    try:
        print("Starting Flask application...")
        socketio.run(app, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received...")
        # Let the signal handler do its job
    except Exception as e:
        print(f"Error starting application: {e}")
        # Set shutdown event and exit without using socketio.stop()
        shutdown_event.set()
        for thread in background_threads:
            if thread.is_alive():
                thread.join(timeout=2)
        sys.exit(1)
