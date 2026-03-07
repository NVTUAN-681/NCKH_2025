from flask import Flask, render_template, Response
import cv2
import mediapipe as mp
import json
import time
import numpy as np
import paho.mqtt.client as mqtt
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

app = Flask(__name__)

# ===== CẤU HÌNH MEDIAPIPE =====
MODEL_PATH = "hand_landmarker.task"
BaseOptions = python.BaseOptions
HandLandmarker = vision.HandLandmarker
HandLandmarkerOptions = vision.HandLandmarkerOptions
VisionRunningMode = vision.RunningMode

options = HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=VisionRunningMode.VIDEO,
    num_hands=2,
    min_hand_detection_confidence=0.6,
    min_hand_presence_confidence=0.6,
    min_tracking_confidence=0.6
)
# ===== CẤU HÌNH MQTT =====
BROKER = "6419f78d6e5e4affbebe010720192414.s1.eu.hivemq.cloud"
Web_Sockets_PORT = 8884
PORT = 8883

client = mqtt.Client(transport="websockets")
client.ws_set_options(path="/mqtt")
client.tls_set()  
client.username_pw_set("NCKH2026", "Nckh-2026")
client.connect(BROKER, Web_Sockets_PORT)
client.loop_start()

def send_led_command(state):
    pay_load = json.dumps({"led1": state})
    client.publish("data", pay_load, qos=1)


def is_hand_open(landmarks):
    finger_tips = [8, 12, 16, 20]
    finger_pips = [6, 10, 14, 18]
    open_count = 0
    for tip, pip in zip(finger_tips, finger_pips):
        if landmarks[tip].y < landmarks[pip].y:
            open_count += 1
    return open_count >= 3

def generate_frames():
    cap = cv2.VideoCapture(0)
    # Khởi tạo các biến đếm
    fps_timer = time.time()
    frame_count = 0
    process_count = 0
    status = 0
    last_status = -1
    process_count_display = 0
    frame_count_display = 0
 
    with HandLandmarker.create_from_options(options) as landmarker:
        while cap.isOpened():
            success, frame = cap.read()
            if not success: break
            
            frame_count += 1
            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            # Xử lý AI
            timestamp_ms = int(time.time() * 1000)
            result = landmarker.detect_for_video(mp_image, timestamp_ms)
            process_count += 1

            open_hands = 0
            fist_hands = 0

            if result.hand_landmarks:
                for hand_landmarks in result.hand_landmarks:
                    for lm in hand_landmarks:
                        cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 4, (0, 255, 0), -1)
                    
                    if is_hand_open(hand_landmarks):
                        open_hands += 1
                    else:
                        fist_hands += 1

            # Logic điều khiển trạng thái
            if fist_hands >= 1:
                status = 0
            elif open_hands >= 1:
                status = 1

            # Chỉ gửi MQTT khi trạng thái thay đổi
            if status != last_status:
                send_led_command(status)
                last_status = status

            # Hiển thị thông tin lên khung hình
            text = "ON (1)" if status else "OFF (0)"
            color = (0, 255, 0) if status else (0, 0, 255)
            cv2.putText(frame, f"STATUS: {text}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

            # Tính toán FPS
            if (time.time() - fps_timer) >= 1.0:
                frame_count_display = frame_count
                process_count_display = process_count
                fps_timer = time.time()
                frame_count = 0
                process_count = 0
            
            cv2.putText(frame, f"FPS: {process_count_display}/{frame_count_display}", (20, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

            # Encode và gửi đến Web
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    
    cap.release()

@app.route('/')
# Trang chủ trả về template HTML chứa giao diện và khung hiển thị video
def index():
    return render_template('esp32.html')

@app.route('/video_feed')
def video_feed():
    # Trả về response với nội dung là luồng video được tạo bởi generator
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False) # Tắt debug khi dùng camera để tránh lỗi luồng