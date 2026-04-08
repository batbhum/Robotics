"""
box_detection_test.py
=====================
TEST version — uses Mac built-in camera (no Basler required).
Includes all overexposure fixes for bright/washed-out pink box.

Requirements:
    pip3 install opencv-python numpy

Run:
    python3 box_detection_test.py

Controls:
    Q  →  quit
    S  →  save snapshot
    R  →  reset HSV sliders
    M  →  cycle mode  (Combined / HSV only / BGR only)
"""

import cv2
import numpy as np
import time

# ──────────────────────────────────────────────────────────────────────────────
# HSV DEFAULTS — tuned for bright / overexposed pink
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_HSV = {
    "H_min": 130, "H_max": 179,   # wide range for washed-out pink
    "S_min":  10, "S_max": 255,   # very low S_min — key fix for overexposure
    "V_min": 180, "V_max": 255,   # only bright pixels (excludes black belt)
}

# BGR ratio thresholds (fallback when HSV fails due to overexposure)
BGR_RATIO = {
    "R_min_ratio":    1.05,
    "B_max_ratio":    0.97,
    "brightness_min": 180,
}

# Contour area limits (pixels²) — adjust if box looks very small/large on screen
MIN_AREA = 2000
MAX_AREA = 200000

# Detection mode
MODES      = ["Combined", "HSV only", "BGR only"]
mode_index = 0


# ──────────────────────────────────────────────────────────────────────────────
# HSV TUNER
# ──────────────────────────────────────────────────────────────────────────────

def create_hsv_tuner():
    cv2.namedWindow("HSV Tuner", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("HSV Tuner", 420, 260)
    def nothing(_): pass
    cv2.createTrackbar("H min", "HSV Tuner", DEFAULT_HSV["H_min"], 179, nothing)
    cv2.createTrackbar("H max", "HSV Tuner", DEFAULT_HSV["H_max"], 179, nothing)
    cv2.createTrackbar("S min", "HSV Tuner", DEFAULT_HSV["S_min"], 255, nothing)
    cv2.createTrackbar("S max", "HSV Tuner", DEFAULT_HSV["S_max"], 255, nothing)
    cv2.createTrackbar("V min", "HSV Tuner", DEFAULT_HSV["V_min"], 255, nothing)
    cv2.createTrackbar("V max", "HSV Tuner", DEFAULT_HSV["V_max"], 255, nothing)


def get_hsv_from_tuner():
    h_min = cv2.getTrackbarPos("H min", "HSV Tuner")
    h_max = cv2.getTrackbarPos("H max", "HSV Tuner")
    s_min = cv2.getTrackbarPos("S min", "HSV Tuner")
    s_max = cv2.getTrackbarPos("S max", "HSV Tuner")
    v_min = cv2.getTrackbarPos("V min", "HSV Tuner")
    v_max = cv2.getTrackbarPos("V max", "HSV Tuner")
    lower = np.array([h_min, s_min, v_min], dtype=np.uint8)
    upper = np.array([h_max, s_max, v_max], dtype=np.uint8)
    return lower, upper


def reset_sliders():
    cv2.setTrackbarPos("H min", "HSV Tuner", DEFAULT_HSV["H_min"])
    cv2.setTrackbarPos("H max", "HSV Tuner", DEFAULT_HSV["H_max"])
    cv2.setTrackbarPos("S min", "HSV Tuner", DEFAULT_HSV["S_min"])
    cv2.setTrackbarPos("S max", "HSV Tuner", DEFAULT_HSV["S_max"])
    cv2.setTrackbarPos("V min", "HSV Tuner", DEFAULT_HSV["V_min"])
    cv2.setTrackbarPos("V max", "HSV Tuner", DEFAULT_HSV["V_max"])


# ──────────────────────────────────────────────────────────────────────────────
# MASK GENERATION
# ──────────────────────────────────────────────────────────────────────────────

def make_hsv_mask(frame, hsv_lower, hsv_upper):
    """Standard HSV threshold. Struggles when pink is overexposed (S → 0)."""
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, hsv_lower, hsv_upper)
    return mask


