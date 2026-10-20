"""Live three-axis MPU6050 graph received over ESP32 USB serial.

Run: py mpu_graph.py
Or:  py mpu_graph.py --port COM5
Close Arduino Serial Monitor and Serial Plotter before running.
"""

import argparse
import math
import sys
import time
from collections import deque

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import serial
from serial.tools import list_ports

BAUD = 115200
WINDOW = 250                 # Around 5 seconds at 50 samples/s
Y_MIN, Y_MAX = -20, 20      # Fixed vertical scale in m/s^2


def pick_port(requested):
    if requested:
        return requested

    ports = list(list_ports.comports())
    if not ports:
        raise RuntimeError(
            "No serial ports detected. Connect the ESP32 with a USB data cable."
        )

    print("Available serial ports:")
    for idx, port in enumerate(ports, 1):
        print(f"  {idx}. {port.device}  ({port.description})")

    if len(ports) == 1:
        selected = ports[0].device
        print(f"Using {selected}\n")
        return selected

    while True:
        answer = input("Enter port number or name (e.g. 1 or COM5): ").strip()
        if not answer:
            continue
        if answer.isdigit() and 1 <= int(answer) <= len(ports):
            return ports[int(answer) - 1].device
        if any(answer.lower() == p.device.lower() for p in ports):
            return answer
        print("Invalid choice; please try again.")


def main():
    parser = argparse.ArgumentParser(description="MPU6050 live X/Y/Z graph")
    parser.add_argument("--port", help="Serial port, for example COM5")
    args = parser.parse_args()

    try:
        port = pick_port(args.port)
        ser = serial.Serial(port, BAUD, timeout=0.05)
    except (RuntimeError, serial.SerialException, OSError) as exc:
        print(f"ERROR: {exc}")
        print("Close Arduino Serial Monitor/Plotter and try again.")
        return 1

    print(f"Connected to {port} at {BAUD} baud.")
    print("Waiting for samples; move or tilt the MPU6050...")
    # Opening the serial port resets many ESP32 boards.
    time.sleep(2)
    ser.reset_input_buffer()

    history = [deque([0.0] * WINDOW, maxlen=WINDOW) for _ in range(3)]
    fig, axes = plt.subplots(3, 1, figsize=(11, 8))
    fig.suptitle(f"ESP32 MPU6050 - LIVE X / Y / Z (port {port})", fontsize=15)
    line_artists = []
    for ax, label, color in zip(axes, ("X", "Y", "Z"), ("red", "green", "blue")):
        (artist,) = ax.plot(range(WINDOW), [0.0] * WINDOW, color=color, linewidth=1.7)
        ax.set_title(f"{label} axis")
        ax.set_xlim(0, WINDOW - 1)
        ax.set_ylim(Y_MIN, Y_MAX)
        ax.set_yticks(range(Y_MIN, Y_MAX + 1, 5))
        ax.set_ylabel("Acceleration (m/s²)")
        ax.grid(True, alpha=0.35)
        line_artists.append(artist)
    axes[-1].set_xlabel("Most recent 250 samples (about 5 seconds)")

    status = fig.text(0.5, 0.012, "Waiting for sensor data...", ha="center")
    read_count = 0
    last_valid = time.monotonic()

    def update(_frame):
        nonlocal read_count, last_valid
        # Limit work per redraw so graph remains responsive.
        for _ in range(120):
            if not ser.in_waiting:
                break
            raw = ser.readline().decode("utf-8", errors="ignore").strip()
            fields = raw.split(",")
            if len(fields) != 3:
                continue
            try:
                values = tuple(map(float, fields))
            except ValueError:
                continue
            if not all(math.isfinite(v) for v in values):
                continue
            for sequence, value in zip(history, values):
                sequence.append(value)
            read_count += 1
            last_valid = time.monotonic()
            status.set_text(
                f"LIVE | X = {values[0]:+.2f}   Y = {values[1]:+.2f}   "
                f"Z = {values[2]:+.2f} m/s² | {read_count} samples"
            )

        if time.monotonic() - last_valid > 3:
            status.set_text("No valid data for 3 seconds. Check ESP32/upload/wiring.")
        for artist, values in zip(line_artists, history):
            artist.set_ydata(list(values))
        return line_artists

    animation = FuncAnimation(fig, update, interval=50, cache_frame_data=False)
    # Keep animation referenced until plot closes.
    _ = animation
    plt.tight_layout(rect=(0, 0.04, 1, 0.96))
    try:
        plt.show()
    finally:
        if ser.is_open:
            ser.close()
        print("Serial port closed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
