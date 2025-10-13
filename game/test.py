# main.py
import pygame
from sys import exit
import sys
import random
import subprocess


from player import Player
from coin import Coin
from parallax import ParallaxBG

from serial_input import poll_serial_commands, send_reset_signal


from guide import Guide
from enemy import Enemy
from obstacle import Obstacle
from projectile import Fireball  # ใช้หรือไม่ใช้ก็ได้

# from character import start_game  # ฟังก์ชันไปหน้า home


pygame.init()
W, H = 960, 540
screen = pygame.display.set_mode((W, H))
clock = pygame.time.Clock()
GROUND_Y = 440
font = pygame.font.SysFont(None, 28)

chosen = sys.argv[1] if len(sys.argv) > 1 else "Unknown"
# ---------- Player class / alt key ----------
PLAYER_CLASS = chosen  # "wizard" หรือ "swordman"
ALT_KEY = "M" if PLAYER_CLASS.lower() == "wizard" else "P"

# ใช้เฉพาะเลเวล >= 3 เวลาอยู่ใน challenge (เริ่มที่ J)
challenge_expect_key = "J"

# ---------- Game variables ----------
level = 3
coins_collected = 0
COINS_TO_PASS = 10

# Lv2
level2_kills = 0
LEVEL2_KILL_TARGET = 5

# Lv3
level3_kills = 0
LEVEL3_KILL_TARGET = 10

# Lv4 (บอสไฟ)
level4_kills = 0
LEVEL4_KILL_TARGET = 15

# Lv5 (ลูป)
level5_kills_total = 0
level5_cycle_kills = 0
LEVEL5_CYCLE_TARGET = 5
level5_force_boss_next = False

# progress
progress = 0.0  # ใช้ในเลเวล 1
PROGRESS_TO_SPAWN = 100
PROGRESS_SPEED_PER_MS = 0.05

LEVEL2_PROGRESS_MAX = 100  # ใช้ในเลเวล 2–4
level2_progress = 0.0

sequence = None

# Spawn rates
COIN_PROB_L2 = 0.75
COIN_PROB_L3 = 0.50
COIN_PROB_L4 = 0.25
L3_MONSTER_VS_OBS = 0.75
L4_MONSTER_VS_OBS = 0.90

# ---------- Sprite groups ----------
player_group = pygame.sprite.GroupSingle(Player(PLAYER_CLASS, (500, GROUND_Y)))
coin_group = pygame.sprite.Group()
enemy_group = pygame.sprite.Group()
obstacle_group = pygame.sprite.Group()
projectile_group = pygame.sprite.Group()
prop_group = pygame.sprite.Group()

# ---------- Props scroll ----------
next_prop_px = 0
prop_scroll_accum = 0.0  # เก็บเศษทศนิยมของพิกเซลไว้รวมรอบถัดไป

PROP_TYPES = [
    {"path": "graphics/props/crate-stack.png", "weight": 1, "scale": 1.0},
    {"path": "graphics/props/street-lamp.png", "weight": 1, "scale": 1.0},
    {"path": "graphics/props/wagon.png", "weight": 1, "scale": 1.0},
    {"path": "graphics/props/well.png", "weight": 1, "scale": 1.0},
]

# ---------- Guide ----------
animations_dict = {
    "collect_coin": "graphics/guide/collect_coin.png",
    "squeeze": "graphics/guide/squeeze.png",
    "wizard_attack": "graphics/guide/wizard_attack.png",
    "swordman_attack": "graphics/guide/swordman_attack.png",
    "squat": "graphics/guide/squat.png",
}
guide = Guide(animations_dict, pos=(180, 350), scale=4.0)
guide_group = pygame.sprite.Group(guide)
guide.visible = False
guide.active = False

# ตัวจับเวลาให้ไกด์หายเอง + ธงว่าถูกบังคับระหว่างชาเลนจ์/อุปสรรค
guide_timer_ms = 0
guide_forced = False


