import os
import sys
import math
import time
import subprocess
import shutil
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

# ==============================================================================
# CONFIGURATION & LUXURY GOLD / OBSIDIAN FULL-STACK PALETTE (30 SECONDS @ 60FPS)
# ==============================================================================
W, H = 1920, 1080
FPS = 60
DURATION = 30.0
TOTAL_FRAMES = int(FPS * DURATION)  # 1800 frames (30.0s)

# Luxury Gold & Obsidian Full-Stack Palette (RGB uint8)
C_BLACK     = (8, 9, 14)         # #08090E Deep Obsidian Void
C_OCEAN     = (10, 13, 20)       # #0A0D14 Cartographic Ocean Dark
C_LAND      = (19, 24, 36)       # #131824 Continent Landmass Fill
C_LAND_LINE = (52, 62, 88)       # #343E58 Coastline & Contour Border
C_DARK      = (16, 19, 29)       # #10131D Dark Card Slate
C_GRAY      = (42, 48, 66)       # #2A3042 Grid Hairline
C_MUTED     = (155, 162, 180)    # #9BA2B4 Clean Silver Subtitle
C_WHITE     = (246, 244, 238)    # #F6F4EE Platinum Off-White
C_GOLD      = (255, 186, 12)     # #FFBA0C Royal Cyber Gold (Primary Accent)
C_CRIMSON   = (255, 64, 32)      # #FF4020 High-Energy Amber/Crimson
C_COBALT    = (24, 98, 255)      # #1862FF Enterprise Tech Blue
C_CYAN      = (0, 229, 255)      # #00E5FF Cyber Cyan

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts") if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")) else "/home/user/assets/fonts"

# ==============================================================================
# EASING & MATH UTILITIES
# ==============================================================================
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))

def ease_out_expo(t):
    t = clamp(t)
    return 1.0 if t >= 1.0 else 1.0 - (2.0 ** (-10.0 * t))

def ease_out_cubic(t):
    t = clamp(t)
    return 1.0 - ((1.0 - t) ** 3)

def ease_in_out_cubic(t):
    t = clamp(t)
    return 4.0 * t * t * t if t < 0.5 else 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0

def ease_spring(t, damping=6.8, freq=11.0):
    t = clamp(t)
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return 1.0 - math.exp(-damping * t) * math.cos(freq * t)

