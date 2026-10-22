// ESP32 DevKit V1 + MPU6050: X,Y,Z streaming with push-button event.
// MPU6050: VCC->3V3, GND->GND, SDA->GPIO21, SCL->GPIO22.
// Push button: GPIO27 -> momentary switch -> GND (internal pull-up).
// Serial protocol: X,Y,Z data lines and BTN:1/BTN:0 event lines, 115200 baud.
#include <Wire.h>

#define MPU_ADDR 0x68
#define BUTTON_PIN 27
const uint32_t BUTTON_DEBOUNCE_MS = 35;

bool lastRawPressed = false;
bool stablePressed = false;
uint32_t rawChangedAt = 0;

void writeRegister(byte reg, byte value) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

bool readRegisters(byte reg, byte *data, byte length) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)length) != length) return false;
  for (byte i = 0; i < length; ++i) data[i] = Wire.read();
  return true;
}

void checkButton() {
  bool rawPressed = digitalRead(BUTTON_PIN) == LOW;
  uint32_t now = millis();

  if (rawPressed != lastRawPressed) {
    lastRawPressed = rawPressed;
    rawChangedAt = now;
  }
  if ((uint32_t)(now - rawChangedAt) >= BUTTON_DEBOUNCE_MS &&
      rawPressed != stablePressed) {
    stablePressed = rawPressed;
    Serial.println(stablePressed ? "BTN:1" : "BTN:0");
  }
}

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  stablePressed = digitalRead(BUTTON_PIN) == LOW;
  lastRawPressed = stablePressed;
  rawChangedAt = millis();

  Serial.begin(115200);
  delay(1000);
  Wire.begin(21, 22);
  Wire.setClock(100000);

  byte id;
  if (readRegisters(0x75, &id, 1)) {
    Serial.print("WHO_AM_I: 0x");
    Serial.println(id, HEX);
  } else {
    Serial.println("Cannot read chip ID");
  }

  writeRegister(0x6B, 0x00); // Wake MPU6050
  delay(100);
  writeRegister(0x1C, 0x00); // Accel range +/-2g
  Serial.println("Starting acceleration readings; button on GPIO27");
}

void loop() {
  checkButton();
  byte data[6];
  if (readRegisters(0x3B, data, 6)) {
    int16_t ax = (int16_t)((data[0] << 8) | data[1]);
    int16_t ay = (int16_t)((data[2] << 8) | data[3]);
    int16_t az = (int16_t)((data[4] << 8) | data[5]);
    float x = ax * 9.80665f / 16384.0f;
    float y = ay * 9.80665f / 16384.0f;
    float z = az * 9.80665f / 16384.0f;
    Serial.print(x, 3);
    Serial.print(',');
    Serial.print(y, 3);
    Serial.print(',');
    Serial.println(z, 3);
  } else {
    Serial.println("Sensor read failed");
  }
  checkButton();
  delay(20); // Approx. 50 samples/sec
}
