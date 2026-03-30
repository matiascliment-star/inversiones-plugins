# Inversiones Plugins

Plugin marketplace de inversiones para Claude Code. Herramientas de asesoramiento financiero cuantitativo con datos en tiempo real de Supabase.

## Skills disponibles

### que-compro
Asesor financiero quant que analiza todo el universo de acciones (US, AR, BR) y genera recomendaciones con tesis de inversion fundamentada.

**Features:**
- Semaforo de proteccion basado en 8 sistemas academicos (Faber, VAA, DAA, PAA, GTAA, Dual Momentum, Vol Target, Crash Protection)
- Framework de entrada/salida basado en papers de Keller (2016-2018) y Faber (2007)
- DAA como trigger principal de entrada (canary assets VWO + AGG)
- VAA como sistema principal de salida (momentum ponderado 4 activos)
- Sizing escalonado: 25% (DAA solo) -> 50% (DAA confirmado) -> 75% (DAA + PAA) -> 100% (DAA + PAA + FABER)
- Factor scores: momentum, value, quality, size, investment (Fama-French)
- Fundamentals, tecnicos, noticias, sentimiento, insiders, institucionales
- Analisis de portfolio actual con sugerencias de rebalanceo
- Contexto macro: tasas, bonos, market regime, earnings calendar

**Triggers:** `que compro`, `en que invierto`, `recomendaciones`, `oportunidades de inversion`, `asesorame`, `que conviene`, `que onda el mercado`

**Requiere:** Supabase con tablas del quant dashboard (factor_scores, fundamentals, prices, technical_indicators, news, insider_activity, institutional_holdings, protection_dashboard, etc.)

## Instalacion

Agregar a tu `settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "inversiones-plugins": {
      "source": {
        "source": "github",
        "repo": "matiascliment-star/inversiones-plugins"
      }
    }
  }
}
```

## Papers academicos referenciados

- Faber, M. (2007). "A Quantitative Approach to Tactical Asset Allocation"
- Antonacci, G. (2014). "Dual Momentum Investing"
- Keller, W. & Keuning, J. (2016). "Protective Asset Allocation (PAA)"
- Keller, W. & Keuning, J. (2017). "Vigilant Asset Allocation (VAA)"
- Keller, W. & Keuning, J. (2018). "Defensive Asset Allocation (DAA)"
- Fama, E. & French, K. (1992-2015). Factor models
