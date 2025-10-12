# player.py
import pygame
from animation_helper import load_animation_with_fallback, _ensure_animation_safety

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
                "attack2":["graphics/player/wizard/Attack1.png"],
                "hit":    ["graphics/player/wizard/Hit.png"],
                "death":  ["graphics/player/wizard/Death.png"],
        },
        "anim_speed": {"idle":0.15,"run":0.25,"jump":0.12,"attack":0.22,"attack2":0.22,"hit":0.18,"death":0.18},
    },
}

def _dummy_frame():
    s = pygame.Surface((1, 1), pygame.SRCALPHA)
    s.fill((0,0,0,0))
    return s

class Player(pygame.sprite.Sprite):
    def __init__(self, character, pos=(500, 420)):
        super().__init__()
        cfg = CHAR_CONFIGS[character]
        self.animations = {st: load_animation_with_fallback(paths, scale=cfg["scale"])
                           for st, paths in cfg["assets"].items()}
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
        self.full_lock = False
        self.challenge_lock = False

        self.attack_pressed_total = 0
        self.just_finished = None

        self.is_moving = False
        self.external_move = False
        self.external_dir = 0
        self.coin_lock = False
        self.obstacle_lock = False

        self.max_hp = 20
        self.hp = self.max_hp

        # ★ i-frame กันโดนซ้ำหลังโดนดาเมจ
        self.iframe_ms = 0          # นับถอยหลังหน่วย ms

        self.heart_images = [
            pygame.image.load("graphics/ui/Hearts_Red_1.png").convert_alpha(),
            pygame.image.load("graphics/ui/Hearts_Red_2.png").convert_alpha(),
            pygame.image.load("graphics/ui/Hearts_Red_3.png").convert_alpha(),
            pygame.image.load("graphics/ui/Hearts_Red_4.png").convert_alpha(),
            pygame.image.load("graphics/ui/Hearts_Red_5.png").convert_alpha(),
        ]

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
            self.external_move = False
            if self.on_ground and not self.locked:
                self.set_state("idle")

    def set_challenge_lock(self, active: bool):
        self.challenge_lock = active

    def handle_input(self, keys):
        if self.full_lock or self.locked or self.dead or getattr(self, "coin_lock", False) or getattr(self,"obstacle_lock",False):
            self.is_moving = False
            self.external_move = False
            return

        moving_keys = (keys[pygame.K_LEFT] or keys[pygame.K_a] or
                       keys[pygame.K_RIGHT] or keys[pygame.K_d])
        moving = moving_keys or self.external_move
        self.is_moving = moving
        self.external_move = False

        if (keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]) and self.on_ground:
            self.vel_y = -self.jump_power
            self.on_ground = False
            self.set_state("jump")

        if self.on_ground and not self.locked:
            self.set_state("run" if moving else "idle")

    def start_attack(self):
        if not self.dead and self.challenge_lock:
            self.attack_pressed_total += 1
            return
        if not self.dead and not self.locked:
            self.play_attack_anim()

    def play_attack_anim(self, ignore_locked=False):
        if not self.dead and (not self.locked or ignore_locked):
            self.locked = True
            self.set_state("attack")

    def play_attack_anim_named(self, name: str, ignore_locked=True):
        if self.dead:
            return
        if self.locked and not ignore_locked:
            return
        if name not in self.animations:
            name = "attack"
        self.locked = True
        self.set_state(name)

    def start_death(self):
        if self.dead: return
        self.dead = True
        self.locked = True
        self.set_state("death")

    def revive(self):
        self.dead = False
        self.locked = False
        self.vel_y = 0.0
        self.on_ground = True
        self.just_finished = None
        self.iframe_ms = 0
        self.set_state("idle")

    def start_hit(self, damage=1):
        # ★ กันโดนซ้ำถ้ายังอยู่ในช่วง i-frame
        if self.iframe_ms > 0:
            return
        if not self.dead:
            self.hp -= damage
            # เริ่ม i-frame ~0.6 วินาที (ปรับได้)
            self.iframe_ms = 600
            if self.hp <= 0:
                self.hp = 0
                self.start_death()
            else:
                self.locked = True
                self.set_state("hit")

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

        if self.state in ("attack","attack2","hit"):
            if self.frame_index >= end:
                self.frame_index = 0.0
                self.just_finished = self.state
                self.locked = False
                self.set_state("idle" if self.on_ground else "jump")
        elif self.state == "death":
            if self.frame_index >= end:
                self.frame_index = end-1
                self.just_finished = "death"
        else:
            if self.frame_index >= end:
                self.frame_index = 0.0

        surf = frames[int(self.frame_index)]
        midbottom = self.rect.midbottom
        self.image = surf
        self.rect = self.image.get_rect(midbottom=midbottom)

    def update(self, keys, ground_y, dt_ms=None):
        # ★ นับถอยหลัง i-frame ตามเวลาจริง
        if self.iframe_ms > 0:
            self.iframe_ms = max(0, self.iframe_ms - (dt_ms if dt_ms is not None else 16))

        self.handle_input(keys)
        self.apply_gravity(ground_y)
        self.animate()
