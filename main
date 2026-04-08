import socket
import time
import os

# ── Connection settings ──────────────────────────────────────
ROBOT_IP    = "10.10.0.8"
MOVE_PORT   = 30003
GRIP_PORT   = 63352
CONV_PORT   = 2002
VBAI_PORT   = 5000        # port VBAI TCP I/O will send coords to
VBAI_IP     = "10.10.1.10"
PC_IP       = "10.10.1.10"  # your PC IP — check via ipconfig

# ── Fixed positions (metres) ─────────────────────────────────
HOME        = [0.116, -0.300, 0.200]
DROP_POINT  = [0.300, -0.100, 0.200]  # ← tune this on pendant first
APPROACH_Z  =  0.200   # height to travel above box before descending
GRAB_Z      = -0.150   # height to actually grab (your GRABDOWN value)
ROT_DOWN    = [0, -3.143, 0]
ROT_UP      = [2.28, 2.157, 0]

# ── Belt settings ────────────────────────────────────────────
BELT_SPEED_MMS = 20     # 2 cm/s = 20 mm/s
ROBOT_TRAVEL_TIME = 2.0 # seconds for arm to reach pick point — tune this

CAMERA_WIDTH = 2046
CAMERA_HEIGHT = 1086

# ════════════════════════════════════════════════════════════
# CONNECTIONS
# ════════════════════════════════════════════════════════════
print("Connecting to robot arm...")
s_arm = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s_arm.connect((ROBOT_IP, MOVE_PORT))

print("Connecting to gripper...")
s_grip = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s_grip.connect((ROBOT_IP, GRIP_PORT))

print("Connecting to TCP port...")
s_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s_tcp.connect((VBAI_IP, VBAI_PORT))

# while True:
#     p = s_tcp.recv(1024).decode().strip()
#     if p:
#         print(f"Received TCP data: {p}")

#print("Connecting to conveyor...")
#s_conv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# s_conv.connect((ROBOT_IP, CONV_PORT))

# ════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════
def move_arm(x, y, z, rot):
    cmd = f'movel(p[{x},{y},{z},{rot[0]},{rot[1]},{rot[2]}],0.5,0.3,0,0)\n'
    s_arm.send(cmd.encode('utf-8'))
    time.sleep(2)

def gripper_open():
    s_grip.send(b'SET POS 0\n')
    time.sleep(0.5)

def gripper_close():
    s_grip.send(b'SET POS 200\n')   # ← tune 0-255, 255=fully closed
    time.sleep(0.5)

def send_conv(cmd):
    s_conv.sendall(cmd.encode())
    time.sleep(0.5)

# ════════════════════════════════════════════════════════════
# STARTUP SEQUENCE
# ════════════════════════════════════════════════════════════
def startup():
    # Activate gripper
    s_grip.send(b'GET ACT\n')
    g_recv = str(s_grip.recv(10), 'UTF-8')
    print(f'Gripper status: {g_recv}')
    s_grip.send(b'SET ACT 1\n')
    s_grip.send(b'SET GTO 1\n')
    s_grip.send(b'SET FOR 1\n')
    s_grip.send(b'SET SPE 255\n')
    gripper_open()
    print("Gripper activated and open")

    # Start conveyor
    # send_conv('activate,tcp,0\n')
    # send_conv('pwr_on,conv,0\n')
    # send_conv('set_vel,conv,20\n')
    # send_conv('jog_fwd,conv,0\n')
    # print("Conveyor running at 2 cm/s")

    # Move arm to home
    move_arm(*HOME, ROT_UP)
    print("Arm at home position")

# ════════════════════════════════════════════════════════════
# PICK AND PLACE
# ════════════════════════════════════════════════════════════
def pick_and_place(px, py):
    """
    px, py = pixel coordinates from VBAI
    Convert to robot coordinates first
    """
    # ── Pixel to robot coordinate conversion ──
    # Measure PIXEL_TO_MM from your actual setup
    PIXEL_TO_MM  = 0.5        # 1 pixel = 0.5mm — TUNE THIS
    OFFSET_X_MM  = 100        # camera offset from robot base — TUNE THIS
    OFFSET_Y_MM  = 50         # TUNE THIS

    rx = ((px * PIXEL_TO_MM) + OFFSET_X_MM) / 1000   # convert to metres
    ry = ((py * PIXEL_TO_MM) + OFFSET_Y_MM) / 1000

    # Belt compensation — box moves while robot travels
    belt_offset = (BELT_SPEED_MMS * ROBOT_TRAVEL_TIME) / 1000
    ry += belt_offset

    print(f"Picking at robot coords: ({rx:.4f}m, {ry:.4f}m)")

    # 1 — Approach above box
    move_arm(rx, ry, APPROACH_Z, ROT_DOWN)

    # 2 — Stop conveyor before grabbing
    send_conv('jog_stop,conv,0\n')
    time.sleep(0.3)

    # 3 — Move down to grab
    move_arm(rx, ry, GRAB_Z, ROT_DOWN)

    # 4 — Close gripper
    gripper_close()
    time.sleep(0.5)

    # 5 — Lift up
    move_arm(rx, ry, APPROACH_Z, ROT_UP)

    # 6 — Move to drop point
    move_arm(*DROP_POINT, APPROACH_Z, ROT_UP)

    # 7 — Open gripper — release box
    gripper_open()
    time.sleep(0.3)

    # 8 — Return home
    move_arm(*HOME, ROT_UP)

    # 9 — Restart conveyor
    send_conv('jog_fwd,conv,0\n')
    print("Cycle complete — waiting for next box")

# ════════════════════════════════════════════════════════════
# VBAI LISTENER — receives pixel coordinates
# ════════════════════════════════════════════════════════════
# def listen_for_box():
#     server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#     server.bind((PC_IP, VBAI_PORT))
#     server.listen(1)
#     print(f"Waiting for VBAI to connect on {PC_IP}:{VBAI_PORT}...")
#     conn, addr = server.accept()
#     print(f"VBAI connected from {addr}")
#     return server, conn

# ════════════════════════════════════════════════════════════
# MAIN LOOP
# ════════════════════════════════════════════════════════════
def main():
    startup()

    try:
        while True:
            data = s_tcp.recv(1024).decode().strip()
            if not data:
                continue

            # Expected format from VBAI TCP I/O: "x,y,score"
            parts = []
            for d in data.split('\\n'):
                if d != "":
                    parts = d.split(',')
            if len(parts) >= 4:
                is_detected = bool(parts[0])
                px    = float(parts[1] if parts[1] else 0)
                py    = float(parts[2] if parts[2] else 0)
                angle = float(parts[3] if parts[3] else 0)  # if VBAI sends angle, otherwise ignore
                print(f"Parsed VBAI data - Detected: {is_detected}, Pixel coords: ({px}, {py}), Angle: {angle}")

            else:
                print("Invalid data format from VBAI")
                continue

    except KeyboardInterrupt:
        print("\nStopping...")
        send_conv('jog_stop,conv,0\n')
        gripper_open()
        os._exit(0)

if __name__ == "__main__":
    main()
