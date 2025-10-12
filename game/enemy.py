# enemy.py
import pygame
from animation_helper import load_animation_with_fallback, _ensure_animation_safety

CHAR_CONFIGS = {
    "mushroom": {
        "scale": 3.0, "speed": 2, "hp": 2, "damage": 1,
        "assets": {
            "idle": ["graphics/enemy/mushroom/Idle.png"],
            "run": ["graphics/enemy/mushroom/Run.png"],
            "attack": ["graphics/enemy/mushroom/Attack.png"],
            "hit": ["graphics/enemy/mushroom/Take Hit.png"],
            "death": ["graphics/enemy/mushroom/Death.png"],
        },
        "anim_speed": {"idle":0.18,"run":0.24,"attack":0.22,"hit":0.18,"death":0.18},
        "spawn_grace_ms": 800,
    },
    "goblin": {
        "scale": 4.0, "speed": 2, "hp": 4, "damage": 1,
        "assets": {
            "idle": ["graphics/enemy/goblin/Idle.png"],
            "run": ["graphics/enemy/goblin/Run.png"],
            "attack": ["graphics/enemy/goblin/Attack.png"],
            "hit": ["graphics/enemy/goblin/Hit.png"],
            "death": ["graphics/enemy/goblin/Death.png"],
        },
        "anim_speed": {"idle":0.18,"run":0.24,"attack":0.22,"hit":0.18,"death":0.18},
        "spawn_grace_ms": 800,
    },
    "skeleton": {
        "scale": 4.0, "speed": 2, "hp": 4, "damage": 2,
        "assets": {
            "idle": ["graphics/enemy/skeleton/Idle.png"],
            "run": ["graphics/enemy/skeleton/Walk.png"],
            "attack": ["graphics/enemy/skeleton/Attack.png"],
            "hit": ["graphics/enemy/skeleton/Hit.png"],
            "death": ["graphics/enemy/skeleton/Death.png"],
        },
        "anim_speed": {"idle":0.18,"run":0.24,"attack":0.22,"hit":0.18,"death":0.18},
        "spawn_grace_ms": 800,
    },
    "flying eye": {
        "scale": 3.0, "speed": 2, "hp": 2, "damage": 1,
        "assets": {
            "idle": ["graphics/enemy/flying_eye/Flight.png"],
            "run":  ["graphics/enemy/flying_eye/Flight.png"],
            "attack": ["graphics/enemy/flying_eye/Attack.png"],
            "hit":  ["graphics/enemy/flying_eye/Take Hit.png"],
            "death":["graphics/enemy/flying_eye/Death.png"],
        },
        "anim_speed": {"idle":0.18,"run":0.24,"attack":0.22,"hit":0.18,"death":0.18},
        "spawn_grace_ms": 800,
    },
    "evil": {
        "scale": 4.0, "speed": 2, "hp": 8, "damage": 5,
        "assets": {
            "idle": ["graphics/enemy/evil/Idle.png"],
            "run":  ["graphics/enemy/evil/Run.png"],
            "attack": ["graphics/enemy/evil/Attack2.png"],
            "hit":  ["graphics/enemy/evil/Take Hit.png"],
            "death":["graphics/enemy/evil/Death.png"],
        },
        "anim_speed": {"idle":0.18,"run":0.24,"attack":0.22,"hit":0.18,"death":0.18},
        "spawn_grace_ms": 800,
    },
    "neon phantom": {
        "scale": 5.0, "speed": 2, "hp": 10, "damage": 7,
        "assets": {
            "idle": ["graphics/enemy/NeonPhantom/Idle.png"],
            "run":  ["graphics/enemy/NeonPhantom/Run.png"],
            "attack": ["graphics/enemy/NeonPhantom/Attack2.png"],
            "hit":  ["graphics/enemy/NeonPhantom/Take Hit.png"],
            "death":["graphics/enemy/NeonPhantom/Death.png"],
        },
        "anim_speed": {"idle":0.18,"run":0.24,"attack":0.22,"hit":0.18,"death":0.18},
        "spawn_grace_ms": 800,
    },
    "gorgon": {
        "scale": 3.0, "speed": 2, "hp": 10, "damage": 7,
        "assets": {
            "idle": ["graphics/enemy/gorgon/Idle.png"],
            "run":  ["graphics/enemy/gorgon/Run.png"],
            "attack": ["graphics/enemy/gorgon/Attack_1.png"],
            "hit":  ["graphics/enemy/gorgon/Hurt.png"],
            "death":["graphics/enemy/gorgon/Dead.png"],
        },
        "anim_speed": {"idle":0.18,"run":0.24,"attack":0.22,"hit":0.18,"death":0.18},
        "spawn_grace_ms": 800,
    },
    # บอสหนอนไฟ
    "fireworm": {
        "scale": 4.0,
        "speed": 2,
        "hp": 8,
        "damage": 5,
        "required_delta": 7,  # ★ กำหนดเกณฑ์กดเฉพาะตัว (อยากให้กี่ยังก็เปลี่ยนตรงนี้ได้)\
        "assets": {
            "idle":   ["graphics/enemy/worm/Idle.png"],
            "run":    ["graphics/enemy/worm/Walk.png"],
            "attack": ["graphics/enemy/worm/Attack.png"],     # ถ้ายังไม่มีไฟล์ ใช้ Move.png ไปก่อน
            "hit":    ["graphics/enemy/worm/Get Hit.png"],   # หรือ Move.png
            "death":  ["graphics/enemy/worm/Death.png"],
        },
        "anim_speed": {"idle":0.18,"run":0.24,"attack":0.22,"hit":0.18,"death":0.18},
        
    "shoot_period_ms": 0,       # ไม่ยิงอัตโนมัติ (ยิงเฉพาะตอนผู้เล่นแพ้)
    "projectile_damage": 5,     # ★ ลูกไฟทำดาเมจ 5
    "muzzle_y_offset": -20
    }

}

