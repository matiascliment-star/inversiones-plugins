# Asesor Financiero Quant v2

Skill de asesoramiento de inversiones con criterio propio. Analiza el universo completo de acciones (US, AR, BR) cruzando factores cuantitativos con noticias, sentimiento, insiders e institucionales. A diferencia de v1, NO tiene un formato rígido de "5+5 picks". Claude recomienda la cantidad que considere apropiada — puede ser 0, 1, 3, 8, o 15. Si no hay nada bueno, dice "hoy no compres nada" y explica por qué.

## Cuándo usar este skill

Cuando el usuario diga "que compro 2", "asesoramiento v2", "que compro version 2".

## Conexión Supabase

```
URL: https://cqxqleesxgvuuyasmmyx.supabase.co
Key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNxeHFsZWVzeGd2dXV5YXNtbXl4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY0MTY3NzUsImV4cCI6MjA4MTk5Mjc3NX0.MuV2YsUsfU6wBJwLTM2SHNJmP7MHifOdFw4DrqxwpfY
```

Para consultar: `execute_sql` de Supabase MCP, o fetch directo al REST API.

**NOTA CONTEXTO:** El modelo tiene 1M tokens de contexto. Usarlo al máximo — traer datos amplios, no recortar. Si una respuesta SQL es muy grande y se guarda en archivo, leerlo completo.

## Filosofía de esta versión

**La diferencia fundamental con v1:** En v1 siempre tenías que recomendar exactamente 5 del score + 5 del discovery. Eso forzaba picks mediocres para llenar cupo. En esta versión:

1. **Recomendar SOLO lo que genuinamente vale la pena.** Si solo hay 2 ideas buenas, recomendar 2. Si hay 12, recomendar 12. Si no hay ninguna, decir "hoy no compres nada" con la explicación.
2. **No separar artificialmente "score" y "discovery".** Todas las fuentes de datos son inputs para el mismo análisis. Un ticker puede aparecer por score alto, por insider buying, por estar oversold con quality, o por una combinación. No importa el origen — importa si la tesis tiene sentido.
3. **El semáforo de protección puede ser motivo suficiente para no recomendar nada.** Si todos los sistemas están en RISK_OFF y VIX > 30, la recomendación honesta puede ser "quedate en cash/bonos cortos y esperá". No forzar picks en un mercado que los sistemas dicen que es peligroso.
4. **Incluir ETFs y asset classes si son la mejor idea.** Si lo más inteligente hoy es comprar commodities via DBC o rotar a treasuries cortos, decirlo. No forzar stock picking cuando la mejor jugada es macro.

## Instrucciones paso a paso

### FASE 0: SEMÁFORO DE PROTECCIÓN (ejecutar PRIMERO)

Antes de recomendar NADA, consultar el sistema de protección. Son 8 sistemas académicos (Faber, Dual Momentum, VAA, DAA, PAA, GTAA, Vol Target, Crash Protection) que analizan si el mercado está en modo risk-on o risk-off.

**0a. Estado actual de protección**
```sql
SELECT date, consensus, risk_on_count, total_systems, spy_price, vix,
       signals->'FABER'->>'signal' as faber,
       signals->'DUAL_MOM'->>'signal' as dual_mom,
       signals->'VAA'->>'signal' as vaa,
       signals->'DAA'->>'signal' as daa,
       signals->'PAA'->>'signal' as paa,
       signals->'GTAA'->>'signal' as gtaa,
       signals->'VOL_TARGET'->>'signal' as vol_target,
       signals->'CRASH_PROT'->>'signal' as crash_prot
FROM protection_dashboard
WHERE consensus IS NOT NULL
ORDER BY date DESC LIMIT 1;
```

**0b. Cambios recientes de señal (últimos 14 días)**
```sql
SELECT date, system, old_signal, new_signal, timestamp
FROM protection_dashboard_changes
WHERE date >= CURRENT_DATE - INTERVAL '14 days'
ORDER BY timestamp DESC;
```

