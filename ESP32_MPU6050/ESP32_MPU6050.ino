
#include <Wire.h>

#define MPU_ADDR 0x68

void writeRegister(byte reg, byte value) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

bool readRegisters(byte reg, byte *data, byte length) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);

  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  if (Wire.requestFrom((uint8_t)MPU_ADDR,
                       (uint8_t)length) != length) {
    return false;
  }

  for (byte i = 0; i < length; i++) {
    data[i] = Wire.read();
  }

  return true;
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin(21, 22);
  Wire.setClock(100000);

  // Read chip identity for troubleshooting
  byte id;
  if (readRegisters(0x75, &id, 1)) {
    Serial.print("WHO_AM_I: 0x");
    Serial.println(id, HEX);
  } else {
    Serial.println("Cannot read chip ID");
  }

  // Wake up MPU6050
  writeRegister(0x6B, 0x00);
  delay(100);

  // Accelerometer range: +/- 2g
  writeRegister(0x1C, 0x00);

  Serial.println("Starting acceleration readings");
}

void loop() {
  byte data[6];

  if (readRegisters(0x3B, data, 6)) {

    int16_t ax = (int16_t)((data[0] << 8) | data[1]);
    int16_t ay = (int16_t)((data[2] << 8) | data[3]);
    int16_t az = (int16_t)((data[4] << 8) | data[5]);

    float x = ax * 9.80665 / 16384.0;
    float y = ay * 9.80665 / 16384.0;
    float z = az * 9.80665 / 16384.0;

    Serial.print(x, 3);
    Serial.print(",");
    Serial.print(y, 3);
    Serial.print(",");
    Serial.println(z, 3);

  } else {
    Serial.println("Sensor read failed");
  }

  delay(20);
}
