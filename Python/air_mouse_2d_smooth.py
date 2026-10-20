"""Smooth 2D tilt air mouse for ESP32 DevKit V1 + MPU6050 on Windows.

The ESP32 sends CSV acceleration lines X,Y,Z in m/s^2 at 115200 baud.
No changes to your working ESP32 firmware or wiring are required.

Install: py -m pip install pyserial
Run:     py air_mouse_2d_smooth.py --port COM3
Stop:    ESC (or Ctrl+C in the console)
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
    raise SystemExit("Please install pyserial: py -m pip install pyserial")

# -------- SETTINGS YOU CAN TUNE --------
BAUD = 115200
DEAD_ZONE = 0.10          # Increase to 0.14 if the pointer drifts while resting
CURSOR_SPEED = 780.0      # Pixels/second at the calibrated full tilt
MAX_SPEED = 1300.0        # Safety cap for larger tilts
SPEED_CURVE = 1.50        # >1 makes small tilts more precise
INPUT_SMOOTH_MS = 95      # Increase to 130 for less jitter; decrease to 60 for quicker response
SPEED_SMOOTH_MS = 65      # Smooths movement without excessive lag
GRAVITY_TOLERANCE = 2.8  # Reject sharp shakes (m/s^2 deviation from resting gravity)
POSE_SAMPLES = 35
# ---------------------------------------


class Point(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def mag(a):
    return math.sqrt(dot(a, a))


def port_picker(port):
    if port:
        return port
    ports = list(list_ports.comports())
    if not ports:
        raise RuntimeError("No COM port found. Connect your ESP32.")
    for i, item in enumerate(ports, 1):
        print(f"{i}. {item.device} ({item.description})")
    if len(ports) == 1:
        return ports[0].device
    while True:
        choice = input("Enter a port number or COM name: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(ports):
            return ports[int(choice) - 1].device
        if any(choice.upper() == item.device.upper() for item in ports):
            return choice.upper()
        print("Not a valid selection.")


def read_xyz(connection, timeout=2.0):
    """Read a *full* valid CSV line; ignore ESP32 boot messages."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        line = connection.readline().decode("utf-8", errors="ignore").strip()
        fields = line.split(",")
        if len(fields) != 3:
            continue
        try:
            values = tuple(float(f) for f in fields)
        except ValueError:
            continue
        if all(math.isfinite(n) and abs(n) < 100 for n in values):
            return values
    raise TimeoutError("No valid X,Y,Z data from ESP32. Check firmware and COM port.")


def get_pose(connection, name, how):
    while True:
        input(f"\n{name}: {how}\nHold still and press ENTER to record...")
        time.sleep(0.25)  # Allow Enter key motion to settle
        connection.reset_input_buffer()
        samples = [read_xyz(connection, 3.0) for _ in range(POSE_SAMPLES)]
        values = []
        for k in range(3):
            ordered = sorted(point[k] for point in samples)
            values.append(sum(ordered[4:-4]) / (len(ordered) - 8))
        center = tuple(values)
        rms = math.sqrt(sum(mag(sub(point, center)) ** 2 for point in samples) / len(samples))
        print(f"  X={center[0]:+.2f} Y={center[1]:+.2f} Z={center[2]:+.2f}  stability={rms:.2f}")
        if rms <= 1.0:
            return center
        print("  The sensor was moving during calibration. Please try this position again.")


class FivePointCalibration:
    def __init__(self, center, up, down, right, left):
        self.center = center
        self.vert = sub(up, down)
        self.horiz = sub(right, left)
        aa = dot(self.vert, self.vert)
        bb = dot(self.horiz, self.horiz)
        ab = dot(self.vert, self.horiz)
        self.det = aa * bb - ab * ab
        self.aa, self.bb, self.ab = aa, bb, ab
        if min(mag(sub(p, center)) for p in (up, down, right, left)) < 1.1:
            raise ValueError("A tilt was too small. Try a 20-30 degree tilt in every direction.")
        if aa == 0 or bb == 0 or self.det < 0.01 or abs(ab) / math.sqrt(aa * bb) > 0.92:
            raise ValueError("Vertical and horizontal poses are too similar. Roll sideways for LEFT/RIGHT.")
        u_up, _ = self.raw_axes(up)
        u_down, _ = self.raw_axes(down)
        _, r_right = self.raw_axes(right)
        _, r_left = self.raw_axes(left)
        if not (u_up > 0.05 and u_down < -0.05 and r_right > 0.05 and r_left < -0.05):
            raise ValueError("UP/DOWN or LEFT/RIGHT did not land on opposite sides of CENTER.")
        self.up_scale = u_up
        self.down_scale = -u_down
        self.right_scale = r_right
        self.left_scale = -r_left

    def raw_axes(self, xyz):
        delta = sub(xyz, self.center)
        v = dot(delta, self.vert)
        h = dot(delta, self.horiz)
        return ((v * self.bb - h * self.ab) / self.det,
                (h * self.aa - v * self.ab) / self.det)

    def tilt(self, xyz):
        up, right = self.raw_axes(xyz)
        return (up / (self.up_scale if up >= 0 else self.down_scale),
                right / (self.right_scale if right >= 0 else self.left_scale))


def calibrate(connection):
    print("\nFIVE-POINT CALIBRATION: tilt/roll the sensor; do not slide it sideways.")
    while True:
        center = get_pose(connection, "1/5 CENTER", "Hold your normal resting wrist position.")
        up = get_pose(connection, "2/5 UP", "Tilt wrist UP, about 20-30 degrees.")
        down = get_pose(connection, "3/5 DOWN", "Return to center, then tilt DOWN.")
        right = get_pose(connection, "4/5 RIGHT", "Return to center, then ROLL wrist RIGHT.")
        left = get_pose(connection, "5/5 LEFT", "Return to center, then ROLL wrist LEFT.")
        try:
            calib = FivePointCalibration(center, up, down, right, left)
            break
        except ValueError as error:
            print(f"\nCalibration needs repeating: {error}\n")
    print("\nCalibration successful (including independent LEFT and RIGHT).")
    input("Return to CENTER, hold still, then press ENTER to activate the mouse...")
    return calib


