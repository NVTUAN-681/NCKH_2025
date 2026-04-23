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
# ============================================================
# PHẦN KHỞI TẠO MQTT — SỬA ĐỔI
# Xóa client.connect() thứ 2 bị gọi thừa trong on_message block
# Tách on_message ra khỏi block khởi tạo cho rõ ràng
# ============================================================

BROKER          = "6419f78d6e5e4affbebe010720192414.s1.eu.hivemq.cloud"
Web_Sockets_PORT = 8884
PORT            = 8883
TOPIC_COMMAND   = "home/commands"

client = mqtt.Client(transport="websockets")
client.ws_set_options(path="/mqtt")
client.tls_set()
client.username_pw_set("NCKH2026", "Nckh-2026")

def on_connect(c, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Đã kết nối HiveMQ")
        c.subscribe("home/state")   # Nhận state để đồng bộ current_state
        c.subscribe("feedback")
    else:
        print(f"[MQTT] Lỗi kết nối: rc={rc}")

def on_message(c, userdata, msg):
    """Nhận trạng thái thực tế từ ESP32 để đồng bộ current_state."""
    if msg.topic == "feedback":
        try:
            data = json.loads(msg.payload)
            if "t_sent" in data:
                rtt     = (time.time() * 1000) - data["t_sent"]
                latency = rtt / 2
                print(f"--- LATENCY: {latency:.2f} ms (RTT: {rtt:.2f} ms) ---")
        except Exception as e:
            print(f"[ERROR] feedback parse: {e}")

    elif msg.topic == "home/state":
        # Đồng bộ current_state từ ESP32 — tránh lệch khi có nguồn điều khiển khác
        try:
            data = json.loads(msg.payload)
            if "Living_light"  in data: current_state["Living_light"]  = int(data["Living_light"])
            if "Kitchen_light" in data: current_state["Kitchen_light"] = int(data["Kitchen_light"])
            if "Door"          in data: current_state["Door"]          = int(data["Door"])
        except Exception as e:
            print(f"[ERROR] state sync: {e}")

client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, Web_Sockets_PORT)  # Chỉ gọi 1 lần duy nhất
client.loop_start()

# Trạng thái thực tế — được đồng bộ từ ESP32 qua home/state
current_state = {
    "Living_light":  0,
    "Kitchen_light": 0,
    "Door":          0
}

# Cooldown: thời điểm gửi lệnh gần nhất cho từng thiết bị
last_sent_time = {
    "Living_light":  0.0,
    "Kitchen_light": 0.0,
    "Door":          0.0
}
GESTURE_COOLDOWN = 1.2  # giây


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

# ============================================================
# HÀM MỚI: is_thumb_and_index_only(landmarks)
# Kiểm tra CHỈ ngón cái và ngón trỏ được giơ lên
# Dùng cho cử chỉ mở/đóng cửa với 1 bàn tay
# ============================================================
def is_thumb_and_index_only(landmarks):
    # Ngón cái (tip=4, khớp=3): so sánh trục x (ngang)
    # Vì frame đã flip, ngón cái mở ra = tip.x < mcp.x
    thumb_open = landmarks[4].x < landmarks[3].x

    # Ngón trỏ (tip=8, pip=6): giơ thẳng = tip.y < pip.y
    index_open = landmarks[8].y < landmarks[6].y

    # Các ngón còn lại phải GẬP
    others_closed = (landmarks[12].y > landmarks[10].y and
                     landmarks[16].y > landmarks[14].y and
                     landmarks[20].y > landmarks[18].y)

    return thumb_open and index_open and others_closed

# ============================================================
# HÀM MỚI: get_thumb_index_distance(landmarks, frame_w)
# Tính khoảng cách chuẩn hóa giữa đầu ngón cái (4) và ngón trỏ (8)
# Trả về tỉ lệ 0.0–1.0 so với chiều rộng frame
# ============================================================
def get_thumb_index_distance(landmarks, frame_w):
    dx   = (landmarks[4].x - landmarks[8].x) * frame_w
    dy   = (landmarks[4].y - landmarks[8].y) * frame_w
    dist = math.sqrt(dx * dx + dy * dy)
    return dist / frame_w  # Chuẩn hóa để độc lập với độ phân giải camera

