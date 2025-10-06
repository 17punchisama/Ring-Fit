import pygame
from sys import exit
from player import Player
from coin import Coin
from parallax import ParallaxBG
from serial_input import poll_serial_commands
from guide import Guide
from enemy import Enemy
import random

pygame.init()
W, H = 960, 540
screen = pygame.display.set_mode((W, H))
clock = pygame.time.Clock()
GROUND_Y = 460
font = pygame.font.SysFont(None, 28)

# ----------------- Player class / alt key -----------------
PLAYER_CLASS = "wizard"  # "wizard" -> ALT_KEY = 'M' / "swordman" -> ALT_KEY = 'P'
ALT_KEY = 'M' if PLAYER_CLASS.lower() == 'wizard' else 'P'

# ปุ่มที่ต้องกดสำหรับ "รอบชาเลนจ์นี้" (เริ่มที่ J)
challenge_expect_key = 'J'   # จะ flip เป็น ALT_KEY แล้วกลับเป็น 'J' เฉพาะเลเวล >= 3

# ----------------- Game variables -----------------
level = 1
coins_collected = 0
COINS_TO_PASS = 20

# Lv2
level2_kills = 0
LEVEL2_KILL_TARGET = 5

# Lv3
level3_kills = 0
LEVEL3_KILL_TARGET = 10
LEVEL3_ENEMIES = ["goblin", "skeleton"]  # สุ่มสองตัวนี้

# progress (เลเวล 1 ใช้ progress, เลเวล >=2 ใช้ level2_progress)
progress = 0.0
PROGRESS_TO_SPAWN = 100
PROGRESS_SPEED_PER_MS = 0.05

LEVEL2_PROGRESS_MAX = 100
level2_progress = 0.0

sequence = None

# Damage config
LEVEL2_ENEMY_DAMAGE = 1
LEVEL3_ENEMY_DAMAGE = 2   # ด่าน 3 ตีแรงขึ้น

# ----------------- Sprite groups -----------------
player_group = pygame.sprite.GroupSingle(Player("wizard", (500, GROUND_Y)))
coin_group = pygame.sprite.Group()
enemy_group = pygame.sprite.Group()  # รองรับหลายศัตรู

# Guide setup (ใช้กับเลเวล 1)
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

# ----------------- Helper -----------------
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
        if heart_hp >= 4: idx = 0
        elif heart_hp >= 3: idx = 1
        elif heart_hp >= 2: idx = 2
        elif heart_hp >= 1: idx = 3
        else: idx = 4
        screen.blit(player.heart_images[idx], (x,y))
        x += player.heart_images[idx].get_width() + spacing

# ----------------- Serial run impulse (optional) -----------------
RUN_IMPULSE_MS = 250
serial_run_ms = 0

