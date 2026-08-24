# -*- coding: utf-8 -*-
"""Line-icon set for the Caiman PRe deck.

Drawn on a 0..100 logical grid, rendered at 4x supersampling and downsampled,
white on transparent so each icon sits inside a coloured circle on the slide.
"""
import math
import os
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
os.makedirs(OUT, exist_ok=True)

SIZE = 256          # final px
S = 4               # supersample
C = SIZE * S        # canvas
K = C / 100.0       # logical -> canvas
W = 7.0             # default stroke, logical units
WHITE = (255, 255, 255, 255)


def px(v):
    return v * K


class Pen:
    def __init__(self, d):
        self.d = d

    def line(self, pts, w=W, cap=True):
        p = [(px(x), px(y)) for x, y in pts]
        wp = int(round(px(w)))
        self.d.line(p, fill=WHITE, width=wp, joint="curve")
        if cap:
            for x, y in p:
                r = wp / 2.0
                self.d.ellipse([x - r, y - r, x + r, y + r], fill=WHITE)

    def arc(self, cx, cy, r, a0, a1, w=W, cap=True):
        b = [px(cx - r), px(cy - r), px(cx + r), px(cy + r)]
        self.d.arc(b, a0, a1, fill=WHITE, width=int(round(px(w))))
        if cap:
            for a in (a0, a1):
                x = cx + r * math.cos(math.radians(a))
                y = cy + r * math.sin(math.radians(a))
                self.dot(x, y, w / 2.0)

    def circle(self, cx, cy, r, w=W):
        self.d.ellipse([px(cx - r), px(cy - r), px(cx + r), px(cy + r)],
                       outline=WHITE, width=int(round(px(w))))

    def dot(self, cx, cy, r):
        self.d.ellipse([px(cx - r), px(cy - r), px(cx + r), px(cy + r)], fill=WHITE)

    def rect(self, x0, y0, x1, y1, w=W, r=0):
        b = [px(x0), px(y0), px(x1), px(y1)]
        if r:
            self.d.rounded_rectangle(b, radius=px(r), outline=WHITE, width=int(round(px(w))))
        else:
            self.d.rectangle(b, outline=WHITE, width=int(round(px(w))))

    def frect(self, x0, y0, x1, y1, r=0):
        b = [px(x0), px(y0), px(x1), px(y1)]
        if r:
            self.d.rounded_rectangle(b, radius=px(r), fill=WHITE)
        else:
            self.d.rectangle(b, fill=WHITE)

    def poly(self, pts, w=W):
        p = [(px(x), px(y)) for x, y in pts] + [(px(pts[0][0]), px(pts[0][1]))]
        self.d.line(p, fill=WHITE, width=int(round(px(w))), joint="curve")
        for x, y in p:
            self.dot(x / K, y / K, w / 2.0)

    def fpoly(self, pts):
        self.d.polygon([(px(x), px(y)) for x, y in pts], fill=WHITE)


# ----------------------------------------------------------------- icons
def i_no_radio(p):
    """Radio waves, struck through: the physical lock."""
    for r in (14, 25, 36):
        p.arc(50, 68, r, 205, 335, 6.5, cap=False)
    p.dot(50, 68, 5)
    p.line([(20, 82), (80, 24)], 7.5)


def i_sub(p):
    """AUV hull with tower and thruster."""
    p.rect(20, 40, 74, 64, 6.5, r=12)
    p.line([(40, 40), (40, 28), (54, 28), (54, 40)], 6.5)
    p.line([(74, 52), (86, 52)], 6.5)
    p.line([(86, 40), (86, 64)], 6.5)
    p.dot(31, 52, 4)


def i_chip(p):
    """Microcontroller."""
    p.rect(28, 28, 72, 72, 6.5, r=5)
    p.rect(42, 42, 58, 58, 5)
    for t in (38, 50, 62):
        p.line([(t, 28), (t, 18)], 5.5)
        p.line([(t, 72), (t, 82)], 5.5)
        p.line([(28, t), (18, t)], 5.5)
        p.line([(72, t), (82, t)], 5.5)


def i_capacitor(p):
    """Decoupling capacitor, correctly to ground."""
    p.line([(14, 50), (40, 50)], 6.5)
    p.line([(40, 26), (40, 74)], 7.5)
    p.line([(58, 26), (58, 74)], 7.5)
    p.line([(58, 50), (84, 50)], 6.5)


def i_bolt(p):
    """Power rail."""
    p.fpoly([(58, 8), (28, 54), (46, 54), (40, 92), (72, 44), (52, 44)])


def i_ruler(p):
    """Design rules / tolerance."""
    p.rect(12, 36, 88, 64, 6.5, r=4)
    for x in (28, 44, 60, 76):
        p.line([(x, 36), (x, 48)], 5)


def i_alert(p):
    """Manufacturing review flag."""
    p.poly([(50, 16), (90, 84), (10, 84)], 7)
    p.line([(50, 42), (50, 62)], 7)
    p.dot(50, 73, 4.5)


