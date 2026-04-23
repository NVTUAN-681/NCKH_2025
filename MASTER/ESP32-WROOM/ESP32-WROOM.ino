#include <ArduinoJson.h>
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <MQTTPubSubClient.h>
#include <ESP32Servo.h> 
#include <NTPClient.h>
#include <WiFiUdp.h>

WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org", 7 * 3600); // Múi giờ +7 (Việt Nam)

Servo myServo;
WebSocketsClient client;
MQTTPubSubClient mqtt;

const char* ssid = "Want";
const char* pass = "87654321";

#define Living_light 13
#define Kitchen_light 14
#define Door 18

// Biến lưu trữ trạng thái để đồng bộ
bool status_living = false;
bool status_kitchen = false;
int status_door = 0; // 0: Đóng, 1: Mở

struct DeviceSchedule {
    bool timerActive = false;
    long startTimeSec = -1; // Giờ bắt đầu tính bằng giây trong ngày
    long endTimeSec = -1;   // Giờ kết thúc tính bằng giây trong ngày
    long remainStart = 0;   // Giây còn lại đến khi BẬT
    long remainEnd = 0;     // Giây còn lại đến khi TẮT
};

DeviceSchedule schedLiving, schedKitchen, schedDoor;

long timeToSeconds(String timeStr) {
    if (timeStr == "") return -1;
    int firstColon = timeStr.indexOf(':');
    int hour = timeStr.substring(0, firstColon).toInt();
    int minute = timeStr.substring(firstColon + 1).toInt();
    return (hour * 3600L) + (minute * 60L);
}

void updateAndPublishSchedules() {
  timeClient.update();
  long now = (timeClient.getHours() * 3600L)
           + (timeClient.getMinutes() * 60L)
           + timeClient.getSeconds();

  // Lambda cập nhật thiết bị đèn
  auto updateLight = [&](DeviceSchedule &s, int pin, bool &statusVar) {
    if (!s.timerActive) return;

    bool inWindow = (now >= s.startTimeSec && now < s.endTimeSec);

    if (inWindow) {
      if (!statusVar) {              // Chỉ ghi khi trạng thái thay đổi
        digitalWrite(pin, HIGH);
        statusVar = true;
        Serial.printf("[SCHED] BẬT pin %d\n", pin);
      }
    } else if (now >= s.endTimeSec) {
      if (statusVar) {
        digitalWrite(pin, LOW);
        statusVar = false;
        Serial.printf("[SCHED] TẮT pin %d\n", pin);
      }
      s.timerActive = false;
    }
    // Tính lại giây còn lại (Web dùng để hiển thị)
    s.remainStart = max(0L, s.startTimeSec - now);
    s.remainEnd   = max(0L, s.endTimeSec   - now);
  };

  // Lambda cập nhật cửa servo
  auto updateDoor = [&](DeviceSchedule &s) {
    if (!s.timerActive) return;

    bool inWindow = (now >= s.startTimeSec && now < s.endTimeSec);

    if (inWindow) {
      if (status_door != 1) {
        myServo.write(90);
        status_door = 1;
        Serial.println("[SCHED] MỞ cửa");
      }
    } else if (now >= s.endTimeSec) {
      if (status_door != 0) {
        myServo.write(0);
        status_door = 0;
        Serial.println("[SCHED] ĐÓNG cửa");
      }
      s.timerActive = false;
    }
    s.remainStart = max(0L, s.startTimeSec - now);
    s.remainEnd   = max(0L, s.endTimeSec   - now);
  };

  updateLight(schedLiving,  Living_light,  status_living);
  updateLight(schedKitchen, Kitchen_light, status_kitchen);
  updateDoor(schedDoor);

  // Dùng publishFullStatus() duy nhất — tránh 2 format JSON
  publishFullStatus();
}

void publishFullStatus() {
  timeClient.update();
  String formattedTime = timeClient.getFormattedTime();
  long now = (timeClient.getHours() * 3600L)
           + (timeClient.getMinutes() * 60L)
           + timeClient.getSeconds();

  StaticJsonDocument<512> statusDoc;

  // Trạng thái thiết bị
  statusDoc["Living_light"]  = status_living;
  statusDoc["Kitchen_light"] = status_kitchen;
  statusDoc["Door"]          = status_door;
  statusDoc["esp_time"]      = formattedTime;
  statusDoc["status"]        = "synchronized";

  // Dữ liệu lịch trình — Web dùng để hiển thị đồng hồ đếm ngược
  // Living_light
  statusDoc["ll_active"]    = schedLiving.timerActive;
  statusDoc["ll_rem_start"] = schedLiving.timerActive ? max(0L, schedLiving.startTimeSec - now) : 0;
  statusDoc["ll_rem_end"]   = schedLiving.timerActive ? max(0L, schedLiving.endTimeSec   - now) : 0;

  // Kitchen_light
  statusDoc["kl_active"]    = schedKitchen.timerActive;
  statusDoc["kl_rem_start"] = schedKitchen.timerActive ? max(0L, schedKitchen.startTimeSec - now) : 0;
  statusDoc["kl_rem_end"]   = schedKitchen.timerActive ? max(0L, schedKitchen.endTimeSec   - now) : 0;

  // Door
  statusDoc["dr_active"]    = schedDoor.timerActive;
  statusDoc["dr_rem_start"] = schedDoor.timerActive ? max(0L, schedDoor.startTimeSec - now) : 0;
  statusDoc["dr_rem_end"]   = schedDoor.timerActive ? max(0L, schedDoor.endTimeSec   - now) : 0;

  char buffer[512];
  serializeJson(statusDoc, buffer);

  Serial.print("[SYNC] Gửi trạng thái lúc: ");
  Serial.println(formattedTime);

  mqtt.publish("home/state", buffer, false, 1); // QoS 1
}

