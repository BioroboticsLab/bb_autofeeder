#include <Arduino.h>
#include <Preferences.h>
#include "EEPROM.h"

// Constants for Preferences
Preferences prefs;
const char* ns = "prefs";       // namespace
const char* capKey = "capValue"; // key for the capacitive value
const char* pumpKey = "totalPump"; // key for total pump count

// Pin Definitions
const int pumpPin = 23;         // GPIO-Pin connected to MOSFET gate
#define TOUCH_PIN T0
#define EN_PIN 18
#define BUTTON_HIGH 27
#define BUTTON_IN 33
#define LED_BUILTIN 2

// PWM Settings
const int freq = 50;            // PWM frequency in Hz
const int resolution = 8;
const int dutyCycle = 125;      // ~67% of 255 for approx. 6V -> Edit if using different voltage for power supply

// Sensor Settings
int overflow_protect = 0;
uint16_t emptyCapacitiveValue = 0;
uint16_t fullCapacitiveValue = 45;
uint32_t totalPumpsSincePowerUp = 0;
uint32_t totalPumpsSinceCalibration = 0;

/**
* Smooths touch readings by averaging multiple samples
*
* @param touchPin Pin to read from
* @param samples Number of samples to take
* @param delayMicros Delay between samples in microseconds
* @return Averaged touch reading
*/
uint16_t getSmoothedTouch(uint8_t touchPin, uint16_t samples = 64, uint16_t delayMicros = 50) {
  uint32_t sum = 0;
  for (uint16_t i = 0; i < samples; i++) {
    sum += touchRead(touchPin);
    delayMicroseconds(delayMicros);
  }
  return sum / samples;
}

void blinkLED(int times, int onTime = 200, int offTime = 200) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(onTime);
    digitalWrite(LED_BUILTIN, LOW);
    delay(offTime);
  }
}

/* 
 * Turn the pump on for a specified duration 
 * Updates pump counters and saves to persistent storage
 */
void runPump(int durationMs = 1000) {
  // Open preferences for writing
  prefs.begin(ns, false);
  
  // Run the pump
  ledcWrite(pumpPin, dutyCycle);
  Serial.println("Pump on");
  delay(durationMs);
  ledcWrite(pumpPin, 0);
  Serial.println("Pump off");
  
  // Update counters
  totalPumpsSincePowerUp++;
  totalPumpsSinceCalibration++;
  
  // Save to persistent storage
  prefs.putUInt(pumpKey, totalPumpsSinceCalibration);
  
  // Close preferences
  prefs.end();
}

void setup() {
  // Initialize serial for debugging output
  Serial.begin(115200);
  
  // Initialize LEDC PWM and assign pin
  if (ledcAttach(pumpPin, freq, resolution)) {
    Serial.println("LEDC successfully configured!");
  } else {
    Serial.println("Error in LEDC configuration!");
  }
  
  // Configure pins
  pinMode(EN_PIN, OUTPUT);
  pinMode(BUTTON_HIGH, OUTPUT);
  pinMode(BUTTON_IN, INPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  
  // Set initial pin states
  digitalWrite(EN_PIN, HIGH);
  digitalWrite(BUTTON_HIGH, HIGH);
  digitalWrite(BUTTON_IN, LOW); // PULL DOWN
  
  // Open non-volatile storage
  prefs.begin(ns, false); // false = read+write
  delay(1000);
  
  // Load total pumps since calibration
  totalPumpsSinceCalibration = prefs.getUInt(pumpKey, 0);
  prefs.end();
  Serial.print("Total pumps since last calibration: ");
  Serial.println(totalPumpsSinceCalibration);
  
  // Check if calibration has been done
  prefs.begin(ns, false); // false = read+write
  int prefCalibrationValue = prefs.getInt(capKey, 0);
  if (prefCalibrationValue == 0) {
    Serial.println("No custom capacitive value set, setting default.");
    prefs.putInt(capKey, fullCapacitiveValue);
    Serial.print("Stored default value: ");
    Serial.println(prefs.getInt(capKey, 0));
  } else {
    fullCapacitiveValue = prefCalibrationValue;
    Serial.print("Loaded calibrated capacitive value: ");
    Serial.println(fullCapacitiveValue);
  }
  prefs.end();
  
  // Wait and check if button is pressed for calibration
  delay(5000);
  if (digitalRead(BUTTON_IN) == 1) {
    Serial.println("Calibration...");
    blinkLED(5);
    digitalWrite(LED_BUILTIN, HIGH);
    
    // Get empty capacitive value
    emptyCapacitiveValue = getSmoothedTouch(TOUCH_PIN);
    Serial.print("Empty capacitive value: ");
    Serial.println(emptyCapacitiveValue);
    delay(1000);
    
    // Wait for button press to continue calibration
    while(digitalRead(BUTTON_IN) == 0) {
      runPump();
      Serial.print("Capacitive Value: ");
      Serial.println(getSmoothedTouch(TOUCH_PIN));
      delay(2000);
    }
    
    delay(2000);
    fullCapacitiveValue = getSmoothedTouch(TOUCH_PIN) + 1;
    Serial.print("Updated capacitive from ");
    Serial.print(prefCalibrationValue);
    Serial.print(" to ");
    Serial.println(fullCapacitiveValue);

    prefs.begin(ns, false); // false = read+write
    // Save calibrated value
    prefs.putInt(capKey, fullCapacitiveValue);
    
    // Reset pump counter since we're calibrating
    totalPumpsSinceCalibration = 0;
    prefs.putUInt(pumpKey, totalPumpsSinceCalibration);
    prefs.end();
    Serial.println("Pump counter reset to 0");
  }
  
  // Indicate setup completion
  blinkLED(5);
  prefs.end();
}

void loop() {
  // Read capacitive value from the touch pin
  int capacitiveValue = getSmoothedTouch(TOUCH_PIN);
  
  // Print capacitive values
  Serial.println("\n========== STATS ==========");
  Serial.print("Measured Capacitive Value: ");
  Serial.println(capacitiveValue);
  Serial.print("Full Capacitive Value: ");
  Serial.println(fullCapacitiveValue);
  Serial.print("Pumps since power up: ");
  Serial.println(totalPumpsSincePowerUp);
  Serial.print("Pumps since last calibration: ");
  Serial.println(totalPumpsSinceCalibration);
  
  // Check if we need to run the pump
  if (capacitiveValue > fullCapacitiveValue) {
    if (overflow_protect > 5) {
      Serial.println("Overflow protect");
      delay(30000);
      overflow_protect = 0;
    } else {
      runPump();
      overflow_protect++;
    }
  }
  
  delay(2000);  // 2 seconds pause between readings
}
