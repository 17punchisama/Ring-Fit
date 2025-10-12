import pygame
import sys
from pathlib import Path
import serial
import subprocess

# ---------------- Serial Config ----------------
PORT = "COM3"  # 👈 ตรวจให้ตรงกับพอร์ตจริงของ STM32
BAUD = 115200
ser = serial.Serial(PORT, BAUD, timeout=0.05)

# ---------------- Pygame Setup ----------------
TARGET_WIDTH = 960
TARGET_HEIGHT = 540
FPS = 60

pygame.init()
clock = pygame.time.Clock()
screen = pygame.display.set_mode((TARGET_WIDTH, TARGET_HEIGHT))
pygame.display.set_caption("FITRING Adventure - Home Screen")

# ---------------- Load Assets ----------------
ASSET_DIR = Path(__file__).parent
bg_path = ASSET_DIR / "pg/bg1.png"
button_path = ASSET_DIR / "pg/start2.png"
name_path = ASSET_DIR / "pg/name.png"


def load_img(path, size=None):
    """โหลดรูปพร้อมปรับขนาด (ถ้ามี)"""
    if path.exists():
        img = pygame.image.load(str(path)).convert_alpha()
        if size:
            img = pygame.transform.smoothscale(img, size)
        return img
    return None


background = load_img(bg_path, (TARGET_WIDTH, TARGET_HEIGHT))
button_img = load_img(button_path, (220, 110))  # ✅ ใหญ่ขึ้น
name_img = load_img(name_path, (750, 220))  # ✅ ชัดขึ้น

button_rect = button_img.get_rect(center=(TARGET_WIDTH // 2, TARGET_HEIGHT - 100))
name_rect = name_img.get_rect(center=(TARGET_WIDTH // 2, TARGET_HEIGHT // 2 - 60))

# ---------------- Joystick Calibration ----------------
CENTER_X, CENTER_Y = 2880, 2020  # ค่ากลางจาก STM32
DEADZONE = 250
SPEED = 6

# ---------------- Cursor ----------------
cursor_x, cursor_y = TARGET_WIDTH // 2, TARGET_HEIGHT // 2
btn_prev = 0
x_val = CENTER_X
y_val = CENTER_Y
btn = 0

# ---------------- Font ----------------
font_title = pygame.font.SysFont("consolas", 36, bold=True)
font_debug = pygame.font.SysFont("consolas", 24, bold=True)

print("✅ Connected to STM32 on", PORT)


# ---------------- Helper Functions ----------------
def is_hover(rect, pos):
    return rect.collidepoint(pos)


def draw_text_outline(surface, text, font, pos, text_color, outline_color, thickness=2):
    """วาดข้อความแบบมีขอบ"""
    base = font.render(text, True, text_color)
    x, y = pos
    for dx in range(-thickness, thickness + 1):
        for dy in range(-thickness, thickness + 1):
            if dx == 0 and dy == 0:
                continue
            surface.blit(font.render(text, True, outline_color), (x + dx, y + dy))
    surface.blit(base, pos)


def go_to_character():
    print("➡️ Going to character.py ...")
    subprocess.Popen([sys.executable, str(ASSET_DIR / "character.py")])
    ser.close()
    pygame.quit()
    sys.exit()


# ---------------- Main Loop ----------------
running = True
while running:
    clock.tick(FPS)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # ---- อ่านค่าจาก STM32 ----
    try:
        line = ser.readline().decode(errors="ignore").strip()
        if line.startswith("X="):
            parts = line.replace(" ", "").split(",")
            x_val = int(parts[0].split("=")[1])
            y_val = int(parts[1].split("=")[1])
            btn = int(parts[2].split("=")[1]) if len(parts) >= 3 else 0

            dx = x_val - CENTER_X
            dy = y_val - CENTER_Y

            if abs(dx) < DEADZONE:
                dx = 0
            if abs(dy) < DEADZONE:
                dy = 0

            cursor_x += int(dx / 300 * SPEED)
            cursor_y += int(dy / 300 * SPEED)
            cursor_x = max(8, min(TARGET_WIDTH - 8, cursor_x))
            cursor_y = max(8, min(TARGET_HEIGHT - 8, cursor_y))

            # ตรวจการกดปุ่มจอย
            if btn == 1 and btn_prev == 0:
                if is_hover(button_rect, (cursor_x, cursor_y)):
                    print("🎮 Start Game clicked! (joystick)")
                    go_to_character()
            btn_prev = btn

    except Exception as e:
        print("⚠️ Parse error:", e)

    # ---------------- วาดภาพ ----------------
    if background:
        screen.blit(background, (0, 0))
    else:
        screen.fill((40, 40, 50))

    # โลโก้ / ชื่อเกม
    if name_img:
        screen.blit(name_img, name_rect)

    # ปุ่ม Start
    screen.blit(button_img, button_rect)
    if is_hover(button_rect, (cursor_x, cursor_y)):
        pygame.draw.rect(
            screen, (255, 255, 0), button_rect.inflate(10, 10), 5, border_radius=20
        )
        glow_radius = 20
        pygame.draw.circle(
            screen, (255, 255, 150), (cursor_x, cursor_y), glow_radius, 4
        )

    # เคอร์เซอร์ (เรืองแสง)
    pygame.draw.circle(screen, (255, 255, 80), (cursor_x, cursor_y), 14)
    pygame.draw.circle(screen, (0, 0, 0), (cursor_x, cursor_y), 14, 3)
    pygame.draw.circle(screen, (255, 255, 200), (cursor_x, cursor_y), 8)

    # # Debug overlay
    # debug_lines = [f"X={x_val}, Y={y_val}, BTN={btn}"]
    # y_offset = 10
    # for text in debug_lines:
    #     surf = font_debug.render(text, True, (255, 255, 255))
    #     screen.blit(surf, (10, y_offset))
    #     y_offset += 28

    pygame.display.flip()

# ---------------- Exit ----------------
ser.close()
pygame.quit()
sys.exit()
