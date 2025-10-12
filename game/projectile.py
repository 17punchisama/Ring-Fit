# projectile.py
import pygame

def load_sheet(path):
    try:
        return pygame.image.load(path).convert_alpha()
    except Exception:
        s = pygame.Surface((32, 32), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 120, 0), (16, 16), 16)
        return s

def slice_sheet_horiz(sheet, frames=None, scale=None):
    w, h = sheet.get_width(), sheet.get_height()
    if frames is None:
        frames = max(1, w // h) if h else 1  # เดาจำนวนเฟรม (เฟรมจัตุรัส)
    frame_w = max(1, w // frames)
    images = []
    for i in range(frames):
        rect = pygame.Rect(i * frame_w, 0, frame_w, h)
        surf = pygame.Surface((frame_w, h), pygame.SRCALPHA)
        surf.blit(sheet, (0, 0), rect)
        if scale:
            surf = pygame.transform.smoothscale(surf, scale)
        images.append(surf)
    return images

class Fireball(pygame.sprite.Sprite):
    def __init__(
        self,
        pos,
        dir_x=-1,
        speed=7,
        damage=2,
        max_life_ms=5000,
        move_path="graphics/projectiles/Move.png",
        explode_path="graphics/projectiles/Explosion.png",
        move_frames=None,       # None = auto (เดา w//h)
        explode_frames=None,    # None = auto (เดา w//h)
        move_scale=(42, 42),
        explode_scale=(64, 64),
        move_fps=18,
        explode_fps=22
    ):
        super().__init__()
        self.dir_x = dir_x
        self.speed = speed
        self.damage = int(damage)
        self.state = "fly"
        self.timer_ms = 0
        self.max_life_ms = max_life_ms

        # โหลดชีต + ตัดเฟรม
        move_sheet = load_sheet(move_path)
        explode_sheet = load_sheet(explode_path)
        self.move_frames = slice_sheet_horiz(move_sheet, frames=move_frames, scale=move_scale)
        self.explode_frames = slice_sheet_horiz(explode_sheet, frames=explode_frames, scale=explode_scale)

        # ตั้งค่าอนิเมะ
        self._move_fps = max(1, int(move_fps))
        self._explode_fps = max(1, int(explode_fps))
        self._move_frame_time = 1000 // self._move_fps
        self._explode_frame_time = 1000 // self._explode_fps
        self._move_acc = 0
        self._explode_acc = 0
        self._move_idx = 0
        self._explode_idx = 0

        # รูปเริ่มต้น
        self.image = self.move_frames[self._move_idx] if self.move_frames else move_sheet
        self.rect = self.image.get_rect(center=pos)

    def explode(self):
        if self.state == "explode":
            return
        self.state = "explode"
        self._explode_acc = 0
        self._explode_idx = 0
        # รีเซ็นเตอร์รูปเฟรมแรกของระเบิด
        center = self.rect.center
        self.image = self.explode_frames[0] if self.explode_frames else self.image
        self.rect = self.image.get_rect(center=center)

    def update(self, dt_ms, screen_rect=None):
        self.timer_ms += dt_ms

        if self.state == "fly":
            # อนิเมะบิน
            self._move_acc += dt_ms
            while self._move_acc >= self._move_frame_time and self.move_frames:
                self._move_acc -= self._move_frame_time
                self._move_idx = (self._move_idx + 1) % len(self.move_frames)
                center = self.rect.center
                self.image = self.move_frames[self._move_idx]
                self.rect = self.image.get_rect(center=center)

            # เคลื่อนที่
            self.rect.x += int(self.dir_x * self.speed)

            # ออกนอกจอ/หมดอายุ -> ลบ
            off_screen = (screen_rect is not None) and (not self.rect.colliderect(screen_rect))
            if off_screen or (self.timer_ms > self.max_life_ms):
                self.kill()

        elif self.state == "explode":
            # อนิเมะระเบิด (เล่นจบแล้ว kill)
            self._explode_acc += dt_ms
            while self._explode_acc >= self._explode_frame_time and self.explode_frames:
                self._explode_acc -= self._explode_frame_time
                self._explode_idx += 1
                if self._explode_idx >= len(self.explode_frames):
                    self.kill()
                    return
                center = self.rect.center
                self.image = self.explode_frames[self._explode_idx]
                self.rect = self.image.get_rect(center=center)
