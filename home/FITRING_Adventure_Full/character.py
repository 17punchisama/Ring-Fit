import pygame
import sys
import serial
import subprocess
from pathlib import Path

# --------- Serial Config (STM32) ----------
PORT = "COM3"  # 👈 เปลี่ยนให้ตรงกับพอร์ตจริง
BAUD = 115200
ser = serial.Serial(PORT, BAUD, timeout=0.01)

# --------- ตั้งค่า ----------
TARGET_WIDTH = 960
TARGET_HEIGHT = 540
FPS = 60

# --------- เริ่ม ----------
pygame.init()
clock = pygame.time.Clock()
screen = pygame.display.set_mode((TARGET_WIDTH, TARGET_HEIGHT))
pygame.display.set_caption("FITRING Adventure - Character Select")

# --------- โหลด assets ----------
ASSET_DIR = Path(__file__).parent
bg_path = ASSET_DIR / "pg/bg1.png"
char1_path = ASSET_DIR / "pg/loongmadsaifah.png"
char2_path = ASSET_DIR / "pg/nakdablangkhom.png"
char_btn_path = ASSET_DIR / "pg/character.png"
font_path = ASSET_DIR / "fonts/Itim-Regular.ttf"
titlebox_path = ASSET_DIR / "pg/TitleBox.png"
circlebox_path = ASSET_DIR / "pg/CircleBox.png"
arrow_path = ASSET_DIR / "pg/LeftArrowButton.png"

BOX_SIZE = (370, 370)
BUTTON_SIZE = (180, 90)


def load_image(path, scale=None):
    if path.exists():
        img = pygame.image.load(str(path)).convert_alpha()
        if scale:
            img = pygame.transform.smoothscale(img, (int(scale[0]), int(scale[1])))
        return img
    else:
        print(f"⚠️ Warning: Missing file {path}")
        return None


background = load_image(bg_path, (TARGET_WIDTH, TARGET_HEIGHT))
char1_img = load_image(char1_path, BOX_SIZE)
char2_img = load_image(char2_path, BOX_SIZE)
char_btn_img = load_image(char_btn_path, BUTTON_SIZE)
titlebox_img = load_image(titlebox_path, (130, 40))
circlebox_img = load_image(circlebox_path)
arrow_img = load_image(arrow_path)

