import pygame, os

def slice_by_alpha_regions(path, expected=None):
    sheet = pygame.image.load(path).convert_alpha()
    sw, sh = sheet.get_width(), sheet.get_height()

    def col_has_pixel(x):
        for y in range(sh):
            if sheet.get_at((x, y))[3] != 0:
                return True
        return False

    segments = []
    in_run, run_start = False, 0
    for x in range(sw):
        nonempty = col_has_pixel(x)
        if nonempty and not in_run:
            in_run, run_start = True, x
        elif not nonempty and in_run:
            in_run = False
            segments.append((run_start, x))
    if in_run:
        segments.append((run_start, sw))

    raw_frames = []
    for sx, ex in segments:
        w = max(1, ex - sx)
        raw_frames.append(sheet.subsurface(pygame.Rect(sx, 0, w, sh)).copy())

    if expected is not None and len(raw_frames) != expected and len(raw_frames) > 0:
        widths = [f.get_width() for f in raw_frames]
        thr = max(8, int(0.15 * max(widths)))
        raw_frames = [f for f in raw_frames if f.get_width() >= thr]

    return raw_frames

def align_and_pad(frames, anchor="midbottom"):
    cropped = []
    for f in frames:
        bbox = f.get_bounding_rect(min_alpha=1)
        cropped.append(f.subsurface(bbox).copy())

    if not cropped:
        return []

    max_w = max(f.get_width() for f in cropped)
    max_h = max(f.get_height() for f in cropped)

    aligned = []
    for f in cropped:
        canvas = pygame.Surface((max_w, max_h), pygame.SRCALPHA)
        r = f.get_rect()
        if anchor == "midbottom":
            r.midbottom = (max_w // 2, max_h)
        else:
            r.center = (max_w // 2, max_h // 2)
        canvas.blit(f, r)
        aligned.append(canvas)
    return aligned

def _load_animation_single(path, scale=3.0, expected=None):
    frames = slice_by_alpha_regions(path, expected=expected)
    frames = align_and_pad(frames, anchor="midbottom")
    if scale != 1.0 and frames:
        frames = [pygame.transform.scale_by(f, scale) for f in frames]
    return frames

def load_animation_with_fallback(paths, scale=3.0, expected=None):
    last_err = None
    for p in paths:
        try:
            if os.path.exists(p):
                return _load_animation_single(p, scale=scale, expected=expected)
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    raise FileNotFoundError(f"No valid asset found among: {paths}")

# ----- เพิ่มฟังก์ชันนี้ -----
def _ensure_animation_safety(anims: dict):
    """ให้ทุก state มีเฟรมเสมอ: ถ้าว่าง -> ใช้ idle; ถ้า idle ว่าง -> ใส่ dummy 1x1"""
    idle_frames = anims.get("idle") or []
    if not idle_frames:
        anims["idle"] = [pygame.Surface((1,1), pygame.SRCALPHA)]
    for st in list(anims.keys()):
        if not anims[st]:
            anims[st] = anims["idle"]