def _dummy_frame():
    s = pygame.Surface((1,1),pygame.SRCALPHA)
    s.fill((0,0,0,0))
    return s

class Enemy(pygame.sprite.Sprite):
    def __init__(self, enemy_type="mushroom", pos=(900,420), stop_offset=None, speed=None, hp=None):
        super().__init__()
        self.enemy_type = enemy_type
        cfg = CHAR_CONFIGS.get(enemy_type, CHAR_CONFIGS["mushroom"])

        # stats
        self.speed = speed if speed is not None else cfg.get("speed", 2)
        self.hp = hp if hp is not None else cfg.get("hp", 1)
        self.stop_offset = stop_offset if stop_offset is not None else 300
        self.damage = cfg.get("damage", 1)

        self.dead = False
        self.challenge_ms_total = 5000
        self.challenge_ms_left = None
        self.player_attack_baseline = 0
        self.facing = -1
        self.just_finished = None
        self.locked = False

        # กันโจมตี/ยิงทันทีตอน spawn
        self.no_shoot_ms = cfg.get("spawn_grace_ms", 800)

        # ถ้าเป็นตัวที่ “ยิงได้” ใส่คูลดาวน์เริ่มต้น
        self.shoot_period_ms = cfg.get("shoot_period_ms", 0)
        self.shoot_cd_ms = 0
        self.shoot_first_delay_ms = cfg.get("shoot_first_delay_ms", 0)
        self.projectile_damage = cfg.get("projectile_damage", self.damage)
        self.muzzle_y_offset = cfg.get("muzzle_y_offset", -20)
        self.required_delta = cfg.get("required_delta", 3)

        # animations
        self.animations = {state: load_animation_with_fallback(paths, scale=cfg["scale"])
                           for state, paths in cfg["assets"].items()}
        _ensure_animation_safety(self.animations)
        self.anim_speed = cfg.get("anim_speed", {"idle":0.18, "run":0.24, "attack":0.22, "hit":0.18, "death":0.18})

        self.state = "run"
        self.frame_index = 0.0
        self.image = self.animations[self.state][0]
        self.rect = self.image.get_rect(midbottom=pos)

    def set_state(self, state):
        if self.dead and state != "death":
            return
        if self.state != state:
            self.state = state
            self.frame_index = 0.0

    def start_challenge(self, player):
        self.challenge_ms_left = self.challenge_ms_total
        self.player_attack_baseline = player.attack_pressed_total
        self.locked = False
        self.set_state("idle")
        # กันยิงช่วงเริ่มดวลรอบแรก
        self.no_shoot_ms = max(self.no_shoot_ms, self.shoot_first_delay_ms)

    def think(self, player, dt_ms):
        if self.dead or self.locked:
            return
        if self.challenge_ms_left is None:
            target_x = player.rect.centerx + self.stop_offset
            if self.rect.centerx > target_x:
                self.rect.centerx -= self.speed
                self.set_state("run")
            else:
                self.start_challenge(player)
        else:
            self.set_state("idle")

    def animate(self):
        self.just_finished = None
        frames = self.animations.get(self.state) or [_dummy_frame()]
        end = len(frames)
        if end == 0: return

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
                self.frame_index = end-1
                self.just_finished = "death"
                self.kill()
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
        if self.no_shoot_ms > 0:
            self.no_shoot_ms = max(0, self.no_shoot_ms - dt_ms)
        if self.shoot_cd_ms > 0:
            self.shoot_cd_ms = max(0, self.shoot_cd_ms - dt_ms)

        self.think(player, dt_ms)
        self.animate()

    # ★ ยิงกระสุน (เมธอดว่างสำหรับศัตรูทั่วไป / มีลอจิกสำหรับตัวที่ยิงได้)
    def shoot_tick(self, player, dt_ms, projectile_group, ProjectileClass):
        # ต้องอยู่ใน challenge เท่านั้น
        if self.challenge_ms_left is None:
            return
        # ยังอยู่ในช่วงกันยิง หรือยังไม่มีระบบยิง → ไม่ยิง
        if self.no_shoot_ms > 0 or self.shoot_period_ms <= 0:
            return
        # คูลดาวน์อยู่ → ยังไม่ถึงรอบ
        if self.shoot_cd_ms > 0:
            return

        # เล่นแอนิเมชันโจมตีสั้น ๆ
        self.locked = True
        self.set_state("attack")
        self.frame_index = 0.0

        # จุดเริ่มกระสุน (ยิงซ้าย)
        dir_x = -1
        start_pos = (self.rect.centerx - 30, self.rect.centery + self.muzzle_y_offset)
        dmg = self.projectile_damage

        # สร้างลูกไฟ
        projectile_group.add(ProjectileClass(start_pos, dir_x=dir_x, damage=dmg))

        # ตั้งคูลดาวน์รอบต่อไป
        self.shoot_cd_ms = self.shoot_period_ms