def i_question(p):
    """The pivot."""
    p.arc(50, 38, 17, 180, 20, 7.5, cap=False)
    p.line([(66, 44), (52, 58), (50, 65)], 7.5)
    p.dot(50, 80, 5)


def i_network(p):
    """Fleet topology."""
    p.line([(24, 30), (76, 26)], 5.5)
    p.line([(24, 30), (50, 70)], 5.5)
    p.line([(76, 26), (50, 70)], 5.5)
    p.line([(50, 70), (82, 74)], 5.5)
    for x, y in ((24, 30), (76, 26), (50, 70), (82, 74)):
        p.dot(x, y, 8)


def i_monitor(p):
    """Supervision dashboard."""
    p.rect(12, 22, 88, 70, 6.5, r=5)
    p.line([(50, 70), (50, 84)], 6)
    p.line([(32, 84), (68, 84)], 6.5)
    p.line([(26, 40), (46, 40)], 5)
    p.line([(26, 53), (60, 53)], 5)


def i_lock(p):
    """Authenticated frame."""
    p.arc(50, 44, 18, 180, 360, 7)
    p.rect(26, 44, 74, 84, 6.5, r=6)
    p.dot(50, 62, 5.5)
    p.line([(50, 64), (50, 73)], 5.5)


def i_packet(p):
    """32-byte frame: header | payload | tag."""
    p.rect(8, 32, 92, 68, 6.5, r=4)
    p.line([(33, 32), (33, 68)], 5.5, cap=False)
    p.line([(50, 32), (50, 68)], 5.5, cap=False)


def i_two_chips(p):
    """HIL: two real processors."""
    p.rect(8, 34, 38, 66, 6, r=4)
    p.rect(62, 34, 92, 66, 6, r=4)
    p.line([(38, 50), (62, 50)], 5.5)
    p.dot(50, 50, 6)


def i_steps(p):
    """Levels of evidence."""
    p.line([(10, 84), (34, 84), (34, 62), (58, 62), (58, 40), (82, 40), (82, 18)], 6.5)


def i_arrow(p):
    """Next steps."""
    p.circle(50, 50, 36, 6.5)
    p.line([(34, 50), (64, 50)], 6.5)
    p.line([(52, 38), (64, 50), (52, 62)], 6.5)


def i_survey(p):
    """Bathymetric survey: boustrophedon transects inside a survey box."""
    p.rect(10, 20, 90, 86, 5.0, r=5)
    p.line([(26, 38), (74, 38), (74, 56), (26, 56), (26, 74), (74, 74)], 6.5)


def i_plume(p):
    """Plume or water-column tracking."""
    p.line([(28, 18), (21, 40), (33, 60), (26, 84)], 6.5)
    p.line([(50, 14), (43, 38), (55, 60), (48, 88)], 6.5)
    p.line([(72, 18), (65, 40), (77, 60), (70, 84)], 6.5)


def i_inspect(p):
    """Inspection of a submerged structure."""
    p.circle(42, 42, 25, 6.5)
    p.line([(60, 60), (86, 86)], 8.5)
    p.line([(32, 54), (32, 32), (54, 32)], 5.5)


def i_check(p):
    p.line([(22, 52), (42, 72), (78, 30)], 9)


def i_cross(p):
    p.line([(28, 28), (72, 72)], 9)
    p.line([(72, 28), (28, 72)], 9)


def i_tilde(p):
    p.arc(35, 50, 15, 180, 360, 8, cap=False)
    p.arc(65, 50, 15, 0, 180, 8, cap=False)


def i_calendar(p):
    """Timeline."""
    p.rect(12, 24, 88, 84, 6.5, r=6)
    p.line([(12, 44), (88, 44)], 6)
    p.line([(32, 14), (32, 32)], 6.5)
    p.line([(68, 14), (68, 32)], 6.5)
    p.dot(35, 60, 5)
    p.dot(50, 60, 5)
    p.dot(65, 60, 5)


ICONS = {
    "no_radio": i_no_radio, "sub": i_sub, "chip": i_chip, "capacitor": i_capacitor,
    "bolt": i_bolt, "ruler": i_ruler, "alert": i_alert, "question": i_question,
    "network": i_network, "monitor": i_monitor, "lock": i_lock, "packet": i_packet,
    "two_chips": i_two_chips, "steps": i_steps, "arrow": i_arrow, "check": i_check,
    "cross": i_cross, "tilde": i_tilde, "calendar": i_calendar,
    "survey": i_survey, "plume": i_plume, "inspect": i_inspect,
}

for name, fn in ICONS.items():
    img = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    fn(Pen(ImageDraw.Draw(img)))
    img.resize((SIZE, SIZE), Image.LANCZOS).save(os.path.join(OUT, name + ".png"))

print("wrote %d icons to %s" % (len(ICONS), OUT))
