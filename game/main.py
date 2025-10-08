# main.py
import pygame
from sys import exit
import random

from player import Player
from coin import Coin
from parallax import ParallaxBG
from serial_input import poll_serial_commands
from guide import Guide
from enemy import Enemy
from obstacle import Obstacle

pygame.init()
W, H = 960, 540
screen = pygame.display.set_mode((W, H))
clock = pygame.time.Clock()
GROUND_Y = 460
font = pygame.font.SysFont(None, 28)

# ---------- Player class / alt key ----------
PLAYER_CLASS = "wizard"   # "wizard" -> ALT_KEY = 'M' / "swordman" -> ALT_KEY = 'P'
ALT_KEY = 'M' if PLAYER_CLASS.lower() == 'wizard' else 'P'

# ใช้เฉพาะเลเวล >= 3 เวลาอยู่ใน challenge (เริ่มที่ J)
challenge_expect_key = 'J'

# ---------- Game variables ----------
level = 2
coins_collected = 0
COINS_TO_PASS = 10

# Lv2
level2_kills = 0
LEVEL2_KILL_TARGET = 5

# Lv3
level3_kills = 0
LEVEL3_KILL_TARGET = 10

# progress
progress = 0.0                   # ใช้ในเลเวล 1
PROGRESS_TO_SPAWN = 100
PROGRESS_SPEED_PER_MS = 0.05

LEVEL2_PROGRESS_MAX = 100        # ใช้ในเลเวล 2–3
level2_progress = 0.0

sequence = None

# Damage config
# LEVEL2_ENEMY_DAMAGE = 1
# LEVEL3_ENEMY_DAMAGE = 2
# LEVEL4_ENEMY_DEMAGE = 4

# Spawn rates
COIN_PROB_L2 = 0.75
COIN_PROB_L3 = 0.50
COIN_PROB_L4 = 0.25
L3_MONSTER_VS_OBS = 0.50   # ถ้าไม่ใช่เหรียญ: 50% มอน / 50% obstacle
L4_MONSTER_VS_OBS = 0.75

# ---------- Sprite groups ----------
player_group = pygame.sprite.GroupSingle(Player("wizard", (500, GROUND_Y)))
coin_group = pygame.sprite.Group()
enemy_group = pygame.sprite.Group()
obstacle_group = pygame.sprite.Group()

# Guide (ใช้กับเลเวล 1 เท่านั้น)
animations_dict = {
    "collect_coin": "graphics/guide/collect_coin.png",
    "squeeze": "graphics/guide/squeeze.png",
}
guide = Guide(animations_dict, pos=(150,300), scale=4.0)
guide_group = pygame.sprite.Group(guide)
guide.visible = False

# Parallax background
parallax = ParallaxBG(
    W, H,
    [("graphics/background/sky.png", 0.0),
     ("graphics/background/ground.png", 0.34)]
)

# ---------- Helpers ----------
def spawn_coin():
    coin = Coin((W+50, GROUND_Y-70), "graphics/items/Coin.png")
    coin_group.add(coin)

def start_sequence(steps):
    return {"steps": steps, "idx": 0, "started": False}

def draw_hearts(screen, player, pos=(20,20), spacing=4):
    hp_per_heart = player.max_hp / 5
    x, y = pos
    for i in range(5):
        heart_hp = player.hp - i*hp_per_heart
        if   heart_hp >= 4: idx = 0
        elif heart_hp >= 3: idx = 1
        elif heart_hp >= 2: idx = 2
        elif heart_hp >= 1: idx = 3
        else: idx = 4
        screen.blit(player.heart_images[idx], (x,y))
        x += player.heart_images[idx].get_width() + spacing

def spawn_obstacle():
    # spawn ขวานอกจอ → เข้ามาหยุด → ให้ผู้เล่นกระโดดข้าม → ไหลออกหลังผู้เล่น
    obstacle = Obstacle(pos=(W+100, GROUND_Y), stop_offset=120, approach_speed=3, exit_speed=6)
    obstacle_group.add(obstacle)

# ---------- UART walk impulse (ให้การเดินลื่นเมื่อ UART ส่งครั้งละตัวอักษร) ----------
RUN_IMPULSE_MS = 200
serial_run_ms = 0
serial_dir = 1
IMPULSE_ADD_MS = 140
IMPULSE_MAX_MS = 300