def show_guide(state_name, duration_ms=1200):
    """แสดงไกด์ state_name ชั่วคราว แล้วหายหลังครบ duration_ms"""
    global guide_timer_ms
    if state_name in guide.animations:
        guide.set_state(state_name)
        guide.visible = True
        guide.active = True
        guide.frame_index = 0.0
        guide_timer_ms = duration_ms


# === พื้นหลังไกด์แบบเก่า ===
USE_OLD_GUIDE_BG = True
GUIDE_BG_OLD_PATH = "graphics/guide/background.png"
try:
    GUIDE_BG_OLD = pygame.image.load(GUIDE_BG_OLD_PATH).convert_alpha()
except:
    GUIDE_BG_OLD = None


def draw_guide_background(screen, target_rect):
    """
    วาดพื้นหลังไกด์:
    - ถ้ารูปมีขนาดเท่าหน้าจอ -> วาดที่ (0,0) เลย (เพราะกรอบถูกวางแบบ absolute ในไฟล์)
    - ถ้ารูปเล็ก -> จัดกลางตามตำแหน่งของ guide (เลื่อนลงนิดหน่อย)
    """
    if not (USE_OLD_GUIDE_BG and GUIDE_BG_OLD):
        return

    bg = GUIDE_BG_OLD
    bw, bh = bg.get_size()

    # 1) ภาพเต็มจอ → วาดทับทั้งจอ
    if bw == screen.get_width() and bh == screen.get_height():
        screen.blit(bg, (0, 0))
        return

    # 2) ภาพเล็ก → จัดกลางกับไกด์
    bg_rect = bg.get_rect()
    bg_rect.centerx = target_rect.centerx
    bg_rect.centery = target_rect.centery + 10
    screen.blit(bg, bg_rect.topleft)


# ---------- Parallax ----------
parallax = ParallaxBG(
    W,
    H,
    [
        ("graphics/background/sky.png", 0.0),
        ("graphics/background/town.png", 0.25),
        ("graphics/background/houses.png", 0.17, (1400, 420), GROUND_Y + 12),
        ("graphics/background/ground.png", 0.34),
    ],
)
PARALLAX_SCROLL_RATE = 0.12  # ต้องตรงกับ ParallaxBG.update()
HOUSES_LAYER_SPEED = 0.17  # ต้องตรงกับ speed ของ houses ใน layers


# ---------- Helpers ----------
def load_img_scaled(path, scale=1.0):
    img = pygame.image.load(path).convert_alpha()
    if scale != 1.0:
        w, h = img.get_size()
        img = pygame.transform.smoothscale(img, (int(w * scale), int(h * scale)))
    return img


