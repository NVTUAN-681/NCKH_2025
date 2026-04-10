#include <ArduinoJson.h>
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <MQTTPubSubClient.h>
#include <ESP32Servo.h>

Servo myServo;
WebSocketsClient client;
MQTTPubSubClient mqtt;

const char* ssid = "Want";
const char* pass = "87654321";

#define Living_light 13
#define Kitchen_light 14
#define Door 18

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

  // Đăng ký nhận dữ liệu từ topic "data"
  mqtt.subscribe("data", [](const String& payload, const size_t size){
    Serial.print("Dữ liệu về: "); Serial.println(payload);
    uint32_t rececived_time = millis();

// {
//  "living_led":1,
//  "kitchen_led":0,
//  "door":1
// }

    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, payload);

    if(error){
      Serial.print(F("deserializeJson() failed: "));
      Serial.println(error.f_str());
      return;
    }

    JsonObject obj = doc.as<JsonObject>();

    if(obj.containsKey("t_sent")){
      double t_sent = doc["t_sent"];
      Serial.print("dữ liệu được nhận tại t = "); Serial.print(rececived_time);
    }

    Serial.print("Payload: "); Serial.println(payload);


    // Xử lý Đèn 1 (Living Room)
    if(obj.containsKey("Living_light")){
      bool val1 = doc["Living_light"];
      digitalWrite(Living_light, val1);
      mqtt.publish("status/Living_light", String(val1)); // Phản hồi trạng thái
    }

    // Xử lý Đèn 2 (Kitchen Room)
    if(obj.containsKey("Kitchen_light")){
      bool val2 = doc["Kitchen_light"];
      digitalWrite(Kitchen_light, val2);
      mqtt.publish("status/Kitchen_light", String(val2)); // Phản hồi trạng thái
    }

    // Xử lý Cửa (Servo)
    if(obj.containsKey("Door")){
      int doorPos = doc["Door"];
      if(doorPos == 1) {
          myServo.write(90); // Mở cửa
          Serial.println("Cửa: MỞ");
      } else {
          myServo.write(0);  // Đóng cửa
          Serial.println("Cửa: ĐÓNG");
      }
      mqtt.publish("status/Door", String(doorPos)); // Sửa lỗi String ở đây
    }
    StaticJsonDocument<100> resDoc;
    resDoc["status"] = "received";
    resDoc["esp_ms"] = rececived_time;
    if(obj.containsKey("t_sent")) resDoc["t_sent"] = doc["t_sent"]; // Trả lại để Python đối chiếu
    
    char buffer[128];
    serializeJson(resDoc, buffer);
    mqtt.publish("feedback", buffer);
  });
}


void loop(){
  mqtt.update(); 
  static uint32_t prev_ms = millis();
  if (millis() > prev_ms + 10000){
    prev_ms = millis();
    mqtt.publish("uptime", String(millis()/1000));
  }
}