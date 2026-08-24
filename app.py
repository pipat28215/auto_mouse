"""
Auto Mouse: หันขวาทีละ 15 องศาไปเรื่อยๆ แล้วคลิกซ้าย
- ตรวจสอบตอนเริ่มว่าเชื่อมต่อ/ควบคุมเมาส์ได้หรือไม่
- ขยับเมาส์แบบ raw input (SendInput) เพื่อให้เกมที่ใช้ DirectInput รับรู้
- กด ESC เพื่อหยุด (ต้องติดตั้ง keyboard) หรือ Ctrl+C ใน terminal

การใช้งาน: กดปุ่ม D ค้าง -> เมาส์หันขวาเรื่อยๆ (smooth) และคลิกซ้ายค้างไว้
           ปล่อย D -> หยุดหันและปล่อยคลิกซ้าย
รัน: uv run app.py            (จะถามว่าจะทำงานกี่วินาที)
     uv run app.py 60         (ทำงาน 60 วินาทีแล้วหยุดเอง, 0 = ไม่จำกัด)
"""

import ctypes
import sys
import time
from ctypes import wintypes

import pyautogui

# ให้ console แสดงภาษาไทยได้ (Windows ใช้ cp874 โดยค่าเริ่มต้น)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import keyboard  # สำหรับกด ESC หยุด
except ImportError:
    keyboard = None

# ---------- ตั้งค่า ----------
DEGREE_STEP = 20          # องศาที่หันต่อรอบ
PIXELS_PER_DEGREE = 10    # จำนวน pixel ต่อ 1 องศา (ปรับตามความไวเมาส์ในเกม)
DELAY = 0.25              # หน่วงเวลาระหว่างรอบ (วินาที)
TURN_DURATION = 0.2       # เวลาที่ใช้หันแต่ละครั้ง (วินาที) — ยิ่งมากยิ่งช้า/นุ่ม
TURN_STEPS = 20
HOLD_KEY = "D"            # ปุ่มที่ต้องกดค้างเพื่อให้เมาส์หันขวา + คลิกซ้ายค้าง
TICK = 0.02               # ช่วงเวลาตรวจปุ่ม/ขยับเมาส์ตอนกดค้าง (วินาที)           # จำนวนขั้นย่อยในการหันแต่ละครั้ง — ยิ่งมากยิ่ง smooth
RUN_SECONDS = 60          # เวลาทำงานทั้งหมด (วินาที) ค่าเริ่มต้น — ถามผู้ใช้ตอนรัน, 0 = ไม่จำกัด
START_DELAY = 3           # เวลารอก่อนเริ่ม เพื่อสลับไปหน้าต่างเกม
# -----------------------------

pyautogui.FAILSAFE = True  # ลากเมาส์ไปมุมซ้ายบนสุดเพื่อหยุดฉุกเฉิน
pyautogui.PAUSE = 0

# ---------- ตรวจจับปุ่ม ESC ----------
VK_ESCAPE = 0x1B
stop_requested = False


def _on_esc() -> None:
    global stop_requested
    stop_requested = True


def esc_pressed() -> bool:
    """คืน True ถ้าผู้ใช้กด ESC (ใช้ hook ของ keyboard ถ้ามี ไม่งั้นอ่านสถานะปุ่มจาก Win32)"""
    if stop_requested:
        return True
    if ctypes.windll.user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000:
        _on_esc()
        return True
    return False


def install_esc_hook() -> None:
    if keyboard:
        try:
            keyboard.add_hotkey("esc", _on_esc)
        except Exception:
            pass  # ถ้า hook ไม่ได้ (ไม่มีสิทธิ์) จะใช้ GetAsyncKeyState แทน


# ---------- Raw input ผ่าน Win32 SendInput ----------
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
INPUT_MOUSE = 0

ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def _send(flags: int, dx: int = 0, dy: int = 0) -> bool:
    inp = INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dx, dy, 0, flags, 0, 0))
    return ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) == 1


def move_rel(dx: int, dy: int = 0) -> bool:
    return _send(MOUSEEVENTF_MOVE, dx, dy)


def smooth_move(dx: int, duration: float = TURN_DURATION, steps: int = TURN_STEPS) -> bool:
    """ขยับเมาส์ dx pixel แบบนุ่มนวล โดยแบ่งเป็นหลายขั้นย่อยกระจายตามเวลา"""
    steps = max(1, steps)
    sent = 0
    for i in range(1, steps + 1):
        if esc_pressed():
            return True  # หยุดหันทันที ให้ main จัดการต่อ
        target = round(dx * i / steps)   # ตำแหน่งสะสมที่ควรถึงในขั้นนี้
        part = target - sent
        if part and not move_rel(part):
            return False
        sent = target
        time.sleep(duration / steps)
    return True


def key_held(key: str) -> bool:
    """คืน True ขณะที่ปุ่ม (ตัวอักษร A-Z / 0-9) ถูกกดค้างอยู่"""
    return bool(ctypes.windll.user32.GetAsyncKeyState(ord(key.upper())) & 0x8000)


def left_down() -> bool:
    return _send(MOUSEEVENTF_LEFTDOWN)


def left_up() -> bool:
    return _send(MOUSEEVENTF_LEFTUP)


def left_click() -> bool:
    return _send(MOUSEEVENTF_LEFTDOWN) and _send(MOUSEEVENTF_LEFTUP)


