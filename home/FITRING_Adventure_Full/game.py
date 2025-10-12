import pygame
import sys
import serial
import subprocess
import re

# --------- Serial Config ----------
PORT_JOYSTICK = "COM3"  # ✅ ใช้พอร์ตเดียว
BAUD = 115200
ser_joy = serial.Serial(PORT_JOYSTICK, BAUD, timeout=0.01)

# --------- Pygame Init ----------
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("FITRING Adventure - Game")
clock = pygame.time.Clock()

font = pygame.font.SysFont("arial", 32, bold=True)
chosen = sys.argv[1] if len(sys.argv) > 1 else "Unknown"

paused = False
pause_menu_selection = 0  # 0 = Resume, 1 = Exit
stm_time_str = "00:00"
stm_calories = 0.0


# --------- ฟังก์ชันช่วย ----------
def toggle_pause(source="Unknown"):
    """สลับ pause/resume ทั้งเกมและ STM32"""
    global paused
    paused = not paused
    if paused:
        print(f"⏸ Game Paused ({source})")
        ser_joy.write(b"P")  # ➡ หยุดเวลา STM32
    else:
        print(f"▶️ Game Resumed ({source})")
        ser_joy.write(b"S")  # ➡ ต่อเวลา STM32


def go_home():
    """ออกจากเกมและกลับหน้า Home"""
    try:
        ser_joy.write(b"R")  # ✅ รีเซ็ตเวลาและแคลอรี่บน STM32
        print("🔄 Reset timer & calories on STM32")
    except Exception as e:
        print("⚠️ ไม่สามารถส่งสัญญาณรีเซ็ตได้:", e)

    ser_joy.close()
    pygame.quit()
    subprocess.run(["python", "home.py"])
    sys.exit()


# --------- เริ่มจับเวลาทันทีเมื่อเข้าเกม ----------
ser_joy.write(b"S")

# --------- Game Loop ----------
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if not paused and event.key == pygame.K_SPACE:
                toggle_pause("Keyboard")
            elif paused:
                if event.key in (pygame.K_UP, pygame.K_w):
                    pause_menu_selection = (pause_menu_selection - 1) % 2
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    pause_menu_selection = (pause_menu_selection + 1) % 2
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if pause_menu_selection == 0:
                        toggle_pause("Keyboard Resume")
                    elif pause_menu_selection == 1:
                        go_home()

    # --- อ่านค่าจาก STM32 ---
    line_joy = ser_joy.readline().decode(errors="ignore").strip()
    if line_joy:
        # อ่านค่าเวลา/แคลอรี่
        match = re.search(r"Time\s+(\d{2}:\d{2}).*Calories\s*=\s*([\d.]+)", line_joy)
        if match:
            stm_time_str = match.group(1)
            stm_calories = float(match.group(2))

        # ตรวจจับคำสั่งภายในจาก STM32
        if "INFO: TIMER PAUSED" in line_joy:
            paused = True
        elif "INFO: TIMER START" in line_joy or "INFO: TIMER RESUME" in line_joy:
            paused = False

        # ---- ควบคุมเมนู pause ด้วย joystick ----
        if paused and line_joy.startswith("X="):
            try:
                parts = line_joy.split(",")
                x_val = int(parts[0].split("=")[1])
                y_val = int(parts[1].split("=")[1])
                btn_val = int(parts[2].split("=")[1])

                # --- ควบคุมการเลื่อนเมนูด้วยแกน Y ---
                center_y = 2054
                deadzone = 300
                if y_val > center_y + deadzone:  # ดันลง
                    pause_menu_selection = 1
                elif y_val < center_y - deadzone:  # ดันขึ้น
                    pause_menu_selection = 0

                # --- กดปุ่ม joystick เพื่อเลือก ---
                if btn_val == 1:
                    if pause_menu_selection == 0:
                        toggle_pause("Joystick Resume")
                    elif pause_menu_selection == 1:
                        go_home()

            except Exception as e:
                print("Parse error:", e)

    # --------- วาดหน้าจอหลัก ----------
    screen.fill((30, 30, 60))

    title_text = font.render(f"Character: {chosen}", True, (255, 255, 0))
    screen.blit(title_text, (200, 160))

    time_text = font.render(f"Time: {stm_time_str}", True, (0, 255, 0))
    screen.blit(time_text, (200, 220))

    kcal_text = font.render(f"Calories: {stm_calories:.2f} kcal", True, (255, 100, 100))
    screen.blit(kcal_text, (200, 260))

    # --------- เมนู Pause ----------
    if paused:
        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        pause_title = font.render("GAME PAUSED", True, (255, 255, 255))
        screen.blit(
            pause_title, pause_title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 100))
        )

        options = ["RESUME", "EXIT"]
        for i, opt in enumerate(options):
            color = (255, 255, 0) if i == pause_menu_selection else (200, 200, 200)
            text = font.render(opt, True, color)
            screen.blit(text, text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + i * 60)))

    pygame.display.flip()
    clock.tick(60)

go_home()
