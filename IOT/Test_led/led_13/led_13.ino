#define LED_PIN_13 13
// #define LED_PIN_4 4

void setup() 
{
// pinMode(LED_PIN_4, OUTPUT);   
pinMode(LED_PIN_13, OUTPUT); 
}  

void loop() {   
  // digitalWrite(LED_PIN_4, LOW);  // Bật LED 
  digitalWrite(LED_PIN_13, LOW);
  // Serial.write("off");
  delay(500);
  digitalWrite(LED_PIN_13, HIGH);
  // Serial.write("on");
  delay(500);
}

// đoạn code này của tôi có chính xác không