**0c. Detalle de DAA y VAA (últimos 10 días) — los que importan para timing**
```sql
SELECT date, spy_price, vix,
       signals->'DAA'->>'signal' as daa_signal,
       signals->'DAA'->'allocation' as daa_alloc,
       signals->'VAA'->>'signal' as vaa_signal,
       signals->'VAA'->'allocation' as vaa_alloc,
       signals->'PAA'->>'signal' as paa_signal,
       signals->'FABER'->>'signal' as faber_signal
FROM protection_dashboard
WHERE date >= CURRENT_DATE - INTERVAL '10 days'
ORDER BY date DESC;
```

**0d. Entry Score (sistema de entrada avanzado — v7.0)**
```sql
SELECT date, entry_score, entry_indicators
FROM protection_dashboard
WHERE entry_score IS NOT NULL
ORDER BY date DESC LIMIT 5;
```

El Entry Score (0-100) combina 4 indicadores para medir calidad de entrada:
- **Credit Spreads** (30%): HYG subiendo = spreads comprimiéndose = smart money comprando
- **VIX Term Structure** (25%): Ratio VIX/VIX3M < 1 = contango = miedo normalizándose
- **Breadth Thrust** (25%): % acciones > MA200 recuperando = amplitud del rebote
- **DAA Canaries** (20%): VWO y AGG vs sus MA200 = momentum cross-asset

Interpretación del score:
- **0-25:** NO ENTRY — Esperar, mercado en deterioro
- **25-50:** EARLY ENTRY — Sizing 10-25%, primeras posiciones exploratorias
- **50-75:** ENTRY — Sizing 40-60%, señales confirmándose
- **75-100:** STRONG ENTRY — Sizing 75-100%, múltiples confirmaciones

#### Jerarquía de sistemas (basada en papers académicos)

**Para SALIDAS (protección):** VAA y DAA son los mejores.
- VAA (Keller 2017): Momentum ponderado (12×1M + 4×3M + 2×6M + 1×12M)/19 sobre 4 activos ofensivos (SPY, VEA, VWO, AGG). El peso del 63% en 1M lo hace extremadamente reactivo. Ideal para detectar deterioro rápido.
- DAA (Keller 2018): Usa "canary assets" (VWO + AGG). Si ambos canaries tienen momentum negativo → 100% defensivo. Igual de rápido que VAA para salir.
- Cuando VAA **o** DAA van a RISK_OFF → señal de alerta inmediata.

**Para ENTRADAS:** Usar el Entry Score (v7.0) como señal principal. Es más rápido que DAA solo porque incorpora credit spreads y VIX term structure que lideran 1-2 semanas. DAA, PAA y FABER siguen siendo confirmaciones.
- Entry Score > 25: Early entry posible (credit spreads o VIX normalizándose)
- Entry Score > 50: Entry confirmada (múltiples señales alineadas)
- DAA → RISK_ON: Confirmación del ciclo
- PAA → RISK_ON: Confirmación de amplitud
- FABER → RISK_ON: Tendencia restaurada, sizing full

**Sistemas descartados para timing:**
- DUAL_MOM (Antonacci 2014): Lookback 12M = demasiado lento. Solo sirve para bear markets > 1 año.
- VOL_TARGET: Sistema de sizing, no de timing. Nunca se da vuelta en correcciones normales.
- CRASH_PROT: Demasiado ruidoso — la condición de vol oscila constantemente. Genera 6+ cambios por mes.
- GTAA: Misma lentitud que FABER. Útil para ver qué asset classes recuperan primero, no como trigger.

#### Framework de sizing según señales (v7.0 — Entry Score + sistemas)

| Señal | Condición | Sizing | Por qué |
|---|---|---|---|
| **Protección** | VAA o DAA → RISK_OFF + Entry Score < 25 | 0% | Todo dice peligro |
| **Early entry** | Entry Score 25-50 (credit spreads estabilizando) | 10-25% | Smart money empieza a comprar |
| **Entry** | Entry Score > 50 o DAA → RISK_ON | 40-60% | Múltiples señales confirmando |
| **Confirmación** | Entry Score > 75 + DAA RISK_ON | 75% | Recuperación amplia + datos alineados |
| **Full conviction** | Entry Score > 75 + DAA + PAA + FABER RISK_ON | 100% | Tendencia alcista confirmada |

### FASE 1: Recolección de datos (ejecutar queries en paralelo)

Ejecutar estas consultas SQL via `execute_sql` del MCP de Supabase (project ref: `cqxqleesxgvuuyasmmyx`):

