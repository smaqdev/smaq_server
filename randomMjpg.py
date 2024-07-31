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
    frame = video_clip.get_frame(frame_number / video_clip.fps)
    image = Image.fromarray(np.uint8(frame))
    
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=45)
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
            frame_count = 0
            one_second_timer = time.time()
            one_second_frame_count = 0
            
            for frame_number in range(total_frames):
                frame_start_time = time.time()
                
                image_buffer = await get_frame_as_jpeg(video_clip, frame_number)
                image_data = image_buffer.getvalue()
                await websocket.send(image_data)
                
                frame_count += 1
                one_second_frame_count += 1
                elapsed_time = time.time() - start_time
                frame_elapsed_time = time.time() - frame_start_time
                
                if time.time() - one_second_timer >= 1.0:
                    print(f"Frames in last second: {one_second_frame_count}")
                    one_second_timer = time.time()
                    one_second_frame_count = 0
                
                await asyncio.sleep(max(0, (frame_number / video_clip.fps) - elapsed_time))
            
            # 프레임 레이트 로깅
            total_time = time.time() - start_time
            frame_rate = frame_count / total_time
            print(f"Frame rate: {frame_rate:.2f} fps")
            
            video_clip = VideoFileClip(video_path)

async def main():
    server_uri = 'ws://127.0.0.1:8765/testsession'
    video_path = 'sample.mp4'
    await send_video_frames(server_uri, video_path)

if __name__ == "__main__":
    asyncio.run(main())