# ----------------- Main loop -----------------
while True:
    dt = clock.tick(60)

    # กัน resolve/เริ่มรอบใหม่ซ้ำในเฟรมเดียว
    frame_resolved = False
    pending_start_next = False

    # ================= Events =================
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
                    # เลเวล 2 รับ J อย่างเดียว / เลเวล >=3 รับตาม expected key
                    if (level == 2 and challenge_expect_key == 'J') or (level >= 3 and challenge_expect_key == 'J'):
                        p.attack_pressed_total += 1
                elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                    # นอกชาเลนจ์ → เล่นท่า attack
                    if hasattr(p, "play_attack_anim_named"):
                        p.play_attack_anim_named("attack")
                    else:
                        p.start_attack()

            # --- M (wizard) ---
            if event.key == pygame.K_m:
                if in_challenge:
                    if level >= 3 and ALT_KEY == 'M' and challenge_expect_key == 'M':
                        p.attack_pressed_total += 1
                elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                    if hasattr(p, "play_attack_anim_named"):
                        p.play_attack_anim_named("attack2")
                    else:
                        p.set_state("attack2")

            # --- P (swordman) ---
            if event.key == pygame.K_p:
                if in_challenge:
                    if level >= 3 and ALT_KEY == 'P' and challenge_expect_key == 'P':
                        p.attack_pressed_total += 1
                elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                    if hasattr(p, "play_attack_anim_named"):
                        p.play_attack_anim_named("attack2")
                    else:
                        p.set_state("attack2")

            # Revive
            if event.key == pygame.K_r:
                player_group.sprite.revive()

            # เลเวล 1 กด I เก็บเหรียญ
            if level == 1 and event.key == pygame.K_i:
                if getattr(player_group.sprite,"coin_lock",False) and coin_group.sprites():
                    coin_group.sprites()[0].kill()
                    progress = 0
                    player_group.sprite.coin_lock = False
                    guide.visible = False
                    player_group.sprite.guide_shown = False
                    coins_collected += 1

    keys = pygame.key.get_pressed()
    p = player_group.sprite
    enemy = enemy_group.sprites()[0] if enemy_group.sprites() else None

    # ================ Serial input (ถ้ามีอุปกรณ์) ================
    serial_cmds = poll_serial_commands()
    if serial_cmds:
        in_challenge = bool(enemy and enemy.challenge_ms_left is not None)
        in_sequence  = (sequence is not None)

        if any(ch in ('W','w') for ch in serial_cmds) and p.on_ground and not (p.full_lock or p.locked or p.dead):
            p.vel_y = -p.jump_power
            p.on_ground = False
            p.set_state("jump")

        if any(ch in ('J','j') for ch in serial_cmds):
            if in_challenge and ((level == 2 and challenge_expect_key == 'J') or (level >= 3 and challenge_expect_key == 'J')):
                p.attack_pressed_total += 1
            elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                if hasattr(p, "play_attack_anim_named"):
                    p.play_attack_anim_named("attack")
                else:
                    p.start_attack()

        if any(ch in ('M','m') for ch in serial_cmds):
            if in_challenge and level >= 3 and ALT_KEY == 'M' and challenge_expect_key == 'M':
                p.attack_pressed_total += 1
            elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                if hasattr(p, "play_attack_anim_named"):
                    p.play_attack_anim_named("attack2")
                else:
                    p.set_state("attack2")

        if any(ch in ('P','p') for ch in serial_cmds):
            if in_challenge and level >= 3 and ALT_KEY == 'P' and challenge_expect_key == 'P':
                p.attack_pressed_total += 1
            elif not in_sequence and not (p.full_lock or p.locked or p.dead):
                if hasattr(p, "play_attack_anim_named"):
                    p.play_attack_anim_named("attack2")
                else:
                    p.set_state("attack2")

        if any(ch in ('D','d') for ch in serial_cmds):
            if not (p.full_lock or p.locked or p.dead):
                serial_run_ms = RUN_IMPULSE_MS

    if serial_run_ms > 0 and not (p.full_lock or p.locked or p.dead):
        p.external_move = True
        serial_run_ms -= dt

    # ============== Update player & enemies ==============
    player_group.update(keys, GROUND_Y)
    for e in enemy_group.sprites():
        e.update(p, dt)

    # ================= Level 1 =================
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

        if getattr(p,"coin_lock",False) and keys[pygame.K_i] and coin:
            coin.kill()
            progress = 0
            p.coin_lock = False
            guide.visible = False
            p.guide_shown = False
            coins_collected += 1

        if coins_collected >= COINS_TO_PASS:
            level = 2
            progress = 0
            level2_progress = 0
            challenge_expect_key = 'J'  # เผื่อ safety

    # ============== Level 2 & 3: spawn/approach/challenge ==============
    if level in (2, 3):
        # เก็บ progress เฉพาะตอนยังไม่มี enemy + ไม่มี sequence + ผู้เล่นกำลังวิ่ง
        if (sequence is None) and (enemy is None) and p.is_moving:
            level2_progress += PROGRESS_SPEED_PER_MS * dt
            if level2_progress > LEVEL2_PROGRESS_MAX:
                level2_progress = LEVEL2_PROGRESS_MAX

        # เต็มหลอด → spawn enemy (Lv2: mushroom, Lv3: random goblin/skeleton)
        if (enemy is None) and (level2_progress >= LEVEL2_PROGRESS_MAX):
            if level == 2:
                etype = "mushroom"
            else:  # level 3
                if level3_kills >= LEVEL3_KILL_TARGET:
                    etype = None
                else:
                    etype = random.choice(LEVEL3_ENEMIES)

            if etype:
                new_enemy = Enemy(etype, pos=(W+120, GROUND_Y))
                enemy_group.add(new_enemy)
            level2_progress = 0.0

    # ============== Enemy challenge countdown ==============
    enemy = enemy_group.sprites()[0] if enemy_group.sprites() else None
    if enemy and enemy.challenge_ms_left is not None and not frame_resolved:
        enemy.challenge_ms_left -= dt
        if enemy.challenge_ms_left <= 0 and sequence is None:
            # ตัดสินผลรอบนี้
            delta = p.attack_pressed_total - enemy.player_attack_baseline
            p.attack_pressed_total = 0
            enemy.challenge_ms_left = None
            p.set_challenge_lock(False)

            if delta >= 3:
                enemy.hp -= 1

                # flip เฉพาะเลเวล >= 3 (เลเวล 2 บังคับ J)
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
                    elif level >= 3:
                        level3_kills += 1
                    sequence = start_sequence(["player_attack","enemy_death"])
                else:
                    sequence = start_sequence(["player_attack","enemy_hit"])

                sequence["attack_anim"] = anim
                frame_resolved = True
            else:
                # แพ้: flip เฉพาะเลเวล >= 3
                if level >= 3:
                    challenge_expect_key = ALT_KEY if challenge_expect_key == 'J' else 'J'
                else:
                    challenge_expect_key = 'J'
                sequence = start_sequence(["enemy_attack","player_hit"])
                frame_resolved = True

    # ============== Run sequence ==============
    if sequence and enemy:
        step = sequence["steps"][sequence["idx"]]

        if step == "player_attack":
            if not sequence["started"]:
                desired = sequence.get("attack_anim", "attack")
                if desired not in ("attack","attack2") or (not hasattr(p, "animations")) or (desired not in p.animations):
                    desired = "attack"

                # เรียกครั้งเดียว
                if hasattr(p, "play_attack_anim_named"):
                    p.play_attack_anim_named(desired, ignore_locked=True)
                else:
                    p.locked = True
                    p.set_state(desired)

                sequence["started"] = True

            # รอจนจบจริง ๆ
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

        elif step=="enemy_death":
            if not sequence["started"]:
                enemy.locked = True
                enemy.set_state("death")
                sequence["started"] = True
            if enemy.just_finished == "death":
                # เคลียร์ศัตรูให้จบจริง ๆ
                enemy.challenge_ms_left = None
                enemy.dead = True
                enemy.kill()
                enemy_group.empty()

                # รีเซ็ต progress bar เพื่อกลับไปวิ่งต่อ
                level2_progress = 0.0

                # ปลดทุกล็อกของผู้เล่น
                p.set_full_lock(False)
                p.set_challenge_lock(False)
                p.locked = False
                if p.on_ground:
                    p.set_state("idle")

                # จบ sequence เลย (ไม่มีมอนแล้ว)
                sequence = None
                enemy = None

        elif step == "enemy_attack":
            if not sequence["started"]:
                enemy.locked = True
                enemy.set_state("attack")
                sequence["started"] = True
            if enemy.just_finished == "attack":
                dmg = LEVEL3_ENEMY_DAMAGE if level >= 3 else LEVEL2_ENEMY_DAMAGE
                p.start_hit(damage=dmg)
                sequence["idx"] += 1
                sequence["started"] = False

        elif step == "player_hit":
            if not sequence["started"]:
                sequence["started"] = True
            if p.just_finished == "hit":
                sequence["idx"] += 1
                sequence["started"] = False

        # จบคิว → นัดเริ่มชาเลนจ์ใหม่ "เฟรมถัดไป"
        if sequence and sequence["idx"] >= len(sequence["steps"]):
            sequence = None
            e2 = enemy_group.sprites()[0] if enemy_group.sprites() else None
            if e2 and not e2.dead:
                pending_start_next = True

    # ============== Level up after kills ==============
    if level == 2 and level2_kills >= LEVEL2_KILL_TARGET:
        level2_kills = 0
        level = 3
        level2_progress = 0
        enemy_group.empty()
        challenge_expect_key = 'J'  # เริ่มรอบแรกที่ J

    if level == 3 and level3_kills >= LEVEL3_KILL_TARGET:
        # ผ่านเลเวล 3
        enemy_group.empty()
        p.set_full_lock(False)
        p.set_challenge_lock(False)

    # ----- Orphan sequence cleanup: ถ้า sequence ค้างแต่ไม่มีมอน → เคลียร์ -----
    if sequence is not None and not enemy_group.sprites():
        sequence = None

    # ===== Centralize locks at end of frame =====
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

    # เริ่ม challenge ใหม่ถ้านัดไว้ (เฟรมถัดไป)
    if pending_start_next:
        e2 = enemy_group.sprites()[0] if enemy_group.sprites() else None
        if e2 and not e2.dead:
            e2.start_challenge(p)
        pending_start_next = False

    # ================= Draw =================
    screen.fill((30,30,30))
    pygame.draw.line(screen,(70,70,70),(0,GROUND_Y),(W,GROUND_Y),2)
    parallax.update(p.is_moving, dt)
    parallax.draw(screen)

    player_group.draw(screen)
    coin_group.draw(screen)
    enemy_group.draw(screen)

    # UI progress bar
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
