import websocket
import json
import time

def on_message(ws, message):
    print("Received:", message)

def on_error(ws, error):
    print("Error:", error)

def on_close(ws, close_status_code, close_msg):
    print("### WebSocket Closed ###")

def on_open(ws):
    print("WebSocket connection opened.")
    test_data = {
        "type": "waypoint_result",
        "order": "test_order_id",
        "sequence": [1, 2, 3]
    }
    ws.send(json.dumps(test_data))
    print("Test message sent.")

if __name__ == "__main__":
    ws_url = "ws://localhost:48236"  # Change if using a different port
    ws = websocket.WebSocketApp(ws_url,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever()
