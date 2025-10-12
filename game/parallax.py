import pygame

def load_scaled_alpha(path, size):
    img = pygame.image.load(path).convert_alpha()
    return pygame.transform.scale(img, size)

class ParallaxBG:
    """
    layers รับได้หลายรูปแบบ:
      (path, speed)
      (path, speed, scale)                # scale เป็น float หรือ (w,h)
      (path, speed, scale, bottom_y)      # จัดขอบล่างให้อยู่ที่ bottom_y (เช่น GROUND_Y)
    """
    def __init__(self, W, H, layers):
        self.W, self.H = W, H
        self.layers = []
        for item in layers:
            # แกะพารามิเตอร์
            if len(item) == 2:
                path, sp = item
                scale = (W, H)
                bottom_y = None
            elif len(item) == 3:
                path, sp, sc = item
                scale = (int(W*sc), int(H*sc)) if isinstance(sc, (int,float)) else sc
                bottom_y = None
            else:
                path, sp, sc, bottom_y = item
                scale = (int(W*sc), int(H*sc)) if isinstance(sc, (int,float)) else sc

            surf = load_scaled_alpha(path, scale)
            w, h = surf.get_width(), surf.get_height()

            # ตำแหน่งแกน Y: ถ้ามี bottom_y ให้ชิดล่างตรงนั้น ไม่งั้นกึ่งกลาง
            y = (bottom_y - h) if (bottom_y is not None) else (self.H - h) // 2

            self.layers.append({"surf": surf, "sp": float(sp), "w": w, "y": y})

        self.t = 0.0

    def update(self, moving, dt_ms):
        if moving:
            self.t += dt_ms * 0.12

    def draw(self, screen):
        for L in self.layers:
            surf, sp, w, y = L["surf"], L["sp"], L["w"], L["y"]
            off = int(self.t * sp) % w
            # ปูกระเบื้องแนวนอนให้เต็มจอ
            x0 = -off
            tiles = (self.W // w) + 2
            for i in range(-1, tiles):
                screen.blit(surf, (x0 + i * w, y))
