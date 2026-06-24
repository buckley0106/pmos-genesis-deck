"""Deterministic OG image generator — neon cosmic card for each canon asset."""
from __future__ import annotations

import io
import hashlib
from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _seed_color(seed: str) -> tuple[int, int, int]:
    h = hashlib.sha256(seed.encode()).hexdigest()
    # bias towards neon hues
    return (int(h[0:2], 16) % 80, 200 + (int(h[2:4], 16) % 55), 220 + (int(h[4:6], 16) % 35))


def render_og(seed: str, rarity_tier: str, rarity_score: int, faction: str, species: str, ticker: str, asset_id: str) -> bytes:
    W, H = 1200, 630
    bg = (5, 5, 10)
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)

    # grid
    grid = (15, 20, 36)
    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill=grid, width=1)
    for y in range(0, H, 40):
        d.line([(0, y), (W, y)], fill=grid, width=1)

    # accent corner glow
    accent = _seed_color(seed)
    cyan = (0, 240, 255)
    magenta = (255, 0, 255)

    # frame
    d.rectangle([(40, 40), (W - 40, H - 40)], outline=cyan, width=2)
    d.rectangle([(48, 48), (W - 48, H - 48)], outline=(30, 60, 70), width=1)

    # corner ticks
    for (cx, cy) in [(40, 40), (W - 40, 40), (40, H - 40), (W - 40, H - 40)]:
        d.rectangle([(cx - 8, cy - 8), (cx + 8, cy + 8)], outline=magenta, width=2)

    # eyebrow
    f_eye = _font(22)
    d.text((72, 78), "PMOS • WMEU — CANON CERTIFICATE", fill=cyan, font=f_eye)

    # seed (h1)
    f_h1 = _font(72)
    d.text((72, 130), seed[:36], fill=(255, 255, 255), font=f_h1)

    # subtitle
    f_sub = _font(32)
    d.text((72, 230), f"{species} · {faction}", fill=accent, font=f_sub)

    # rarity badge
    f_badge = _font(54)
    badge_text = rarity_tier.upper()
    bbox = d.textbbox((0, 0), badge_text, font=f_badge)
    bw = bbox[2] - bbox[0]
    bh = bbox[3] - bbox[1]
    bx, by = 72, 320
    d.rectangle([(bx - 12, by - 8), (bx + bw + 12, by + bh + 14)], outline=magenta, width=3)
    d.text((bx, by), badge_text, fill=magenta, font=f_badge)
    d.text((bx, by + bh + 30), f"SCORE {rarity_score}", fill=cyan, font=_font(28))

    # ticker chip
    f_chip = _font(26)
    chip = f"  {ticker}  "
    cbbox = d.textbbox((0, 0), chip, font=f_chip)
    cw, ch = cbbox[2] - cbbox[0], cbbox[3] - cbbox[1]
    cx, cy = W - 72 - cw, 320
    d.rectangle([(cx - 6, cy - 6), (cx + cw + 6, cy + ch + 10)], outline=cyan, width=2)
    d.text((cx, cy), chip, fill=cyan, font=f_chip)

    # footer
    f_foot = _font(20)
    d.text((72, H - 92), "© 2026 PATRICK BUCKLEY · P.BUCK™ · PMOS™ · WMEU™", fill=(150, 160, 180), font=f_foot)
    d.text((72, H - 64), f"asset {asset_id[:24]}", fill=(80, 90, 110), font=f_foot)

    # signature line
    d.line([(72, H - 110), (W - 72, H - 110)], fill=cyan, width=1)

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