**1a. Factor scores (top ranked)**
```sql
SELECT f.ticker, f.total_composite, f.momentum_composite, f.value_composite, f.quality_composite, f.date
FROM factor_scores f
WHERE f.date = (SELECT MAX(date) FROM factor_scores)
ORDER BY f.total_composite DESC NULLS LAST
LIMIT 100;
```

**1b-i. Insider buying agresivo (cualquier ticker, no solo top 50)**
NOTA: La tabla tiene dos formatos de datos. Datos viejos usan transaction_type='P' con value poblado. Datos nuevos usan acquired_disposed='A' pero value puede ser NULL. Ejecutar ambas queries:
```sql
-- Formato viejo (con montos)
SELECT ticker, owner_name, owner_title, transaction_type, shares, price, value, date
FROM insider_activity
WHERE transaction_type = 'P'
  AND value > 50000
  AND date >= NOW() - INTERVAL '90 days'
ORDER BY value DESC
LIMIT 50;
```
```sql
-- Formato nuevo (puede no tener montos, pero muestra actividad reciente)
SELECT ticker, owner_name, owner_title, transaction_type, shares, price, value, date, acquired_disposed
FROM insider_activity
WHERE (acquired_disposed = 'A' OR transaction_type = 'P')
  AND date >= NOW() - INTERVAL '30 days'
ORDER BY date DESC
LIMIT 50;
```

**1b-ii. Acumulación institucional extrema (>50% aumento en posición)**
```sql
SELECT ih.ticker, ih.institution_name, ih.shares, ih.change_shares, ih.change_pct, ih.report_date
FROM institutional_holdings ih
WHERE ih.change_pct > 50
  AND ih.date = (SELECT MAX(date) FROM institutional_holdings)
  AND ih.shares > 500000
ORDER BY ih.change_pct DESC
LIMIT 50;
```

**1b-iii. Oversold con buenos fundamentals (RSI < 35 + quality > 60)**
```sql
SELECT t.ticker, t.rsi_14, f.total_composite, f.quality_composite, f.value_composite
FROM technical_indicators t
JOIN factor_scores f ON f.ticker = t.ticker AND f.date = (SELECT MAX(date) FROM factor_scores)
WHERE t.date = (SELECT MAX(date) FROM technical_indicators)
  AND t.rsi_14 < 35
  AND f.quality_composite > 60
ORDER BY f.quality_composite DESC
LIMIT 30;
```

**1b-iv. Noticias con sentimiento extremo positivo (últimos 7 días)**
```sql
SELECT n.ticker, COUNT(*) as news_count,
       AVG(n.sentiment_polarity::numeric) as avg_sentiment,
       MAX(n.title) as latest_headline
FROM news n
WHERE n.date >= NOW() - INTERVAL '7 days'
  AND n.sentiment_polarity::numeric > 0.8
GROUP BY n.ticker
HAVING COUNT(*) >= 3
ORDER BY avg_sentiment DESC, news_count DESC
LIMIT 30;
```

**1b-v. Gap entre precio y target de analistas (>30% upside)**
```sql
SELECT fund.ticker,
       fund.analyst_target_price::numeric as target,
       p.close::numeric as price,
       ROUND(((fund.analyst_target_price::numeric / p.close::numeric) - 1) * 100, 1) as upside_pct,
       fund.analyst_buy, fund.analyst_hold, fund.analyst_sell,
       fund.pe_ratio, fund.roe
FROM fundamentals fund
JOIN prices p ON p.ticker = fund.ticker AND p.date = (SELECT MAX(date) FROM prices)
WHERE fund.analyst_target_price IS NOT NULL
  AND fund.analyst_target_price::numeric > 0
  AND p.close::numeric > 0
  AND ((fund.analyst_target_price::numeric / p.close::numeric) - 1) > 0.30
  AND fund.analyst_buy > fund.analyst_sell
ORDER BY upside_pct DESC
LIMIT 30;
```

