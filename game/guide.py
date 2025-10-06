import pygame
from animation_helper import slice_by_alpha_regions, align_and_pad

class Guide(pygame.sprite.Sprite):
    def __init__(self, animations_dict, pos, scale=1.0):
        """
        animations_dict: dict {"collect_coin": path, "jump": path, ...}
        pos: tuple(x, y) ตำแหน่งกลาง guide
        scale: ปรับขนาดของ guide
        """
        super().__init__()
        self.animations = {}
        for key, path in animations_dict.items():
            # slice sprite sheet เป็น frames
            raw_frames = slice_by_alpha_regions(path)
            frames = align_and_pad(raw_frames)
            if scale != 1.0:
                frames = [pygame.transform.scale(f, (int(f.get_width()*scale), int(f.get_height()*scale))) for f in frames]
            if not frames:
                frames = [pygame.Surface((50,50), pygame.SRCALPHA)]
            self.animations[key] = frames

        self.state = list(self.animations.keys())[0]  # animation เริ่มต้น
        self.frame_index = 0.0
        self.anim_speed = 0.05  # ปรับความเร็ว animation
        self.image = self.animations[self.state][0]
        self.rect = self.image.get_rect(center=pos)

        self.visible = True   # ควบคุม draw
        self.active = True    # ควบคุม update animation

    def set_state(self, state):
        """
        เปลี่ยน animation state ของ guide
        """
        if state in self.animations:
            self.state = state
            self.frame_index = 0.0

    def update(self):
        """
        update animation frame index
        """
        if not self.active:
            return  # ถ้า inactive จะไม่ update frame

        frames = self.animations[self.state]
        if not frames:
            return

        self.frame_index += self.anim_speed
        if self.frame_index >= len(frames):
            self.frame_index = 0.0

        self.image = frames[int(self.frame_index)]
