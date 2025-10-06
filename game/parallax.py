import pygame

def load_scaled_alpha(path, size):
    img = pygame.image.load(path).convert_alpha()
    return pygame.transform.scale(img, size)

class ParallaxBG:
    def __init__(self, W, H, layers):
        self.W, self.H = W,H
        self.layers = [(load_scaled_alpha(p,(W,H)), sp) for p,sp in layers]
        self.t = 0.0
    def update(self, moving, dt_ms):
        if moving:
            self.t += dt_ms*0.12
    def draw(self, screen):
        for img, sp in self.layers:
            off = int(self.t*sp)%self.W
            screen.blit(img, (-off,0))
            screen.blit(img, (self.W-off,0))