# ==============================================================================
# FAST CACHED TYPOGRAPHY ENGINE
# ==============================================================================
class TextRenderer:
    def __init__(self):
        self.font_cache = {}
        self.sprite_cache = {}

    def get_font(self, family, size, weight=700):
        key = (family, size, weight)
        if key not in self.font_cache:
            path = os.path.join(FONT_DIR, family)
            font = ImageFont.truetype(path, size)
            if family in ("SpaceGrotesk.ttf", "Syne.ttf", "JetBrainsMono.ttf"):
                try:
                    font.set_variation_by_axes([weight])
                except Exception:
                    pass
            elif family == "Inter.ttf":
                try:
                    font.set_variation_by_axes([28, weight])
                except Exception:
                    pass
            self.font_cache[key] = font
        return self.font_cache[key]

    def get_sprite(self, text, family, size, color, weight=700, pad=12):
        key = (text, family, size, color, weight)
        if key in self.sprite_cache:
            return self.sprite_cache[key]

        font = self.get_font(family, size, weight)
        dummy = Image.new("L", (1, 1), 0)
        d = ImageDraw.Draw(dummy)
        bbox = d.textbbox((0, 0), text, font=font)
        tw = max(1, bbox[2] - bbox[0] + pad * 2)
        th = max(1, bbox[3] - bbox[1] + pad * 2)

        mask_img = Image.new("L", (tw, th), 0)
        dm = ImageDraw.Draw(mask_img)
        dm.text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=255)
        alpha = np.array(mask_img, dtype=np.uint8)

        ys, xs = np.nonzero(alpha)
        if len(xs) > 0:
            x0, x1 = xs.min(), xs.max() + 1
            y0, y1 = ys.min(), ys.max() + 1
            alpha = alpha[y0:y1, x0:x1]

        sprite = (alpha, color)
        if len(self.sprite_cache) < 1500:
            self.sprite_cache[key] = sprite
        return sprite

    def draw(self, canvas, text, x, y, family="ArchivoBlack.ttf", size=64, color=C_WHITE,
             weight=700, align="left", valign="top", opacity=1.0, rgb_split=0, slice_offset=0.0):
        if not text or opacity <= 0.01:
            return (0, 0)
        alpha, col = self.get_sprite(text, family, size, color, weight)
        sh, sw = alpha.shape
        if align == "center":
            x = int(x - sw // 2)
        elif align == "right":
            x = int(x - sw)
        else:
            x = int(x)

        if valign == "center":
            y = int(y - sh // 2)
        elif valign == "bottom":
            y = int(y - sh)
        else:
            y = int(y)

        if abs(slice_offset) > 0.5:
            n_bands = 3
            band_h = max(1, sh // n_bands)
            for b in range(n_bands):
                by0 = b * band_h
                by1 = sh if b == n_bands - 1 else (b + 1) * band_h
                shift = int(slice_offset * (b - 1))
                self._blit_alpha(canvas, alpha[by0:by1, :], col, x + shift, y + by0, opacity)
            return (sw, sh)

        if rgb_split > 0:
            self._blit_channel(canvas, alpha, 0, C_CRIMSON[0], x - rgb_split, y, opacity * 0.85)
            self._blit_channel(canvas, alpha, 2, C_CYAN[2], x + rgb_split, y, opacity * 0.85)

        self._blit_alpha(canvas, alpha, col, x, y, opacity)
        return (sw, sh)

    def _blit_alpha(self, canvas, alpha, color, x, y, opacity=1.0):
        sh, sw = alpha.shape
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(canvas.shape[1], x + sw)
        y1 = min(canvas.shape[0], y + sh)
        if x0 >= x1 or y0 >= y1:
            return
        sx0, sy0 = x0 - x, y0 - y
        sx1, sy1 = sx0 + (x1 - x0), sy0 + (y1 - y0)

        a_patch = alpha[sy0:sy1, sx0:sx1].astype(np.float32) * (opacity / 255.0)
        a_3 = a_patch[:, :, None]
        roi = canvas[y0:y1, x0:x1].astype(np.float32)
        c_arr = np.array(color, dtype=np.float32)[None, None, :]
        canvas[y0:y1, x0:x1] = (roi * (1.0 - a_3) + c_arr * a_3).astype(np.uint8)

    def _blit_channel(self, canvas, alpha, ch_idx, ch_val, x, y, opacity=1.0):
        sh, sw = alpha.shape
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(canvas.shape[1], x + sw)
        y1 = min(canvas.shape[0], y + sh)
        if x0 >= x1 or y0 >= y1:
            return
        sx0, sy0 = x0 - x, y0 - y
        sx1, sy1 = sx0 + (x1 - x0), sy0 + (y1 - y0)
        a_patch = alpha[sy0:sy1, sx0:sx1].astype(np.float32) * (opacity / 255.0)
        roi_ch = canvas[y0:y1, x0:x1, ch_idx].astype(np.float32)
        canvas[y0:y1, x0:x1, ch_idx] = (roi_ch * (1.0 - a_patch) + ch_val * a_patch).astype(np.uint8)


TXT = TextRenderer()

# ==============================================================================
# CLEAN CARTOGRAPHIC WORLD & TERRITORY MAP BASE (NO CLUTTER TEXT)
# ==============================================================================
def build_cartographic_base_map():
    """Creates a clean Luxury Gold & Obsidian Cartographic World/Tech Terrain Map without coordinate clutter."""
    base = np.zeros((H, W, 3), dtype=np.uint8)
    base[:] = C_OCEAN

    mx, my = 48, 42
    continents = [
        # West Continent (Frontend Territory)
        [(95, 165), (260, 125), (490, 145), (660, 205), (750, 320), (700, 490),
         (570, 575), (500, 700), (620, 790), (540, 945), (340, 955), (205, 835),
         (235, 650), (125, 515), (85, 340)],
        # Central Command Island (JAVA IT HQ)
        [(820, 355), (960, 305), (1100, 355), (1145, 495), (1085, 650),
         (960, 700), (835, 640), (785, 495)],
        # East Continent (Backend, DB & Cloud Territory)
        [(1185, 145), (1460, 125), (1735, 170), (1835, 310), (1805, 530),
         (1690, 645), (1785, 795), (1665, 950), (1380, 945), (1235, 830),
         (1310, 660), (1205, 525), (1155, 320)],
        # Southern Island
        [(760, 805), (920, 775), (1085, 825), (1035, 950), (810, 945)],
    ]

    land_mask = np.zeros((H, W), dtype=np.uint8)
    for poly in continents:
        pts = np.array(poly, dtype=np.int32)
        cv2.fillPoly(base, [pts], C_LAND, cv2.LINE_AA)
        cv2.fillPoly(land_mask, [pts], 255)
        cv2.polylines(base, [pts], True, C_LAND_LINE, 2, cv2.LINE_AA)

    # Subtle dot-matrix texture on landmasses
    for y in range(my + 20, H - my - 20, 24):
        for x in range(mx + 20, W - mx - 20, 24):
            if land_mask[y, x] > 0:
                cv2.circle(base, (x, y), 2, (36, 44, 66), -1)
            elif (x + y) % 48 == 0:
                cv2.circle(base, (x, y), 1, (18, 22, 34), -1)

    # Topographic Elevation Contour Rings
    contours = [
        (410, 360, 240, 150, -15), (410, 360, 160, 95, -15),
        (420, 760, 170, 110, 20),  (960, 500, 190, 140, 0),
        (1490, 350, 260, 155, 12), (1490, 350, 175, 100, 12),
        (1520, 770, 195, 115, -18)
    ]
    for cx, cy, rx, ry, ang in contours:
        cv2.ellipse(base, (cx, cy), (rx, ry), ang, 0, 360, (34, 42, 64), 1, cv2.LINE_AA)

    # Clean, unlabeled map grid lines
    for col in range(1, 8):
        gx = mx + int((W - 2 * mx) * (col / 8.0))
        cv2.line(base, (gx, my), (gx, H - my), (22, 27, 40), 1)
    for row in range(1, 5):
        gy = my + int((H - 2 * my) * (row / 5.0))
        cv2.line(base, (mx, gy), (W - mx, gy), (22, 27, 40), 1)

    cv2.rectangle(base, (mx, my), (W - mx, H - my), C_GRAY, 2)
    return base

CARTO_BASE = build_cartographic_base_map()

# ==============================================================================
# GEOMETRIC & LOCATION PIN DRAWING HELPERS
# ==============================================================================
def draw_crosshair(canvas, x, y, size=10, color=C_GOLD, thickness=1):
    x, y = int(x), int(y)
    cv2.line(canvas, (x - size, y), (x + size, y), color, thickness, cv2.LINE_AA)
    cv2.line(canvas, (x, y - size), (x, y + size), color, thickness, cv2.LINE_AA)

def draw_compass_rose(canvas, cx, cy, radius=42, rot_deg=0.0):
    cv2.circle(canvas, (cx, cy), radius, C_GRAY, 1, cv2.LINE_AA)
    cv2.circle(canvas, (cx, cy), int(radius * 0.72), C_GRAY, 1, cv2.LINE_AA)
    for i in range(4):
        a = math.radians(i * 90 - 90 + rot_deg)
        x1 = int(cx + math.cos(a) * (radius - 8))
        y1 = int(cy + math.sin(a) * (radius - 8))
        col = C_GOLD if i == 0 else C_MUTED
        cv2.line(canvas, (cx, cy), (x1, y1), col, 2 if i == 0 else 1, cv2.LINE_AA)

def draw_location_pin(canvas, px, py, title, subtitle, category_tag, pin_color=C_GOLD,
                      appear_prog=1.0, active_pulse=0.0, card_side="right", is_hq=False):
    """
    Draws an authentic Teardrop Location Pin + Pulsing Ground Ring + Clean Skill Info Card.
    """
    if appear_prog <= 0.02:
        return
    scale = ease_spring(appear_prog, damping=6.2, freq=11.0)
    px, py = int(px), int(py)

    # 1. Ground Radar Ring lying flat on map surface
    ring_r = int((28 + 22 * active_pulse) * min(1.2, scale))
    cv2.ellipse(canvas, (px, py), (ring_r, int(ring_r * 0.52)), 0, 0, 360, pin_color, 2, cv2.LINE_AA)
    cv2.ellipse(canvas, (px, py), (int(ring_r * 0.55), int(ring_r * 0.28)), 0, 0, 360, C_WHITE, 1, cv2.LINE_AA)
    cv2.circle(canvas, (px, py), 4, C_WHITE, -1, cv2.LINE_AA)

    # 2. Classic Teardrop Map Location Pin Icon
    pin_h = int((52 if is_hq else 42) * scale)
    head_r = int((23 if is_hq else 18) * scale)
    head_cy = py - pin_h
    if head_r >= 4:
        cone_pts = np.array([
            [px, py],
            [px - int(head_r * 0.88), head_cy + int(head_r * 0.38)],
            [px + int(head_r * 0.88), head_cy + int(head_r * 0.38)]
        ], dtype=np.int32)
        cv2.fillPoly(canvas, [cone_pts], pin_color, cv2.LINE_AA)
        cv2.circle(canvas, (px, head_cy), head_r, pin_color, -1, cv2.LINE_AA)
        cv2.circle(canvas, (px, head_cy), head_r, C_WHITE, 2, cv2.LINE_AA)
        cv2.circle(canvas, (px, head_cy), int(head_r * 0.42), C_BLACK, -1, cv2.LINE_AA)
        if is_hq:
            cv2.circle(canvas, (px, head_cy), int(head_r * 0.20), C_GOLD, -1, cv2.LINE_AA)

    # 3. Clean Floating Location Callout Card
    if appear_prog > 0.25:
        card_p = ease_out_expo((appear_prog - 0.25) / 0.75)
        cw = 365 if not is_hq else 410
        ch = 90 if not is_hq else 100
        cw_curr = int(cw * card_p)
        if cw_curr < 30:
            return

        if card_side == "right":
            cx0 = px + 28
            cy0 = head_cy - ch // 2
        elif card_side == "left":
            cx0 = px - 28 - cw_curr
            cy0 = head_cy - ch // 2
        elif card_side == "top":
            cx0 = px - cw_curr // 2
            cy0 = head_cy - head_r - ch - 14
        else:
            cx0 = px - cw_curr // 2
            cy0 = py + 20

        cx0 = max(64, min(W - 64 - cw_curr, cx0))
        cy0 = max(56, min(H - 56 - ch, cy0))

        cv2.line(canvas, (px, head_cy), (cx0 if card_side == "right" else cx0 + cw_curr, cy0 + ch // 2),
                 pin_color, 2, cv2.LINE_AA)

        cv2.rectangle(canvas, (cx0, cy0), (cx0 + cw_curr, cy0 + ch), C_DARK, -1)
        cv2.rectangle(canvas, (cx0, cy0), (cx0 + cw_curr, cy0 + ch), pin_color if active_pulse > 0.2 else C_GRAY, 2)
        cv2.rectangle(canvas, (cx0, cy0), (cx0 + 8, cy0 + ch), pin_color, -1)

        if card_p > 0.65:
            TXT.draw(canvas, category_tag, cx0 + 20, cy0 + 11, "JetBrainsMono.ttf", 14, pin_color, weight=700)
            TXT.draw(canvas, title, cx0 + 20, cy0 + 31, "ArchivoBlack.ttf", 27 if not is_hq else 30, C_WHITE)
            TXT.draw(canvas, subtitle, cx0 + 20, cy0 + 64, "SpaceGrotesk.ttf", 16, C_MUTED, weight=600)

def draw_gps_route_segment(canvas, p1, p2, progress=1.0, color=C_GOLD, thickness=3):
    if progress <= 0.0:
        return
    p = clamp(progress)
    x1, y1 = p1
    x2, y2 = p2
    curr_x = int(x1 + (x2 - x1) * p)
    curr_y = int(y1 + (y2 - y1) * p)

    dist = math.hypot(curr_x - x1, curr_y - y1)
    n_dashes = max(2, int(dist // 18))
    for i in range(n_dashes):
        t0 = i / n_dashes
        t1 = min(1.0, (i + 0.55) / n_dashes)
        dx0 = int(x1 + (curr_x - x1) * t0)
        dy0 = int(y1 + (curr_y - y1) * t0)
        dx1 = int(x1 + (curr_x - x1) * t1)
        dy1 = int(y1 + (curr_y - y1) * t1)
        cv2.line(canvas, (dx0, dy0), (dx1, dy1), color, thickness, cv2.LINE_AA)

    if 0.02 < p < 0.99:
        cv2.circle(canvas, (curr_x, curr_y), 11, color, 2, cv2.LINE_AA)
        cv2.circle(canvas, (curr_x, curr_y), 5, C_WHITE, -1, cv2.LINE_AA)
        draw_crosshair(canvas, curr_x, curr_y, size=18, color=C_WHITE, thickness=1)

def draw_java_it_emblem(canvas, cx, cy, size, rot_deg=0.0, progress=1.0):
    s = int(size * ease_spring(progress, damping=6.0, freq=12.0))
    if s < 5:
        return
    ang = math.radians(rot_deg)
    pts_outer = []
    for i in range(4):
        a = ang + i * (math.pi / 2.0) + math.pi / 4.0
        pts_outer.append([int(cx + math.cos(a) * s), int(cy + math.sin(a) * s)])
    pts_outer = np.array(pts_outer, dtype=np.int32)
    cv2.fillPoly(canvas, [pts_outer], C_DARK, cv2.LINE_AA)
    cv2.polylines(canvas, [pts_outer], True, C_GOLD, 3, cv2.LINE_AA)

    s_in = int(s * 0.88)
    pts_in = []
    for i in range(4):
        a = ang + i * (math.pi / 2.0) + math.pi / 4.0
        pts_in.append([int(cx + math.cos(a) * s_in), int(cy + math.sin(a) * s_in)])
    cv2.polylines(canvas, [np.array(pts_in, dtype=np.int32)], True, C_GRAY, 1, cv2.LINE_AA)

    x_l = cx - int(s * 0.50)
    y_t = cy - int(s * 0.48)
    y_b = cy + int(s * 0.48)
    w_p = int(s * 0.20)
    cv2.rectangle(canvas, (x_l, y_t), (x_l + w_p, y_b), C_CRIMSON, -1, cv2.LINE_AA)

    x_r = cx + int(s * 0.30)
    cv2.rectangle(canvas, (x_r, y_t), (x_r + w_p, y_b), C_GOLD, -1, cv2.LINE_AA)
    cv2.rectangle(canvas, (cx - int(s * 0.06), y_b - int(s * 0.16)), (x_r + w_p, y_b), C_GOLD, -1, cv2.LINE_AA)

    v_pts = np.array([
        [x_l + w_p, y_t],
        [cx, cy + int(s * 0.08)],
        [x_r, y_t],
        [x_r, y_t + int(s * 0.24)],
        [cx, cy + int(s * 0.30)],
        [x_l + w_p, y_t + int(s * 0.24)]
    ], dtype=np.int32)
    cv2.fillPoly(canvas, [v_pts], C_WHITE, cv2.LINE_AA)
    cv2.circle(canvas, (cx, cy - int(s * 0.22)), max(4, int(s * 0.075)), C_GOLD, -1, cv2.LINE_AA)


# ==============================================================================
# SKILL MAP DATA (CLEAN TITLES & SUBTITLES — NO COORDINATE CLUTTER)
# ==============================================================================
FRONTEND_LOCATIONS = [
    (210, 265, "HTML5 & CSS3",      "RESPONSIVE WEB STRUCTURE",  "FRONTEND // 01", "right"),
    (780, 235, "TAILWIND & SASS",   "MODERN UI DESIGN SYSTEMS",  "FRONTEND // 02", "right"),
    (1360,270, "JAVASCRIPT ES6+",   "DYNAMIC CLIENT ENGINE",     "FRONTEND // 03", "right"),
    (1340,565, "TYPESCRIPT",        "TYPE-SAFE ARCHITECTURE",    "FRONTEND // 04", "right"),
    (770, 555, "REACT.JS & VUE.JS", "COMPONENT UI FRAMEWORKS",   "FRONTEND // 05", "right"),
    (230, 815, "NEXT.JS",           "FULL-STACK REACT FRAMEWORK","FRONTEND // 06", "right"),
]

BACKEND_LOCATIONS = [
    (210, 265, "NODE.JS & EXPRESS", "HIGH-SPEED ASYNC BACKEND",  "BACKEND // 01",  "right"),
    (780, 235, "PYTHON & DJANGO",   "AI & SCALABLE WEB CORE",    "BACKEND // 02",  "right"),
    (1360,270, "PHP & LARAVEL",     "FULL-STACK WEB ARTISAN",    "BACKEND // 03",  "right"),
    (1340,565, "JAVA & SPRING",     "ENTERPRISE MICROSERVICES",  "BACKEND // 04",  "right"),
    (770, 555, "SQL • PG • MONGO",  "DATABASE ARCHITECTURE",     "DATABASE // 05", "right"),
    (230, 815, "DOCKER • AWS • API","CLOUD, DEVOPS & GRAPHQL",   "CLOUD // 06",    "right"),
]

GLOBAL_SKILL_NODES = [
    # West Wing (6 Frontend Skills)
    (195, 215, "HTML5 & CSS3",      "FRONTEND", C_GOLD,    "right"),
    (255, 345, "TAILWIND & SASS",   "FRONTEND", C_GOLD,    "right"),
    (185, 475, "JAVASCRIPT ES6+",   "FRONTEND", C_GOLD,    "right"),
    (265, 605, "TYPESCRIPT",        "FRONTEND", C_GOLD,    "right"),
    (195, 735, "REACT.JS & VUE.JS", "FRONTEND", C_GOLD,    "right"),
    (275, 865, "NEXT.JS",           "FRONTEND", C_GOLD,    "right"),
    # East Wing (6 Backend, DB & Cloud Skills)
    (1725, 215, "NODE.JS & EXPRESS","BACKEND",  C_CRIMSON, "left"),
    (1665, 345, "PYTHON & DJANGO",  "BACKEND",  C_CRIMSON, "left"),
    (1735, 475, "PHP & LARAVEL",    "BACKEND",  C_CRIMSON, "left"),
    (1655, 605, "JAVA & SPRING",    "BACKEND",  C_CRIMSON, "left"),
    (1725, 735, "SQL & MONGODB",    "DATABASE", C_CYAN,    "left"),
    (1645, 865, "DOCKER & AWS",     "CLOUD",    C_CYAN,    "left"),
]


# ==============================================================================
# 6 CLEAN, UNHURRIED SCENES ACROSS 30.0 SECONDS (1800 FRAMES @ 60 FPS)
# ==============================================================================

def render_scene_1(canvas, f):
    """SCENE 01 (Frames 0-239 | 0.0s-4.0s): CLEAN BRAND & ARCHITECT INTRO"""
    canvas[:] = C_BLACK
    sec_step = min(3, f // 60)
    step_f = (f % 60) / 60.0

    mx, my = 48, 42
    iw, ih = W - 2 * mx, H - 2 * my
    grid_prog = ease_out_cubic(min(1.0, f / 50.0))
    cv2.rectangle(canvas, (mx, my), (mx + int(iw * grid_prog), my + int(ih * grid_prog)), C_GRAY, 2)
    cx_mid = W // 2
    cv2.line(canvas, (cx_mid, my), (cx_mid, my + int(ih * grid_prog)), C_GRAY, 2)

    # Left Monolith: Clean Brand Words instead of technical countdown numbers
    cards = [
        ("JAVA IT",   " PREMIER IT INSTITUTION", C_GOLD,    C_BLACK),
        ("MUN2ASIR",  "LEAD FULL-STACK ARCHITECT", C_CRIMSON, C_WHITE),
        ("FRONTEND",  "MODERN INTERACTIVE WEB UI", C_COBALT,  C_WHITE),
        ("BACKEND",   "SCALABLE SERVER & CLOUD",   C_WHITE,   C_BLACK),
    ]
    main_w, sub_w, bg_c, fg_c = cards[sec_step]

    box_h = int(ih * ease_out_expo(min(1.0, (f + 12) / 36.0)))
    cv2.rectangle(canvas, (mx, my), (cx_mid - 12, my + box_h), bg_c, -1)

    slice_amt = (1.0 - ease_out_expo(step_f * 2.2)) * 40.0
    TXT.draw(canvas, main_w, (mx + cx_mid - 12) // 2, H // 2 - 25,
             "Anton.ttf", 175, fg_c, align="center", valign="center", slice_offset=slice_amt)
    TXT.draw(canvas, sub_w, (mx + cx_mid - 12) // 2, H // 2 + 115,
             "SpaceGrotesk.ttf", 28, fg_c, weight=700, align="center", valign="center")

    # Right Half: Central HQ Map Radar Preview
    rcx, rcy = (cx_mid + W - mx) // 2, H // 2 + 10
    for r_idx, rad in enumerate([230, 175, 115, 60]):
        ang_start = (f * (1.8 if r_idx % 2 == 0 else -2.2) + r_idx * 45) % 360
        col_arc = C_GOLD if r_idx == 0 else (C_CRIMSON if r_idx == 1 else C_WHITE)
        cv2.ellipse(canvas, (rcx, rcy), (rad, rad), 0, ang_start, ang_start + 220, col_arc, 3 if r_idx < 2 else 2, cv2.LINE_AA)
    draw_crosshair(canvas, rcx, rcy, size=245, color=C_GRAY, thickness=1)
    draw_location_pin(canvas, rcx, rcy + 10, "JAVA IT HQ", "MUN2ASIR // FULL-STACK DEV",
                      "HEADQUARTERS", pin_color=C_GOLD, appear_prog=min(1.0, f / 50.0),
                      active_pulse=(1.0 - step_f), card_side="bottom", is_hq=True)

    TXT.draw(canvas, "JAVA IT // BY MUN2ASIR", cx_mid + 44, my + 34, "ArchivoBlack.ttf", 38, C_WHITE)
    TXT.draw(canvas, "FULL-STACK WEB DEVELOPMENT SKILL MAP", cx_mid + 44, my + 86, "SpaceGrotesk.ttf", 24, C_GOLD, weight=700)

    if f >= 218:
        wp = ease_in_out_cubic((f - 218) / 21.0)
        n_blades = 6
        blade_w = W // n_blades + 220
        for b in range(n_blades):
            bx = int(b * (W / n_blades) - 100)
            curr_w = int(blade_w * wp)
            pts = np.array([[bx, 0], [bx + curr_w, 0], [bx + curr_w - 180, H], [bx - 180, H]], dtype=np.int32)
            cv2.fillPoly(canvas, [pts], C_WHITE if b % 2 == 0 else C_GOLD)


def render_scene_2(canvas, f):
    """SCENE 02 (Frames 240-509 | 4.0s-8.5s): CLEAN FULL-STACK MANIFESTO"""
    lf = f - 240
    canvas[:] = C_WHITE
    mx, my = 48, 42
    for col in range(1, 4):
        gx = mx + int((W - 2 * mx) * (col / 4.0))
        cv2.line(canvas, (gx, my), (gx, H - my), (218, 215, 206), 1)

    ticker_y_top = 42
    ticker_y_bot = H - 84
    cv2.rectangle(canvas, (mx, ticker_y_top), (W - mx, ticker_y_top + 42), C_BLACK, -1)
    cv2.rectangle(canvas, (mx, ticker_y_bot), (W - mx, ticker_y_bot + 42), C_CRIMSON, -1)

    scroll_x = int((lf * 4.5) % 1180)
    ticker_top_txt = "JAVA IT // MUN2ASIR // FRONTEND: HTML5 • CSS3 • TAILWIND • JAVASCRIPT • TYPESCRIPT • REACT • NEXT.JS • VUE // "
    ticker_bot_txt = "BACKEND & DATABASE: NODE.JS • EXPRESS • PYTHON • DJANGO • PHP • LARAVEL • JAVA • SPRING • POSTGRESQL • MONGODB • MYSQL // "
    top_strip = canvas[ticker_y_top:ticker_y_top + 42, mx + 6:W - mx - 6]
    bot_strip = canvas[ticker_y_bot:ticker_y_bot + 42, mx + 6:W - mx - 6]
    TXT.draw(top_strip, ticker_top_txt * 3, 4 - scroll_x, 11, "JetBrainsMono.ttf", 19, C_GOLD, weight=700)
    TXT.draw(bot_strip, ticker_bot_txt * 3, 4 - (1180 - scroll_x), 11, "JetBrainsMono.ttf", 19, C_WHITE, weight=700)

    tracks = [
        (0,   "JAVA IT // MUN2ASIR", 100, 210, C_BLACK,  None,      1),
        (38,  "FRONTEND & BACKEND",  312, 210, C_GOLD,   C_BLACK,  -1),
        (76,  "ALL WEB LANGUAGES",   524, 210, C_WHITE,  C_CRIMSON, 1),
        (114, "FULL-STACK MASTER.",  736, 210, C_BLACK,  None,     -1),
    ]

    for start_f, word, y_top, row_h, txt_col, bar_col, direction in tracks:
        if lf < start_f:
            continue
        p = ease_spring((lf - start_f) / 42.0, damping=7.0, freq=9.5)
        slide_offset = int((1.0 - p) * 1200 * direction)
        slice_amt = (1.0 - ease_out_expo((lf - start_f) / 28.0)) * 35.0 * direction

        if bar_col is not None:
            bar_w = int((W - 2 * mx) * ease_out_expo((lf - start_f) / 28.0))
            bx0 = mx if direction > 0 else (W - mx - bar_w)
            cv2.rectangle(canvas, (bx0, y_top), (bx0 + bar_w, y_top + row_h - 12), bar_col, -1)

        TXT.draw(canvas, word, W // 2 + slide_offset, y_top + (row_h - 12) // 2,
                 "ArchivoBlack.ttf", 122, txt_col, align="center", valign="center", slice_offset=slice_amt)


def render_scene_3(canvas, f):
    """
    SCENE 03 (Frames 510-899 | 8.5s-15.0s | 6.5 Seconds):
    CLEAN SKILL MAP PART 1 — FRONTEND TERRITORY (6 SKILL LOCATIONS)
    """
    lf = f - 510
    np.copyto(canvas, CARTO_BASE)

    mx, my = 48, 42
    cv2.rectangle(canvas, (mx, my), (W - mx, my + 78), C_DARK, -1)
    cv2.line(canvas, (mx, my + 78), (W - mx, my + 78), C_GOLD, 2)
    cv2.rectangle(canvas, (mx, my), (mx + 14, my + 78), C_GOLD, -1)
    TXT.draw(canvas, "JAVA IT // FRONTEND SKILL MAP", mx + 34, my + 39,
             "ArchivoBlack.ttf", 36, C_WHITE, valign="center")
    TXT.draw(canvas, "MUN2ASIR // FULL-STACK DEVELOPER", W - mx - 28, my + 39,
             "SpaceGrotesk.ttf", 24, C_GOLD, weight=700, align="right", valign="center")

    radar_x = mx + int(((lf * 4.5) % (W - 2 * mx)))
    cv2.line(canvas, (radar_x, my + 80), (radar_x, H - my), (45, 42, 22), 1)
    draw_compass_rose(canvas, W - 125, H - 125, radius=42, rot_deg=lf * 0.25)

    frames_per_loc = 52.0
    for i in range(len(FRONTEND_LOCATIONS) - 1):
        seg_start = i * frames_per_loc + 12
        seg_prog = (lf - seg_start) / (frames_per_loc * 0.85)
        p1 = (FRONTEND_LOCATIONS[i][0], FRONTEND_LOCATIONS[i][1])
        p2 = (FRONTEND_LOCATIONS[i+1][0], FRONTEND_LOCATIONS[i+1][1])
        draw_gps_route_segment(canvas, p1, p2, progress=seg_prog, color=C_GOLD, thickness=3)

    for i, (px, py, title, subtitle, cat_tag, side) in enumerate(FRONTEND_LOCATIONS):
        loc_start = i * frames_per_loc
        appear_p = (lf - loc_start) / 34.0
        is_current = (0 <= lf - loc_start < frames_per_loc * 1.2)
        pulse = 0.85 * abs(math.sin(lf * 0.15)) if is_current else 0.25 * abs(math.sin(lf * 0.08 + i))
        pin_col = C_GOLD if i % 2 == 0 else C_CRIMSON
        draw_location_pin(canvas, px, py, title, subtitle, cat_tag,
                          pin_color=pin_col, appear_prog=appear_p,
                          active_pulse=pulse, card_side=side)


def render_scene_4(canvas, f):
    """
    SCENE 04 (Frames 900-1289 | 15.0s-21.5s | 6.5 Seconds):
    CLEAN SKILL MAP PART 2 — BACKEND, DATABASE & CLOUD TERRITORY (6 SKILL LOCATIONS)
    """
    lf = f - 900
    np.copyto(canvas, CARTO_BASE)

    mx, my = 48, 42
    cv2.rectangle(canvas, (mx, my), (W - mx, my + 78), C_DARK, -1)
    cv2.line(canvas, (mx, my + 78), (W - mx, my + 78), C_CRIMSON, 2)
    cv2.rectangle(canvas, (mx, my), (mx + 14, my + 78), C_CRIMSON, -1)
    TXT.draw(canvas, "JAVA IT // BACKEND, DATABASE & CLOUD MAP", mx + 34, my + 39,
             "ArchivoBlack.ttf", 36, C_WHITE, valign="center")
    TXT.draw(canvas, "MUN2ASIR // FULL-STACK DEVELOPER", W - mx - 28, my + 39,
             "SpaceGrotesk.ttf", 24, C_GOLD, weight=700, align="right", valign="center")

    radar_y = my + 80 + int(((lf * 3.0) % (H - 2 * my - 80)))
    cv2.line(canvas, (mx, radar_y), (W - mx, radar_y), (45, 24, 24), 1)
    draw_compass_rose(canvas, W - 125, H - 125, radius=42, rot_deg=-lf * 0.25)

    frames_per_loc = 52.0
    for i in range(len(BACKEND_LOCATIONS) - 1):
        seg_start = i * frames_per_loc + 12
        seg_prog = (lf - seg_start) / (frames_per_loc * 0.85)
        p1 = (BACKEND_LOCATIONS[i][0], BACKEND_LOCATIONS[i][1])
        p2 = (BACKEND_LOCATIONS[i+1][0], BACKEND_LOCATIONS[i+1][1])
        draw_gps_route_segment(canvas, p1, p2, progress=seg_prog, color=C_CRIMSON, thickness=3)

    for i, (px, py, title, subtitle, cat_tag, side) in enumerate(BACKEND_LOCATIONS):
        loc_start = i * frames_per_loc
        appear_p = (lf - loc_start) / 34.0
        is_current = (0 <= lf - loc_start < frames_per_loc * 1.2)
        pulse = 0.85 * abs(math.sin(lf * 0.15)) if is_current else 0.25 * abs(math.sin(lf * 0.08 + i))
        pin_col = C_CRIMSON if i % 2 == 0 else C_GOLD
        draw_location_pin(canvas, px, py, title, subtitle, cat_tag,
                          pin_color=pin_col, appear_prog=appear_p,
                          active_pulse=pulse, card_side=side)


def render_scene_5(canvas, f):
    """
    SCENE 05 (Frames 1290-1559 | 21.5s-26.0s | 4.5 Seconds):
    CLEAN GLOBAL MASTER SKILL MAP — ALL 12 SKILL LOCATIONS CONNECTED TO 'JAVA IT HQ'
    """
    lf = f - 1290
    np.copyto(canvas, CARTO_BASE)

    mx, my = 48, 42
    cv2.rectangle(canvas, (mx, my), (W - mx, my + 74), C_DARK, -1)
    cv2.line(canvas, (mx, my + 74), (W - mx, my + 74), C_GOLD, 2)
    TXT.draw(canvas, "JAVA IT // COMPLETE FULL-STACK SKILL NETWORK", W // 2, my + 37,
             "ArchivoBlack.ttf", 34, C_GOLD, align="center", valign="center")

    hq_x, hq_y = W // 2, H // 2 + 20

    net_prog = ease_out_cubic(min(1.0, lf / 65.0))
    for i, (nx, ny, name, cat_tag, col, side) in enumerate(GLOBAL_SKILL_NODES):
        ex = int(nx + (hq_x - nx) * net_prog)
        ey = int(ny + (hq_y - ny) * net_prog)
        cv2.line(canvas, (nx, ny), (ex, ey), (65, 58, 32) if col == C_GOLD else (68, 34, 34), 2, cv2.LINE_AA)

        pkt_t = ((lf * 0.022 + i * 0.17) % 1.0) * net_prog
        px_pkt = int(nx + (hq_x - nx) * pkt_t)
        py_pkt = int(ny + (hq_y - ny) * pkt_t)
        cv2.circle(canvas, (px_pkt, py_pkt), 5, col, -1, cv2.LINE_AA)
        cv2.circle(canvas, (px_pkt, py_pkt), 9, C_WHITE, 1, cv2.LINE_AA)

        cv2.ellipse(canvas, (nx, ny), (20, 11), 0, 0, 360, col, 2, cv2.LINE_AA)
        pin_top_y = ny - 28
        cv2.line(canvas, (nx, ny), (nx, pin_top_y), C_WHITE, 2, cv2.LINE_AA)
        cv2.circle(canvas, (nx, pin_top_y), 11, col, -1, cv2.LINE_AA)
        cv2.circle(canvas, (nx, pin_top_y), 4, C_BLACK, -1, cv2.LINE_AA)

        bw, bh = 235, 50
        bx0 = nx + 18 if side == "right" else nx - 18 - bw
        by0 = pin_top_y - bh // 2
        cv2.rectangle(canvas, (bx0, by0), (bx0 + bw, by0 + bh), C_DARK, -1)
        cv2.rectangle(canvas, (bx0, by0), (bx0 + bw, by0 + bh), col, 2)
        TXT.draw(canvas, cat_tag, bx0 + 12, by0 + 6, "JetBrainsMono.ttf", 12, col, weight=700)
        TXT.draw(canvas, name, bx0 + 12, by0 + 23, "ArchivoBlack.ttf", 19, C_WHITE)

    hq_pulse = 0.5 + 0.5 * math.sin(lf * 0.14)
    cv2.circle(canvas, (hq_x, hq_y), int(115 + 15 * hq_pulse), C_GOLD, 2, cv2.LINE_AA)
    cv2.circle(canvas, (hq_x, hq_y), int(75 + 8 * hq_pulse), C_CRIMSON, 2, cv2.LINE_AA)
    draw_location_pin(canvas, hq_x, hq_y, "JAVA IT // HQ", "MUN2ASIR // FULL-STACK ARCHITECT",
                      "CENTRAL COMMAND", pin_color=C_GOLD,
                      appear_prog=min(1.0, lf / 30.0), active_pulse=hq_pulse,
                      card_side="bottom", is_hq=True)


def render_scene_6(canvas, f):
    """SCENE 06 (Frames 1560-1799 | 26.0s-30.0s | 4.0 Seconds): CLEAN GRAND FINALE LOGO REVEAL"""
    lf = f - 1560
    canvas[:] = C_BLACK

    shake_x = int(math.sin(lf * 2.5) * 14 * math.exp(-lf * 0.20)) if lf < 20 else 0
    shake_y = int(math.cos(lf * 2.9) * 10 * math.exp(-lf * 0.20)) if lf < 20 else 0

    mx, my = 48, 42
    cv2.rectangle(canvas, (mx, my), (W - mx, H - my), C_GRAY, 1)
    for col in range(1, 4):
        cx_g = mx + int((W - 2 * mx) * (col / 4.0))
        cv2.line(canvas, (cx_g, my), (cx_g, H - my), (22, 26, 38), 1)
    for gx in [mx, W // 2, W - mx]:
        for gy in [my, H // 2, H - my]:
            draw_crosshair(canvas, gx, gy, size=8, color=C_GOLD, thickness=1)

    cx, cy = W // 2 + shake_x, H // 2 - 45 + shake_y

    if lf < 75:
        sp1 = ease_out_expo(lf / 65.0)
        sp2 = ease_out_expo(max(0.0, (lf - 8) / 65.0))
        r1 = int(sp1 * 1150)
        r2 = int(sp2 * 920)
        th1 = max(1, int(16 * (1.0 - sp1)))
        th2 = max(1, int(10 * (1.0 - sp2)))
        cv2.circle(canvas, (cx, cy), r1, C_GOLD, th1, cv2.LINE_AA)
        if r2 > 5:
            cv2.circle(canvas, (cx, cy), r2, C_CRIMSON, th2, cv2.LINE_AA)

    emblem_x = cx - 535
    emblem_y = cy + 18
    emblem_prog = min(1.0, lf / 45.0)
    draw_java_it_emblem(canvas, emblem_x, emblem_y, size=155,
                        rot_deg=(1.0 - ease_out_cubic(min(1.0, lf / 55.0))) * 90.0,
                        progress=emblem_prog)

    slice_amt = (1.0 - ease_out_expo(min(1.0, lf / 35.0))) * 55.0
    rgb_split = int(10 * math.exp(-lf * 0.12))

    TXT.draw(canvas, "JAVA IT", cx + 120, cy - 58, "ArchivoBlack.ttf", 162, C_WHITE,
             align="center", valign="center", rgb_split=rgb_split, slice_offset=slice_amt)

    if lf >= 10:
        s2_amt = (1.0 - ease_out_expo(min(1.0, (lf - 10) / 30.0))) * 45.0
        TXT.draw(canvas, "MUN2ASIR // FULL-STACK", cx + 120, cy + 56, "ArchivoBlack.ttf", 72, C_GOLD,
                 align="center", valign="center", rgb_split=rgb_split, slice_offset=-s2_amt)

    if lf >= 20:
        bar_p = ease_out_expo(min(1.0, (lf - 20) / 34.0))
        bx0 = cx - 340
        by0 = cy + 126
        bw = int(920 * bar_p)
        cv2.rectangle(canvas, (bx0, by0), (bx0 + bw, by0 + 50), C_GOLD, -1)
        cv2.rectangle(canvas, (bx0 - 20, by0), (bx0 - 6, by0 + 50), C_CRIMSON, -1)
        if bar_p > 0.45:
            TXT.draw(canvas, "FRONTEND • BACKEND • ALL FULL-STACK WEB LANGUAGES", bx0 + 460, by0 + 25,
                     "JetBrainsMono.ttf", 23, C_BLACK, weight=800, align="center", valign="center")

    if lf >= 34:
        mp = ease_out_cubic(min(1.0, (lf - 34) / 36.0))
        fy = H - 135
        cv2.line(canvas, (64, fy - 24), (64 + int((W - 128) * mp), fy - 24), C_GRAY, 2)
        cols_info = [
            (64,   "INSTITUTION",    "JAVA IT // MUN2ASIR",           C_WHITE),
            (540,  "FRONTEND",       "JS • TS • REACT • NEXT • VUE",  C_GOLD),
            (1090, "BACKEND & DB",   "NODE • PY • PHP • JAVA • SQL",  C_CRIMSON),
            (W-64, "SPECIALIZATION", "FULL-STACK WEB DEVELOPMENT",    C_WHITE),
        ]
        for x_pos, k_lbl, v_lbl, v_col in cols_info:
            al = "right" if x_pos == W - 64 else "left"
            TXT.draw(canvas, k_lbl, x_pos, fy, "JetBrainsMono.ttf", 16, C_MUTED, weight=600, align=al)
            TXT.draw(canvas, v_lbl, x_pos, fy + 26, "SpaceGrotesk.ttf", 23, v_col, weight=700, align=al)

    if lf >= 192:
        fade = 1.0 - ((lf - 192) / 47.0)
        canvas[:] = (canvas.astype(np.float32) * max(0.0, fade)).astype(np.uint8)


# ==============================================================================
# MAIN RENDER & FFMPEG PIPELINE (1800 FRAMES = 30.0 SECONDS)
# ==============================================================================
def main():
    t0 = time.time()
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    raw_mp4 = "java_it_30s_raw.mp4"
    final_mp4 = "java_it_mun2asir_30s_skill_map.mp4"
    audio_wav = "soundtrack_30s.wav"

    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{W}x{H}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
        "-i", "-",
        "-i", audio_wav,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "animation",
        "-crf", "16",
        "-threads", "2",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        raw_mp4
    ]

    print(f"Starting clean 30s 1080p60 render ({TOTAL_FRAMES} frames) -> {final_mp4} ...", flush=True)
    log_f = open("/tmp/ffmpeg_30s.log", "w")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=log_f)

    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    preview_frames = {
        90:   "map30s_scene1_boot.png",
        400:  "map30s_scene2_manifesto.png",
        830:  "map30s_scene3_frontend_map.png",
        1220: "map30s_scene4_backend_map.png",
        1420: "map30s_scene5_global_map.png",
        1640: "map30s_scene6_finale.png"
    }
    os.makedirs("previews", exist_ok=True)

    for f in range(TOTAL_FRAMES):
        if f < 240:
            render_scene_1(canvas, f)
        elif f < 510:
            render_scene_2(canvas, f)
        elif f < 900:
            render_scene_3(canvas, f)
        elif f < 1290:
            render_scene_4(canvas, f)
        elif f < 1560:
            render_scene_5(canvas, f)
        else:
            render_scene_6(canvas, f)

        if f in preview_frames:
            Image.fromarray(canvas).save(f"/home/user/previews/{preview_frames[f]}")

        proc.stdin.write(canvas.tobytes())

        if (f + 1) % 300 == 0 or f == TOTAL_FRAMES - 1:
            elapsed = time.time() - t0
            fps_rate = (f + 1) / max(0.001, elapsed)
            print(f"  Rendered {f+1}/{TOTAL_FRAMES} frames ({fps_rate:.1f} fps)...", flush=True)

    proc.stdin.close()
    ret = proc.wait()
    log_f.close()
    if ret != 0:
        with open("/tmp/ffmpeg_30s.log") as lf_in:
            print("FFmpeg error:", lf_in.read()[-1000:])
        sys.exit(1)

    subprocess.run([
        ffmpeg_exe, "-y", "-i", raw_mp4,
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "animation",
        "-crf", "20", "-x264-params", "rc-lookahead=10", "-threads", "2",
        "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
        final_mp4
    ], check=True, stderr=subprocess.DEVNULL)
    os.remove(raw_mp4)

    

    total_time = time.time() - t0
    size_mb = os.path.getsize(final_mp4) / (1024 * 1024)
    print(f"Complete in {total_time:.1f}s! Output: {final_mp4} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    main()