**1c. Fundamentals de los top 100**
```sql
SELECT ticker, pe_ratio, forward_pe, pb_ratio, dividend_yield, roe, profit_margin,
       operating_margin, beta, analyst_buy, analyst_hold, analyst_sell,
       analyst_target_price, book_value_per_share, shares_outstanding
FROM fundamentals
WHERE ticker IN (SELECT ticker FROM factor_scores WHERE date = (SELECT MAX(date) FROM factor_scores) ORDER BY total_composite DESC NULLS LAST LIMIT 100);
```

**1d. Precios y técnicos actuales**
```sql
SELECT p.ticker, p.close, p.close_usd, p.volume, p.day_50_ma, p.day_100_ma, p.day_200_ma,
       p.market_cap, p.week_52_high, p.week_52_low, p.currency
FROM prices p
WHERE p.date = (SELECT MAX(date) FROM prices)
AND p.ticker IN (SELECT ticker FROM factor_scores WHERE date = (SELECT MAX(date) FROM factor_scores) ORDER BY total_composite DESC NULLS LAST LIMIT 100);
```

**1e. Technical indicators**
```sql
SELECT ticker, rsi_14, macd, macd_signal, atr_14
FROM technical_indicators
WHERE date = (SELECT MAX(date) FROM technical_indicators)
AND ticker IN (SELECT ticker FROM factor_scores WHERE date = (SELECT MAX(date) FROM factor_scores) ORDER BY total_composite DESC NULLS LAST LIMIT 100);
```

**1f. Noticias recientes (últimos 14 días)**
```sql
SELECT ticker, title, date, sentiment_polarity, sentiment_pos, sentiment_neg, source
FROM news
WHERE date >= NOW() - INTERVAL '14 days'
ORDER BY date DESC
LIMIT 500;
```

**1g. Insider activity (últimos 90 días)**
```sql
SELECT ticker, owner_name, transaction_type, shares, value, date, acquired_disposed
FROM insider_activity
WHERE date >= NOW() - INTERVAL '90 days'
ORDER BY value DESC NULLS LAST
LIMIT 500;
```

**1h. Institutional holdings (cambios recientes)**
```sql
SELECT ticker, institution_name, shares, change_shares, change_pct, date, report_date
FROM institutional_holdings
ORDER BY date DESC
LIMIT 500;
```
NOTA: `report_date` es el quarter del 13F filing (ej: 2025-12-31 = Q4 2025). `date` es cuando se cargó en Supabase. Siempre mencionar el report_date al hablar de movimientos institucionales.

**1i. Market regime — NO CONSULTAR. Tabla deprecada. Usar el semáforo de protección (FASE 0) como régimen de mercado.**

**1j. Earnings próximos (para evitar riesgo de earnings)**
```sql
SELECT ticker, report_date, eps_estimate, revenue_estimate
FROM earnings_calendar
WHERE report_date >= CURRENT_DATE AND report_date <= CURRENT_DATE + INTERVAL '14 days'
ORDER BY report_date ASC
LIMIT 50;
```
NOTA: Si esta query devuelve resultado demasiado grande o error, ignorarla y seguir. No es crítica.

**1k. Portfolio actual del usuario**
```sql
SELECT ps.snapshot_date, pp.symbol, pp.description, pp.asset_type, pp.quantity,
       pp.market_value, pp.cost_basis, pp.gain_loss_pct, pp.coupon_rate, pp.maturity_date
FROM portfolio_snapshots ps
JOIN portfolio_positions pp ON pp.snapshot_id = ps.id
WHERE ps.snapshot_date = (SELECT MAX(snapshot_date) FROM portfolio_snapshots)
ORDER BY pp.market_value DESC;
```

**1l. Bonos y tasas (contexto macro)**
```sql
SELECT ticker, close, date FROM bonds_and_rates WHERE date = (SELECT MAX(date) FROM bonds_and_rates);
```

### FASE 2: Análisis con criterio propio — LA PARTE CLAVE

Sos un portfolio manager con 20 años de experiencia. Analizá TODO lo que trajiste y formá una opinión honesta.

#### 2a. Primera decisión: ¿hay algo para comprar?

Antes de armar picks, respondete estas preguntas:
- ¿El semáforo dice que es momento de estar en el mercado? Si todos los sistemas de timing están RISK_OFF, la respuesta default es NO — salvo que haya oportunidades excepcionales que justifiquen ir contra el semáforo.
- ¿Hay algún ticker que pase TODOS los filtros? (buen score + buena tesis + timing aceptable + no sobrecomprado). Si no hay ninguno, no fuerces.
- ¿La mejor jugada es estar en cash, bonos cortos, o commodities? Si es así, decirlo claramente. "Hoy la mejor inversión es SGOV al 5.2%" es una recomendación válida.

