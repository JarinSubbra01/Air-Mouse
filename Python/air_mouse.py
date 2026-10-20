"""MPU6050 vertical air mouse for Windows (ESP32 DevKit V1 over USB).

Uses the UNCHANGED ESP32 sketch from MPU6050_Live_Graph_v2, which
prints X,Y,Z acceleration as comma-separated values at 115200 baud.

Run in Windows Command Prompt:
    py -m pip install pyserial
    py air_mouse.py
or: py air_mouse.py --port COM3

Tilt the sensor UP to calibrate which direction should move the cursor up.
No clicking and no physical buttons. Keep the ESP32 connected over USB.
"""

import argparse
import ctypes
import math
import sys
import time
from ctypes import wintypes

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("Missing pyserial. Run: py -m pip install pyserial")
    sys.exit(1)

BAUD = 115200
SAMPLE_TIMEOUT = 5.0
CALIBRATION_READINGS = 25
MIN_CALIBRATION_DELTA = 1.4  # m/s^2; ensures actual tilt
FILTER_WEIGHT = 0.3          # 0-1, larger is more responsive
MAX_PIXELS_PER_SAMPLE = 15.0


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def choose_port(requested):
    if requested:
        return requested
    ports = list(list_ports.comports())
    if not ports:
        raise RuntimeError("No COM ports found. Connect the ESP32 via USB.")
    print("Detected COM ports:")
    for i, p in enumerate(ports, 1):
        print(f"  {i}. {p.device} - {p.description}")
    if len(ports) == 1:
        print(f"Using {ports[0].device}")
        return ports[0].device
    while True:
        answer = input("Select ESP32 port number or name (e.g. 1 or COM3): ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(ports):
            return ports[int(answer) - 1].device
        if answer.upper() in [p.device.upper() for p in ports]:
            return answer.upper()
        print("Port not recognized. Try again.")


def next_accel(ser, timeout_sec):
    """Discard ESP32 boot/debug text. Return a valid 3-axis sensor sample."""
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        parts = line.split(",")
        if len(parts) != 3:
            continue
        try:
            values = tuple(float(part) for part in parts)
        except ValueError:
            continue
        if all(math.isfinite(value) and abs(value) <= 100 for value in values):
            return values
    raise TimeoutError("No valid X,Y,Z data received from ESP32.")


def average_samples(ser):
    ser.reset_input_buffer()
    totals = [0.0, 0.0, 0.0]
    for _ in range(CALIBRATION_READINGS):
        sample = next_accel(ser, SAMPLE_TIMEOUT)
        for axis in range(3):
            totals[axis] += sample[axis]
    return tuple(total / CALIBRATION_READINGS for total in totals)


def calibrate(ser):
    while True:
        input("\nHold MPU6050 at your comfortable CENTER angle, then press ENTER...")
        print("Measuring center; hold still...")
        center = average_samples(ser)
        print("Center readings: " + ", ".join(f"{v:+.2f}" for v in center))

        input("Now TILT the sensor UP (rotate it, don't only lift it), HOLD, press ENTER...")
        print("Measuring UP tilt; hold still...")
        upward = average_samples(ser)
        differences = [u - c for u, c in zip(upward, center)]
        axis = max(range(3), key=lambda i: abs(differences[i]))
        range_value = abs(differences[axis])

        if range_value < MIN_CALIBRATION_DELTA:
            print("Too little tilt was detected. Tilt farther and try again.")
            continue

        direction = 1 if differences[axis] > 0 else -1
        print(f"Calibrated: {'XYZ'[axis]} axis, UP change = {differences[axis]:+.2f} m/s²")
        print("Return the sensor to CENTER. The cursor should stay still.")
        print("Tilt UP = pointer UP | Tilt DOWN = pointer DOWN")
        print("Press Ctrl+C in this window to exit (or close the window).")
        return axis, center[axis], direction, range_value


def move_cursor_vertical(user32, step):
    cursor = POINT()
    if not user32.GetCursorPos(ctypes.byref(cursor)):
        return
    # Keep the pointer inside the Windows virtual desktop (multiple monitors too).
    top = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
    height = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
    target = max(top, min(top + height - 1, cursor.y + step))
    user32.SetCursorPos(cursor.x, int(target))


def main():
    if sys.platform != "win32":
        print("This script controls the real Windows cursor and requires Windows.")
        return 1
    parser = argparse.ArgumentParser(description="MPU6050 up/down Windows air mouse")
    parser.add_argument("--port", help="ESP32 COM port, e.g. COM3")
    args = parser.parse_args()
    try:
        port = choose_port(args.port)
        with serial.Serial(port, BAUD, timeout=0.15) as ser:
            print(f"\nConnected to ESP32 on {port} at {BAUD} baud.")
            print("NOTE: Close Arduino Serial Monitor and the old Python graph first.")
            time.sleep(2.0)  # Opening COM normally resets ESP32.
            ser.reset_input_buffer()
            print("Checking MPU6050 data...")
            sample = next_accel(ser, SAMPLE_TIMEOUT)
            print("Receiving X/Y/Z:", ", ".join(f"{v:+.2f}" for v in sample))
            axis, center, up_sign, calibration_range = calibrate(ser)

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
            user32.GetCursorPos.restype = wintypes.BOOL
            user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
            user32.SetCursorPos.restype = wintypes.BOOL
            user32.GetSystemMetrics.argtypes = [ctypes.c_int]
            user32.GetSystemMetrics.restype = ctypes.c_int
            deadzone = max(0.30, calibration_range * 0.12)
            filtered = 0.0
            fractional_motion = 0.0
            last_data = time.monotonic()
            last_print = 0.0
            print("\nAIR MOUSE ACTIVE. Move/tilt the MPU6050. No clicking is enabled.\n")
            while True:
                try:
                    xyz = next_accel(ser, 1.0)
                except TimeoutError:
                    if time.monotonic() - last_data > 2:
                        print("Waiting for sensor data... check ESP32 USB connection.")
                        last_data = time.monotonic()
                    continue

                last_data = time.monotonic()
                tilt = up_sign * (xyz[axis] - center)
                filtered += FILTER_WEIGHT * (tilt - filtered)

                if abs(filtered) <= deadzone:
                    fractional_motion = 0.0
                else:
                    amount = min(
                        MAX_PIXELS_PER_SAMPLE,
                        ((abs(filtered) - deadzone) / calibration_range)
                        * MAX_PIXELS_PER_SAMPLE,
                    )
                    # Positive tilt means UP, so decrease Windows Y position.
                    fractional_motion += (-1 if filtered > 0 else 1) * amount
                    whole_pixels = math.trunc(fractional_motion)
                    fractional_motion -= whole_pixels
                    if whole_pixels:
                        move_cursor_vertical(user32, whole_pixels)

                now = time.monotonic()
                if now - last_print > 0.5:
                    print(
                        f"\rLIVE: X={xyz[0]:+6.2f} Y={xyz[1]:+6.2f} "
                        f"Z={xyz[2]:+6.2f} | tilt={filtered:+6.2f}   ",
                        end="", flush=True,
                    )
                    last_print = now
    except (RuntimeError, serial.SerialException, OSError, TimeoutError) as exc:
        print(f"\nERROR: {exc}")
        print("Confirm the ESP32 outputs comma-separated X,Y,Z data at 115200 baud.")
        print("Close Arduino Serial Monitor and any other program using the COM port.")
        return 1
    except KeyboardInterrupt:
        print("\nAir mouse stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
