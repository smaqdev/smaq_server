import signal
import sys
import threading
import asyncio
import subprocess
from flask import Flask, Response, send_file
from flask_cors import CORS
import websockets
import io
from PIL import Image, ImageDraw, ImageFont
import os
import time

app = Flask(__name__)
CORS(app)  # Enable CORS

# Variable for storing the latest JPEG frame
latest_frame = None

# Directory for saving images and video
img_dir = os.path.join(os.getcwd(), 'imgs')
os.makedirs(img_dir, exist_ok=True)  # Ensure the directory exists

# Path for saving the timelapse video
timelapse_video_path = os.path.join(os.getcwd(), 'timelapse_video.mp4')

# Flag to indicate if video generation is in progress
video_generation_lock = threading.Lock()
is_generating_video = False

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
    def generate():
        while True:
            if latest_frame:
                # Send JPEG data as raw bytes
                yield (b'--frame\r\n'
                       b'Content-Type:image/jpeg\r\n'
                       b'Content-Length: ' + f"{len(latest_frame)}".encode() + b'\r\n'
                       b'\r\n' + latest_frame + b'\r\n')
            else:
                time.sleep(0.1)  # Reduce CPU usage when no frame is available

    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/getthumb')
def get_thumbnail():
    if latest_frame:
        # Add watermark to the most recent frame
        frame = add_watermark(latest_frame)
        return Response(frame, mimetype='image/jpeg')
    else:
        # Return a 404 error if no frame is available
        return Response("No frame available", status=404)

@app.route('/')
def serve_index():
    return send_file('index.html')

@app.route('/timelapse_video/update')
def timelapse_video_update():
    global is_generating_video
    
    with video_generation_lock:
        if not is_generating_video:
            is_generating_video = True
            try:
                subprocess.run(['python', 'tl.py'], check=True)
            except subprocess.CalledProcessError as e:
                is_generating_video = False
                return Response(f"Error occurred while generating video: {str(e)}", status=500)
            finally:
                is_generating_video = False
                return Response("OK", status=200)

@app.route('/timelapse_video')
def timelapse_video():
    # Check if the timelapse video file exists
    if os.path.exists(timelapse_video_path):
        return send_file(
            timelapse_video_path,
            mimetype='video/mp4',  # Ensure correct MIME type for MP4
            as_attachment=False
        )
    else:
        return Response("Timelapse video could not be generated", status=500)

async def handle_client(websocket, path):
    global latest_frame, latest_frame_timestamp
    print("Client connected.")
    
    async for message in websocket:
        latest_frame = message
        latest_frame_timestamp = time.time()  # Update to the current time

async def start_websocket_server():
    async with websockets.serve(handle_client, "127.0.0.1", 8765):
        print("WebSocket server started on ws://127.0.0.1:8765")
        await asyncio.Future()  # Run forever

def save_images():
    while not shutdown_event.is_set():
        time.sleep(10)  # Save images every 10 seconds
        if latest_frame:
            # Save the most recent frame
            watermarked_frame = add_watermark(latest_frame)
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            file_path = os.path.join(img_dir, f'image_{timestamp}.jpg')
            with open(file_path, 'wb') as file:
                file.write(watermarked_frame)
            print(f"Saved image to {file_path}")

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
        app.run(host='127.0.0.1', port=5000, use_reloader=False)
    except KeyboardInterrupt:
        print("Server is shutting down...")
        shutdown_event.set()
        loop.call_soon_threadsafe(loop.stop)

if __name__ == '__main__':
    # Handle SIGINT (Ctrl+C) to gracefully shut down the server
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
    run_servers()
