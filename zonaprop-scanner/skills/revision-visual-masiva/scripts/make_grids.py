#!/usr/bin/env python3
"""
Crea montajes/grillas de contacto con thumbnails de propiedades.

Uso:
    python3 make_grids.py <metadata.json> <thumbs-dir> <output-dir> [--multi]

Sin --multi: 1 foto por propiedad, 50 por grilla (10x5). Thumbs como {idx:04d}.jpg
Con --multi: todas las fotos por propiedad en mosaico 4x2, 20 por grilla (5x4).
             Thumbs como {idx:04d}_00.jpg, {idx:04d}_01.jpg, etc.
"""
import json
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow no instalado. Ejecutar: pip install Pillow --break-system-packages")
    sys.exit(1)


def load_fonts():
    """Carga fuentes, con fallback a default."""
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return (
                    ImageFont.truetype(p, 10),
                    ImageFont.truetype(p, 9),
                )
            except Exception:
                continue
    default = ImageFont.load_default()
    return default, default


def make_label_text(idx, p):
    """Genera el texto del label."""
    precio = p.get("precio") or 0
    barrio = (p.get("barrio", "") or "")[:12]
    m2 = p.get("m2") or "?"
    amb = p.get("ambientes") or "?"
    diff = p.get("diff_vs_prom_general")
    diff_str = f"{diff:.0f}%" if diff is not None else ""

    line1 = f"#{idx} {barrio}"
    line2 = f"USD{precio / 1000:.0f}k {m2}m2 {amb}amb"
    return line1, line2, diff_str, diff


# ── Single-photo mode (original) ──────────────────────────────────────

SINGLE_THUMB_W = 200
SINGLE_THUMB_H = 150
SINGLE_COLS = 10
SINGLE_LABEL_H = 36
SINGLE_CELL_H = SINGLE_THUMB_H + SINGLE_LABEL_H
SINGLE_PER_PAGE = 50


def make_grid_single(props, start_idx, thumbs_dir, font, font_small):
    rows = (len(props) + SINGLE_COLS - 1) // SINGLE_COLS
    img_w = SINGLE_COLS * SINGLE_THUMB_W
    img_h = rows * SINGLE_CELL_H
    canvas = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(canvas)

    for i, p in enumerate(props):
        col = i % SINGLE_COLS
        row = i // SINGLE_COLS
        x = col * SINGLE_THUMB_W
        y = row * SINGLE_CELL_H
        idx = start_idx + i

        thumb_path = os.path.join(thumbs_dir, f"{idx:04d}.jpg")
        try:
            if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 100:
                thumb = Image.open(thumb_path)
                thumb = thumb.resize((SINGLE_THUMB_W, SINGLE_THUMB_H), Image.LANCZOS)
                canvas.paste(thumb, (x, y))
            else:
                draw.rectangle([x, y, x + SINGLE_THUMB_W, y + SINGLE_THUMB_H], fill="#ddd")
                draw.text((x + 10, y + 60), "Sin foto", fill="gray", font=font)
        except Exception:
            draw.rectangle([x, y, x + SINGLE_THUMB_W, y + SINGLE_THUMB_H], fill="#ddd")

        line1, line2, diff_str, diff = make_label_text(idx, p)
        draw.rectangle(
            [x, y + SINGLE_THUMB_H, x + SINGLE_THUMB_W, y + SINGLE_CELL_H], fill="#f0f0f0"
        )
        draw.text((x + 2, y + SINGLE_THUMB_H + 2), line1, fill="black", font=font_small)
        draw.text((x + 2, y + SINGLE_THUMB_H + 14), line2, fill="#333", font=font_small)
        if diff_str:
            color = "#d00" if diff and diff < -20 else "#666"
            draw.text((x + 2, y + SINGLE_THUMB_H + 25), diff_str, fill=color, font=font_small)

    return canvas


# ── Multi-photo mode ──────────────────────────────────────────────────

MULTI_COLS = 5          # properties per row
MULTI_PER_PAGE = 20     # properties per page (5 cols x 4 rows)
PHOTO_COLS = 4          # photos per row inside cell
PHOTO_ROWS = 2          # photo rows inside cell
MINI_W = 100            # each mini-thumb width
MINI_H = 75             # each mini-thumb height
CELL_W = PHOTO_COLS * MINI_W   # 400px
LABEL_H = 40
CELL_H = PHOTO_ROWS * MINI_H + LABEL_H  # 190px


def make_grid_multi(props, start_idx, thumbs_dir, font, font_small):
    rows = (len(props) + MULTI_COLS - 1) // MULTI_COLS
    img_w = MULTI_COLS * CELL_W
    img_h = rows * CELL_H
    canvas = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(canvas)

    for i, p in enumerate(props):
        col = i % MULTI_COLS
        row = i // MULTI_COLS
        x = col * CELL_W
        y = row * CELL_H
        idx = start_idx + i

        # Load all available photos for this property
        photos_area_h = PHOTO_ROWS * MINI_H
        draw.rectangle([x, y, x + CELL_W, y + photos_area_h], fill="#eee")

        for j in range(PHOTO_COLS * PHOTO_ROWS):
            thumb_path = os.path.join(thumbs_dir, f"{idx:04d}_{j:02d}.jpg")
            pc = j % PHOTO_COLS
            pr = j // PHOTO_COLS
            px = x + pc * MINI_W
            py = y + pr * MINI_H

            try:
                if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 100:
                    thumb = Image.open(thumb_path)
                    thumb = thumb.resize((MINI_W, MINI_H), Image.LANCZOS)
                    canvas.paste(thumb, (px, py))
            except Exception:
                pass

        # Label
        line1, line2, diff_str, diff = make_label_text(idx, p)
        draw.rectangle([x, y + photos_area_h, x + CELL_W, y + CELL_H], fill="#f0f0f0")
        draw.text((x + 4, y + photos_area_h + 3), line1, fill="black", font=font)
        draw.text((x + 4, y + photos_area_h + 15), line2, fill="#333", font=font_small)
        if diff_str:
            color = "#d00" if diff and diff < -20 else "#666"
            draw.text((x + 4, y + photos_area_h + 27), diff_str, fill=color, font=font_small)

        # Border between cells
        draw.rectangle([x, y, x + CELL_W, y + CELL_H], outline="#ccc", width=1)

    return canvas


def main():
    if len(sys.argv) < 4:
        print(f"Uso: {sys.argv[0]} <metadata.json> <thumbs-dir> <output-dir> [--multi]")
        sys.exit(1)

    metadata_path = sys.argv[1]
    thumbs_dir = sys.argv[2]
    output_dir = sys.argv[3]
    multi = "--multi" in sys.argv
    os.makedirs(output_dir, exist_ok=True)

    with open(metadata_path) as f:
        props = json.load(f)

    font, font_small = load_fonts()

    per_page = MULTI_PER_PAGE if multi else SINGLE_PER_PAGE
    make_fn = make_grid_multi if multi else make_grid_single

    page = 0
    for start in range(0, len(props), per_page):
        batch = props[start : start + per_page]
        canvas = make_fn(batch, start, thumbs_dir, font, font_small)
        fname = os.path.join(output_dir, f"page_{page:02d}.jpg")
        canvas.save(fname, quality=90)
        print(f"Grilla {page}: #{start}-{start + len(batch) - 1} -> {fname}")
        page += 1

    mode = "multi-foto" if multi else "single-foto"
    print(f"\nTotal: {page} grillas ({len(props)} propiedades, modo {mode})")


if __name__ == "__main__":
    main()
