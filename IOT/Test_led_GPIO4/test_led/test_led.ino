#define LED_PIN 13

void setup() {
  pinMode(LED_PIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_PIN, HIGH);  // Bật LED
  delay(500);                   // 500 ms

  digitalWrite(LED_PIN, LOW);   // Tắt LED
  delay(500);                   // 500 ms
}
