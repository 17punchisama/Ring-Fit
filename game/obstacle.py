# obstacle.py
import pygame, random

def _load_image(path, scale):
    surf = pygame.image.load(path).convert_alpha()
    if isinstance(scale, (int, float)):
        if scale != 1:
            w, h = surf.get_width(), surf.get_height()
            surf = pygame.transform.smoothscale(surf, (int(w*scale), int(h*scale)))
    elif isinstance(scale, (tuple, list)) and len(scale) == 2:
        surf = pygame.transform.smoothscale(surf, (int(scale[0]), int(scale[1])))
    return surf

class Obstacle(pygame.sprite.Sprite):
    def __init__(
        self,
        pos=(900, 420),
        stop_offset=120,
        approach_speed=10,
        exit_speed=10,
        pass_margin=120,
        image_paths=None,          # ← ใส่ลิสต์หรือสตริงได้
        scale=1.0,                 # ← สเกล (float) หรือ (w,h)
    ):
        super().__init__()

        # ===== สุ่มรูปจาก assets =====
        if image_paths:
            path = random.choice(image_paths) if isinstance(image_paths, (list, tuple)) else image_paths
            self.image = _load_image(path, scale)
        else:
            # ถ้าไม่ส่ง assets มา ใช้สี่เหลี่ยมเดิม
            self.image = pygame.Surface((40, 40), pygame.SRCALPHA)
            self.image.fill((220, 160, 80))

        # วางให้ "ฐาน" ชิดพื้นด้วย midbottom
        self.rect = self.image.get_rect(midbottom=pos)

        # พารามิเตอร์
        self.stop_offset   = stop_offset
        self.approach_step = approach_speed
        self.exit_step     = exit_speed
        self.pass_margin   = pass_margin

        # สถานะ
        self.state    = "approach"    # approach -> wait -> pass -> tail
        self.target_x = None

    def start_wait(self, player):
        self.state = "wait"
        player.obstacle_lock = True
        player.is_moving = False
        if player.on_ground and not player.locked:
            player.set_state("idle")

    def start_pass(self, player):
        self.state = "pass"
        self.target_x = player.rect.centerx - self.pass_margin

    def update(self, player, dt_ms):
        if self.state == "approach":
            target_x = player.rect.centerx + self.stop_offset
            if self.rect.centerx > target_x:
                if getattr(player, "is_moving", False):
                    self.rect.centerx -= self.approach_step
            else:
                self.start_wait(player)

        elif self.state == "wait":
            pass

        elif self.state == "pass":
            self.rect.centerx -= self.exit_step
            if self.rect.centerx <= player.rect.centerx - self.pass_margin:
                self.state = "tail"

        elif self.state == "tail":
            if getattr(player, "is_moving", False):
                self.rect.centerx -= self.exit_step
            if self.rect.right < 0:
                self.kill()