# --------- Rects ----------
box1_pos = (TARGET_WIDTH // 3.5, TARGET_HEIGHT // 2)
box2_pos = (TARGET_WIDTH * 2.5 // 3.5, TARGET_HEIGHT // 2)

if char1_img is None:
    char1_img = pygame.Surface(BOX_SIZE)
    char1_img.fill((150, 50, 50))
if char2_img is None:
    char2_img = pygame.Surface(BOX_SIZE)
    char2_img.fill((50, 50, 150))

char1_rect = char1_img.get_rect(center=box1_pos)
char2_rect = char2_img.get_rect(center=box2_pos)

BUTTON_POS = (TARGET_WIDTH // 2, 50)
button_rect = pygame.Rect(
    BUTTON_POS[0] - BUTTON_SIZE[0] // 2,
    BUTTON_POS[1] - BUTTON_SIZE[1] // 2,
    BUTTON_SIZE[0],
    BUTTON_SIZE[1],
)

BACK_BTN_POS = (50, 50)
circlebox_rect = (
    circlebox_img.get_rect(center=BACK_BTN_POS)
    if circlebox_img
    else pygame.Rect(BACK_BTN_POS[0] - 25, BACK_BTN_POS[1] - 25, 50, 50)
)
arrow_rect = arrow_img.get_rect(center=BACK_BTN_POS) if arrow_img else None

font = (
    pygame.font.Font(str(font_path), 16)
    if font_path.exists()
    else pygame.font.SysFont("arial", 16, bold=True)
)

# --------- Cursor (Joystick) ----------
cursor_x, cursor_y = TARGET_WIDTH // 2, TARGET_HEIGHT // 2
center_x, center_y = 2880, 2020
deadzone = 250
speed = 10
btn_prev = 0
stm32_btn_prev = 0


# --------- ฟังก์ชัน ----------
def go_to_home():
    print("🏠 กลับหน้า Home")
    subprocess.Popen([sys.executable, str(ASSET_DIR / "home.py")])
    ser.close()
    pygame.quit()
    sys.exit()


def start_game(char):
    print(f"🎮 เริ่มเกมเป็น {char}")
    # ✅ ส่งสัญญาณให้ STM32 เริ่มนับเวลาก่อนเข้าเกม
    try:
        ser.write(b"S")
        print("🕒 ส่งสัญญาณเริ่มเวลาไป STM32 แล้ว (S)")
    except Exception as e:
        print("⚠️ ไม่สามารถส่งสัญญาณเริ่มได้:", e)

    # ✅ จากนั้นเปิดหน้า game.py
    subprocess.Popen([sys.executable, str(ASSET_DIR / "/Ring-Fit/game/main.py"), char])
    ser.close()
    pygame.quit()
    sys.exit()


# --------- Main Loop ----------
running = True
while running:
    dt = clock.tick(FPS) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEMOTION:
            cursor_x, cursor_y = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if circlebox_rect.collidepoint(event.pos):
                go_to_home()
            elif char1_rect.collidepoint(event.pos):
                start_game("char1")
            elif char2_rect.collidepoint(event.pos):
                start_game("char2")

    # --- อ่านค่าจาก STM32 ---
    line = ser.readline().decode(errors="ignore").strip()
    if line.startswith("X="):
        try:
            parts = line.split(",")
            x_val = int(parts[0].split("=")[1])
            y_val = int(parts[1].split("=")[1])
            btn = int(parts[2].split("=")[1]) if len(parts) >= 3 else 0

            dx = x_val - center_x
            dy = y_val - center_y
            if abs(dx) < deadzone:
                dx = 0
            if abs(dy) < deadzone:
                dy = 0

            cursor_x += int(dx / 400 * speed)
            cursor_y += int(dy / 400 * speed)
            cursor_x = max(8, min(TARGET_WIDTH - 8, cursor_x))
            cursor_y = max(8, min(TARGET_HEIGHT - 8, cursor_y))

            if btn == 1 and btn_prev == 0:
                if circlebox_rect.collidepoint((cursor_x, cursor_y)):
                    go_to_home()
                elif char1_rect.collidepoint((cursor_x, cursor_y)):
                    start_game("char1")
                elif char2_rect.collidepoint((cursor_x, cursor_y)):
                    start_game("char2")
                else:
                    print("[JOY] ปุ่มถูกกด แต่ไม่ได้ชี้ปุ่มใด")
            btn_prev = btn

        except Exception as e:
            print("Parse error:", line, e)

    elif "START BUTTON PRESSED" in line:
        if stm32_btn_prev == 0:
            if circlebox_rect.collidepoint((cursor_x, cursor_y)):
                go_to_home()
            elif char1_rect.collidepoint((cursor_x, cursor_y)):
                start_game("char1")
            elif char2_rect.collidepoint((cursor_x, cursor_y)):
                start_game("char2")
        stm32_btn_prev = 1
    else:
        stm32_btn_prev = 0

    # --------- วาด ----------
    if background:
        screen.blit(background, (0, 0))
    else:
        screen.fill((40, 40, 50))

    # ตัวละคร
    screen.blit(char1_img, char1_rect)
    screen.blit(char2_img, char2_rect)

    # ตรวจว่าอยู่ในพื้นที่ hover ใดไหม
    hovering = (
        circlebox_rect.collidepoint((cursor_x, cursor_y))
        or char1_rect.collidepoint((cursor_x, cursor_y))
        or char2_rect.collidepoint((cursor_x, cursor_y))
    )

    # highlight เฉพาะปุ่มย้อนกลับ + ตัวละคร 2 ตัว
    if circlebox_rect.collidepoint((cursor_x, cursor_y)):
        pygame.draw.rect(
            screen, (255, 255, 0), circlebox_rect.inflate(10, 10), 4, border_radius=20
        )
    if char1_rect.collidepoint((cursor_x, cursor_y)):
        hl = char1_rect.inflate(10, 10)
        pygame.draw.rect(screen, (255, 255, 0), hl, 4, border_radius=10)
    if char2_rect.collidepoint((cursor_x, cursor_y)):
        hl = char2_rect.inflate(10, 10)
        pygame.draw.rect(screen, (255, 255, 0), hl, 4, border_radius=10)

    # ชื่อใต้ตัวละคร
    if titlebox_img:
        tr1 = titlebox_img.get_rect(center=(char1_rect.centerx, char1_rect.top - 40))
        tr2 = titlebox_img.get_rect(center=(char2_rect.centerx, char2_rect.top - 40))
        screen.blit(titlebox_img, tr1)
        screen.blit(titlebox_img, tr2)
        screen.blit(
            font.render("ลุงหมัดสายฟ้า", True, (255, 255, 255)),
            font.render("ลุงหมัดสายฟ้า", True, (255, 255, 255)).get_rect(
                center=tr1.center
            ),
        )
        screen.blit(
            font.render("นักดาบหลังค่อม", True, (255, 255, 255)),
            font.render("นักดาบหลังค่อม", True, (255, 255, 255)).get_rect(
                center=tr2.center
            ),
        )

    # ปุ่ม Character ด้านบน (ไม่มี hover)
    if char_btn_img:
        screen.blit(char_btn_img, button_rect)

    # ปุ่มย้อนกลับ
    if circlebox_img:
        screen.blit(circlebox_img, circlebox_rect)
    if arrow_img:
        screen.blit(arrow_img, arrow_rect)

    # ✅ เคอร์เซอร์เรืองแสงเหมือนหน้า Home + glow ตอน hover
    if hovering:
        # วาดวงเรืองแสงรอบเคอร์เซอร์ (เมื่อ hover)
        pygame.draw.circle(screen, (255, 255, 150), (cursor_x, cursor_y), 20, 4)
    pygame.draw.circle(screen, (255, 255, 80), (cursor_x, cursor_y), 14)  # วงนอกสีเหลือง
    pygame.draw.circle(screen, (0, 0, 0), (cursor_x, cursor_y), 14, 3)  # ขอบดำ
    pygame.draw.circle(screen, (255, 255, 200), (cursor_x, cursor_y), 8)  # แกนในสีขาวนวล

    pygame.display.flip()

# --------- Exit ----------
ser.close()
pygame.quit()
sys.exit()