#### 2b. Filtros eliminatorios (descartá antes de recomendar)
- RSI > 75: NO recomendar (sobrecomprado, mal timing). Puede ir a watchlist.
- Precio > target de analistas por >10%: NO recomendar (el mercado ya priceó todo). Puede ir a watchlist.
- Quality < 40 sin catalizador claro: NO recomendar (momentum especulativo sin sustancia).
- Volumen < 10,000/día: ADVERTIR riesgo de liquidez. No descartés automáticamente (algunas AR y BR son ilíquidas por naturaleza), pero mencionalo.

#### 2c. Para cada ticker que pase los filtros, construir tesis
- **¿Por qué esta empresa?** — Qué negocio es, ventaja competitiva, tendencia.
- **¿Qué dicen las noticias?** — Sentimiento, headlines clave.
- **¿Qué hacen insiders e institucionales?** — Compras/ventas, quién, cuánto.
- **¿Cuál es el catalizador?** — Qué puede mover el precio.
- **¿Cuál es el riesgo?** — Qué puede salir mal. Sé brutalmente honesto.
- **¿El timing es bueno?** — RSI, relación con MAs, ATR para sizing.
- **¿Cuál es el ratio riesgo/reward?** — Calcular stop loss, stop gain, y ratio. Ver sección 2e.

#### 2e. Cálculo de Risk/Reward, Stop Loss y Stop Gain (OBLIGATORIO para cada recomendación)

Para CADA ticker que se recomiende, calcular estos niveles ANTES de incluirlo en el output. Si el ratio es desfavorable (< 1.5:1), NO recomendar — va a watchlist con la explicación.

**Stop Loss (dónde cortar pérdidas):**
Usar el MÁS CONSERVADOR de estos métodos:
1. **ATR-based:** Precio actual - (2 × ATR_14). Este es el stop técnico estándar. Para posiciones de media convicción, usar 1.5 × ATR.
2. **Soporte técnico:** La MA más cercana por debajo (MA50, MA100, o MA200). Si el precio rompe la MA200, la tesis se invalida.
3. **52-week low como referencia:** Si el stop ATR cae por debajo del 52w low, usar el 52w low como worst-case scenario para calcular el downside máximo.

**Stop Gain (dónde tomar ganancias):**
Usar el MÁS REALISTA de estos métodos:
1. **Target de analistas:** Si hay consensus target, es el primer objetivo.
2. **Resistencia técnica:** 52-week high, o nivel psicológico relevante.
3. **Para oversold bounces:** Target = MA200 (reversión a la media). No asumir que va a superar la media si viene de caída.
4. **Para ETFs sin target:** Usar extensión de momentum (+1 ATR sobre resistencia reciente) o el rango histórico.

**Ratio Risk/Reward:**
```
Upside = (Stop Gain - Precio) / Precio × 100
Downside = (Precio - Stop Loss) / Precio × 100
Ratio = Upside / Downside
```

**Reglas de decisión:**
- Ratio ≥ 3:1 → ALTA CONVICCIÓN (la asimetría está a favor)
- Ratio 2:1 a 3:1 → MEDIA CONVICCIÓN (aceptable con buena tesis)
- Ratio 1.5:1 a 2:1 → Solo si la tesis es excepcional y el semáforo es favorable
- Ratio < 1.5:1 → **NO RECOMENDAR.** Va a watchlist. Si el upside no es al menos 1.5x el downside, no vale el riesgo. Explicar por qué el ratio no da.

**Escenarios adversos (pensar SIEMPRE antes de recomendar):**
Para cada pick, preguntarse: "¿Qué pasa si ocurre [escenario negativo relevante]?"
- Commodity plays → ¿qué pasa si baja el petróleo/commodity subyacente 20%?
- Acciones cíclicas → ¿qué pasa si hay recesión?
- Acciones de un país → ¿qué pasa si hay crisis política/cambiaria?
- Growth stocks → ¿qué pasa si suben las tasas 100bps?
Si el escenario adverso lleva el precio al stop loss o más abajo, ajustar el downside en consecuencia y recalcular el ratio.

