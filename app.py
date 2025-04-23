from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app) 

@app.route('/get-table-array', methods=['POST'])
def get_table_array():
    data = request.get_json()
    trays = data.get('trays', {})

    print(trays)

    tray_array = [trays.get(i, None) for i in range(1, 4)]

    return jsonify(tray_array)

if __name__ == '__main__':
    app.run(debug=True)
