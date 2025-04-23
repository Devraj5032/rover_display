from flask import Flask, request, jsonify
from flask_cors import CORS
import psutil
import os
import platform

app = Flask(__name__)
CORS(app)

@app.route('/get-table-array', methods=['POST'])
def get_table_array():
    data = request.get_json()
    trays = data.get('trays', {})
    print(trays)
    tray_array = [trays.get(i, None) for i in range(1, 4)]
    return jsonify(tray_array)


@app.route("/stats")
def stats():
    return jsonify({
        "cpu_overall_percent": psutil.cpu_percent(interval=1),
        "cpu_per_core_percent": psutil.cpu_percent(interval=1, percpu=True),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {},
        "cpu_times": psutil.cpu_times()._asdict(),
        "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else [None, None, None],
        "memory": psutil.virtual_memory()._asdict()
    })


@app.route("/shutdown", methods=["POST"])
def shutdown():
    system = platform.system()
    if system == "Windows":
        os.system("shutdown /s /t 1")
    elif system == "Linux":
        os.system("sudo shutdown now")
    return jsonify({"message": "Shutting down..."})

if __name__ == '__main__':
    app.run(debug=True)
