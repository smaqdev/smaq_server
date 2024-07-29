import io
import numpy as np
import asyncio
import websockets
from PIL import Image
import time
from moviepy.editor import VideoFileClip

async def get_frame_as_jpeg(video_clip, frame_number):
    """
    주어진 비디오 클립에서 특정 프레임 번호에 해당하는 이미지를 JPEG 포맷으로 반환합니다.
    """
    # 프레임을 이미지로 추출합니다.
    frame = video_clip.get_frame(frame_number / video_clip.fps)
    image = Image.fromarray(np.uint8(frame))
    
    # 이미지를 바이트 스트림으로 변환합니다.
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=75)  # Adjust quality for speed/size trade-off
    buffer.seek(0)
    return buffer

async def send_video_frames(ws_uri, video_path):
    """
    MP4 비디오 파일의 프레임을 순차적으로 JPEG로 변환하여 WebSocket 서버에 전송합니다.
    """
    async with websockets.connect(ws_uri) as websocket:
        video_clip = VideoFileClip(video_path)
        total_frames = int(video_clip.fps * video_clip.duration)
        
        while True:
            start_time = time.time()
            
            for frame_number in range(total_frames):
                image_buffer = await get_frame_as_jpeg(video_clip, frame_number)
                
                # 이미지를 WebSocket을 통해 전송합니다.
                image_data = image_buffer.getvalue()
                await websocket.send(image_data)
                #print("Image sent.")
                
                # 프레임 속도를 맞추기 위한 대기 시간 계산
                elapsed_time = time.time() - start_time
                await asyncio.sleep(max(0, (frame_number / video_clip.fps) - elapsed_time))  # Maintain frame rate
            
            # 비디오가 끝나면 처음부터 반복
            video_clip = VideoFileClip(video_path)  # Re-open the video clip

async def main():
    server_uri = 'ws://127.0.0.1:8765/anothersession'  # WebSocket 서버 URI
    video_path = 'sample2.mp4'  # MP4 비디오 파일 경로
    await send_video_frames(server_uri, video_path)

if __name__ == "__main__":
    asyncio.run(main())