void setup() {
  Serial.begin(115200);

  pinMode(Living_light, OUTPUT);
  pinMode(Kitchen_light, OUTPUT);

  myServo.attach(Door, 500, 2400);
  myServo.write(0); 

  Serial.print("connecting to wifi...");
  WiFi.begin(ssid, pass);
  while (WiFi.status() != WL_CONNECTED){
    Serial.print(".");
    delay(1000);
  }

  Serial.println(" connected! ");
  
  mqtt.begin(client);
  const char* mqtt_server = "6419f78d6e5e4affbebe010720192414.s1.eu.hivemq.cloud";
  client.beginSSL(mqtt_server, 8884, "/mqtt");
  client.setReconnectInterval(2000);

  Serial.print("connecting to mqtt broker...");
  while(!mqtt.connect("ESP32", "NCKH2026", "Nckh-2026")){
    Serial.print(".");
    delay(500);
  }
  Serial.println(" connected");

// Đăng ký nhận lệnh lẻ từ Web qua topic mới
// Đăng ký nhận lệnh từ Web (Topic nâng cấp)
   mqtt.subscribe("home/commands", [](const String& payload, const size_t size) {
    timeClient.update();
    Serial.println("\n------------------------------------");
    Serial.print("[CMD] Nhận lúc: "); Serial.println(timeClient.getFormattedTime());
    Serial.print("[PAYLOAD]: "); Serial.println(payload);

    StaticJsonDocument<512> doc;
    if (deserializeJson(doc, payload)) {
      Serial.println("[ERROR] JSON parse thất bại");
      return;
    }

    JsonObject obj = doc.as<JsonObject>();

    // ── 1. LỆNH TỨC THỜI (immediate control) ──────────────────
    if (obj.containsKey("Living_light")) {
      status_living = (int)obj["Living_light"] == 1;
      digitalWrite(Living_light, status_living);
      Serial.printf("[CMD] Living_light → %d\n", status_living);
    }
    if (obj.containsKey("Kitchen_light")) {
      status_kitchen = (int)obj["Kitchen_light"] == 1;
      digitalWrite(Kitchen_light, status_kitchen);
      Serial.printf("[CMD] Kitchen_light → %d\n", status_kitchen);
    }
    if (obj.containsKey("Door")) {
      status_door = (int)obj["Door"];
      myServo.write(status_door == 1 ? 90 : 0);
      Serial.printf("[CMD] Door → %d\n", status_door);
    }

    // ── 2. ĐẶT LỊCH TRÌNH ─────────────────────────────────────
    // Format Web gửi: { "device":"Living_light", "start_time":"22:00", "end_time":"06:00" }
    if (obj.containsKey("start_time") && obj.containsKey("end_time") && obj.containsKey("device")) {
      String device    = obj["device"].as<String>();
      long   startSec  = timeToSeconds(obj["start_time"].as<String>());
      long   endSec    = timeToSeconds(obj["end_time"].as<String>());

      // Xử lý qua đêm: nếu endSec <= startSec, cộng thêm 1 ngày (86400s)
      if (endSec <= startSec) endSec += 86400L;

      DeviceSchedule* target = nullptr;
      if      (device == "Living_light")  target = &schedLiving;
      else if (device == "Kitchen_light") target = &schedKitchen;
      else if (device == "Door")          target = &schedDoor;

      if (target) {
        target->startTimeSec = startSec;
        target->endTimeSec   = endSec;
        target->timerActive  = true;
        Serial.printf("[SCHED] Đặt lịch %s: %s → %s\n",
          device.c_str(),
          obj["start_time"].as<const char*>(),
          obj["end_time"].as<const char*>());
      }
    }

    // ── 3. HỦY LỊCH TRÌNH ─────────────────────────────────────
    // Format Web gửi: { "action":"cancel_schedule", "device":"Living_light" }
    if (obj["action"] == "cancel_schedule" && obj.containsKey("device")) {
      String device = obj["device"].as<String>();
      DeviceSchedule* target = nullptr;
      if      (device == "Living_light")  target = &schedLiving;
      else if (device == "Kitchen_light") target = &schedKitchen;
      else if (device == "Door")          target = &schedDoor;

      if (target) {
        target->timerActive  = false;
        target->startTimeSec = -1;
        target->endTimeSec   = -1;
        target->remainStart  = 0;
        target->remainEnd    = 0;
        Serial.printf("[SCHED] Đã hủy lịch: %s\n", device.c_str());
      }
    }

    // Phản hồi trạng thái ngay sau khi xử lý lệnh
    publishFullStatus();
    Serial.println("------------------------------------");
  });
}


void loop() {
  client.loop();
  mqtt.update();

  // WiFi reconnect non-blocking (không dùng delay)
  static uint32_t lastWifiRetry = 0;
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastWifiRetry >= 5000) {
      lastWifiRetry = millis();
      Serial.println("[WARN] Mất WiFi, thử kết nối lại...");
      WiFi.begin(ssid, pass);
    }
    return; // Chưa có WiFi thì không làm gì thêm
  }

  // Đồng bộ mỗi 1 giây
  static uint32_t lastTick = 0;
  if (millis() - lastTick >= 1000) {
    lastTick = millis();
    timeClient.update();
    updateAndPublishSchedules(); // Tính lịch + gửi state gộp

    // Heartbeat mỗi 10 giây
    static int hbCount = 0;
    if (++hbCount >= 10) {
      hbCount = 0;
      mqtt.publish("home/heartbeat", String(millis() / 1000));
    }
  }
}