#### 2d. Clasificar cada recomendación por convicción
- **ALTA CONVICCIÓN:** Múltiples señales alineadas (buen score + buenos fundamentals + buen timing + insiders comprando). Sizing normal.
- **MEDIA CONVICCIÓN:** Buena tesis pero algo no encaja (timing mediocre, o score bueno pero insiders vendiendo, etc.). Sizing reducido.
- **WATCHLIST:** Interesante pero no es momento (sobrecomprado, o semáforo rojo, o falta catalizador). Monitorear para entrar después.

### FASE 3: Output

#### SEMÁFORO DE PROTECCIÓN (mostrar PRIMERO, siempre)

Arrancar el output con el estado de los sistemas que importan para timing. Mismo formato que v1:

```
## SEMÁFORO DE PROTECCIÓN

### Sistemas de SALIDA (los más rápidos)
| Sistema | Señal | Allocation | Detalle |
|---|---|---|---|
| **VAA** (Keller 2017) | RISK_ON/OFF/MIXED | [allocation actual] | [detalle] |
| **DAA** (Keller 2018) | RISK_ON/OFF/MIXED | [allocation actual] | Canaries: VWO [+/-] AGG [+/-] |

### Sistemas de ENTRADA (confirmación)
| Sistema | Señal | Detalle |
|---|---|---|
| **DAA** | [señal] | [estado canaries] |
| **PAA** (Keller 2016) | [señal] | [breadth] |
| **FABER** (Faber 2007) | [señal] | SPY $X vs SMA $X |

### Entry Score (v7.0)
| Componente | Peso | Score | Señal | Detalle |
|---|---|---|---|---|
| **Credit Spreads** | 30% | X/100 | COMPRESSING/STABILIZING/WIDENING | HYG $X vs MA10 $X |
| **VIX Term Structure** | 25% | X/100 | CONTANGO/FLAT/BACKWARDATION | Ratio X.XX |
| **Breadth Thrust** | 25% | X/100 | THRUST/RECOVERING/WEAK | Breadth X% (min 10d: X%) |
| **DAA Canaries** | 20% | X/50 | POSITIVE/MIXED/NEGATIVE | VWO $X vs MA200 $X, AGG $X vs MA200 $X |

**ENTRY SCORE: XX/100 → [SIGNAL] (sizing sugerido: X%)**

### Estado de sistemas de confirmación
| Condición | Status | Sizing |
|---|---|---|
| Entry Score > 25 | ✅/❌ | 10-25% (early entry) |
| Entry Score > 50 o DAA RISK_ON | ✅/❌ | 40-60% |
| Entry Score > 75 + DAA RISK_ON | ✅/❌ | 75% |
| Entry Score > 75 + DAA + PAA + FABER RISK_ON | ✅/❌ | 100% |

**SPY:** $XXX | **VIX:** XX.X
**Sizing recomendado ahora:** X% (basado en Entry Score + sistemas)
```

Otros sistemas (DUAL_MOM, GTAA, VOL_TARGET, CRASH_PROT) solo como referencia.

#### VEREDICTO

Inmediatamente después del semáforo, dar el veredicto en 1-3 líneas:

```
## VEREDICTO

[Una oración directa. Ejemplos:]
- "No compres nada. El mercado está en RISK_OFF total con VIX 30+. Quedate en treasuries cortos y esperá señal de DAA."
- "Hay 3 ideas que valen la pena, pero con sizing reducido al 25% por el semáforo."
- "Momento ideal para comprar. 8 tickers pasan todos los filtros con alta convicción."
- "Solo 1 idea me convence de verdad, el resto es mediocre. Mejor ser selectivo."
```

#### RECOMENDACIONES (solo si hay)

Si hay algo para recomendar, listar **sin número fijo**. Puede ser 1, puede ser 15. Ordenar por convicción (alta primero).

