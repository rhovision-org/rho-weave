"""Render the README motion study and its static storyboard."""

import argparse
from functools import cache
from math import atan2, cos, hypot, pi, sin
from pathlib import Path
from subprocess import check_output

from PIL import Image, ImageColor, ImageDraw, ImageFont


WIDTH, HEIGHT, SCALE, FPS = 768, 432, 2, 12


def mix(start, end, amount):
    start, end = ImageColor.getrgb(start), ImageColor.getrgb(end)
    return tuple(round(a + (b - a) * amount) for a, b in zip(start, end))


def ease(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


@cache
def font(family, size):
    path = check_output(["fc-match", "--format=%{file}", family], text=True)
    return ImageFont.truetype(path, round(size * SCALE))


class Canvas:
    def __init__(self, background):
        self.image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE), background)
        self.pen = ImageDraw.Draw(self.image)

    @staticmethod
    def coords(xy):
        return tuple(round(value * SCALE) for value in xy)

    def txt(self, value, x, y, size, color, family, anchor="lt"):
        self.pen.text(self.coords((x, y)), value, fill=color, font=font(family, size), anchor=anchor)

    def rule(self, points, color, width=1):
        self.pen.line([self.coords(point) for point in points], fill=color,
                      width=max(1, round(width * SCALE)), joint="curve")

    def rect(self, rect, fill=None, outline=None, width=1, radius=0):
        if radius:
            self.pen.rounded_rectangle(self.coords(rect), round(radius * SCALE), fill=fill,
                                       outline=outline, width=max(1, round(width * SCALE)))
        else:
            self.pen.rectangle(self.coords(rect), fill=fill, outline=outline,
                               width=max(1, round(width * SCALE)))

    def disk(self, x, y, radius, fill=None, outline=None, width=1):
        self.pen.ellipse(self.coords((x-radius, y-radius, x+radius, y+radius)),
                         fill=fill, outline=outline, width=max(1, round(width * SCALE)))

    def arc(self, x, y, radius, start, end, color, width=1):
        self.pen.arc(self.coords((x-radius, y-radius, x+radius, y+radius)), start, end,
                     fill=color, width=max(1, round(width * SCALE)))

    def polygon(self, points, fill):
        self.pen.polygon([self.coords(p) for p in points], fill=fill)

    def arrow(self, start, end, color, width=2, head=8):
        self.rule([start, end], color, width)
        x, y = end
        angle = atan2(y - start[1], x - start[0])
        arms = [(x - head*cos(angle + offset), y - head*sin(angle + offset))
                for offset in (-0.55, 0.55)]
        self.polygon([end, *arms], color)

    def dashed(self, start, end, color, width=1, dash=5, gap=6):
        dx, dy = end[0] - start[0], end[1] - start[1]
        distance = hypot(dx, dy)
        for offset in range(0, round(distance), dash + gap):
            stop = min(offset + dash, distance)
            self.rule([(start[0]+dx*offset/distance, start[1]+dy*offset/distance),
                       (start[0]+dx*stop/distance, start[1]+dy*stop/distance)], color, width)

    def finish(self):
        return self.image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def export(frame, length, stills):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    panels = [frame(t) for t in stills]
    storyboard = Image.new("RGB", (WIDTH, len(panels) * HEIGHT + (len(panels)-1)*6), "#24242d")
    for index, panel in enumerate(panels):
        storyboard.paste(panel, (0, index * (HEIGHT + 6)))
    storyboard.save(args.out / "overview.png", optimize=True)

    # Keep a stable palette across frames so text and stationary areas do not shimmer.
    palette = storyboard.quantize(colors=112, method=Image.Quantize.MEDIANCUT)
    frames = [frame(i / FPS).quantize(palette=palette, dither=Image.Dither.NONE)
              for i in range(round(length * FPS))]
    frames[0].save(args.out / "overview.gif", save_all=True, append_images=frames[1:],
                   duration=round(1000/FPS), loop=0, disposal=1, optimize=True)


PAPER = "#f7eade"
EDGE = "#caad9b"
INK = "#392742"
QUIET = "#705167"
ISSUED = "#533051"
BRASS = "#996648"
GREEN = "#336f61"
CREAM = "#fff8f0"
HEADING = "Noto Serif Display:style=Bold"
BODY = "Liberation Sans"
BOLD = "Liberation Sans:style=Bold"


