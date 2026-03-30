# /zonaprop:revision-visual

Revisión visual masiva de propiedades inmobiliarias.

## Instrucciones

1. Llamar a zonaprop_bulk_export PAGINADO (page_size=100) iterando TODAS las páginas. Concatenar propiedades en un solo array.
2. Guardar el JSON en /tmp/propiedades.json.
3. Descargar TODAS las fotos con `scripts/download_thumbs.py --all` (hasta 8 por propiedad).
4. Armar grillas multi-foto (20 props por grilla, mosaico 4x2 por celda) con `scripts/make_grids.py --multi`.
5. Recorrer TODAS las grillas visualmente (cada celda muestra todas las fotos de la propiedad).
6. Profundizar en las candidatas con fotos en mayor resolución (730x532).
7. Armar ranking final: Top 3, Interesantes, Descartadas. Incluir links de ZonaProp.
8. Generar HTML interactivo con `scripts/make_html_report.py`. **CRÍTICO: incluir TODAS las fotos de cada propiedad (las 6-8 URLs del campo `imagenes`, con `/360x266/` reemplazado por `/730x532/`).** El HTML sin fotos es inútil.