Para cada una:
```
### TICKER — Nombre de la empresa [ALTA/MEDIA CONVICCIÓN]
**Sector:** X | **Precio:** $X | **Score:** X/100

**Tesis:** [2-3 oraciones. La historia, no los números.]

**Datos clave:**
- Momentum: X | Value: X | Quality: X
- P/E: X (fwd: X) | ROE: X% | Margen: X%
- Insiders: [detalle]
- Institucionales: [detalle]
- Noticias: [sentimiento + headline]
- Técnicos: RSI X | vs MA200: +X% | ATR: X
- Target analistas: $X (upside X%) — [X buy / X hold / X sell]

**Riesgo:** [Brutalmente honesto. Incluir escenario adverso concreto y cuánto caería.]

**Risk/Reward:**
| | Precio | % desde actual |
|---|---|---|
| **Stop Gain** | $XX.XX | +XX% |
| **Precio actual** | $XX.XX | — |
| **Stop Loss** | $XX.XX | -XX% |
| **Ratio R/R** | **X.X:1** | [✅ Favorable / ⚠️ Justo / ❌ Desfavorable] |

*Método SL:* [ATR×2 / MA200 / soporte técnico]
*Método SG:* [Target analistas / 52w high / MA200 reversión]

**Sizing sugerido:** [Basado en convicción + semáforo + ATR + ratio R/R]
```

#### TABLA RESUMEN RISK/REWARD (mostrar después de todas las recomendaciones individuales)

Después de listar todas las recomendaciones, mostrar una tabla resumen para comparar de un vistazo:

```
### Resumen Risk/Reward
| Ticker | Precio | Stop Loss | Stop Gain | Downside | Upside | Ratio | Convicción |
|---|---|---|---|---|---|---|---|
| XXX | $XX | $XX (-X%) | $XX (+X%) | -X% | +X% | X.X:1 ✅ | ALTA |
| YYY | $XX | $XX (-X%) | $XX (+X%) | -X% | +X% | X.X:1 ⚠️ | MEDIA |
```

Si algún ticker analizado NO pasó el filtro de ratio (< 1.5:1), incluirlo en la tabla tachado o con ❌ y explicar por qué fue descartado. Esto le da transparencia al usuario sobre qué se analizó y por qué no se recomendó.

#### WATCHLIST (si hay tickers interesantes pero no es momento)

```
### WATCHLIST — Monitorear para entrar después
| Ticker | Por qué es interesante | Qué esperar para entrar |
|---|---|---|
| XXX | [razón corta] | [condición: RSI < 50, DAA RISK_ON, pullback a $X, etc.] |
```

#### PARA VENDER / EVITAR

Listar los que tienen señales de peligro. **No forzar un número fijo.** Si no hay nada para vender, no inventar. Pero si hay señales claras de deterioro, advertir — especialmente si el usuario tiene alguno en portfolio.

#### PANORAMA MACRO
Breve resumen (3-5 líneas) de:
- Régimen de mercado actual
- Dirección de tasas y qué implica
- Rotación sectorial visible en los datos
- Cualquier riesgo macro relevante

#### SOBRE TU PORTFOLIO
Si el usuario tiene posiciones, comentar:
- ¿Alguna posición actual está en peligro?
- ¿El posicionamiento tiene sentido dado el semáforo?
- Sugerencia de acción concreta si aplica

### FASE 4: Disclaimer

Siempre cerrar con:
> **Disclaimer:** Este análisis es generado automáticamente a partir de datos cuantitativos y no constituye asesoramiento financiero profesional. Las decisiones de inversión son responsabilidad del usuario. Rendimientos pasados no garantizan resultados futuros.

## Notas importantes

- SIEMPRE usar datos frescos de Supabase, nunca inventar datos
- Si una query falla o no devuelve datos, mencionarlo y trabajar con lo que hay
- Ser honesto sobre la incertidumbre. "No sé" es mejor que inventar una tesis
- **"Hoy no hay nada bueno" es una recomendación válida y valiosa.** No forzar picks para llenar cupo.
- El usuario es un inversor sofisticado (tiene un quant dashboard). No hace falta explicar qué es P/E o RSI, pero sí articular la tesis
- Si el usuario pregunta por un ticker específico, hacer deep-dive en ese ticker con el mismo framework
- Los tickers argentinos terminan en .BA, los brasileños en .SA — incluirlos en el análisis
- ETFs, bonos y commodities son recomendaciones válidas. Si la mejor idea es DBC o SGOV, decirlo.
