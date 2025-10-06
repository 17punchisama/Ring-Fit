SERIAL_ENABLED = True
try:
    import serial
    ser = serial.Serial("COM8", 115200, timeout=0)
except:
    SERIAL_ENABLED = False
    ser = None

# เก็บตัวอักษรล่าสุดที่อ่าน
_last_serial_char = None

def poll_serial_commands():
    global _last_serial_char
    if not SERIAL_ENABLED or ser is None:
        return []

    cmds = []
    try:
        data = ser.read(1024)
        if data:
            s = data.decode('utf-8', 'ignore')
            for ch in s:
                if ch.strip() == '':
                    continue
                # edge-trigger: เพิ่มเฉพาะถ้าแตกต่างจากครั้งก่อน
                if ch != _last_serial_char:
                    cmds.append(ch)
                    _last_serial_char = ch
                # ถ้าเหมือนตัวเดิม จะไม่เพิ่ม
    except:
        pass
    return cmds
