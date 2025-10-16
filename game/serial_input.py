import serial
import re

SERIAL_ENABLED = True
try:
    ser = serial.Serial("COM3", 115200, timeout=0.01)
    print("✅ Connected to STM32 on COM3")
except Exception as e:
    SERIAL_ENABLED = False
    ser = None
    print("⚠️ ไม่พบ STM32:", e)


def poll_serial_commands():
    """อ่านทุกคำสั่งจาก STM32 ผ่าน Serial"""
    if not SERIAL_ENABLED or ser is None:
        return []

    cmds = []
    try:
        data = ser.read(1024)
        if data:
            s = data.decode("utf-8", "ignore").replace("\r", "")
            lines = s.split("\n")

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # ✅ ตรวจจับคำสั่ง PAUSE / RESUME
                if "PAUSE" in line:
                    cmds.append("PAUSE")
                elif "RESUME" in line:
                    cmds.append("RESUME")

                elif line.startswith("X="):
                    try:
                        parts = line.split(",")
                        if len(parts) < 3:
                            # ถ้ายังไม่ครบ X,Y,BTN ให้ข้าม
                            continue

                        x_val = int(parts[0].split("=")[1])
                        y_val = int(parts[1].split("=")[1])
                        btn_val = int(parts[2].split("=")[1])
                        cmds.append(
                            {"type": "JOY", "x": x_val, "y": y_val, "btn": btn_val}
                        )
                    except Exception as e:
                        print("⚠️ Parse error:", e, "Line:", line)

                # ✅ ตรวจจับปุ่มเกมอื่น ๆ (J, M, P, D, I, W)
                elif re.match(r"^[JMPDIW]$", line.strip(), re.IGNORECASE):
                    cmds.append(line.strip().upper())

    except Exception as e:
        print("Serial read error:", e)

    return cmds


# --- เพิ่มไว้ท้ายไฟล์ serial_input.py ---
def send_reset_signal():
    """ส่งคำสั่ง 'R' กลับไป STM32"""
    if not SERIAL_ENABLED or ser is None:
        print("⚠️ Serial not available for sending R.")
        return

    try:
        ser.write(b"R\n")
        ser.flush()
        print("📤 Sent 'R' to STM32 (reset LCD)")
    except Exception as e:
        print("⚠️ Failed to send 'R':", e)