def make_bgr_mask(frame):
    """
    BGR channel ratio mask — works when pink looks almost white.
    Even in near-white pink, Red channel is still slightly stronger
    than Green and Blue. We detect this ratio instead of absolute colour.
    """
    b = frame[:, :, 0].astype(np.float32)
    g = frame[:, :, 1].astype(np.float32)
    r = frame[:, :, 2].astype(np.float32)

    epsilon    = 1.0
    brightness = (r + g + b) / 3.0
    r_over_g   = r / (g + epsilon)
    r_over_b   = r / (b + epsilon)

    bright_pink = (
        (brightness >= BGR_RATIO["brightness_min"]) &
        (r_over_g   >= BGR_RATIO["R_min_ratio"])    &
        (r_over_b   >= BGR_RATIO["B_max_ratio"])    &
        (r          >  100)
    )
    return bright_pink.astype(np.uint8) * 255


def clean_mask(mask):
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    mask   = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask   = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel, iterations=1)
    return mask


# ──────────────────────────────────────────────────────────────────────────────
# BOX DETECTION
# ──────────────────────────────────────────────────────────────────────────────

def detect_boxes(frame, hsv_lower, hsv_upper):
    global mode_index

    hsv_mask = make_hsv_mask(frame, hsv_lower, hsv_upper)
    bgr_mask = make_bgr_mask(frame)

    if MODES[mode_index] == "HSV only":
        combined = hsv_mask
    elif MODES[mode_index] == "BGR only":
        combined = bgr_mask
    else:
        combined = cv2.bitwise_or(hsv_mask, bgr_mask)

    mask = clean_mask(combined)

    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    boxes = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if not (MIN_AREA <= area <= MAX_AREA):
            continue

        rect                    = cv2.minAreaRect(cnt)
        (cx, cy), (w, h), angle = rect

        if w < h:
            w, h   = h, w
            angle += 90.0
        angle = angle % 180.0

        if h > 0 and (w / h) > 5.0:
            continue

        boxes.append({
            "cx": cx, "cy": cy,
            "w": w,   "h": h,
            "angle": angle,
            "area":  area,
            "contour": cnt,
        })

    boxes.sort(key=lambda b: b["area"], reverse=True)
    return boxes, mask, hsv_mask, bgr_mask


# ──────────────────────────────────────────────────────────────────────────────
# DRAWING
# ──────────────────────────────────────────────────────────────────────────────

