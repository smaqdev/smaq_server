import subprocess
import os
import sys

def create_video_from_images(image_folder, output_video_path, fps=60):
    # 이미지 파일 목록 가져오기
    image_files = [f for f in os.listdir(image_folder) if f.endswith(('.png', '.jpg', '.jpeg'))]
    
    # 이미지 파일을 이름 기준으로 정렬 (이미 정렬된 경우 이 단계는 생략 가능)
    image_files.sort()
    
    if not image_files:
        print(f"이미지 파일이 {image_folder}에 없습니다.")
        return

    # 정렬된 이미지 파일 목록을 파일에 기록
    list_file_path = 'image_list.txt'
    with open(list_file_path, 'w') as list_file:
        for image_file in image_files:
            list_file.write(f"file '{os.path.join(image_folder, image_file)}'\n")
    
    # FFmpeg 명령어 구성
    command = [
        'ffmpeg',
        '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', list_file_path,
        '-framerate', str(fps),
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        output_video_path
    ]
    
    # FFmpeg 명령어 실행
    try:
        subprocess.run(command, check=True)
        print(f"비디오가 {output_video_path}로 생성되었습니다.")
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg 명령어 실행 중 오류 발생: {e}")
    
    # 임시 목록 파일 삭제
    os.remove(list_file_path)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("사용법: python tl.py <image_folder> <output_video_path>")
        sys.exit(1)
    
    image_folder = sys.argv[1]
    output_video_path = sys.argv[2]

    create_video_from_images(image_folder, output_video_path)
