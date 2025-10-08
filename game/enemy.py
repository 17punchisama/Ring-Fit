import pygame
from animation_helper import load_animation_with_fallback, _ensure_animation_safety

CHAR_CONFIGS = {
    "mushroom": {
        "scale": 3.0,
        "speed": 2,
        "hp": 2,
        "damage": 1,
        "assets": {
            "idle": ["graphics/enemy/mushroom/Idle.png"],
            "run": ["graphics/enemy/mushroom/Run.png"],
            "attack": ["graphics/enemy/mushroom/Attack.png"],
            "hit": ["graphics/enemy/mushroom/Take Hit.png"],
            "death": ["graphics/enemy/mushroom/Death.png"],
        },
        "anim_speed": {"idle":0.18, "run":0.24, "attack":0.22, "hit":0.18, "death":0.18}
    },
        "flying eye": {
        "scale": 3.0,
        "speed": 2,
        "hp": 2,
        "damage": 1,
        "assets": {
            "idle": ["graphics/enemy/flying_eye/Flight.png"],
            "run": ["graphics/enemy/flying_eye/Flight.png"],
            "attack": ["graphics/enemy/flying_eye/Attack.png"],
            "hit": ["graphics/enemy/flying_eye/Take Hit.png"],
            "death": ["graphics/enemy/flying_eye/Death.png"],
        },
        "anim_speed": {"idle":0.18, "run":0.24, "attack":0.22, "hit":0.18, "death":0.18},
        "hover_from_ground": 130
    },
    "goblin": {
        "scale": 4.0,
        "speed": 2,
        "hp": 4,
        "damage": 2,
        "assets": {
            "idle": ["graphics/enemy/goblin/Idle.png"],
            "run": ["graphics/enemy/goblin/Run.png"],
            "attack": ["graphics/enemy/goblin/Attack.png"],
            "hit": ["graphics/enemy/goblin/Hit.png"],
            "death": ["graphics/enemy/goblin/Death.png"],
        },
        "anim_speed": {"idle":0.18, "run":0.24, "attack":0.22, "hit":0.18, "death":0.18}
    },
    "skeleton": {
        "scale": 4.0,
        "speed": 2,
        "hp": 4,
        "damage": 3,
        "assets": {
            "idle": ["graphics/enemy/skeleton/Idle.png"],
            "run": ["graphics/enemy/skeleton/Walk.png"],
            "attack": ["graphics/enemy/skeleton/Attack.png"],
            "hit": ["graphics/enemy/skeleton/Hit.png"],
            "death": ["graphics/enemy/skeleton/Death.png"],
        },
        "anim_speed": {"idle":0.18, "run":0.24, "attack":0.22, "hit":0.18, "death":0.18}
    }
}

def _dummy_frame():
    s = pygame.Surface((1,1),pygame.SRCALPHA)
    s.fill((0,0,0,0))
    return s

class Enemy(pygame.sprite.Sprite):
    def __init__(self, enemy_type="mushroom", pos=(900,420), stop_offset=None, speed=None, hp=None):
        super().__init__()
        cfg = CHAR_CONFIGS.get(enemy_type, CHAR_CONFIGS["mushroom"])

        # stats
        self.speed = speed if speed is not None else cfg.get("speed", 2)
        self.hp = hp if hp is not None else cfg.get("hp", 1)
        self.stop_offset = stop_offset if stop_offset is not None else 300

        self.dead = False
        self.challenge_ms_total = 5000
        self.challenge_ms_left = None
        self.player_attack_baseline = 0
        self.facing = -1
        self.just_finished = None
        self.locked = False
        
        self.damage = cfg.get("damage", 1)

        # animations
        self.animations = {state: load_animation_with_fallback(paths, scale=cfg["scale"])
                           for state, paths in cfg["assets"].items()}
        _ensure_animation_safety(self.animations)
        self.anim_speed = cfg.get("anim_speed", {"idle":0.18, "run":0.24, "attack":0.22, "hit":0.18, "death":0.18})

        self.state = "run"
        self.frame_index = 0.0
        self.image = self.animations[self.state][0]
        self.rect = self.image.get_rect(midbottom=pos)
        
        hover = cfg.get("hover_from_ground", 0)
        if hover:
            ground_y = pos[1]          # เราส่ง GROUND_Y มาเป็น pos[1] ตอน spawn
            self.rect.bottom = ground_y - hover


    def set_state(self, state):
        if self.dead and state != "death":
            return
        if self.state != state:
            self.state = state
            self.frame_index = 0.0

    def start_challenge(self, player):
        self.challenge_ms_left = self.challenge_ms_total
        self.player_attack_baseline = player.attack_pressed_total
        # ❌ ห้ามแตะ lock ของ player
        # player.set_full_lock(True)
        # player.set_challenge_lock(True)
        self.locked = False
        self.set_state("idle")

    def think(self, player, dt_ms):
        if self.dead or self.locked:
            return
        if self.challenge_ms_left is None:
            target_x = player.rect.centerx + self.stop_offset
            # ❌ ห้ามแตะ lock ของ player ที่นี่เช่นกัน
            if self.rect.centerx > target_x:
                self.rect.centerx -= self.speed
                self.set_state("run")
            else:
                self.start_challenge(player)
        else:
            self.set_state("idle")


    def resolve_challenge(self, player):
        delta = player.attack_pressed_total - self.player_attack_baseline
        player.attack_pressed_total = 0
        self.challenge_ms_left = None
        player.set_challenge_lock(False)
        return "player_win" if delta >= 3 else "enemy_win"

    # def think(self, player, dt_ms):
    #     if self.dead or self.locked:
    #         return
    #     if self.challenge_ms_left is None:
    #         target_x = player.rect.centerx + self.stop_offset
    #         # player.set_full_lock(True)
    #         # player.set_challenge_lock(False)
    #         if self.rect.centerx > target_x:
    #             self.rect.centerx -= self.speed
    #             self.set_state("run")
    #         else:
    #             self.start_challenge(player)
    #     else:
    #         self.set_state("idle")

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
        self.think(player, dt_ms)
        self.animate()
