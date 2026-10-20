# ESP32 DevKit V1 + MPU6050: Live X/Y/Z Graph (Windows)

The ESP32 reads three acceleration axes from an MPU6050 and sends them by USB serial to a Python live-graph window. The graphs have a fixed Y axis from -20 to +20 m/s^2, with current numeric readings.

## 1. Wiring (power off before connecting)

| MPU6050 (GY-521) | DOIT ESP32 DevKit V1 |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO21 |
| SCL | GPIO22 |

Other MPU6050 pins are not used. Use a USB **data** cable.

## 2. Upload ESP32 code (Arduino IDE)

1. Open `ESP32_MPU6050/ESP32_MPU6050.ino` with Arduino IDE.
2. From Library Manager install **Adafruit MPU6050** by Adafruit. Accept installation of dependencies (Adafruit Unified Sensor and Adafruit BusIO).
3. Select board **DOIT ESP32 DEVKIT V1** and your ESP32 COM port under Tools > Port.
4. Set Upload Speed to **115200** if you encountered upload timeouts.
5. Click **Upload**. If stuck at `Connecting...`, hold BOOT during connection and release when writing begins. Close any Python or Serial Monitor connection first.
6. To confirm the sensor is operating, open Serial Monitor at **115200 baud**. You should see `MPU6050 Ready` followed by lines like `0.200,-0.100,9.780`. Move/tilt the MPU6050 and watch the numbers change.
7. **Close Serial Monitor / Serial Plotter before running Python.** They cannot share the same COM port with Python.

If you see `ERROR: MPU6050 NOT FOUND`, check power, GND, SDA=21, SCL=22 and the wiring.

## 3. Start live Python graphs on Windows

1. Install Python 3 from python.org, including the Python launcher (`py`).
2. Extract this ZIP to a regular folder.
3. In the `Python` folder, double-click **INSTALL_LIBRARIES.bat** (one-time setup, requires internet).
4. Double-click **START_GRAPH.bat**.
5. The program displays available serial ports. If your ESP32 is the only port it will select it; otherwise select its COM port from the list.
6. A window displays separate **X (red), Y (green), Z (blue)** acceleration graphs and numerical readings. The scale stays -20 to +20 m/s^2.

You can also use CMD in the `Python` folder:

```
py -m pip install -r requirements.txt
py mpu_graph.py
```

To specify a port without being prompted:

```
py mpu_graph.py --port COM5
```

## 4. What to expect

- With the sensor stationary, graph lines should be mostly steady. Due to gravity, the total acceleration vector magnitude is approximately 9.8 m/s^2 at rest.
- Tilt the board slowly: acceleration components (X, Y, Z) redistribute as the gravity direction changes.
- Shake/move the board: sharp peaks should appear.
- Sensor readings are acceleration, **not** finger bend measurements or sign-language labels.

## Troubleshooting

- `Could not open COM port` / `PermissionError`: close Arduino Serial Monitor, Serial Plotter, other Python tools; reconnect USB and select the correct COM port.
- `No serial ports detected`: try a different USB data cable and check ESP32's USB serial driver (usually CP210x or CH340 depending on the board).
- `MPU6050 NOT FOUND`: check four sensor wires and 3.3 V power.
- `No valid data`: confirm ESP32 has successfully uploaded the supplied sketch; check Serial Monitor at 115200 and close it again.
- `Write timeout` while uploading: try holding ESP32 BOOT while upload connects, reduce upload speed to 115200, and try another cable/USB port.

These files are supplied ready to use, but actual operation requires testing with your own ESP32, USB adapter, and sensor.
