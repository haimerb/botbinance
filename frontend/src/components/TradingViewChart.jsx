import { useEffect, useMemo, useRef, useState } from 'react'
import { getKlines } from '../api.js'

const WIDTH = 720
const HEIGHT = 320
const PADDING = { top: 20, right: 70, bottom: 30, left: 20 }
const INTERVALS = ['15m', '1h', '4h', '1d']

function formatTime(ts) {
  const d = new Date(ts)
  if (isNaN(d.getTime())) return String(ts).slice(0, 10)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatPrice(p) {
  if (p >= 1000) return p.toLocaleString('en-US', { maximumFractionDigits: 0 })
  if (p >= 1) return p.toFixed(2)
  return p.toFixed(4)
}

export default function TradingViewChart({ symbol = 'BTCUSDT', onSymbolChange }) {
  const [interval, setInterval_] = useState('1h')
  const [candles, setCandles] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [hover, setHover] = useState(null)
  const [livePrice, setLivePrice] = useState(null)
  const wrapRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    getKlines(symbol, interval, 200)
      .then((data) => {
        if (cancelled) return
        setCandles(data.klines || [])
        const last = (data.klines || []).slice(-1)[0]
        if (last) setLivePrice(last.close)
      })
      .catch((e) => {
        if (!cancelled) setError(e.message || 'Error cargando velas')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [symbol, interval])

  useEffect(() => {
    if (!symbol) return
    const wsSymbol = symbol.toLowerCase().replace('/usdt', 'usdt')
    let ws
    try {
      ws = new WebSocket(`wss://stream.binance.com:9443/ws/${wsSymbol}@trade`)
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.p) setLivePrice(parseFloat(msg.p))
        } catch {}
      }
      ws.onerror = () => {}
    } catch {}
    return () => {
      if (ws) ws.close()
    }
  }, [symbol])

  const chart = useMemo(() => {
    if (!candles || candles.length < 2) return null

    const highs = candles.map((c) => c.high)
    const lows = candles.map((c) => c.low)
    const maxPrice = Math.max(...highs, livePrice || 0)
    const minPrice = Math.min(...lows, livePrice || Infinity)
    const range = maxPrice - minPrice || 1
    const innerW = WIDTH - PADDING.left - PADDING.right
    const innerH = HEIGHT - PADDING.top - PADDING.bottom
    const step = innerW / candles.length
    const bodyW = Math.max(1.5, step * 0.6)

    const yOf = (p) => PADDING.top + innerH - ((p - minPrice) / range) * innerH
    const xOf = (i) => PADDING.left + i * step + step / 2

    const rendered = candles.map((c, i) => {
      const bullish = c.close >= c.open
      const color = bullish ? '#22c55e' : '#ef4444'
      const yHigh = yOf(c.high)
      const yLow = yOf(c.low)
      const yOpen = yOf(c.open)
      const yClose = yOf(c.close)
      const bodyTop = Math.min(yOpen, yClose)
      const bodyH = Math.max(1, Math.abs(yClose - yOpen))
      return { c, i, color, x: xOf(i), yHigh, yLow, bodyTop, bodyH, bodyW }
    })

    const yTicks = 5
    const yLabels = Array.from({ length: yTicks }, (_, i) => {
      const price = maxPrice - (i / (yTicks - 1)) * range
      return { price, y: PADDING.top + (i / (yTicks - 1)) * innerH }
    })

    const xTicks = 6
    const xLabels = Array.from({ length: xTicks }, (_, i) => {
      const idx = Math.floor((i / (xTicks - 1)) * (candles.length - 1))
      return { x: xOf(idx), label: formatTime(candles[idx].time) }
    })

    return { rendered, yLabels, xLabels, yOf, maxPrice, minPrice, innerH, innerW }
  }, [candles, livePrice])

  const lastClose = livePrice ?? (candles.length ? candles[candles.length - 1].close : null)
  const firstClose = candles.length ? candles[0].close : null
  const changePct = lastClose && firstClose ? ((lastClose - firstClose) / firstClose) * 100 : 0
  const positive = changePct >= 0

  return (
    <div className="tv-chart-wrapper" ref={wrapRef}>
      <div className="tv-chart-header">
        <div className="tv-chart-title">
          <strong>{symbol}</strong>
          {lastClose != null && (
            <span className="tv-price">${formatPrice(lastClose)}</span>
          )}
          {firstClose != null && (
            <span className={`tv-change ${positive ? 'up' : 'down'}`}>
              {positive ? '▲' : '▼'} {Math.abs(changePct).toFixed(2)}%
            </span>
          )}
        </div>
        <div className="tv-intervals">
          {INTERVALS.map((iv) => (
            <button
              key={iv}
              type="button"
              className={`tv-interval-btn ${iv === interval ? 'active' : ''}`}
              onClick={() => setInterval_(iv)}
            >
              {iv}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="tv-chart-status">Cargando velas…</div>}
      {error && <div className="tv-chart-status error">{error}</div>}

      {!loading && !error && !chart && (
        <div className="tv-chart-status">Sin datos disponibles</div>
      )}

      {chart && (
        <svg
          width="100%"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="tv-chart-svg"
          preserveAspectRatio="xMidYMid meet"
          onMouseLeave={() => setHover(null)}
        >
          <defs>
            <linearGradient id="tvGridFade" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--border)" stopOpacity="0.25" />
              <stop offset="100%" stopColor="var(--border)" stopOpacity="0.05" />
            </linearGradient>
          </defs>

          <rect
            x={PADDING.left}
            y={PADDING.top}
            width={chart.innerW}
            height={chart.innerH}
            fill="rgba(0,0,0,0.18)"
            rx={3}
          />

          {chart.yLabels.map((t, i) => (
            <g key={`y${i}`}>
              <line
                x1={PADDING.left}
                y1={t.y}
                x2={WIDTH - PADDING.right}
                y2={t.y}
                stroke="url(#tvGridFade)"
                strokeWidth="0.6"
                strokeDasharray="2,4"
              />
              <text
                x={WIDTH - PADDING.right + 6}
                y={t.y + 4}
                fill="var(--text-dim)"
                fontSize="10"
                fontFamily="var(--font-mono)"
              >
                {formatPrice(t.price)}
              </text>
            </g>
          ))}

          {chart.xLabels.map((t, i) => (
            <text
              key={`x${i}`}
              x={t.x}
              y={HEIGHT - PADDING.bottom + 16}
              textAnchor="middle"
              fill="var(--text-dim)"
              fontSize="9"
              fontFamily="var(--font-mono)"
            >
              {t.label}
            </text>
          ))}

          {chart.rendered.map((r) => (
            <g key={r.i} className="tv-candle">
              <line x1={r.x} y1={r.yHigh} x2={r.x} y2={r.yLow} stroke={r.color} strokeWidth="1" />
              <rect
                x={r.x - r.bodyW / 2}
                y={r.bodyTop}
                width={r.bodyW}
                height={r.bodyH}
                fill={r.color}
                rx={0.5}
              />
              <rect
                x={r.x - r.bodyW / 2}
                y={PADDING.top}
                width={r.bodyW}
                height={chart.innerH}
                fill="transparent"
                onMouseEnter={() =>
                  setHover({
                    ...r.c,
                    x: r.x,
                    color: r.color,
                  })
                }
              />
            </g>
          ))}

          {lastClose != null && (
            <g>
              <line
                x1={PADDING.left}
                y1={chart.yOf(lastClose)}
                x2={WIDTH - PADDING.right}
                y2={chart.yOf(lastClose)}
                stroke={positive ? '#22c55e' : '#ef4444'}
                strokeWidth="1"
                strokeDasharray="3,3"
                opacity="0.7"
              />
              <rect
                x={WIDTH - PADDING.right + 2}
                y={chart.yOf(lastClose) - 8}
                width={62}
                height={16}
                rx={2}
                fill={positive ? '#22c55e' : '#ef4444'}
              />
              <text
                x={WIDTH - PADDING.right + 33}
                y={chart.yOf(lastClose) + 4}
                textAnchor="middle"
                fill="#060b14"
                fontSize="10"
                fontWeight="700"
                fontFamily="var(--font-mono)"
              >
                {formatPrice(lastClose)}
              </text>
            </g>
          )}
        </svg>
      )}

      {hover && (
        <div className="tv-tooltip">
          <span className="tv-tooltip-time">{formatTime(hover.time)}</span>
          <span>A <b>{formatPrice(hover.open)}</b></span>
          <span>A <b>{formatPrice(hover.high)}</b></span>
          <span>B <b>{formatPrice(hover.low)}</b></span>
          <span>C <b style={{ color: hover.color }}>{formatPrice(hover.close)}</b></span>
        </div>
      )}
    </div>
  )
}