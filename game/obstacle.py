import pygame

class Obstacle(pygame.sprite.Sprite):
    def __init__(self, pos=(900, 420), stop_offset=120, approach_speed=10, exit_speed=10, pass_margin=120):
        super().__init__()
        self.image = pygame.Surface((40, 40), pygame.SRCALPHA)
        self.image.fill((220, 160, 80))
        self.rect = self.image.get_rect(midbottom=pos)

        # พารามิเตอร์
        self.stop_offset   = stop_offset
        self.approach_step = approach_speed   # เข้าหาเหมือน coin (ขึ้นกับ player.is_moving)
        self.exit_step     = exit_speed       # ตอนไหลออกเฟรม/ผ่านหลังผู้เล่น
        self.pass_margin   = pass_margin      # ให้ผ่านไป "หลังผู้เล่น" กี่พิกเซล

        # สถานะ
        self.state = "approach"               # approach -> wait -> pass -> tail
        self.target_x = None

    def start_wait(self, player):
        self.state = "wait"
        player.obstacle_lock = True
        player.is_moving = False
        if player.on_ground and not player.locked:
            player.set_state("idle")

    def start_pass(self, player):
        """เริ่มวิ่งผ่านด้านหลังผู้เล่นทันที ไม่ต้องพึ่ง player.is_moving"""
        self.state = "pass"
        # ผ่านให้ศูนย์กลางของ obstacle ไปอยู่ "หลังผู้เล่น" ตาม margin
        self.target_x = player.rect.centerx - self.pass_margin

    def update(self, player, dt_ms):
        if self.state == "approach":
            # ขยับเข้าหาผู้เล่นเฉพาะตอนผู้เล่นกำลังวิ่ง
            target_x = player.rect.centerx + self.stop_offset
            if self.rect.centerx > target_x:
                if getattr(player, "is_moving", False):
                    self.rect.centerx -= self.approach_step
            else:
                self.start_wait(player)

        elif self.state == "wait":
            # รอ main.py สั่ง start_pass() ตอนผู้เล่นกดกระโดด
            pass

        elif self.state == "pass":
            # วิ่งผ่านไปด้านหลังผู้เล่น "โดยไม่ผูกกับ is_moving"
            # เพื่อให้เกิดฟีล "ผู้เล่นกระโดดแล้วสิ่งกีดขวางไหลผ่านด้านล่าง"
            self.rect.centerx -= self.exit_step
            # พอผ่านหลังผู้เล่นพอ (centerx <= player.centerx - margin) → เข้าสู่ tail
            if self.rect.centerx <= player.rect.centerx - self.pass_margin:
                self.state = "tail"

        elif self.state == "tail":
            # ออกจากเฟรมโดยผูกกับการวิ่งของผู้เล่น (เหมือน coin)
            if getattr(player, "is_moving", False):
                self.rect.centerx -= self.exit_step
            if self.rect.right < 0:
                self.kill()
