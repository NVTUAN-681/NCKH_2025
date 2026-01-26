#define led_1 21
#define led_2 22
#define led_3 23

void setup() {
  // put your setup code here, to run once:
  pinMode(led_1, OUTPUT);
  pinMode(led_2, OUTPUT);
  pinMode(led_3, OUTPUT);

}

void loop() {
  digitalWrite(led_1, HIGH);
  delay(1000);
  // digitalWrite(led_1, LOW);
  // delay(1000);

  digitalWrite(led_2, HIGH);
  delay(1000);
  // digitalWrite(led_2, LOW);
  // delay(1000);

  digitalWrite(led_3, HIGH);
  delay(1000);
  digitalWrite(led_3, LOW);
  digitalWrite(led_2, LOW);
  digitalWrite(led_1, LOW);
  delay(1000);
  

  // delay(1000);

}
