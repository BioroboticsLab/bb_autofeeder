#include <Arduino.h>
#include <Preferences.h>
Preferences prefs;

const int pumpPin = 23;  // GPIO-Pin, der mit dem MOSFET-Gate verbunden ist
#define TOUCH_PIN T0
#define EN_PIN 18
#define BUTTON_HIGH 27
#define BUTTON_IN 33
#define LED_BUILTIN 2

// PWM settings
const int freq = 50; // PWM-Frequenz in Hz
const int resolution = 8;
const int dutyCycle = 125; // ~67% von 255 für ca. 6V
// Sensor settings
int overflow_protect = 0;
int emptyCapacitiveValue = 0;
int fullCapacitiveValue = 45;

void setup() {
  // Serieller Monitor zur Debugging-Ausgabe
  Serial.begin(115200);

  // LEDC PWM initialisieren und Pin zuweisen
    if (ledcAttach(pumpPin, freq, resolution)) {
    Serial.println("LEDC erfolgreich konfiguriert!");
  } else {
    Serial.println("Fehler bei der LEDC-Konfiguration!");
  }
  
  pinMode(EN_PIN, OUTPUT);
  pinMode(BUTTON_HIGH, OUTPUT);
  pinMode(BUTTON_IN, INPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(EN_PIN, HIGH);
  digitalWrite(BUTTON_HIGH, HIGH);
  digitalWrite(BUTTON_IN, LOW); // PULL DOWN

  prefs.begin("config", false); // false = read+write
  delay(1000);

  // Check if calibration has done.
  int prefCalibrationValue = prefs.getInt("fullCapacitiveValue", 0);
  if (prefCalibrationValue == 0) {
    Serial.println("No custom capacitive value set, set default.");
    prefs.putInt("fullCapacitiveValue", fullCapacitiveValue);
    prefs.end();  // Force flush
    prefs.begin("config", true); // Reopen in read-only
    Serial.print("Stored default Value: ");
    Serial.println(prefs.getInt("fullCapacitiveValue", 0));
  } else {
    fullCapacitiveValue = prefCalibrationValue;
    Serial.print("Loaded calibrated capacitive value: ");
    Serial.println(fullCapacitiveValue);
  }

  
  // Wait a second and check, if button has pressed for calibration
  delay(5000);
  if (digitalRead(BUTTON_IN) == 1) {
    Serial.println("Calibration...");
    for (int i = 0; i < 5; i++) {
      digitalWrite(LED_BUILTIN, HIGH);
      delay(200);
      digitalWrite(LED_BUILTIN, LOW);
      delay(200);
    }
    digitalWrite(LED_BUILTIN, HIGH);
    emptyCapacitiveValue = touchRead(TOUCH_PIN);
    Serial.print("Empty capacitive value: ");
    Serial.println(emptyCapacitiveValue);
    delay(1000);
    while(digitalRead(BUTTON_IN) == 0) {
      ledcWrite(pumpPin, dutyCycle);
      Serial.println("Pump on");
      
      delay(1000);
    
      // Pumpe ausschalten
      ledcWrite(pumpPin, 0);
      Serial.println("Pump off");
      Serial.print("Capacitive Value: ");
      Serial.println(touchRead(TOUCH_PIN));
      delay(2000);
    }
    delay(2000);
    fullCapacitiveValue = touchRead(TOUCH_PIN) + 1;
    Serial.print("Updated capacitive from ");
    Serial.print(prefCalibrationValue);
    Serial.print(" to ");
    Serial.println(fullCapacitiveValue);
    // Save value
    prefs.putInt("fullCapacitiveValue", fullCapacitiveValue);
  }
  for (int i = 0; i < 5; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(200);
    digitalWrite(LED_BUILTIN, LOW);
    delay(200);
  }
  prefs.end();
  
}

void loop() {
  // Read capacitive value from the touch pin
  int capacitiveValue = touchRead(TOUCH_PIN);
  // int buttonValue = digitalRead(BUTTON_IN);

  // Print capacitive value
  Serial.print("Measured Capacitive Value: ");
  Serial.println(capacitiveValue);
  Serial.print("Full Capacitive Value: ");
  Serial.println(fullCapacitiveValue);

  if (capacitiveValue > fullCapacitiveValue) {
    if (overflow_protect > 5){
      Serial.println("Overflow protect");
      delay(30000);
      overflow_protect = 0;
    } else {
      ledcWrite(pumpPin, dutyCycle);
      Serial.println("Pump on");
      
      delay(1000);
    
      // Pumpe ausschalten
      ledcWrite(pumpPin, 0);
      Serial.println("Pump off");
      overflow_protect++;
    }
  }


  delay(2000);  // 5 Sekunden Pause
}
