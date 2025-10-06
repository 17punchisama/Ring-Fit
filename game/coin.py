import pygame
from animation_helper import slice_by_alpha_regions, align_and_pad

class Coin(pygame.sprite.Sprite):
    def __init__(self, pos, sprite_sheet_path, scale=3.0):
        super().__init__()
        raw_frames = slice_by_alpha_regions(sprite_sheet_path)
        frames = align_and_pad(raw_frames)
        
        # scale frames
        self.frames = [pygame.transform.scale(f, (int(f.get_width()*scale), int(f.get_height()*scale))) for f in frames]
        
        if not self.frames:
            self.frames = [pygame.Surface((24,24), pygame.SRCALPHA)]
            pygame.draw.circle(self.frames[0], (255,215,0), (12,12), 12)

        self.frame_index = 0.0
        self.anim_speed = 0.07
        self.image = self.frames[0]
        self.rect = self.image.get_rect(center=pos)


    def update(self):
        # animate: frame_index เพิ่มทีละ anim_speed
        self.frame_index += self.anim_speed
        if self.frame_index >= len(self.frames):
            self.frame_index = 0.0
        self.image = self.frames[int(self.frame_index)]