# ---------- ตรวจสอบการเชื่อมต่อเมาส์ ----------
def check_mouse() -> bool:
    print("=" * 40)
    print("ตรวจสอบเมาส์...")

    is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    print(f"  สิทธิ์ Administrator : {'ใช่' if is_admin else 'ไม่ใช่ (บางเกมอาจไม่รับ input)'}")

    try:
        w, h = pyautogui.size()
        x, y = pyautogui.position()
        print(f"  ขนาดหน้าจอ          : {w}x{h}")
        print(f"  ตำแหน่งเมาส์ปัจจุบัน : ({x}, {y})")
    except Exception as e:
        print(f"  [FAIL] อ่านตำแหน่งเมาส์ไม่ได้: {e}")
        return False

    # ทดสอบขยับ 5 px แล้วขยับกลับ
    ok = move_rel(5, 0)
    time.sleep(0.05)
    x2, _ = pyautogui.position()
    move_rel(-5, 0)

    if ok and x2 != x:
        print("  ทดสอบขยับเมาส์       : ผ่าน")
        print("[OK] เชื่อมต่อเมาส์สำเร็จ")
        print("=" * 40)
        return True

    err = ctypes.get_last_error()
    print(f"  ทดสอบขยับเมาส์       : ล้มเหลว (SendInput={ok}, error={err})")
    print("[FAIL] ควบคุมเมาส์ไม่ได้")
    print("       ลองรัน terminal แบบ Administrator หรือเช็คว่าไม่ได้อยู่ใน RDP/VM")
    print("=" * 40)
    return False


def ask_run_seconds() -> float:
    """รับจำนวนวินาทีที่จะทำงานจาก argument หรือถามผู้ใช้ (0 = ไม่จำกัด)"""
    if len(sys.argv) > 1:
        try:
            v = float(sys.argv[1])
            if v >= 0:
                return v
        except ValueError:
            pass
        print(f"ค่า '{sys.argv[1]}' ไม่ถูกต้อง จะถามใหม่")

    while True:
        raw = input(f"จะให้ทำงานกี่วินาที? (Enter = {RUN_SECONDS}, 0 = ไม่จำกัด): ").strip()
        if raw == "":
            return RUN_SECONDS
        try:
            v = float(raw)
            if v >= 0:
                return v
            print("ต้องเป็นตัวเลข 0 ขึ้นไป")
        except ValueError:
            print("กรุณาใส่ตัวเลข เช่น 30 หรือ 120")


def sleep_until(seconds: float) -> bool:
    """นอนรอตามเวลา แต่ตื่นทันทีถ้ากด ESC — คืน False ถ้าถูกกด ESC"""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if esc_pressed():
            return False
        time.sleep(min(0.02, max(0.0, end - time.monotonic())))
    return True


def main() -> int:
    if not check_mouse():
        return 1

    run_seconds = ask_run_seconds()
    limit = "ไม่จำกัด" if run_seconds == 0 else f"{run_seconds:g} วินาที"
    speed = DEGREE_STEP * PIXELS_PER_DEGREE / TURN_DURATION  # px ต่อวินาที
    print(f"ตั้งค่า: กด {HOLD_KEY} ค้าง = หันขวา {DEGREE_STEP}° ทุก {TURN_DURATION:g}s + คลิกซ้ายค้าง | ทำงาน {limit}")

    install_esc_hook()
    print(f"เริ่มใน {START_DELAY} วินาที... (กด ESC หรือ Ctrl+C เพื่อหยุด)")
    if not sleep_until(START_DELAY):
        print("หยุดโดยผู้ใช้ (ESC)")
        return 0

    print(f"พร้อมแล้ว — กด {HOLD_KEY} ค้างเพื่อเริ่มหัน ปล่อยเพื่อหยุด")
    holding = False
    carry = 0.0          # เศษ pixel สะสม เพื่อให้ความเร็วคงที่แม้ dx ต่อ tick เป็นทศนิยม
    total_px = 0
    start = time.monotonic()
    last = start
    try:
        while True:
            now = time.monotonic()
            elapsed = now - start
            if run_seconds > 0 and elapsed >= run_seconds:
                print(f"ครบ {run_seconds:g} วินาทีแล้ว — หยุดการทำงาน")
                break
            if esc_pressed():
                print("หยุดโดยผู้ใช้ (ESC)")
                break

            pressed = key_held(HOLD_KEY)

            if pressed and not holding:
                holding = True
                left_down()
                last = now
                print(f"[{HOLD_KEY} กด] เริ่มหันขวา + คลิกซ้ายค้าง")
            elif not pressed and holding:
                holding = False
                left_up()
                deg = total_px / PIXELS_PER_DEGREE
                print(f"[{HOLD_KEY} ปล่อย] หยุด | หันไปแล้ว {deg:.0f}° ({total_px}px)")
                total_px = 0

            if holding:
                dt = now - last
                last = now
                carry += speed * dt
                dx = int(carry)
                carry -= dx
                if dx and not move_rel(dx):
                    left_up()
                    print("[FAIL] ส่งคำสั่งขยับเมาส์ไม่สำเร็จ — หยุดการทำงาน")
                    return 1
                total_px += dx

            time.sleep(TICK)
    except KeyboardInterrupt:
        print("หยุดโดยผู้ใช้ (Ctrl+C)")
    except pyautogui.FailSafeException:
        print("หยุดฉุกเฉิน (เมาส์อยู่มุมซ้ายบน)")
    finally:
        if holding:
            left_up()  # ปล่อยปุ่มซ้ายเสมอเมื่อจบโปรแกรม
    return 0


if __name__ == "__main__":
    sys.exit(main())