def spawn_prop():
    weights = [t.get("weight", 1) for t in PROP_TYPES]
    idx = random.choices(range(len(PROP_TYPES)), weights=weights, k=1)[0]
    cfg = PROP_TYPES[idx]
    img = load_img_scaled(cfg["path"], cfg.get("scale", 1.0))
    spr = pygame.sprite.Sprite()
    spr.image = img
    spr.rect = img.get_rect(midbottom=(W + img.get_width() // 2, GROUND_Y - 17))
    prop_group.add(spr)


def spawn_coin():
    coin = Coin((W + 50, GROUND_Y - 70), "graphics/items/Coin.png")
    coin_group.add(coin)


def start_sequence(steps):
    return {"steps": steps, "idx": 0, "started": False}


def draw_hearts(screen, player, pos=(20, 20), spacing=4):
    hp_per_heart = player.max_hp / 5
    x, y = pos
    for i in range(5):
        heart_hp = player.hp - i * hp_per_heart
        if heart_hp >= 4:
            idx = 0
        elif heart_hp >= 3:
            idx = 1
        elif heart_hp >= 2:
            idx = 2
        elif heart_hp >= 1:
            idx = 3
        else:
            idx = 4
        screen.blit(player.heart_images[idx], (x, y))
        x += player.heart_images[idx].get_width() + spacing


OBSTACLE_ASSETS = [
    "graphics/obstacles/barrel.png",
    "graphics/obstacles/crate.png",
]


def spawn_obstacle():
    obstacle = Obstacle(
        pos=(W + 100, GROUND_Y),
        stop_offset=120,
        approach_speed=3,
        exit_speed=6,
        pass_margin=150,
        image_paths=OBSTACLE_ASSETS,
        scale=1.5,
    )
    obstacle_group.add(obstacle)


# ---------- UART walk impulse ----------
RUN_IMPULSE_MS = 200
serial_run_ms = 0
serial_dir = 1
IMPULSE_ADD_MS = 140
IMPULSE_MAX_MS = 300

# ---------- Pause Control (จาก COM3) ----------
game_paused = False  # จะถูกเปลี่ยนโดยสัญญาณ PAUSE/RESUME จาก STM32
pause_menu_selection = 0


def go_home():
    """กลับหน้า Home"""
    send_reset_signal()
    pygame.quit()
    subprocess.run(["python", "home.py"])
    sys.exit()


# ---------- Main loop ----------
while True:
    dt = clock.tick(60)

    frame_resolved = False
    pending_start_next = False

    # ===== Events =====
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            send_reset_signal()  # ✅ ใช้พอร์ตเดิม ไม่ต้องเปิดใหม่
            pygame.quit()
            sys.exit()

        if event.type == pygame.KEYDOWN:
            p = player_group.sprite
            enemy = enemy_group.sprites()[0] if enemy_group.sprites() else None
            in_challenge = bool(enemy and enemy.challenge_ms_left is not None)
            in_sequence = sequence is not None

            # --- J ---
            if event.key == pygame.K_j and not game_paused:
                if in_challenge:
                    need_j = (level == 2 and challenge_expect_key == "J") or (
                        level >= 3 and challenge_expect_key == "J"
                    )
                    if need_j:
                        p.attack_pressed_total += 1
                elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                    p.play_attack_anim_named("attack")

            # --- M/P (ALT) + โชว์ไกด์ตามปุ่มที่กด ---
            if event.key in (pygame.K_m, pygame.K_p) and not game_paused:
                alt_ok = (ALT_KEY == "M" and event.key == pygame.K_m) or (
                    ALT_KEY == "P" and event.key == pygame.K_p
                )

                if event.key == pygame.K_m:
                    show_guide("wizard_attack", 1200)
                if event.key == pygame.K_p:
                    show_guide("swordman_attack", 1200)

                if (
                    in_challenge
                    and level >= 3
                    and alt_ok
                    and challenge_expect_key == ALT_KEY
                ):
                    p.attack_pressed_total += 1
                elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                    p.play_attack_anim_named("attack2")

            if event.key == pygame.K_r and not game_paused:
                p.revive()

            # ---- Pick coin (I) ----
            if event.key == pygame.K_i and not game_paused:
                if getattr(p, "coin_lock", False) and coin_group.sprites():
                    coin_group.sprites()[0].kill()
                    if level == 1:
                        progress = 0
                        guide.visible = False
                        guide.active = False
                        p.guide_shown = False
                    else:
                        level2_progress = 0.0
                    p.coin_lock = False
                    coins_collected += 1

            # --- Jump over obstacle ---
            if (
                event.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP)
                and not game_paused
            ):
                obstacle = (
                    obstacle_group.sprites()[0] if obstacle_group.sprites() else None
                )
                if (
                    getattr(p, "obstacle_lock", False)
                    and obstacle
                    and getattr(obstacle, "state", "") == "wait"
                ):
                    if p.on_ground and not (p.full_lock or p.locked or p.dead):
                        p.vel_y = -p.jump_power
                        p.on_ground = False
                        p.set_state("jump")
                    p.obstacle_lock = False
                    obstacle.start_pass(p)
                # ไม่โชว์ squat ตรงนี้แล้ว — ให้ขึ้นเฉพาะตอน obstacle อยู่ใน state "wait"

    # ===== Serial input =====
    keys = pygame.key.get_pressed()
    p = player_group.sprite
    enemy = enemy_group.sprites()[0] if enemy_group.sprites() else None

    serial_cmds = poll_serial_commands()

    for cmd in serial_cmds:
        if isinstance(cmd, dict) and cmd["type"] == "JOY":
            print(f"Joystick X={cmd['x']} Y={cmd['y']} BTN={cmd['btn']}")
        elif cmd == "PAUSE":
            # หยุดเกม
            pass
        elif cmd == "RESUME":
            # เล่นต่อ
            pass

    # ---- รับคำสั่ง PAUSE/RESUME จาก STM32 (COM3) ----
    if "PAUSE" in serial_cmds:
        if not game_paused:
            print("⏸ Game paused from STM32")
        game_paused = True

    if "RESUME" in serial_cmds:
        if game_paused:
            print("▶️ Game resumed from STM32")
        game_paused = False

    # ถ้าหยุดเกม ให้หยุดแรงขับการเดินที่มาจาก serial ด้วย
    if game_paused:
        serial_run_ms = 0
        p.external_dir = 0

    # ---- ควบคุม action อื่นๆ จาก serial เฉพาะตอนไม่ pause ----
    if serial_cmds and not game_paused:
        in_challenge = bool(enemy and enemy.challenge_ms_left is not None)
        in_sequence = sequence is not None

        if any(ch in ("W", "w") for ch in serial_cmds) or any(
            ch == " " for ch in serial_cmds
        ):
            obstacle = obstacle_group.sprites()[0] if obstacle_group.sprites() else None
            if (
                getattr(p, "obstacle_lock", False)
                and obstacle
                and getattr(obstacle, "state", "") == "wait"
            ):
                if p.on_ground and not (p.full_lock or p.locked or p.dead):
                    p.vel_y = -p.jump_power
                    p.on_ground = False
                    p.set_state("jump")
                p.obstacle_lock = False
                obstacle.start_pass(p)

        if any(ch in ("J", "j") for ch in serial_cmds):
            need_j = (level == 2 and challenge_expect_key == "J") or (
                level >= 3 and challenge_expect_key == "J"
            )
            if in_challenge and need_j:
                p.attack_pressed_total += 1
            elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                p.play_attack_anim_named("attack")

        if any(ch in ("M", "m", "P", "p") for ch in serial_cmds):
            alt_hit = (
                ("M" in serial_cmds or "m" in serial_cmds)
                if ALT_KEY == "M"
                else ("P" in serial_cmds or "p" in serial_cmds)
            )
            if "M" in serial_cmds or "m" in serial_cmds:
                show_guide("wizard_attack", 1200)
            if "P" in serial_cmds or "p" in serial_cmds:
                show_guide("swordman_attack", 1200)

            if (
                in_challenge
                and level >= 3
                and alt_hit
                and challenge_expect_key == ALT_KEY
            ):
                p.attack_pressed_total += 1
            elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                p.play_attack_anim_named("attack2")

        if any(ch in ("D", "d") for ch in serial_cmds) and not (
            p.full_lock or p.locked or p.dead
        ):
            serial_dir = 1
            serial_run_ms = min(serial_run_ms + IMPULSE_ADD_MS, IMPULSE_MAX_MS)

        if any(ch in ("I", "i") for ch in serial_cmds):
            if getattr(p, "coin_lock", False) and coin_group.sprites():
                coin_group.sprites()[0].kill()
                if level == 1:
                    progress = 0
                    guide.visible = False
                    guide.active = False
                    p.guide_shown = False
                else:
                    level2_progress = 0.0
                p.coin_lock = False
                coins_collected += 1

    if (
        serial_run_ms > 0
        and not (p.full_lock or p.locked or p.dead)
        and not game_paused
    ):
        p.external_move = True
        p.external_dir = serial_dir
        serial_run_ms -= dt
    else:
        p.external_dir = 0

    # ===== Update =====
    if not game_paused:
        player_group.update(keys, GROUND_Y)

        # enemies
        for e in enemy_group.sprites():
            e.update(p, dt)
            # e.shoot_tick(p, dt, projectile_group, Fireball)  # ถ้าจะเปิดระบบยิง

        # ----- Guide timer -----
        if guide_timer_ms > 0:
            guide_timer_ms = max(0, guide_timer_ms - dt)
            if guide_timer_ms == 0 and not guide_forced:
                guide.visible = False
                guide.active = False

        # ===== Props on ground =====
        if p.is_moving:
            prop_scroll_accum += dt * PARALLAX_SCROLL_RATE * HOUSES_LAYER_SPEED

        move_px = int(prop_scroll_accum)
        if move_px > 0:
            for pr in prop_group.sprites():
                pr.rect.x -= move_px
                if pr.rect.right < 0:
                    pr.kill()
            next_prop_px -= move_px
            prop_scroll_accum -= move_px

        if next_prop_px <= 0:
            spawn_prop()
            next_prop_px = random.randint(100, 400)

        for obs in obstacle_group.sprites():
            obs.update(p, dt)

        # โปรเจกไทล์
        for fb in projectile_group.sprites():
            fb.update(dt, screen_w=W)

        # ===== Level 1 =====
        if level == 1:
            if len(coin_group) == 0:
                spawn_coin()
            coin = coin_group.sprites()[0] if coin_group.sprites() else None

            if p.is_moving and not getattr(p, "coin_lock", False):
                progress += PROGRESS_SPEED_PER_MS * dt
                if progress > PROGRESS_TO_SPAWN:
                    progress = PROGRESS_TO_SPAWN

            if progress >= PROGRESS_TO_SPAWN and coin:
                if coin.rect.centerx > p.rect.centerx:
                    if p.is_moving:
                        coin.rect.centerx -= 10
                else:
                    if not getattr(p, "guide_shown", False):
                        guide.set_state("collect_coin")
                        guide.active = True
                        guide.visible = True
                        guide.frame_index = 0.0
                        p.guide_shown = True
                    p.coin_lock = True
                    p.is_moving = False
                    p.set_state("idle")

            if coins_collected >= COINS_TO_PASS:
                level = 2
                progress = 0
                level2_progress = 0
                challenge_expect_key = "J"
                coin_group.empty()
                guide.visible = False
                guide.active = False
                p.coin_lock = False
                p.guide_shown = False

        # ===== Level 2/3/4/5: spawn =====
        if level in (2, 3, 4, 5):
            no_enemy = not enemy_group.sprites()
            no_coin = not coin_group.sprites()
            no_obs = not obstacle_group.sprites()
            no_event = no_enemy and no_coin and no_obs

            if (sequence is None) and no_event and p.is_moving:
                level2_progress += PROGRESS_SPEED_PER_MS * dt
                if level2_progress > LEVEL2_PROGRESS_MAX:
                    level2_progress = LEVEL2_PROGRESS_MAX

            if no_event and (level2_progress >= LEVEL2_PROGRESS_MAX):
                level2_progress = 0.0

                if level == 2:
                    if random.random() < COIN_PROB_L2:
                        spawn_coin()
                    else:
                        etype = random.choice(["mushroom", "flying eye"])
                        enemy_group.add(Enemy(etype, pos=(W + 120, GROUND_Y)))

                elif level == 3:
                    if random.random() < COIN_PROB_L3:
                        spawn_coin()
                    else:
                        if random.random() < L3_MONSTER_VS_OBS:
                            etype = random.choice(
                                ["mushroom", "goblin", "skeleton", "flying eye"]
                            )
                            enemy_group.add(Enemy(etype, pos=(W + 120, GROUND_Y)))
                        else:
                            spawn_obstacle()

                elif level == 4:
                    if level4_kills == LEVEL4_KILL_TARGET - 1:
                        roll = random.random()
                        if roll < COIN_PROB_L4:
                            spawn_coin()
                        else:
                            if random.random() < L4_MONSTER_VS_OBS:
                                enemy_group.add(
                                    Enemy("gorgon", pos=(W + 120, GROUND_Y))
                                )
                            else:
                                spawn_obstacle()
                    else:
                        roll = random.random()
                        if roll < COIN_PROB_L4:
                            spawn_coin()
                        else:
                            if random.random() < L4_MONSTER_VS_OBS:
                                etype = random.choice(
                                    ["mushroom", "goblin", "skeleton"]
                                )
                                enemy_group.add(Enemy(etype, pos=(W + 120, GROUND_Y)))
                            else:
                                spawn_obstacle()

                elif level == 5:
                    roll = random.random()
                    if level5_force_boss_next:
                        level5_force_boss_next = False
                        boss_type = random.choice(["evil", "neon phantom", "gorgon"])
                        enemy_group.add(Enemy(boss_type, pos=(W + 120, GROUND_Y)))
                    else:
                        if roll < COIN_PROB_L4:
                            spawn_coin()
                        else:
                            if random.random() < L4_MONSTER_VS_OBS:
                                etype = random.choice(
                                    ["mushroom", "goblin", "skeleton", "flying eye"]
                                )
                                enemy_group.add(Enemy(etype, pos=(W + 120, GROUND_Y)))
                            else:
                                spawn_obstacle()

            coin = coin_group.sprites()[0] if coin_group.sprites() else None
            if coin:
                if not getattr(p, "coin_lock", False):
                    if coin.rect.centerx > p.rect.centerx:
                        if p.is_moving:
                            coin.rect.centerx -= 10
                    else:
                        p.coin_lock = True
                        p.is_moving = False
                        p.set_state("idle")

        # ===== Challenge countdown =====
        enemy = enemy_group.sprites()[0] if enemy_group.sprites() else None
        if enemy and enemy.challenge_ms_left is not None and not frame_resolved:
            enemy.challenge_ms_left -= dt
            if enemy.challenge_ms_left <= 0 and sequence is None:
                delta = p.attack_pressed_total - enemy.player_attack_baseline
                p.attack_pressed_total = 0
                enemy.challenge_ms_left = None
                p.set_challenge_lock(False)

                need_delta = getattr(enemy, "required_delta", 3)

                if delta >= need_delta:
                    enemy.hp -= 1

                    if level >= 3:
                        just_used_key = challenge_expect_key
                        challenge_expect_key = (
                            ALT_KEY if challenge_expect_key == "J" else "J"
                        )
                        anim = "attack2" if (just_used_key == ALT_KEY) else "attack"
                    else:
                        challenge_expect_key = "J"
                        anim = "attack"

                    if enemy.hp <= 0:
                        if level == 2:
                            level2_kills += 1
                        elif level == 3:
                            level3_kills += 1
                        elif level == 4:
                            level4_kills += 1
                        elif level == 5:
                            level5_kills_total += 1
                            level5_cycle_kills += 1
                            if level5_cycle_kills >= LEVEL5_CYCLE_TARGET:
                                level5_cycle_kills = 0
                                level5_force_boss_next = True
                        sequence = start_sequence(["player_attack", "enemy_death"])
                    else:
                        sequence = start_sequence(["player_attack", "enemy_hit"])

                    sequence["attack_anim"] = anim
                    frame_resolved = True

                else:
                    if level >= 3:
                        challenge_expect_key = (
                            ALT_KEY if challenge_expect_key == "J" else "J"
                        )
                    else:
                        challenge_expect_key = "J"
                    sequence = start_sequence(["enemy_attack", "player_hit"])
                    frame_resolved = True

        # ----- Orphan sequence cleanup -----
        if sequence is not None and not enemy_group.sprites():
            sequence = None

        # ===== Centralize locks =====
        enemy = enemy_group.sprites()[0] if enemy_group.sprites() else None
        in_sequence = sequence is not None
        in_challenge = bool(enemy and enemy.challenge_ms_left is not None)
        in_approach = bool(
            enemy and enemy.challenge_ms_left is None and enemy.state == "run"
        )
        in_combat = bool(enemy) and (in_sequence or in_challenge or in_approach)

        p.set_full_lock(in_combat)
        p.set_challenge_lock(in_challenge)

        if not in_combat:
            p.locked = False
            p.set_challenge_lock(False)
            if p.on_ground and p.state not in ("idle", "run"):
                p.set_state("idle")

        if pending_start_next:
            e2 = enemy_group.sprites()[0] if enemy_group.sprites() else None
            if e2 and not e2.dead:
                e2.start_challenge(p)
            pending_start_next = False

    # ===== Draw =====
    screen.fill((30, 30, 30))
    pygame.draw.line(screen, (70, 70, 70), (0, GROUND_Y), (W, GROUND_Y), 2)

    # พอ pause ให้หยุด parallax ด้วย (ส่ง dt=0 และ is_moving=False)
    if not game_paused:
        parallax.update(p.is_moving, dt)
    else:
        parallax.update(False, 0)
    parallax.draw(screen)
    prop_group.draw(screen)

    # Guide (วาดพื้นหลังเก่าก่อน แล้วค่อยวาดไกด์)
    guide_group.update()  # Guide.update() ของคุณไม่รับ dt
    if guide.visible:
        draw_guide_background(screen, guide.rect)
        guide_group.draw(screen)

    player_group.draw(screen)
    coin_group.draw(screen)
    obstacle_group.draw(screen)
    enemy_group.draw(screen)
    projectile_group.draw(screen)

    # Progress bar
    bar_w, bar_h = 320, 14
    x, y = 620, 16
    pygame.draw.rect(screen, (80, 80, 80), (x, y, bar_w, bar_h), border_radius=6)
    fill_w = int(
        bar_w
        * (
            (progress / PROGRESS_TO_SPAWN)
            if level == 1
            else (level2_progress / LEVEL2_PROGRESS_MAX)
        )
    )
    pygame.draw.rect(screen, (180, 220, 120), (x, y, fill_w, bar_h), border_radius=6)

    # Hearts
    draw_hearts(screen, p, pos=(20, 20), spacing=4)

    # Text
    if level == 1:
        txt = font.render(
            f"Level {level} - Coins {coins_collected}/{COINS_TO_PASS}", True, (0, 0, 0)
        )
    elif level == 2:
        txt = font.render(
            f"Level {level} - Kills {level2_kills}/{LEVEL2_KILL_TARGET}",
            True,
            (0, 0, 0),
        )
    elif level == 3:
        txt = font.render(
            f"Level {level} - Kills {level3_kills}/{LEVEL3_KILL_TARGET}",
            True,
            (0, 0, 0),
        )
    elif level == 4:
        txt = font.render(
            f"Level {level} - Kills {level4_kills}/{LEVEL4_KILL_TARGET}",
            True,
            (0, 0, 0),
        )
    else:
        txt = font.render(
            f"Level {level} - Kills {level5_kills_total} (boss every {LEVEL5_CYCLE_TARGET})",
            True,
            (0, 0, 0),
        )
    screen.blit(txt, (x, y + 20))

    # Challenge HUD
    enemy = enemy_group.sprites()[0] if enemy_group.sprites() else None
    if enemy:
        txt2 = font.render(f"Enemy HP: {enemy.hp}", True, (0, 0, 0))
        screen.blit(txt2, (20, 60))
        if enemy.challenge_ms_left:
            left = max(0, enemy.challenge_ms_left) // 1000 + 1
            need_key = challenge_expect_key if level >= 3 else "J"
            txt3 = font.render(
                f"Challenge: press {need_key} >=3 in {left}s", True, (0, 0, 0)
            )
            screen.blit(txt3, (20, 84))

            # delta แบบเรียลไทม์
            current_delta = max(
                0, p.attack_pressed_total - enemy.player_attack_baseline
            )
            need_total = getattr(enemy, "required_delta", 3)
            txt_delta = font.render(
                f"Count: {current_delta}/{need_total}", True, (0, 0, 0)
            )
            screen.blit(txt_delta, (20, 108))

    hint = font.render(
        f"J = attack, ALT = {ALT_KEY}, I = collect coin, R = Revive", True, (0, 0, 0)
    )
    screen.blit(hint, (20, 132))

    # ===== Overlay เมื่อ pause =====
    if game_paused:
        overlay = pygame.Surface((W, H))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        pause_txt = font.render("GAME PAUSED", True, (255, 255, 255))
        screen.blit(pause_txt, pause_txt.get_rect(center=(W // 2, H // 2)))

    pygame.display.flip()
