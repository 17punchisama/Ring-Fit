import pygame
from sys import exit
import os

# ============== helpers: slice by alpha gaps + align midbottom ==============
def slice_by_alpha_regions(path, expected=None):
    sheet = pygame.image.load(path).convert_alpha()
    sw, sh = sheet.get_width(), sheet.get_height()

    def col_has_pixel(x):
        for y in range(sh):
            if sheet.get_at((x, y))[3] != 0:
                return True
        return False

    segments = []
    in_run, run_start = False, 0
    for x in range(sw):
        nonempty = col_has_pixel(x)
        if nonempty and not in_run:
            in_run, run_start = True, x
        elif not nonempty and in_run:
            in_run = False
            segments.append((run_start, x))
    if in_run:
        segments.append((run_start, sw))

    raw_frames = []
    for sx, ex in segments:
        w = max(1, ex - sx)
        raw_frames.append(sheet.subsurface(pygame.Rect(sx, 0, w, sh)).copy())

    if expected is not None and len(raw_frames) != expected and len(raw_frames) > 0:
        widths = [f.get_width() for f in raw_frames]
        thr = max(8, int(0.15 * max(widths)))
        raw_frames = [f for f in raw_frames if f.get_width() >= thr]

    return raw_frames

def align_and_pad(frames, anchor="midbottom"):
    cropped = []
    for f in frames:
        bbox = f.get_bounding_rect(min_alpha=1)
        cropped.append(f.subsurface(bbox).copy())

    if not cropped:
        return []

    max_w = max(f.get_width() for f in cropped)
    max_h = max(f.get_height() for f in cropped)

    aligned = []
    for f in cropped:
        canvas = pygame.Surface((max_w, max_h), pygame.SRCALPHA)
        r = f.get_rect()
        if anchor == "midbottom":
            r.midbottom = (max_w // 2, max_h)
        else:
            r.center = (max_w // 2, max_h // 2)
        canvas.blit(f, r)
        aligned.append(canvas)
    return aligned

def _load_animation_single(path, scale=3.0, expected=None):
    frames = slice_by_alpha_regions(path, expected=expected)
    frames = align_and_pad(frames, anchor="midbottom")
    if scale != 1.0 and frames:
        frames = [pygame.transform.scale_by(f, scale) for f in frames]
    return frames

def load_animation_with_fallback(paths, scale=3.0, expected=None):
    last_err = None
    for p in paths:
        try:
            if os.path.exists(p):
                return _load_animation_single(p, scale=scale, expected=expected)
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    raise FileNotFoundError(f"No valid asset found among: {paths}")

def _dummy_frame():
    s = pygame.Surface((1, 1), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    return s

def _ensure_animation_safety(anims: dict):
    """ให้ทุก state มีเฟรมเสมอ: ถ้าว่าง -> ใช้ idle; ถ้า idle ว่าง -> ใส่ dummy 1x1"""
    idle_frames = anims.get("idle") or []
    if not idle_frames:
        anims["idle"] = [_dummy_frame()]
    for st in list(anims.keys()):
        if not anims[st]:
            anims[st] = anims["idle"]


# ======================= character configs =======================
CHAR_CONFIGS = {
    "wizard": {
        "scale": 3.0,
        "speed": 0,
        "jump_power": 14,
        "assets": {
            "idle":   ["graphics/player/wizard/Idle.png"],
            "run":    ["graphics/player/wizard/Run.png"],
            "jump":   ["graphics/player/wizard/Jump.png"],
            "attack": ["graphics/player/wizard/Attack2.png"],
            "hit":    ["graphics/player/wizard/Hit.png"],
            "death":  ["graphics/player/wizard/Death.png"],
        },
        "anim_speed": {"idle":0.15,"run":0.25,"jump":0.12,"attack":0.22,"hit":0.18,"death":0.18},
    },
    "swordman": {
        "scale": 3.0,
        "speed": 0,
        "jump_power": 12,
        "assets": {
            "idle":   ["graphics/player/swordman/Idle.png",   "graphics/player/wizard/Idle.png"],
            "run":    ["graphics/player/swordman/Run.png",    "graphics/player/wizard/Run.png"],
            "jump":   ["graphics/player/swordman/Jump.png",   "graphics/player/wizard/Jump.png"],
            "attack": ["graphics/player/swordman/Attack2.png","graphics/player/wizard/Attack2.png"],
            "hit":    ["graphics/player/swordman/Hit.png",    "graphics/player/wizard/Hit.png"],
            "death":  ["graphics/player/swordman/Death.png",  "graphics/player/wizard/Death.png"],
        },
        "anim_speed": {"idle":0.14,"run":0.26,"jump":0.12,"attack":0.20,"hit":0.18,"death":0.18},
    }
}

# ================================ Player ================================
class Player(pygame.sprite.Sprite):
    def __init__(self, character: str, pos=(480, 420)):
        super().__init__()
        cfg = CHAR_CONFIGS[character]
        self.cfg = cfg
        self.animations = {
            state: load_animation_with_fallback(paths, scale=cfg["scale"])
            for state, paths in cfg["assets"].items()
        }
        _ensure_animation_safety(self.animations)
        self.anim_speed = cfg["anim_speed"]

        self.state = "idle"
        self.frame_index = 0.0
        self.image = self.animations[self.state][0]
        self.rect = self.image.get_rect(midbottom=pos)

        self.vel_y = 0.0
        self.jump_power = cfg["jump_power"]
        self.on_ground = True

        self.locked = False
        self.dead = False

        self.full_lock = False        # ล็อกทุกอินพุต (เดิน/โดดไม่ได้)
        self.challenge_lock = False   # โหมด J-only ระหว่างจับเวลา

        self.attack_pressed_total = 0
        self.just_finished = None
        self.is_moving = False

    def set_state(self, new_state):
        if self.dead and new_state != "death":
            return
        if self.state != new_state:
            self.state = new_state
            self.frame_index = 0.0

    def set_full_lock(self, active: bool):
        self.full_lock = active
        if active:
            self.is_moving = False
            if self.on_ground and not self.locked:
                self.set_state("idle")

    def set_challenge_lock(self, active: bool):
        self.challenge_lock = active

    def handle_input(self, keys):
        if self.full_lock or self.locked or self.dead:
            self.is_moving = False
            return

        moving = (keys[pygame.K_LEFT] or keys[pygame.K_a] or
                  keys[pygame.K_RIGHT] or keys[pygame.K_d])
        self.is_moving = moving

        if (keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]) and self.on_ground:
            self.vel_y = -self.jump_power
            self.on_ground = False
            self.set_state("jump")

        if self.on_ground and not self.locked:
            self.set_state("run" if moving else "idle")

    def start_attack(self):
        # นับเฉพาะตอนที่อยู่ในโหมดชาเลนจ์เท่านั้น
        if not self.dead and self.challenge_lock:
            self.attack_pressed_total += 1

    def play_attack_anim(self):
        if not self.locked and not self.dead:
            self.locked = True
            self.set_state("attack")

    def start_hit(self):
        if not self.locked and not self.dead:
            self.locked = True
            self.set_state("hit")

    def start_death(self):
        if self.dead: return
        self.dead = True; self.locked = True; self.set_state("death")

    def revive(self):
        self.dead = False; self.locked = False
        self.vel_y = 0.0; self.on_ground = True
        self.just_finished = None
        self.set_state("idle")

    def apply_gravity(self, ground_y):
        if not self.dead:
            self.vel_y += 0.8
            self.rect.y += int(self.vel_y)
            if self.rect.bottom >= ground_y:
                self.rect.bottom = ground_y
                self.vel_y = 0
                if not self.on_ground:
                    self.on_ground = True
                    if not self.locked:
                        self.set_state("idle")

    def animate(self):
        self.just_finished = None
        frames = self.animations.get(self.state) or self.animations["idle"]
        end = len(frames)
        if end == 0:
            return

        self.frame_index += self.anim_speed.get(self.state, 0.18)

        if self.state in ("attack", "hit"):
            if self.frame_index >= end:
                self.frame_index = 0.0
                self.just_finished = self.state
                self.locked = False
                self.set_state("idle" if self.on_ground else "jump")
        elif self.state == "death":
            if self.frame_index >= end:
                self.frame_index = end - 1
                self.just_finished = "death"
        else:
            if self.frame_index >= end:
                self.frame_index = 0.0

        surf = frames[int(self.frame_index)]
        midbottom = self.rect.midbottom
        self.image = surf
        self.rect = self.image.get_rect(midbottom=midbottom)

    def update(self, keys, ground_y):
        self.handle_input(keys)
        self.apply_gravity(ground_y)
        self.animate()

# ================================ Enemy (mushroom) ================================
class Enemy(pygame.sprite.Sprite):
    """วิ่งจากขวา -> หยุดด้านขวาผู้เล่น -> รอ 5 วิ นับ J"""
    def __init__(self, pos=(900, 420), stop_offset=300, scale=3.0, speed=2, hp=2):
        super().__init__()
        assets = {
            "idle":   ["graphics/enemy/mushroom/Idle.png"],
            "run":    ["graphics/enemy/mushroom/Run.png"],
            "attack": ["graphics/enemy/mushroom/Attack.png"],
            "hit":    ["graphics/enemy/mushroom/Take Hit.png"],
            "death":  ["graphics/enemy/mushroom/Death.png"],
        }
        self.animations = {
            st: load_animation_with_fallback(paths, scale=scale)
            for st, paths in assets.items()
        }
        _ensure_animation_safety(self.animations)
        self.anim_speed = {"idle":0.18,"run":0.24,"attack":0.22,"hit":0.18,"death":0.18}

        self.state = "run"
        self.frame_index = 0.0
        self.image = self.animations[self.state][0]
        self.rect = self.image.get_rect(midbottom=pos)

        self.speed = speed
        self.hp = hp
        self.dead = False

        self.stop_offset = stop_offset
        self.challenge_ms_total = 5000
        self.challenge_ms_left = None
        self.player_attack_baseline = 0

        self.facing = -1  # อยู่ขวาผู้เล่น => หันซ้าย
        self.just_finished = None  # 'attack' | 'hit' | 'death' | None
        self.locked = False
        
    def set_state(self, st):
        if self.dead and st != "death":
            return
        if self.state != st:
            self.state = st
            self.frame_index = 0.0

    def start_challenge(self, player):
        self.challenge_ms_left = self.challenge_ms_total
        self.player_attack_baseline = player.attack_pressed_total
        player.set_full_lock(True)      # enemy อยู่ -> ล็อกเดิน/โดด
        player.set_challenge_lock(True) # ให้กดได้เฉพาะ J
        self.locked = False
        self.set_state("idle")

    def resolve_challenge(self, player):
        delta = player.attack_pressed_total - self.player_attack_baseline
        player.attack_pressed_total = 0
        self.challenge_ms_left = None
        player.set_challenge_lock(False)  # ปิดนับ J ชั่วคราวระหว่างเล่น sequence
        # ❗ แก้สำคัญ: คืนค่าเป็นสตริง ไม่ใช่ print
        return "player_win" if delta >= 3 else "enemy_win"

    def think(self, player, dt_ms):
        if self.dead or self.locked:
            return

        # ยังไม่เริ่มจับเวลา → วิ่งเข้าหาผู้เล่น (อนิเมชัน run) และล็อกผู้เล่น
        if self.challenge_ms_left is None:
            target_x = player.rect.centerx + self.stop_offset
            player.set_full_lock(True)
            player.set_challenge_lock(False)

            if self.rect.centerx > target_x:
                self.rect.centerx -= self.speed
                self.set_state("run")
            else:
                self.start_challenge(player)
        else:
            # ระหว่างจับเวลา: ยืน idle
            self.set_state("idle")

    def animate(self):
        self.just_finished = None
        frames = self.animations.get(self.state) or self.animations["idle"]
        end = len(frames)
        if end == 0:
            return

        self.frame_index += self.anim_speed.get(self.state, 0.18)

        if self.state in ("hit", "attack"):
            if self.frame_index >= end:
                self.frame_index = 0.0
                self.just_finished = self.state
                self.locked = False
                if not self.dead and self.challenge_ms_left is None:
                    self.set_state("idle")
        elif self.state == "death":
            if self.frame_index >= end:
                self.frame_index = end - 1
                self.just_finished = "death"
                self.kill()  # ออกจาก group เมื่อแอนิเมชันตายจบ
        else:
            if self.frame_index >= end:
                self.frame_index = 0.0

        surf = frames[int(self.frame_index)]
        if self.facing == -1:
            surf = pygame.transform.flip(surf, True, False)

        midbottom = self.rect.midbottom
        self.image = surf
        self.rect = self.image.get_rect(midbottom=midbottom)

    def update(self, player, dt_ms):
        self.think(player, dt_ms)
        self.animate()


# ============================= Game / Menu loop ===============================
pygame.init()
W, H = 960, 540
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Run-in-place -> Reach point -> Spawn enemy")
clock = pygame.time.Clock()
GROUND_Y = 460

# ====== วางไว้เหนือ game loop ======
def load_scaled_alpha(path, size):
    img = pygame.image.load(path).convert_alpha()
    return pygame.transform.scale(img, size)

class ParallaxBG:
    def __init__(self, W, H, layers):
        # layers = [(path, speed), ...]  speed มาก = ขยับเร็ว (ชั้นหน้า)
        self.W, self.H = W, H
        self.layers = [(load_scaled_alpha(p, (W, H)), sp) for p, sp in layers]
        self.t = 0.0

    def update(self, moving: bool, dt_ms: int):
        # วิ่งอยู่กับที่ → ให้ฉากไหลช้า ๆ
        if moving:
            self.t += dt_ms * 0.12   # คูณเร็ว-ช้าได้

    def draw(self, screen):
        for img, sp in self.layers:
            # เลื่อนแบบวนซ้ำทั้งภาพ
            off = int(self.t * sp) % self.W
            screen.blit(img, (-off, 0))
            screen.blit(img, (self.W - off, 0))

# ====== สร้างพื้นหลังหลัง pygame.init() ======
parallax = ParallaxBG(
    W, H,
    [
        ("graphics/background/sky.png",         0.00),  # ไกลสุด ขยับน้อย/ไม่ขยับ
        ("graphics/background/graves.png",      0.24),
        ("graphics/background/back_trees.png",  0.26),
        ("graphics/background/crypt.png",       0.28),
        ("graphics/background/wall.png",        0.30),
        ("graphics/background/ground.png",      0.34),  # พื้น
        # ("graphics/background/bones.png",       0.18),  # องค์ประกอบหน้า
        ("graphics/background/tree.png",        0.52),  # ต้นไม้หน้า ๆ
    ]
)


font = pygame.font.SysFont(None, 28)

# --- Player ---
selected = "wizard"
player_group = pygame.sprite.GroupSingle(Player(selected, pos=(W//2 - 120, GROUND_Y)))

# --- Enemy group (เริ่มต้นไม่มีศัตรู) ---
enemy_group = pygame.sprite.GroupSingle()

# --- Travel progress (วิ่งอยู่กับที่เพื่อสะสมระยะ) ---
PROGRESS_TO_SPAWN = 1000         # ระยะที่ต้องวิ่งให้ครบ
PROGRESS_SPEED_PER_MS = 0.25     # เพิ่มต่อมิลลิวินาทีเมื่อกำลังกดเดิน (~4 วิจะครบ 1000)
progress = 0.0                   # ค่าเริ่มต้น

# Orchestrator: จัดคิวแอนิเมชันตามผลลัพธ์
sequence = None  # {"steps":[...], "idx":0, "started":False}
def start_sequence(steps):
    return {"steps": steps, "idx": 0, "started": False}

while True:
    dt = clock.tick(60)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit(); exit()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_j:
                player_group.sprite.start_attack()
            if event.key == pygame.K_r:
                player_group.sprite.revive()
    
    keys = pygame.key.get_pressed()


    # อัปเดต player/enemy
    player = player_group.sprite
    player_group.update(keys, GROUND_Y)

    enemy = enemy_group.sprite
    enemy_group.update(player, dt)

    # ล็อก/ปลดล็อกแบบทั่วๆ ไป: มีศัตรู -> ล็อกเดิน/โดด, ไม่มีศัตรู -> ปลดล็อก
    if enemy_group.sprite is not None:
        player.set_full_lock(True)
    else:
        player.set_full_lock(False)
        player.set_challenge_lock(False)

    # สะสม progress เฉพาะตอนที่ยังไม่มีศัตรู + ผู้เล่นกำลังกดวิ่ง + ไม่มีคิว
    if (enemy_group.sprite is None) and player.is_moving and not sequence:
        progress += PROGRESS_SPEED_PER_MS * dt
        if progress > PROGRESS_TO_SPAWN:
            progress = PROGRESS_TO_SPAWN

    # ถ้ายังไม่มีศัตรู และ progress ถึงเป้า => spawn มอนใหม่ แล้วรีเซ็ต progress
    if (enemy_group.sprite is None) and (progress >= PROGRESS_TO_SPAWN):
        new_enemy = Enemy(pos=(W + 80, GROUND_Y), stop_offset=300, speed=2, hp=2)
        enemy_group.add(new_enemy)
        player.set_full_lock(True)     # ล็อกทันทีที่ศัตรูเกิด
        player.set_challenge_lock(False)
        progress = 0.0

    # จับเวลา 5 วิ (เฉพาะใน main loop)
    enemy = enemy_group.sprite
    if enemy and enemy.challenge_ms_left is not None:
        enemy.challenge_ms_left -= dt
        if enemy.challenge_ms_left <= 0 and sequence is None:
            result = enemy.resolve_challenge(player)
            if result == "player_win":
                enemy.hp -= 1
                if enemy.hp <= 0:
                    sequence = start_sequence(["player_attack", "enemy_death"])
                else:
                    sequence = start_sequence(["player_attack", "enemy_hit"])
            elif result == "enemy_win":
                sequence = start_sequence(["enemy_attack", "player_hit"])

    # Run sequence ทีละสเต็ป
    enemy = enemy_group.sprite
    if sequence and enemy:
        step = sequence["steps"][sequence["idx"]]

        if step == "player_attack":
            if not sequence["started"]:
                player.play_attack_anim()
                sequence["started"] = True
            if player.just_finished == "attack":
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
                sequence = None
                player.set_full_lock(False)
                player.set_challenge_lock(False)

        elif step == "enemy_attack":
            if not sequence["started"]:
                enemy.locked = True
                enemy.set_state("attack")
                sequence["started"] = True
            if enemy.just_finished == "attack":
                sequence["idx"] += 1
                sequence["started"] = False

        elif step == "player_hit":
            if not sequence["started"]:
                player.start_hit()
                sequence["started"] = True
            if player.just_finished == "hit":
                sequence["idx"] += 1
                sequence["started"] = False

        # ถ้าคิวหมดแล้ว ชี้ชัดว่าจะเริ่มจับเวลาใหม่หรือปลดล็อก
        if sequence and sequence["idx"] >= len(sequence["steps"]):
            last_steps = sequence["steps"]
            sequence = None

            enemy = enemy_group.sprite
            if last_steps == ["player_attack", "enemy_death"]:
                player.set_full_lock(False)
                player.set_challenge_lock(False)
            else:
                if enemy and not enemy.dead:
                    enemy.challenge_ms_left = enemy.challenge_ms_total
                    enemy.player_attack_baseline = player.attack_pressed_total
                    player.set_full_lock(True)
                    player.set_challenge_lock(True)
                    enemy.set_state("idle")

    # ----- kill-safe: กันคิวค้างเมื่อศัตรูถูก kill() ออกไปแล้ว -----
    if sequence and sequence["idx"] < len(sequence["steps"]):
        curr_step = sequence["steps"][sequence["idx"]]
        if curr_step == "enemy_death" and enemy_group.sprite is None:
            sequence = None
            player.set_full_lock(False)
            player.set_challenge_lock(False)

    # ---- Draw ----
    screen.fill((30, 30, 30))
    pygame.draw.line(screen, (70, 70, 70), (0, GROUND_Y), (W, GROUND_Y), 2)

    
    # --- วาดฉาก ---
    parallax.update(player.is_moving, dt)  # ใช้ธง is_moving ที่คุณมีอยู่แล้ว
    parallax.draw(screen)

    # --- วาดสปไรต์ ---
    player_group.draw(screen)
    enemy_group.draw(screen)
    
    player_group.draw(screen)
    enemy_group.draw(screen)
    
    

    # UI: progress bar (วิ่งอยู่กับที่เพื่อไปถึงจุด)
    bar_w, bar_h = 320, 14
    x, y = 20, 16
    pygame.draw.rect(screen, (80, 80, 80), (x, y, bar_w, bar_h), border_radius=6)
    fill_w = int(bar_w * (progress / PROGRESS_TO_SPAWN))
    pygame.draw.rect(screen, (180, 220, 120), (x, y, fill_w, bar_h), border_radius=6)
    txt = font.render("Run to reach the point (press ←/→)", True, (200,200,200))
    screen.blit(txt, (x, y + 20))

    # UI: enemy info
    if enemy_group.sprite:
        info1 = font.render(f"Enemy HP: {enemy_group.sprite.hp}", True, (220,220,220))
        screen.blit(info1, (20, 60))
        if enemy_group.sprite.challenge_ms_left is not None:
            left_ms = max(0, enemy_group.sprite.challenge_ms_left)
            left = left_ms//1000 + (1 if left_ms%1000>0 else 0)
            info3 = font.render(f"Challenge: press J >= 3 in {left}s", True, (255,210,160))
            screen.blit(info3, (20, 84))

    # hint
    hint = font.render("J = stack hits (count only), R = Revive", True, (170,170,170))
    screen.blit(hint, (20, 110))

    pygame.display.flip()
