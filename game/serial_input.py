SERIAL_ENABLED = True
try:
    import serial

    ser = serial.Serial("COM3", 115200, timeout=0)
except:
    SERIAL_ENABLED = False
    ser = None


def poll_serial_commands():
    """อ่านทุกตัวอักษรจาก Serial และส่งกลับเป็น list"""
    if not SERIAL_ENABLED or ser is None:
        return []

    cmds = []
    try:
        data = ser.read(1024)  # อ่านสูงสุด 1024 ไบต์
        if data:
            s = data.decode("utf-8", "ignore")
            for ch in s:
                print(ch)
                if ch.strip() != "":  # กรอง whitespace เล็กน้อย
                    if (
                        ch == "M"
                        or ch == "P"
                        or ch == "D"
                        or ch == "W"
                        or ch == "J"
                        or ch == "I"
                    ):
                        cmds.append(ch)  # เก็บทุกตัวอักษรที่ได้
    except:
        pass
    return cmds
