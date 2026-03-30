# Detección de Oportunidades Inmobiliarias

Skill para encontrar propiedades por debajo del promedio del barrio que podrían ser oportunidades de inversión.

## Cuándo usar este skill

Cuando el usuario pregunte por oportunidades, las mejores opciones, qué comprar, propiedades baratas, o pida un resumen del mercado.

## Instrucciones

1. Usar `zonaprop_oportunidades` para obtener la lista ordenada por diff_vs_prom_general (ascendente = más baratas primero).
2. Usar `zonaprop_db_stats` para contexto general del mercado (promedios por barrio).
3. Alertar sobre posibles publicaciones fraudulentas: si el diff es extremo (< -50%) y el m² parece irrazonable, probablemente el publicante infló los metros cuadrados para parecer barato.
4. Para las mejores oportunidades, sugerir usar `zonaprop_analizar_db` con fotos para confirmar visualmente.
5. Comparar siempre el diff_vs_prom_general (vs toda la base) con el diff_vs_prom_busqueda (vs el último escaneo).

## Métricas clave

- **diff_vs_prom_general**: % de diferencia vs el promedio USD/m² de TODAS las propiedades activas del barrio. Negativo = más barato que el promedio.
- **diff_vs_prom_busqueda**: % vs el promedio del último escaneo solamente.
- **precio_m2**: USD por metro cuadrado.
- Una oportunidad real debería tener: diff entre -15% y -40%, m² razonables para la cantidad de ambientes, y fotos que confirmen buen estado.