def tilt_to_speed(value):
    size = abs(value)
    if size <= DEAD_ZONE:
        return 0.0
    fraction = (size - DEAD_ZONE) / (1 - DEAD_ZONE)
    speed = min(MAX_SPEED, CURSOR_SPEED * fraction ** SPEED_CURVE)
    return math.copysign(speed, value)


def mouse_api():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    try:
        user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass
    user32.GetCursorPos.argtypes = [ctypes.POINTER(Point)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetSystemMetrics.restype = ctypes.c_int
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    return user32


def move_pointer(user32, delta_x, delta_y):
    pos = Point()
    if not user32.GetCursorPos(ctypes.byref(pos)):
        return
    left = user32.GetSystemMetrics(76)
    top = user32.GetSystemMetrics(77)
    width = user32.GetSystemMetrics(78)
    height = user32.GetSystemMetrics(79)
    if width <= 0 or height <= 0:
        return
    dest_x = max(left, min(left + width - 1, pos.x + delta_x))
    dest_y = max(top, min(top + height - 1, pos.y + delta_y))
    user32.SetCursorPos(int(dest_x), int(dest_y))


def run():
    if sys.platform != "win32":
        raise RuntimeError("The mouse controller runs on Windows only.")
    parser = argparse.ArgumentParser(description="ESP32 MPU6050 smooth 2D air mouse")
    parser.add_argument("--port", help="Serial port, such as COM3")
    args = parser.parse_args()
    port = port_picker(args.port)
    print(f"Connecting to {port}. Close Arduino Serial Monitor and other graph apps.")
    with serial.Serial(port, BAUD, timeout=0.12) as connection:
        time.sleep(2)  # USB connection can reset ESP32
        connection.reset_input_buffer()
        print("First sensor measurement:", read_xyz(connection))
        calibration = calibrate(connection)
        user32 = mouse_api()
        filtered = list(calibration.center)
        velocity_x = velocity_y = 0.0
        fraction_x = fraction_y = 0.0
        last_time = last_valid_time = time.monotonic()
        last_status = 0.0
        gravity = mag(calibration.center)
        print("\nAIR MOUSE ACTIVE: Up / Down / Left / Right / Diagonals")
        print("Return to CENTER to stop. Press ESC or Ctrl+C to quit.\n")

        while True:
            if user32.GetAsyncKeyState(0x1B) & 0x8000:  # ESC
                print("\nStopped with ESC.")
                break
            try:
                xyz = read_xyz(connection, 0.45)
            except TimeoutError:
                velocity_x = velocity_y = fraction_x = fraction_y = 0.0
                filtered = list(calibration.center)
                last_time = time.monotonic()
                if last_time - last_valid_time > 1.0 and last_time - last_status > 1.0:
                    print("\nSensor stream interrupted; mouse paused.")
                    last_status = last_time
                continue

            now = time.monotonic()
            dt = now - last_time
            last_time = last_valid_time = now
            if dt > 0.20:  # Avoid jumps after USB stalls
                filtered = list(xyz)
                velocity_x = velocity_y = fraction_x = fraction_y = 0.0
                continue
            dt = max(0.005, min(dt, 0.065))

            # A significant change in acceleration magnitude usually means a shake.
            # Ignore it for tilt control; it is not a reliable orientation measurement.
            if abs(mag(xyz) - gravity) > GRAVITY_TOLERANCE:
                continue

            alpha = 1.0 - math.exp(-dt / (INPUT_SMOOTH_MS / 1000.0))
            for axis in range(3):
                filtered[axis] += alpha * (xyz[axis] - filtered[axis])

            tilt_up, tilt_right = calibration.tilt(filtered)
            want_x = tilt_to_speed(tilt_right)
            want_y = -tilt_to_speed(tilt_up)  # Screen Y grows downward
            # Prevent diagonal movement from becoming excessively fast.
            combined = math.hypot(want_x, want_y)
            if combined > MAX_SPEED:
                scale = MAX_SPEED / combined
                want_x *= scale
                want_y *= scale

            # Stop crisply in the center: no slow cursor drift after releasing tilt.
            if want_x == 0.0:
                velocity_x, fraction_x = 0.0, 0.0
            if want_y == 0.0:
                velocity_y, fraction_y = 0.0, 0.0

            accel_alpha = 1.0 - math.exp(-dt / (SPEED_SMOOTH_MS / 1000.0))
            if want_x:
                velocity_x += accel_alpha * (want_x - velocity_x)
            if want_y:
                velocity_y += accel_alpha * (want_y - velocity_y)

            fraction_x += velocity_x * dt
            fraction_y += velocity_y * dt
            dx, dy = math.trunc(fraction_x), math.trunc(fraction_y)
            fraction_x -= dx
            fraction_y -= dy
            if dx or dy:
                move_pointer(user32, dx, dy)
            if now - last_status >= 0.5:
                print(f"\rUP={tilt_up:+.2f} RIGHT={tilt_right:+.2f}   "
                      f"X-speed={velocity_x:+.0f} Y-speed={velocity_y:+.0f} px/s   ",
                      end="", flush=True)
                last_status = now


def main():
    try:
        run()
    except (serial.SerialException, RuntimeError, TimeoutError, OSError) as error:
        print(f"\nERROR: {error}")
        return 1
    except KeyboardInterrupt:
        print("\nStopped with Ctrl+C.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
