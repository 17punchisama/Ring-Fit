import serial
import time

# แทน COM3 ด้วยพอร์ตจริงที่ STM32 ต่อไว้
ser = serial.Serial(port="COM3", baudrate=115200, timeout=1)

# รอให้พอร์ตพร้อม
time.sleep(2)

# ส่งข้อความไปหา STM32
ser.write(b"Hello STM32!\r\n")

# อ่านค่าจาก STM32
while True:
    if ser.in_waiting > 0:          # ถ้ามีข้อมูลเข้ามา
        line = ser.readline().decode('utf-8').rstrip()
        print("From STM32:", line)
