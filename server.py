import signal
import sys
import threading
import asyncio
import subprocess
from flask import Flask, Response, send_file, jsonify, request
from flask_cors import CORS
import websockets
import io
from PIL import Image, ImageDraw, ImageFont
import os
import time
from datetime import datetime, timedelta

IP = "100.105.43.90" # vpn ip
httpPort = 5000
socketPort = 8765

sendCount = 0
recvCount = 0

app = Flask(__name__)
CORS(app)  # Enable CORS

# Base directory for saving images and videos
base_dir = os.path.join(os.getcwd(), 'sessions')
os.makedirs(base_dir, exist_ok=True)  # Ensure the base directory exists

# Dictionary to store sessions data
sessions = {}

class Session:
    def __init__(self, session_id):
        self.session_id = session_id
        self.latest_frame = None
        self.last_received_time = datetime.now()
        self.img_dir = os.path.join(base_dir, session_id, 'imgs')
        os.makedirs(self.img_dir, exist_ok=True)  # Ensure the session's image directory exists
        self.timelapse_video_path = os.path.join(base_dir, session_id, 'timelapse_video.mp4')

def add_watermark(image_bytes):
    # Load the image from bytes
    image = Image.open(io.BytesIO(image_bytes))
    draw = ImageDraw.Draw(image)
    
    # Define watermark text and position
    font = ImageFont.load_default()
    watermark_text = time.strftime('%Y-%m-%d %H:%M:%S')
    
    # Calculate text size
    text_width, text_height = draw.textbbox((0, 0), watermark_text, font=font)[2:]
    
    width, height = image.size
    position = (width - text_width - 10, height - text_height - 10)
    
    # Add watermark to image
    draw.text(position, watermark_text, font=font, fill='white')
    
    # Save image to bytes
    with io.BytesIO() as output:
        image.save(output, format='JPEG')
        return output.getvalue()

@app.route('/video_feed.mjpg')
def video_feed():
    session_id = request.args.get('session_id')
    if not session_id:
        return Response("Session ID is required", status=400)
    session = sessions.get(session_id)
    def generate(frameLen):
        global sendCount
        while True:
            if frameLen > 0:
                yield (b'--frame\r\n'
                       b'Content-Type:image/jpeg\r\n'
                       b'Content-Length: ' + f"{frameLen}".encode() + b'\r\n'
                       b'\r\n' + session.latest_frame + b'\r\n')
                sendCount+=1
            else:
                time.sleep(0.1)  # Reduce CPU usage when no frame is available

    return Response(generate(len(session.latest_frame)),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/getthumb')
def get_thumbnail():
    session_id = request.args.get('session_id')
    if not session_id:
        return Response("Session ID is required", status=400)

    session = sessions.get(session_id)
    if session and session.latest_frame:
        # Add watermark to the most recent frame
        frame = add_watermark(session.latest_frame)
        return Response(frame, mimetype='image/jpeg')
    else:
        # Return a 404 error if no frame is available
        return Response("No frame available", status=404)

@app.route('/')
def serve_index():
    return send_file('index.html')

@app.route('/camera.html')
def serve_stream():
    return send_file('camera.html')

@app.route('/timelapse.html')
def serve_timelapse():
    return send_file('timelapse.html')

@app.route('/timelapse_video/update')
def timelapse_video_update():
    session_id = request.args.get('session_id')
    if not session_id:
        return Response("Session ID is required", status=400)

    session = sessions.get(session_id)
    
    if not session:
        return Response(f"Session {session_id} does not exist", status=404)

    if os.path.exists(session.timelapse_video_path):
        os.remove(session.timelapse_video_path)

    try:
        subprocess.run(['python', 'tl.py', session.img_dir, session.timelapse_video_path], check=True)
    except subprocess.CalledProcessError as e:
        return Response(f"Error occurred while generating video: {str(e)}", status=500)
    
    return Response("OK", status=200)

@app.route('/timelapse_video')
def timelapse_video():
    session_id = request.args.get('session_id')
    if not session_id:
        return Response("Session ID is required", status=400)

    session = sessions.get(session_id)
    
    if not session:
        return Response(f"Session {session_id} does not exist", status=404)

    if os.path.exists(session.timelapse_video_path):
        return send_file(
            session.timelapse_video_path,
            mimetype='video/mp4',  # Ensure correct MIME type for MP4
            as_attachment=False
        )
    else:
        return Response("Timelapse video could not be generated", status=500)

@app.route('/activated')
def get_activated_sessions():
    active_sessions = []
    for session_id, session in sessions.items():
        active_sessions.append({
            "server_ip": f"{IP}:{httpPort}",
            "session_id": session_id
        })
    return jsonify(active_sessions)

async def handle_client(websocket, path):
    global recvCount
    session_id = path.strip('/')
    print(f"Client connected for session {session_id}.")
    
    if session_id not in sessions:
        sessions[session_id] = Session(session_id)
    
    session = sessions[session_id]
    
    try:
        async for message in websocket:
            session.latest_frame = message
            session.last_received_time = datetime.now()
            recvCount+=1
    finally:
        print(f"Client disconnected for session {session_id}.")

async def start_websocket_server():
    async with websockets.serve(handle_client, IP, socketPort):
        print(f"WebSocket server started on ws://{IP}:{socketPort}")
        await asyncio.Future()  # Run forever

def save_images():
    while not shutdown_event.is_set():
        time.sleep(10)  # Save images every 10 seconds
        for session_id, session in list(sessions.items()):
            if datetime.now() - session.last_received_time > timedelta(minutes=10):
                # Remove session if no new frame received in the last 10 minutes
                del sessions[session_id]
                print(f"Session {session_id} removed due to inactivity.")
                continue
            
            if session.latest_frame:
                # Save the most recent frame
                watermarked_frame = add_watermark(session.latest_frame)
                timestamp = time.strftime('%Y%m%d_%H%M%S')
                file_path = os.path.join(session.img_dir, f'image_{timestamp}.jpg')
                with open(file_path, 'wb') as file:
                    file.write(watermarked_frame)
                print(f"Saved image to {file_path} for session {session_id}")
        print(f'send_frame : {sendCount}, recv_frame : {recvCount}')
        print(f'send_frame/s : {sendCount/10}, recv_frame/s : {recvCount/10}')

def run_servers():
    loop = asyncio.new_event_loop()
    global shutdown_event
    shutdown_event = threading.Event()

    # Start WebSocket server in a separate thread
    threading.Thread(target=lambda: loop.run_until_complete(start_websocket_server()), daemon=True).start()
    
    # Start image saving in a separate thread
    threading.Thread(target=save_images, daemon=True).start()
    
    # Start Flask HTTP server
    try:
        app.run(host=IP, port=httpPort, use_reloader=False)
    except KeyboardInterrupt:
        print("Server is shutting down...")
        shutdown_event.set()
        loop.call_soon_threadsafe(loop.stop)

if __name__ == '__main__':
    # Handle SIGINT (Ctrl+C) to gracefully shut down the server
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
    run_servers()
