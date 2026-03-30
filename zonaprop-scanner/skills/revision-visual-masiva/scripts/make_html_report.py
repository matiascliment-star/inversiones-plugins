#!/usr/bin/env python3
"""
Genera un HTML interactivo con las propiedades seleccionadas en la revisión visual masiva.

Uso:
    python3 make_html_report.py <input.json> <output.html>

input.json: JSON con estructura:
{
  "stats": { "total_escaneadas": 700, "seleccionadas": 20, "top_picks": 3, "rango_precios": "USD 92k-200k" },
  "propiedades": [
    {
      "tier": "top3" | "top10" | "interesting",
      "rank": 1,
      "score": "9.5/10",
      "barrio": "Belgrano",
      "direccion": "Cuba 1800",
      "precio": 164000,
      "m2": 67,
      "ambientes": 2,
      "precio_m2": 2448,
      "diff_vs_prom": -31,
      "comentario": "Terraza enorme...",
      "link": "https://www.zonaprop.com.ar/...",
      "fotos": ["path/to/foto1.jpg", "path/to/foto2.jpg"]
    }
  ]
}

Las fotos pueden ser:
- Rutas locales (se leen y embeben como base64)
- URLs http/https del CDN de ZonaProp (se descargan y embeben como base64)
- URLs data: ya codificadas (se usan tal cual)
"""
import base64
import json
import mimetypes
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; }
.header { background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 30px 40px; }
.header h1 { font-size: 28px; margin-bottom: 8px; }
.header p { color: #aaa; font-size: 14px; }
.stats { display: flex; gap: 30px; margin-top: 15px; }
.stat { background: rgba(255,255,255,0.1); padding: 10px 20px; border-radius: 8px; }
.stat .num { font-size: 24px; font-weight: bold; color: #4fc3f7; }
.stat .label { font-size: 12px; color: #999; }
.tier-header { background: #222; color: white; padding: 15px 40px; font-size: 18px; margin-top: 20px; }
.tier-header.top3 { background: #1b5e20; }
.tier-header.top10 { background: #e65100; }
.tier-header.interesting { background: #37474f; }
.card { background: white; margin: 15px 40px; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.card-header { display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; background: #fafafa; border-bottom: 1px solid #eee; }
.card-title { font-size: 16px; font-weight: bold; }
.card-score { background: #4caf50; color: white; padding: 5px 12px; border-radius: 20px; font-weight: bold; }
.card-score.high { background: #2e7d32; }
.card-score.medium { background: #f57c00; }
.card-score.low { background: #757575; }
.card-body { padding: 15px 20px; }
.card-photos { display: flex; gap: 8px; margin-bottom: 12px; overflow-x: auto; }
.card-photos img { flex: 0 0 auto; height: 200px; object-fit: cover; border-radius: 6px; cursor: pointer; transition: transform 0.2s; }
.card-photos img:hover { transform: scale(1.02); }
.card-details { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; margin-bottom: 10px; }
.detail { background: #f5f5f5; padding: 8px 12px; border-radius: 6px; }
.detail .val { font-weight: bold; font-size: 16px; }
.detail .lbl { font-size: 11px; color: #666; }
.diff-neg { color: #2e7d32; font-weight: bold; }
.diff-pos { color: #c62828; }
.comment { color: #555; line-height: 1.5; margin: 10px 0; padding: 10px; background: #f9f9f9; border-left: 3px solid #4caf50; border-radius: 4px; }
.link { display: inline-block; background: #1976d2; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; margin-top: 8px; font-size: 14px; }
.link:hover { background: #1565c0; }
.footer { padding: 30px 40px; color: #999; font-size: 12px; text-align: center; }
"""

TIER_LABELS = {
    "top3": ("top3", "\U0001f3c6 TOP 3"),
    "top10": ("top10", "\u2b50 TOP 10"),
    "interesting": ("interesting", "\U0001f50d Interesantes"),
}


def download_url(url):
    """Download a URL and return bytes, or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except Exception:
        return None


def encode_photo(path):
    """Encode a photo as a data URI. Accepts local paths, http URLs, or data: URIs."""
    if path.startswith("data:"):
        return path
    if path.startswith("http://") or path.startswith("https://"):
        data = download_url(path)
        if not data:
            return ""
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    if not os.path.isfile(path):
        return ""
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def predownload_photos(props):
    """Pre-download all HTTP photos in parallel. Mutates props in-place, replacing URLs with data URIs."""
    url_map = {}  # url -> list of (prop_idx, foto_idx)
    for pi, p in enumerate(props):
        for fi, foto in enumerate(p.get("fotos", [])):
            if foto.startswith("http://") or foto.startswith("https://"):
                url_map.setdefault(foto, []).append((pi, fi))

    if not url_map:
        return

    total = len(url_map)
    print(f"Descargando {total} fotos del CDN...")

    LOGO_THRESHOLD = 5 * 1024  # Images < 5KB are realtor logos

    results = {}  # url -> (data_uri, size_bytes)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(download_url, url): url for url in url_map}
        done = 0
        for future in as_completed(futures):
            url = futures[future]
            data = future.result()
            done += 1
            if data:
                b64 = base64.b64encode(data).decode("ascii")
                results[url] = (f"data:image/jpeg;base64,{b64}", len(data))
            if done % 20 == 0 or done == total:
                print(f"  {done}/{total} descargadas")

    # Replace URLs with data URIs in props
    for url, (data_uri, _size) in results.items():
        for pi, fi in url_map[url]:
            props[pi]["fotos"][fi] = data_uri

    # For each prop: remove failed downloads, then move logos (< 5KB) to the end
    logos_moved = 0
    for pi, p in enumerate(props):
        real_photos = []
        logos = []
        for foto in p.get("fotos", []):
            if not foto.startswith("data:"):
                continue  # failed download, skip
            # Decode base64 to measure actual image size
            try:
                raw = foto.split(",", 1)[1]
                size = len(base64.b64decode(raw))
            except Exception:
                size = 999999
            if size < LOGO_THRESHOLD:
                logos.append(foto)
            else:
                real_photos.append(foto)
        if logos:
            logos_moved += len(logos)
        p["fotos"] = real_photos + logos  # real photos first, logos at the end

    ok = len(results)
    print(f"  {ok}/{total} fotos embebidas OK ({logos_moved} logos movidos al final)")


def score_class(score_str):
    """Return CSS class based on numeric score."""
    try:
        val = float(score_str.split("/")[0])
    except (ValueError, IndexError, AttributeError):
        return "low"
    if val >= 8:
        return "high"
    if val >= 6:
        return "medium"
    return "low"


def fmt_price(precio):
    if not precio:
        return "N/A"
    return f"USD {precio:,.0f}".replace(",", ".")


def fmt_diff(diff):
    if diff is None:
        return "", ""
    css = "diff-neg" if diff < 0 else "diff-pos"
    return f"{diff:+.0f}%", css


def build_card(prop):
    rank = prop.get("rank", "?")
    barrio = prop.get("barrio", "")
    direccion = prop.get("direccion", "")
    title_text = f"#{rank}"
    if barrio:
        title_text += f" &mdash; {barrio}"
    if direccion:
        title_text += f" &middot; {direccion}"

    score = prop.get("score", "")
    sc_class = score_class(score)

    # Photos
    fotos = prop.get("fotos", [])
    photo_tags = []
    for fp in fotos:
        data_uri = encode_photo(fp)
        if data_uri:
            photo_tags.append(f'<img src="{data_uri}" alt="Foto propiedad">')

    photos_html = ""
    if photo_tags:
        photos_html = f'<div class="card-photos">{"".join(photo_tags)}</div>'

    # Details
    precio = prop.get("precio")
    m2 = prop.get("m2")
    amb = prop.get("ambientes")
    precio_m2 = prop.get("precio_m2")
    diff = prop.get("diff_vs_prom")

    details = []
    if precio:
        details.append(f'<div class="detail"><div class="val">{fmt_price(precio)}</div><div class="lbl">Precio</div></div>')
    if m2:
        details.append(f'<div class="detail"><div class="val">{m2} m\u00b2</div><div class="lbl">Superficie</div></div>')
    if amb:
        details.append(f'<div class="detail"><div class="val">{amb} amb</div><div class="lbl">Ambientes</div></div>')
    if precio_m2:
        details.append(f'<div class="detail"><div class="val">USD {precio_m2:,.0f}/m\u00b2</div><div class="lbl">Precio por m\u00b2</div></div>')
    if diff is not None:
        diff_str, diff_css = fmt_diff(diff)
        details.append(f'<div class="detail"><div class="val {diff_css}">{diff_str}</div><div class="lbl">vs. Promedio barrio</div></div>')

    details_html = f'<div class="card-details">{"".join(details)}</div>' if details else ""

    comment = prop.get("comentario", "")
    comment_html = f'<div class="comment">{comment}</div>' if comment else ""

    link = prop.get("link", "")
    link_html = f'<a href="{link}" class="link" target="_blank">Ver en ZonaProp \u2192</a>' if link else ""

    return f"""<div class="card">
    <div class="card-header">
        <div><span class="card-title">{title_text}</span></div>
        <span class="card-score {sc_class}">{score}</span>
    </div>
    <div class="card-body">
        {photos_html}
        {details_html}
        {comment_html}
        {link_html}
    </div>
</div>"""


def build_html(data):
    stats = data.get("stats", {})
    props = data.get("propiedades", [])

    # Pre-download all HTTP photos in parallel
    predownload_photos(props)

    # Header stats
    stat_items = [
        (str(stats.get("total_escaneadas", "?")), "Propiedades escaneadas"),
        (str(stats.get("seleccionadas", len(props))), "Seleccionadas"),
        (str(stats.get("top_picks", "?")), "Top picks"),
        (stats.get("rango_precios", ""), "Rango de precios"),
    ]
    stats_html = "\n".join(
        f'        <div class="stat"><div class="num">{v}</div><div class="label">{l}</div></div>'
        for v, l in stat_items if v
    )

    # Group by tier
    tiers_order = ["top3", "top10", "interesting"]
    grouped = {}
    for p in props:
        t = p.get("tier", "interesting")
        grouped.setdefault(t, []).append(p)

    body_parts = []
    for tier_key in tiers_order:
        tier_props = grouped.get(tier_key, [])
        if not tier_props:
            continue
        css_class, label = TIER_LABELS.get(tier_key, ("interesting", tier_key))
        body_parts.append(f'\n<div class="tier-header {css_class}">{label}</div>\n')
        for p in tier_props:
            body_parts.append(build_card(p))

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    total = stats.get("total_escaneadas", "?")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Top Propiedades - Revisi\u00f3n Visual Masiva</title>
<style>
{CSS}</style>
</head>
<body>
<div class="header">
    <h1>Top Propiedades - Revisi\u00f3n Visual Masiva</h1>
    <p>ZonaProp \u2022 {now}</p>
    <div class="stats">
{stats_html}
    </div>
</div>
{"".join(body_parts)}
<div class="footer">
    Generado autom\u00e1ticamente \u2022 Revisi\u00f3n visual masiva de {total} propiedades \u2022 {now}
</div>
</body></html>"""


def main():
    if len(sys.argv) < 3:
        print(f"Uso: {sys.argv[0]} <input.json> <output.html>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path) as f:
        data = json.load(f)

    html = build_html(data)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)

    size_kb = os.path.getsize(output_path) / 1024
    n_props = len(data.get("propiedades", []))
    print(f"HTML generado: {output_path} ({size_kb:.0f} KB, {n_props} propiedades)")


if __name__ == "__main__":
    main()