def draw_detections(frame, boxes):
    out = frame.copy()

    for i, box in enumerate(boxes):
        cx, cy  = int(box["cx"]), int(box["cy"])
        angle   = box["angle"]
        cnt     = box["contour"]
        box_pts = cv2.boxPoints(cv2.minAreaRect(cnt)).astype(int)

        overlay = out.copy()
        cv2.drawContours(overlay, [box_pts], 0, (180, 105, 255), -1)
        cv2.addWeighted(overlay, 0.25, out, 0.75, 0, out)
        cv2.drawContours(out, [box_pts], 0, (0, 0, 255), 2)
        cv2.circle(out, (cx, cy), 6, (0, 255, 0), -1)

        length    = int(max(box["w"], box["h"]) * 0.4)
        angle_rad = np.deg2rad(angle)
        x2 = int(cx + length * np.cos(angle_rad))
        y2 = int(cy - length * np.sin(angle_rad))
        cv2.arrowedLine(out, (cx, cy), (x2, y2), (255, 255, 0), 2, tipLength=0.3)

        cv2.putText(out, f"BOX #{i+1}  cx={cx} cy={cy}",
                    (cx - 80, cy - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
        cv2.putText(out, f"W={box['w']:.0f} H={box['h']:.0f} ang={angle:.1f}",
                    (cx - 80, cy + 2),  cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

    # Status bar
    color = (0, 255, 0) if boxes else (0, 0, 255)
    cv2.rectangle(out, (0, 0), (420, 30), (0, 0, 0), -1)
    cv2.putText(out, f"Boxes: {len(boxes)}  |  Mode: {MODES[mode_index]}",
                (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # Hint bar
    cv2.rectangle(out, (0, out.shape[0] - 24), (out.shape[1], out.shape[0]), (0, 0, 0), -1)
    cv2.putText(out, "M=mode   S=snapshot   R=reset sliders   Q=quit",
                (8, out.shape[0] - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (160, 160, 160), 1)
    return out


def make_split_mask(hsv_mask, bgr_mask):
    """Side-by-side: left = HSV mask, right = BGR ratio mask."""
    h, w      = hsv_mask.shape
    split     = np.zeros((h, w * 2), dtype=np.uint8)
    split[:, :w] = hsv_mask
    split[:, w:] = bgr_mask
    split_bgr = cv2.cvtColor(split, cv2.COLOR_GRAY2BGR)
    cv2.putText(split_bgr, "HSV mask",
                (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
    cv2.putText(split_bgr, "BGR ratio mask",
                (w + 8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
    cv2.line(split_bgr, (w, 0), (w, h), (80, 80, 80), 2)
    return split_bgr


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    global mode_index

    # Mac built-in camera = index 0
    # If you have an external USB camera try index 1 or 2
    CAMERA_INDEX = 0

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera index {CAMERA_INDEX}")
        print("        Try changing CAMERA_INDEX to 1 or 2")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    print("[INFO] Camera opened.")
    print("[INFO] Controls:  M=mode   S=snapshot   R=reset   Q=quit")

    cv2.namedWindow("Box Detection",   cv2.WINDOW_NORMAL)
    cv2.namedWindow("Mask split view", cv2.WINDOW_NORMAL)
    create_hsv_tuner()

    snapshot_count = 0
    prev_time      = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARNING] Frame grab failed, retrying...")
            time.sleep(0.05)
            continue

        hsv_lower, hsv_upper      = get_hsv_from_tuner()
        boxes, mask, hsv_m, bgr_m = detect_boxes(frame, hsv_lower, hsv_upper)

        now       = time.time()
        fps       = 1.0 / max(now - prev_time, 1e-6)
        prev_time = now

        annotated = draw_detections(frame, boxes)
        cv2.putText(annotated, f"FPS:{fps:.1f}",
                    (annotated.shape[1] - 80, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)

        split = make_split_mask(hsv_m, bgr_m)

        for i, b in enumerate(boxes):
            print(f"[DETECT] Box #{i+1}  "
                  f"centre=({b['cx']:.0f},{b['cy']:.0f})px  "
                  f"size=({b['w']:.0f}x{b['h']:.0f})px  "
                  f"angle={b['angle']:.1f}°  "
                  f"area={b['area']:.0f}px²")

        cv2.imshow("Box Detection",   annotated)
        cv2.imshow("Mask split view", split)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            print("[INFO] Quit.")
            break
        elif key == ord('s'):
            fname = f"snapshot_{snapshot_count:03d}.png"
            cv2.imwrite(fname, annotated)
            print(f"[INFO] Snapshot saved → {fname}")
            snapshot_count += 1
        elif key == ord('r'):
            reset_sliders()
            print("[INFO] Sliders reset.")
        elif key == ord('m'):
            mode_index = (mode_index + 1) % len(MODES)
            print(f"[INFO] Mode → {MODES[mode_index]}")

    cap.release()
    cv2.destroyAllWindows()

    hsv_lower, hsv_upper = get_hsv_from_tuner()
    print("\n── Final HSV values (copy into Basler script when ready) ──")
    print(f"HSV_LOWER = np.array({hsv_lower.tolist()})")
    print(f"HSV_UPPER = np.array({hsv_upper.tolist()})")


if __name__ == "__main__":
    main()