def ticket(c, x, number, issued):
    y, width, bottom = 170, 126, 342
    c.rect((x+2, y+3, x+width+2, bottom+3), fill=EDGE, radius=10)
    c.rect((x, y, x+width, bottom), fill=ISSUED if issued else CREAM,
           outline=ISSUED if issued else EDGE, width=1.5, radius=10)
    text = CREAM if issued else INK
    c.txt(f"{number:02d}", x+width/2, y+25, 48, text, HEADING, "mt")
    c.dashed((x+10, y+102), (x+width-10, y+102), EDGE)
    for edge in (x, x+width):
        c.disk(edge, y+102, 6, PAPER)
    c.txt("ISSUED" if issued else "HELD", x+width/2, y+122, 23, text, BOLD, "mt")


def stamp(c, number, t):
    x = 36+(number-1)*144
    trace = ease(t)
    if trace < 1:
        c.rect((x-5-(1-trace)*10, 165, x+131+(1-trace)*10, 347),
               outline=mix(PAPER, GREEN, 1-trace), width=2, radius=14)


def frame(t):
    c = Canvas(PAPER)
    stage = 0 if t < 2.8 else 1 if t < 5.0 else 2
    revision = 2 + int(t >= 5.75) + int(t >= 6.88)
    issued = revision-1
    headings = ["A reply goes missing", "Read the actor first", "Finish what remains"]
    c.txt("Rho Weave", 35, 24, 22, QUIET, BOLD)
    c.txt(headings[stage], 32, 54, 46, INK, HEADING)
    c.rule([(35, 112), (733, 112)], EDGE)
    c.txt(f"Actor · revision {revision}", 36, 134, 25, INK, BOLD)

    for number in (1, 2, 3):
        ticket(c, 36+(number-1)*144, number, number <= issued)
    for number, instant in [(2, 5.75), (3, 6.88)]:
        if instant <= t < instant+0.65:
            stamp(c, number, (t-instant)/0.65)

    right = 487
    if stage == 0:
        c.dashed((right, 197), (726, 197), BRASS, 2, 5, 7)
        c.disk(726, 197, 11, PAPER, BRASS, 1.5)
        travel = ease((t-0.16)/1.10)
        if travel < 1:
            x = right+126*travel
            color = mix(ISSUED, PAPER, travel**3)
            c.rect((x, 178, x+70, 215), mix(CREAM, PAPER, travel), color, 2, 6)
            c.txt("reply", x+35, 187, 22, color, BOLD, "mt")
        elif t >= 1.22:
            c.rule([(628, 190),(642, 204)], BRASS, 2)
            c.rule([(628, 204),(642, 190)], BRASS, 2)
        c.txt("Waiting" if travel < 1 else "Reply lost", right, 241, 33, INK, HEADING)
        c.txt("Client is waiting", right, 285, 25, QUIET, BODY)
    elif stage == 1:
        c.arrow((727, 187), (488, 187), GREEN, 2, 11)
        p = ease((t-2.8)/1.05)
        if p < 1:
            c.disk(711-209*p, 187, 6, GREEN)
        c.txt("Controller reads", right, 220, 25, INK, BOLD)
        c.txt("1 issued", right, 253, 33, GREEN, HEADING)
        c.txt("2 held", right, 300, 31, QUIET, HEADING)
    else:
        c.txt("Clerk’s policy", right, 172, 25, QUIET, BOLD)
        c.txt("Issue #2", right, 219, 30, GREEN if issued >= 2 else INK, HEADING)
        c.txt("Issue #3", right, 263, 30, GREEN if issued >= 3 else INK, HEADING)
        c.txt("DONE" if issued == 3 else "Check revision", right, 316, 23, GREEN, BOLD)

    c.rule([(35, 375), (733, 375)], EDGE)
    if stage == 0:
        c.txt("The first ticket has already been issued.", 35, 397, 25, QUIET, BODY)
    else:
        c.txt("Manifest + goal", 35, 397, 25, INK, BOLD)
        c.arrow((224, 407), (280, 407), GREEN, 2, 9)
        c.txt("Rholang recovery controller", 298, 397, 25, INK, BOLD)
    return c.finish()


if __name__ == "__main__":
    export(frame, 9.3, (2.25, 4.1, 8.4))
