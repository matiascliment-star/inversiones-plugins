#!/usr/bin/env python3
"""
Descarga thumbnails de propiedades en paralelo.

Uso:
    python3 download_thumbs.py <metadata.json> <output-dir> [--all]

metadata.json: JSON array de propiedades con campo 'imagenes' (array de URLs)
output-dir: carpeta donde guardar los thumbnails

Sin --all: descarga solo la primera foto como {idx:04d}.jpg (modo rápido, para grillas de 1 foto)
Con --all:  descarga TODAS las fotos como {idx:04d}_00.jpg, {idx:04d}_01.jpg, etc. (para grillas multi-foto)
"""
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_all_urls(prop):
    """Extrae TODAS las URLs de fotos de una propiedad."""
    imgs = prop.get("imagenes")
    if imgs and isinstance(imgs, list):
        return [u for u in imgs if u and isinstance(u, str) and u.startswith("http")]
    # Fallback: campo imagen (solo 1)
    img = prop.get("imagen", "")
    if img and img.startswith("http"):
        return [img]
    if prop.get("_thumb", "").startswith("http"):
        return [prop["_thumb"]]
    return []


def download_one(fname, url):
    """Descarga una foto. Retorna (fname, success)."""
    if os.path.exists(fname) and os.path.getsize(fname) > 100:
        return fname, True
    if not url or not url.startswith("http"):
        return fname, False
    try:
        urllib.request.urlretrieve(url, fname)
        return fname, True
    except Exception:
        return fname, False


def main():
    if len(sys.argv) < 3:
        print(f"Uso: {sys.argv[0]} <metadata.json> <output-dir> [--all]")
        sys.exit(1)

    metadata_path = sys.argv[1]
    output_dir = sys.argv[2]
    download_all = "--all" in sys.argv
    os.makedirs(output_dir, exist_ok=True)

    with open(metadata_path) as f:
        props = json.load(f)

    # Build download list
    items = []  # (filename, url)
    for i, p in enumerate(props):
        urls = get_all_urls(p)
        if not urls:
            continue
        if download_all:
            for j, url in enumerate(urls):
                fname = os.path.join(output_dir, f"{i:04d}_{j:02d}.jpg")
                items.append((fname, url))
        else:
            fname = os.path.join(output_dir, f"{i:04d}.jpg")
            items.append((fname, urls[0]))

    total = len(items)
    mode = "TODAS las fotos" if download_all else "1 foto por propiedad"
    print(f"Descargando {total} fotos ({mode}) a {output_dir}...")

    success = 0
    fail = 0

    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = {
            executor.submit(download_one, fname, url): fname
            for fname, url in items
        }
        for future in as_completed(futures):
            fname, ok = future.result()
            if ok:
                success += 1
            else:
                fail += 1
            done = success + fail
            if done % 200 == 0 or done == total:
                print(f"  Progreso: {done}/{total} ({success} ok, {fail} fail)")

    print(f"\nFinal: {success} descargados, {fail} fallidos de {total}")


if __name__ == "__main__":
    main()
