import math

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

def is_hand_open(landmarks):
    finger_tips = [8, 12, 16, 20]
    finger_pips = [6, 10, 14, 18]
    open_count = 0
    for tip, pip in zip(finger_tips, finger_pips):
        if landmarks[tip].y < landmarks[pip].y:
            open_count += 1
    return open_count >= 4

def is_only_index_finger_open(landmarks):
    # Các đầu ngón tay: 8(trỏ), 12(giữa), 16(nhẫn), 20(út)
    # Các khớp pip: 6(trỏ), 10(giữa), 14(nhẫn), 18(út)
    
    # 1. Kiểm tra ngón trỏ phải MỞ
    index_open = landmarks[8].y < landmarks[6].y
    
    # 2. Kiểm tra các ngón còn lại phải ĐÓNG
    others_closed = (landmarks[12].y > landmarks[10].y and 
                     landmarks[16].y > landmarks[14].y and 
                     landmarks[20].y > landmarks[18].y)
    return index_open and others_closed

def generate_frames():
    cap = cv2.VideoCapture(0)

    # Khởi tạo các biến đếm
    fps_timer = time.time()
    frame_count = 0
    process_count = 0
    process_count_display = 0
    frame_count_display = 0
 
    with HandLandmarker.create_from_options(options) as landmarker:
        last_sent_data = {}
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
            start_ai = time.time()
            result = landmarker.detect_for_video(mp_image, timestamp_ms)
            process_count += 1
            t1 = int((time.time() - start_ai) * 1000)

            index_finger_tips = [] # Sẽ lưu: {'label': ..., 'x': ..., 'y': ...}
            mqtt_data = {} # Cập nhật trạng thái đèn và cửa

            if result.hand_landmarks:
                for i, hand_landmarks in enumerate(result.hand_landmarks):
                    hand_label = result.handedness[i][0].category_name
                    
                    # Vẽ xương bàn tay (Code cũ giữ nguyên)
                    for lm in hand_landmarks:
                        cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 3, (0, 255, 0), -1)

                    # XỬ LÝ ĐÈN
                    is_open = is_hand_open(hand_landmarks)
                    if hand_label == "Left":
                        mqtt_data["Living_light"] = 1 if is_open else 0
                    elif hand_label == "Right":
                        mqtt_data["Kitchen_light"] = 1 if is_open else 0

                    # Thu thập tọa độ ngón trỏ
                    index_tip = hand_landmarks[8]
                    index_finger_tips.append({'x': index_tip.x * w, 'y': index_tip.y * h})

                # XỬ LÝ CỬA (Chỉ chạy khi thấy đủ 2 tay)
                if len(index_finger_tips) == 2:
                    # Kiểm tra từng tay có đúng chỉ giơ ngón trỏ hay không
                    if is_only_index_finger_open(hand_landmarks):
                        index_tip = hand_landmarks[8]
                        index_finger_tips.append({'x': index_tip.x * w, 'y': index_tip.y * h})
                        p1 = index_finger_tips[0]
                        p2 = index_finger_tips[1]
                        dist = math.sqrt((p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2)
                        if dist < 100: 
                            mqtt_data["Door"] = 0
                        elif dist >= 100: 
                            mqtt_data["Door"] = 1
                    
                    # Vẽ đường nối để xác nhận hệ thống đang nhận diện đúng
                        cv2.line(frame, (int(p1['x']), int(p1['y'])), (int(p2['x']), int(p2['y'])), (255, 0, 0), 2)
                    else:
                        # Nếu tay này giơ nhiều hơn 1 ngón, ta coi như không hợp lệ cho việc mở cửa
                        pass 
                else:
                    # Nếu len != 2 (có thể là 0, 1 hoặc nhiều hơn do phát hiện sai), 
                    pass

            # Tính toán FPS
            if (time.time() - fps_timer) >= 1.0:
                frame_count_display = frame_count
                process_count_display = process_count
                fps_timer = time.time()
                frame_count = 0
                process_count = 0

            # Chỉ gửi MQTT khi có dữ liệu mới và khác với lần gửi trước đó
            if mqtt_data and mqtt_data != last_sent_data:
                start_mqtt = time.time()  
                client.publish("data", json.dumps(mqtt_data), qos=1) # QoS 1 để đảm bảo tin nhắn được gửi đi
                t2 = (time.time() - start_mqtt) * 1000
                last_sent_data = mqtt_data.copy()

                print(f"MQTT Sent: {mqtt_data} | AI Time: {t1:.2f} ms | MQTT Time: {t2:.2f} ms")

            cv2.putText(frame, f"FPS: {process_count_display}/{frame_count_display}", (20, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

            # Encode và gửi đến Web
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    
    cap.release()

@app.route('/')
# Trang chính hiển thị video và trạng thái
def index():
    return render_template('esp32.html')

@app.route('/video_feed')
def video_feed():
    # Trả về response với nội dung là luồng video được tạo bởi generator
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False) # Tắt debug khi dùng camera để tránh lỗi luồng