# ---------- Main loop ----------
while True:
    dt = clock.tick(60)

    frame_resolved = False
    pending_start_next = False

    # ===== Events =====
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit(); exit()

        if event.type == pygame.KEYDOWN:
            p = player_group.sprite
            enemy = enemy_group.sprites()[0] if enemy_group.sprites() else None
            in_challenge = bool(enemy and enemy.challenge_ms_left is not None)
            in_sequence  = (sequence is not None)

            # --- J ---
            if event.key == pygame.K_j:
                if in_challenge:
                    need_j = (level == 2 and challenge_expect_key == 'J') or (level >= 3 and challenge_expect_key == 'J')
                    if need_j:
                        p.attack_pressed_total += 1
                elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                    p.play_attack_anim_named("attack")

            # --- M (wizard) ---
            if event.key == pygame.K_m:
                if in_challenge and level >= 3 and ALT_KEY == 'M' and challenge_expect_key == 'M':
                    p.attack_pressed_total += 1
                elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                    p.play_attack_anim_named("attack2")

            # --- P (swordman) ---
            if event.key == pygame.K_p:
                if in_challenge and level >= 3 and ALT_KEY == 'P' and challenge_expect_key == 'P':
                    p.attack_pressed_total += 1
                elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                    p.play_attack_anim_named("attack2")

            # Revive
            if event.key == pygame.K_r:
                p.revive()

            # ---- เก็บเหรียญได้ทุกเลเวล (พอกด I ตอน coin_lock) ----
            if event.key == pygame.K_i:
                if getattr(p, "coin_lock", False) and coin_group.sprites():
                    coin_group.sprites()[0].kill()
                    if level == 1:
                        progress = 0
                        guide.visible = False
                        p.guide_shown = False
                    else:
                        level2_progress = 0.0
                    p.coin_lock = False
                    coins_collected += 1  # จะนับหรือไม่ก็ได้ ไม่กระทบ kill target
                    
            # --- Jump over obstacle (SPACE / W / UP) ---
            if event.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                obstacle = obstacle_group.sprites()[0] if obstacle_group.sprites() else None
                if getattr(p, "obstacle_lock", False) and obstacle and getattr(obstacle, "state", "") == "wait":
                    # ให้ผู้เล่นกระโดดจริง (เพื่อมีแอนิเมชัน jump)
                    if p.on_ground and not (p.full_lock or p.locked or p.dead):
                        p.vel_y = -p.jump_power
                        p.on_ground = False
                        p.set_state("jump")

                    # เริ่มโหมด 'pass' ให้สิ่งกีดขวางวิ่งผ่านหลังผู้เล่นระหว่างกระโดด
                    p.obstacle_lock = False
                    obstacle.start_pass(p)


    # ===== Serial input =====
    keys = pygame.key.get_pressed()
    p = player_group.sprite
    enemy = enemy_group.sprites()[0] if enemy_group.sprites() else None

    serial_cmds = poll_serial_commands()
    if serial_cmds:
        in_challenge = bool(enemy and enemy.challenge_ms_left is not None)
        in_sequence  = (sequence is not None)

        if any(ch in ('W','w') for ch in serial_cmds) or any(ch == ' ' for ch in serial_cmds):
            obstacle = obstacle_group.sprites()[0] if obstacle_group.sprites() else None
            if getattr(p, "obstacle_lock", False) and obstacle and getattr(obstacle, "state", "") == "wait":
                if p.on_ground and not (p.full_lock or p.locked or p.dead):
                    p.vel_y = -p.jump_power
                    p.on_ground = False
                    p.set_state("jump")
                p.obstacle_lock = False
                obstacle.start_pass(p)


        if any(ch in ('J','j') for ch in serial_cmds):
            need_j = (level == 2 and challenge_expect_key == 'J') or (level >= 3 and challenge_expect_key == 'J')
            if in_challenge and need_j:
                p.attack_pressed_total += 1
            elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                p.play_attack_anim_named("attack")

        if any(ch in ('M','m') for ch in serial_cmds):
            if in_challenge and level >= 3 and ALT_KEY == 'M' and challenge_expect_key == 'M':
                p.attack_pressed_total += 1
            elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                p.play_attack_anim_named("attack2")

        if any(ch in ('P','p') for ch in serial_cmds):
            if in_challenge and level >= 3 and ALT_KEY == 'P' and challenge_expect_key == 'P':
                p.attack_pressed_total += 1
            elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                p.play_attack_anim_named("attack2")

        if any(ch in ('D','d') for ch in serial_cmds) and not (p.full_lock or p.locked or p.dead):
            serial_dir = 1
            serial_run_ms = min(serial_run_ms + IMPULSE_ADD_MS, IMPULSE_MAX_MS)

        # กด I ผ่าน UART (ถ้ามี)
        if any(ch in ('I','i') for ch in serial_cmds):
            if getattr(p, "coin_lock", False) and coin_group.sprites():
                coin_group.sprites()[0].kill()
                if level == 1:
                    progress = 0
                    guide.visible = False
                    p.guide_shown = False
                else:
                    level2_progress = 0.0
                p.coin_lock = False
                coins_collected += 1

    if serial_run_ms > 0 and not (p.full_lock or p.locked or p.dead):
        p.external_move = True
        p.external_dir = serial_dir
        serial_run_ms -= dt
    else:
        p.external_dir = 0

    # ===== Update =====
    player_group.update(keys, GROUND_Y)
    for e in enemy_group.sprites():
        e.update(p, dt)
    for obs in obstacle_group.sprites():
        obs.update(p, dt)

    # ===== Level 1 =====
    if level == 1:
        if len(coin_group) == 0:
            spawn_coin()
        coin = coin_group.sprites()[0] if coin_group.sprites() else None

        if p.is_moving and not getattr(p,"coin_lock",False):
            progress += PROGRESS_SPEED_PER_MS * dt
            if progress > PROGRESS_TO_SPAWN:
                progress = PROGRESS_TO_SPAWN

        if progress >= PROGRESS_TO_SPAWN and coin:
            if coin.rect.centerx > p.rect.centerx:
                if p.is_moving:
                    coin.rect.centerx -= 10
            else:
                if not getattr(p,"guide_shown",False):
                    guide.set_state("squeeze")
                    guide.active = True
                    guide.visible = True
                    guide.frame_index = 0.0
                    p.guide_shown = True
                p.coin_lock = True
                p.is_moving = False
                p.set_state("idle")

        # (การเก็บเหรียญกด I อยู่ใน event ด้านบนแล้ว)

        if coins_collected >= COINS_TO_PASS:
            level = 2
            progress = 0
            level2_progress = 0
            challenge_expect_key = 'J'
            # cleanup
            coin_group.empty()
            guide.visible = False
            p.coin_lock = False
            p.guide_shown = False

    # ===== Level 2 & 3: spawn/approach/challenge =====
    if level in (2, 3):
        # spawn ได้เมื่อไม่มีอีเวนต์ค้าง และผู้เล่น "กำลังวิ่ง" (คือกดเดิน/impulse) และไม่มี sequence
        no_enemy = not enemy_group.sprites()
        no_coin  = not coin_group.sprites()
        no_obs   = not obstacle_group.sprites()
        no_event = no_enemy and no_coin and no_obs

        if (sequence is None) and no_event and p.is_moving:
            level2_progress += PROGRESS_SPEED_PER_MS * dt
            if level2_progress > LEVEL2_PROGRESS_MAX:
                level2_progress = LEVEL2_PROGRESS_MAX

        if no_event and (level2_progress >= LEVEL2_PROGRESS_MAX):
            level2_progress = 0.0

            if level == 2:
                # 75% coin, 25% monster
                if random.random() < COIN_PROB_L2:
                    spawn_coin()
                else:
                    # “มอนอีกตัวที่เหมือนเห็ดทุกอย่าง” — ถ้ายังไม่มี assets แยก ใช้ mushroom ไปก่อน
                    etype = random.choice(["mushroom", "flying eye"])  # หรือ ["mushroom", "mushroom_alt"]
                    enemy_group.add(Enemy(etype, pos=(W+120, GROUND_Y)))
            else:
                # Level 3: 50% coin, 50% ไม่ใช่เหรียญ → ใน 50% นั้น 50% มอน / 50% obstacle
                if random.random() < COIN_PROB_L3:
                    spawn_coin()
                else:
                    if random.random() < L3_MONSTER_VS_OBS:
                        etype = random.choice(["mushroom", "goblin", "skeleton"])
                        enemy_group.add(Enemy(etype, pos=(W+120, GROUND_Y)))
                    else:
                        spawn_obstacle()

        # ---- Coin behavior for L2/L3 (เหมือนเลเวล 1) ----
        coin = coin_group.sprites()[0] if coin_group.sprites() else None
        if coin:
            if not getattr(p, "coin_lock", False):
                # เหรียญเข้าหาผู้เล่นเฉพาะตอนผู้เล่นกำลังวิ่ง (ให้ฟีลเดียวกับ L1)
                if coin.rect.centerx > p.rect.centerx:
                    if p.is_moving:
                        coin.rect.centerx -= 10
                else:
                    # ถึงตำแหน่ง → ล็อกให้กด I เก็บ (ไม่โชว์ไกด์ใน L2/L3)
                    p.coin_lock = True
                    p.is_moving = False
                    p.set_state("idle")
        # การกด I เก็บอยู่ใน event/serial แล้ว

    # ===== Challenge countdown (สำหรับศัตรู) =====
    enemy = enemy_group.sprites()[0] if enemy_group.sprites() else None
    if enemy and enemy.challenge_ms_left is not None and not frame_resolved:
        enemy.challenge_ms_left -= dt
        if enemy.challenge_ms_left <= 0 and sequence is None:
            delta = p.attack_pressed_total - enemy.player_attack_baseline
            p.attack_pressed_total = 0
            enemy.challenge_ms_left = None
            p.set_challenge_lock(False)

            if delta >= 3:
                enemy.hp -= 1

                if level >= 3:
                    just_used_key = challenge_expect_key
                    challenge_expect_key = ALT_KEY if challenge_expect_key == 'J' else 'J'
                    anim = "attack2" if (just_used_key == ALT_KEY) else "attack"
                else:
                    challenge_expect_key = 'J'
                    anim = "attack"

                if enemy.hp <= 0:
                    if level == 2:
                        level2_kills += 1
                    else:
                        level3_kills += 1
                    sequence = start_sequence(["player_attack","enemy_death"])
                else:
                    sequence = start_sequence(["player_attack","enemy_hit"])

                sequence["attack_anim"] = anim
                frame_resolved = True
            else:
                if level >= 3:
                    challenge_expect_key = ALT_KEY if challenge_expect_key == 'J' else 'J'
                else:
                    challenge_expect_key = 'J'
                sequence = start_sequence(["enemy_attack","player_hit"])
                frame_resolved = True

    # ===== Run sequence =====
    if sequence and enemy:
        step = sequence["steps"][sequence["idx"]]

        if step == "player_attack":
            if not sequence["started"]:
                desired = sequence.get("attack_anim", "attack")
                if desired not in ("attack","attack2") or (desired not in p.animations):
                    desired = "attack"
                p.play_attack_anim_named(desired, ignore_locked=True)
                sequence["started"] = True

            if p.just_finished in ("attack","attack2"):
                sequence["idx"] += 1
                sequence["started"] = False

        elif step == "enemy_hit":
            if not sequence["started"]:
                enemy.locked = True
                enemy.set_state("hit")
                sequence["started"] = True
            if enemy.just_finished == "hit":
                sequence["idx"] += 1
                sequence["started"] = False

        elif step == "enemy_death":
            if not sequence["started"]:
                enemy.locked = True
                enemy.set_state("death")
                sequence["started"] = True
            if enemy.just_finished == "death":
                enemy.challenge_ms_left = None
                enemy.dead = True
                enemy.kill()
                enemy_group.empty()
                level2_progress = 0.0
                p.set_full_lock(False)
                p.set_challenge_lock(False)
                p.locked = False
                if p.on_ground: p.set_state("idle")
                sequence = None
                enemy = None

        elif step == "enemy_attack":
            if not sequence["started"]:
                enemy.locked = True
                enemy.set_state("attack")
                sequence["started"] = True
            if enemy.just_finished == "attack":
                dmg = getattr(enemy, "damage", 1)
                p.start_hit(damage=dmg)
                sequence["idx"] += 1
                sequence["started"] = False

        elif step == "player_hit":
            if not sequence["started"]:
                sequence["started"] = True
            if p.just_finished == "hit":
                sequence["idx"] += 1
                sequence["started"] = False

        # จบคิว → นัดเริ่มชาเลนจ์ใหม่เฟรมถัดไป
        if sequence and sequence["idx"] >= len(sequence["steps"]):
            sequence = None
            e2 = enemy_group.sprites()[0] if enemy_group.sprites() else None
            if e2 and not e2.dead:
                pending_start_next = True

    # ===== Level up =====
    if level == 2 and level2_kills >= LEVEL2_KILL_TARGET:
        level2_kills = 0
        level = 3
        level2_progress = 0
        enemy_group.empty()
        coin_group.empty()
        obstacle_group.empty()
        challenge_expect_key = 'J'  # เริ่มรอบแรกที่ J ในเลเวล 3

    if level == 3 and level3_kills >= LEVEL3_KILL_TARGET:
        # ผ่านเลเวล 3 (จะไปต่อยังไงค่อยเติม)
        enemy_group.empty()
        coin_group.empty()
        obstacle_group.empty()
        p.set_full_lock(False)
        p.set_challenge_lock(False)

    # ----- Orphan sequence cleanup -----
    if sequence is not None and not enemy_group.sprites():
        sequence = None

    # ===== Centralize locks =====
    enemy = enemy_group.sprites()[0] if enemy_group.sprites() else None
    in_sequence  = (sequence is not None)
    in_challenge = bool(enemy and enemy.challenge_ms_left is not None)
    in_approach  = bool(enemy and enemy.challenge_ms_left is None and enemy.state == "run")
    in_combat = bool(enemy) and (in_sequence or in_challenge or in_approach)

    p.set_full_lock(in_combat)
    p.set_challenge_lock(in_challenge)

    if not in_combat:
        p.locked = False
        p.set_challenge_lock(False)
        if p.on_ground and p.state not in ("idle","run"):
            p.set_state("idle")

    if pending_start_next:
        e2 = enemy_group.sprites()[0] if enemy_group.sprites() else None
        if e2 and not e2.dead:
            e2.start_challenge(p)
        pending_start_next = False

    # ===== Draw =====
    screen.fill((30,30,30))
    pygame.draw.line(screen,(70,70,70),(0,GROUND_Y),(W,GROUND_Y),2)
    parallax.update(p.is_moving, dt)
    parallax.draw(screen)

    player_group.draw(screen)
    coin_group.draw(screen)
    obstacle_group.draw(screen)   # obstacle แสดงก่อน enemy
    enemy_group.draw(screen)

    # Progress bar
    bar_w, bar_h = 320, 14
    x, y = 20, 16
    pygame.draw.rect(screen,(80,80,80),(x,y,bar_w,bar_h),border_radius=6)
    if level == 1:
        fill_w = int(bar_w * (progress / PROGRESS_TO_SPAWN))
    else:
        fill_w = int(bar_w * (level2_progress / LEVEL2_PROGRESS_MAX))
    pygame.draw.rect(screen,(180,220,120),(x,y,fill_w,bar_h),border_radius=6)

    # Hearts
    draw_hearts(screen, p, pos=(20,20), spacing=4)

    # Text
    if level == 1:
        txt = font.render(f"Level {level} - Coins {coins_collected}/{COINS_TO_PASS}", True, (200,200,200))
    elif level == 2:
        txt = font.render(f"Level {level} - Kills {level2_kills}/{LEVEL2_KILL_TARGET}", True, (200,200,200))
    else:
        txt = font.render(f"Level {level} - Kills {level3_kills}/{LEVEL3_KILL_TARGET}", True, (200,200,200))
    screen.blit(txt, (x, y+20))

    # Challenge HUD
    enemy = enemy_group.sprites()[0] if enemy_group.sprites() else None
    if enemy:
        txt2 = font.render(f"Enemy HP: {enemy.hp}", True, (220,220,220))
        screen.blit(txt2, (20, 60))
        if enemy.challenge_ms_left:
            left = max(0, enemy.challenge_ms_left)//1000 + 1
            need = challenge_expect_key if level >= 3 else 'J'
            txt3 = font.render(f"Challenge: press {need} >=3 in {left}s", True, (255,210,160))
            screen.blit(txt3, (20, 84))

    hint = font.render(f"J = attack, ALT = {ALT_KEY}, I = collect coin, R = Revive", True, (170,170,170))
    screen.blit(hint, (20, 110))

    pygame.display.flip()
