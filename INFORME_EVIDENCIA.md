# Informe de evidencia

Generado: `2026-11-28T02:20:20Z`  
Repositorio: `haimerb/botbinance`  
Estado: prototipo de investigación. Este documento no es asesoramiento financiero ni una auditoría independiente.

## Resumen ejecutivo

- El gate de funding superó al carry simple en la validación interna: `+4.8427 USD` de diferencia sobre un notional fijo de `100 USD` por operación, con `12/12` folds ganadores frente a simple y `35` operaciones.
- El resultado neto agregado del gate fue `+0.0640 USD`: equivalente al `0.064%` de un notional de `100 USD`, sin capitalización. Es una señal de dirección, no evidencia de rentabilidad invertible.
- Frente al gate clásico, la mejora fue de solo `+0.3993 USD` y el gate ganó en `7/12` folds. `SOLUSDT` cerró con P&L negativo.
- La estrategia ML direccional quedó descartada: accuracy `49.54%`, `0/4` folds ganadores, retorno medio `-0.3%` y Sharpe negativo.
- No se ejecutaron órdenes reales. La operación paper quedó con `dry_run=True`, `MOCK_MODE=true` y `FUNDING_ENABLED=false` en la configuración local.

## Datos utilizados

- Fuente: Binance USDⓈ-M, endpoints públicos de `https://fapi.binance.com`.
- Símbolos: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`.
- Ventana por símbolo: `500` marcas de funding, desde `2026-06-14T16:00:00Z` hasta `2026-11-28T00:00:00Z`.
- Basis: `mark_price - index_price` sobre velas de `8h`, alineado por timestamp de funding.
- Open interest histórico no se incluyó: Binance lo limita a los últimos `30` días y `FundingGate` calcula presión de liquidaciones a partir de funding, basis y racha reciente.
- Las credenciales de Binance no son necesarias para estos endpoints públicos.

## Metodología

- `12` folds: `4` por símbolo.
- Ventana de entrenamiento: `180` filas. Ventana de prueba: `80` filas.
- El modelo de persistencia se ajusta solo con `rows[:train_end]`; la evaluación usa `rows[train_end:test_end]`.
- Las tres variantes comparten exactamente las mismas filas de prueba:
  - `simple`: entra si `funding_rate > 0`.
  - `clásico`: z-score, basis, calendario y funding sostenido.
  - `gate completo`: clásico más persistencia empírica y presión de liquidaciones.
- Notional fijo: `100 USD`. Comisiones: `0.0004` por entrada y `0.0004` por salida.
- `min_net_annual_pct=2.0`, `min_hold_days=7`, `max_hold_days=30`.
- Criterio interno de aceptación: el gate supera a simple, gana al menos la mitad de los folds y genera al menos `3` operaciones.

## Resultados agregados

| Variante | P&L neto USD | Diferencia vs simple |
| --- | ---: | ---: |
| Carry simple | `-4.7787` | — |
| Gate clásico | `-0.3353` | `+4.4434` |
| Gate completo | `+0.0640` | `+4.8427` |

| Métrica | Valor |
| --- | ---: |
| Folds | `12` |
| Folds ganadores vs simple | `12/12` |
| Folds que superan al clásico | `7/12` |
| Operaciones del gate | `35` |
| Aceptado por criterio interno | `true` |

## Resultados por símbolo

| Símbolo | Simple USD | Clásico USD | Gate USD | Delta vs simple | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| `BTCUSDT` | `-0.1030` | `+0.5605` | `+0.6384` | `+0.7414` | `9` |
| `ETHUSDT` | `-1.7626` | `-0.1981` | `+0.0156` | `+1.7782` | `10` |
| `SOLUSDT` | `-2.9131` | `-0.6977` | `-0.5900` | `+2.3231` | `16` |

## Interpretación

- El gate reduce pérdidas del carry simple de forma consistente: los `12/12` folds mejoran, pero eso no significa que los `12` folds sean rentables.
- La mejora real frente al gate clásico es pequeña (`+0.3993 USD`) y no uniforme: `SOLUSDT` sigue negativo y solo `7/12` folds superan al clásico.
- El resultado agregado es demasiado pequeño para cubrir incertidumbre operativa. No debe presentarse como retorno esperado.
- La simulación no modela latencia, rechazos de órdenes, coste de oportunidad, endeudamiento, transferencias entre spot y futuros ni fallos de conectividad.
- El runner expone `execution.last_execution` y `execution.fills` con fills y slippage por pata, pero en `dry_run` esos fills son sintéticos y el slippage es cero o teórico. Medir slippage real requiere ejecución con datos L2.
- El backtest usa comisiones fijas por lado. El runner admite maker/taker configurables, pero el papel de maker real requiere medir fills efectivos.
- El notional es fijo y no hay capitalización entre folds. El P&L no equivale a un rendimiento anualizado de una cartera real.

## Evidencia operativa

- `DRY_RUN=false python -m pytest tests/ -q` → `188 passed`, `14 warnings`.
- CI del PR #153: `Security Scanning` y `Run Tests` completados con éxito.
- `GET /api/funding/status` y WS exponen `execution.last_execution` y `execution.fills` para auditoría de fills y slippage por pata.
- Webhook de Alertmanager: `200` con token Bearer y `401` sin token.
- Validación de payload JWT: REST devuelve `401` con `sub` no entero; handshake WS se rechaza con `4001` y el cliente observa `403`.
- WS válido: recibe estado del bot correctamente.
- Funding paper: `running`, `dry_run=True`, `cycles=1`, `position=SOLUSDT`, `last_error=None`.
- Observabilidad: Prometheus, Grafana y Alertmanager desplegados; `paper_watch.py` disponible para lectura periódica por HTTP.

## Reproducción

Comandos disponibles:

```bash
DRY_RUN=false python -m pytest tests/ -q
python -m pytest tests/test_funding_baseline.py -q
BOTBINANCE_TOKEN=<jwt> python paper_watch.py --intervalo 60 --iteraciones 1
```

Para regenerar el snapshot numérico:

```python
from src.backtest.funding_baseline import walk_forward_funding_validation
from src.config import FUNDING_HISTORY_BASE_URL
from src.data.binance_futures_client import BinanceFuturesClient
from src.data.funding_history import FundingHistoryClient

symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
history = FundingHistoryClient(
    BinanceFuturesClient(base_url=FUNDING_HISTORY_BASE_URL)
)
rows_by_symbol = {}

for symbol in symbols:
    funding = history.funding(symbol, limit=500)
    start = funding[0]["funding_time"]
    end = funding[-1]["funding_time"]
    marks = {
        row["open_time"]: row
        for row in history.mark_index(symbol, start_ms=start, end_ms=end)
    }
    rows_by_symbol[symbol] = [
        {
            "funding_time": row["funding_time"],
            "funding_rate": row["funding_rate"],
            "basis_pct": marks.get(row["funding_time"], {}).get("basis_pct"),
        }
        for row in funding
    ]

result = walk_forward_funding_validation(
    rows_by_symbol,
    folds=12,
    train_size=180,
    test_size=80,
    gate_kwargs={"min_net_annual_pct": 2.0},
)
print(result["summary"])
```

La ventana se mueve con el tiempo. Los valores de este informe corresponden al snapshot indicado al inicio del documento.

## Limitaciones y evidencia pendiente

1. No hay auditoría independiente; estos números provienen del propio código del repositorio.
2. No hay ejecución real; los fills y slippage del paper-forward son sintéticos hasta que se mida con órdenes reales o datos L2.
3. No hay segunda ni tercera fuente externa que valide la tesis de funding.
4. Market making y arbitraje multi-exchange requieren infraestructura, cuentas y capital adicionales.
5. El prototipo es técnicamente funcional, pero el valor comercial sigue siendo bajo-medio hasta acumular evidencia externa y operativa.

## Conclusión

La evidencia disponible sostiene seguir validando en paper trading; no sostiene afirmar que el bot es rentable ni presentarlo como producto financiero probado. El próximo paso de evidencia es una ejecución paper continua usando los nuevos campos de fills y slippage, añadir drawdown y completar una revisión independiente.