def generate_frames():
    cap = cv2.VideoCapture(0)

    fps_timer             = time.time()
    frame_count           = 0
    process_count         = 0
    process_count_display = 0
    frame_count_display   = 0

    # Ngưỡng khoảng cách chuẩn hóa cho cử chỉ cửa
    DOOR_OPEN_THRESHOLD  = 0.20  # Tỉ lệ so với frame_w → mở cửa
    DOOR_CLOSE_THRESHOLD = 0.08  # Tỉ lệ so với frame_w → đóng cửa
 
    with HandLandmarker.create_from_options(options) as landmarker:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break

            frame_count += 1
            frame        = cv2.flip(frame, 1)
            h, w, _      = frame.shape
            rgb          = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image     = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            timestamp_ms = int(time.time() * 1000)
            start_ai     = time.time()
            result       = landmarker.detect_for_video(mp_image, timestamp_ms)
            process_count += 1
            t1           = int((time.time() - start_ai) * 1000)

            # ── RESET mỗi frame — tránh dùng giá trị từ frame trước ──
            commands_to_send = {}  # {device: value} — gom tất cả lệnh trong frame

            if result.hand_landmarks:
                for i, hand_landmarks in enumerate(result.hand_landmarks):
                    hand_label = result.handedness[i][0].category_name
                    # MediaPipe trả nhãn theo gương nên Left/Right đảo chiều với người dùng
                    # hand_label == "Left"  → tay phải người dùng  → Kitchen_light
                    # hand_label == "Right" → tay trái người dùng  → Living_light

                    # Vẽ landmarks
                    for lm in hand_landmarks:
                        cv2.circle(frame,
                                   (int(lm.x * w), int(lm.y * h)),
                                   3, (0, 255, 0), -1)

                    # ── Ưu tiên 1: Cử chỉ cửa (1 tay, cái + trỏ) ────────
                    if is_thumb_and_index_only(hand_landmarks):
                        dist = get_thumb_index_distance(hand_landmarks, w)

                        # Vẽ đường nối cái–trỏ để debug trực quan
                        pt_thumb = (int(hand_landmarks[4].x * w),
                                    int(hand_landmarks[4].y * h))
                        pt_index = (int(hand_landmarks[8].x * w),
                                    int(hand_landmarks[8].y * h))
                        cv2.line(frame, pt_thumb, pt_index, (0, 165, 255), 2)
                        cv2.putText(frame,
                                    f"Door dist: {dist:.2f}",
                                    (pt_thumb[0] - 40, pt_thumb[1] - 20),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 165, 255), 2)

                        if dist > DOOR_OPEN_THRESHOLD:
                            commands_to_send["Door"] = 1
                        elif dist < DOOR_CLOSE_THRESHOLD:
                            commands_to_send["Door"] = 0
                        # Khoảng giữa 2 ngưỡng: không gửi — tránh lệnh không rõ ràng
                        continue  # Tay này đã xử lý cửa, bỏ qua kiểm tra đèn

                    # ── Ưu tiên 2: Cử chỉ đèn (tay mở/đóng) ─────────────
                    is_open    = is_hand_open(hand_landmarks)
                    new_val    = 1 if is_open else 0

                    if hand_label == "Right":   # Tay trái người dùng
                        commands_to_send["Living_light"] = new_val
                    elif hand_label == "Left":  # Tay phải người dùng
                        commands_to_send["Kitchen_light"] = new_val

            # ── Gửi lệnh (có cooldown + so sánh state) ───────────────────
            now = time.time()
            for device, new_val in commands_to_send.items():
                # Chỉ gửi nếu: trạng thái thay đổi VÀ đã qua cooldown
                if (new_val != current_state[device] and
                        now - last_sent_time[device] >= GESTURE_COOLDOWN):

                    current_state[device]   = new_val
                    last_sent_time[device]  = now

                    payload = {
                        device:   new_val,
                        "t_sent": time.time() * 1000
                    }
                    client.publish(TOPIC_COMMAND, json.dumps(payload), qos=1)
                    print(f"[MQTT] Gửi: {device} → {new_val}")

            # ── FPS counter ───────────────────────────────────────────────
            if (time.time() - fps_timer) >= 1.0:
                frame_count_display   = frame_count
                process_count_display = process_count
                fps_timer    = time.time()
                frame_count  = 0
                process_count = 0

            # ── Hiển thị trạng thái lên frame ────────────────────────────
            state_text = (f"L:{current_state['Living_light']} "
                          f"K:{current_state['Kitchen_light']} "
                          f"D:{current_state['Door']}")
            cv2.putText(frame, f"FPS: {process_count_display}/{frame_count_display}",
                        (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
            cv2.putText(frame, state_text,
                        (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            # ── Encode và yield cho Flask ─────────────────────────────────
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