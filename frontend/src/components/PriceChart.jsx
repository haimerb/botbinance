import { useMemo } from 'react'

const CHART_WIDTH = 580
const CHART_HEIGHT = 220
const PADDING = { top: 20, right: 60, bottom: 30, left: 50 }

export default function PriceChart({ history, position, currentPrice, priceChange }) {
  const chartData = useMemo(() => {
    if (!history || history.length < 2) return null

    const prices = history
    const minPrice = Math.min(...prices)
    const maxPrice = Math.max(...prices)
    const priceRange = maxPrice - minPrice || 1

    const xStep = (CHART_WIDTH - PADDING.left - PADDING.right) / (prices.length - 1)

    const points = prices.map((price, i) => ({
      x: PADDING.left + i * xStep,
      y: PADDING.top + CHART_HEIGHT - ((price - minPrice) / priceRange) * (CHART_HEIGHT - PADDING.top - PADDING.bottom),
      price,
      index: i,
    }))

    const entryPoint = position ? points.find(p => Math.abs(p.price - position.entry) < (maxPrice - minPrice) * 0.02) : null

    return {
      points,
      minPrice,
      maxPrice,
      priceRange,
      entryPoint,
      currentPrice,
      priceChange,
      pos: position,
    }
  }, [history, position, currentPrice, priceChange])

  if (!chartData) {
    return (
      <div className="chart-empty">
        <svg width={CHART_WIDTH} height={CHART_HEIGHT} viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}>
          <text x={CHART_WIDTH / 2} y={CHART_HEIGHT / 2} textAnchor="middle" fill="var(--text-dim)" fontSize="14" fontFamily="var(--font-body)">
            Esperando datos de precio...
          </text>
        </svg>
      </div>
    )
  }

  const { points, minPrice, maxPrice, entryPoint, currentPrice: cp, priceChange: pc, pos } = chartData
  const isPositive = pc >= 0
  const lineColor = isPositive ? '#22c55e' : '#ef4444'
  const fillColor = isPositive ? 'rgba(34, 197, 94, 0.12)' : 'rgba(239, 68, 68, 0.12)'

  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
  const areaD = `${pathD} L${points[points.length - 1].x} ${CHART_HEIGHT - PADDING.bottom} L${points[0].x} ${CHART_HEIGHT - PADDING.bottom} Z`

  const yTicks = 5
  const yLabels = Array.from({ length: yTicks }, (_, i) => {
    const price = maxPrice - (i / (yTicks - 1)) * (maxPrice - minPrice)
    const y = PADDING.top + (i / (yTicks - 1)) * (CHART_HEIGHT - PADDING.top - PADDING.bottom)
    return { price, y }
  })

  const xTicks = 6
  const xLabels = Array.from({ length: xTicks }, (_, i) => {
    const idx = Math.floor(i / (xTicks - 1) * (points.length - 1))
    return { x: points[idx].x, label: `${Math.floor((idx / (points.length - 1)) * 100)}%` }
  })

  return (
    <div className="price-chart-wrapper">
      <svg width={CHART_WIDTH} height={CHART_HEIGHT} viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} className="price-chart">
        <defs>
          <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={lineColor} stopOpacity="0.25" />
            <stop offset="100%" stopColor={lineColor} stopOpacity="0" />
          </linearGradient>
          <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={lineColor} stopOpacity="0.6" />
            <stop offset="100%" stopColor={lineColor} stopOpacity="1" />
          </linearGradient>
        </defs>

        <rect x={PADDING.left} y={PADDING.top}
              width={CHART_WIDTH - PADDING.left - PADDING.right}
              height={CHART_HEIGHT - PADDING.top - PADDING.bottom}
              fill="rgba(0,0,0,0.15)" rx={2} />

        {yLabels.map((tick, i) => (
          <g key={i}>
            <line x1={PADDING.left} y1={tick.y} x2={CHART_WIDTH - PADDING.right} y2={tick.y}
                  stroke="var(--border)" strokeWidth="0.5" strokeDasharray="2,4" />
            <text x={PADDING.left - 8} y={tick.y + 4} textAnchor="end"
                  fill="var(--text-dim)" fontSize="10" fontFamily="var(--font-mono)">
              ${tick.price.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </text>
          </g>
        ))}

        {xLabels.map((tick, i) => (
          <g key={i}>
            <line x1={tick.x} y1={PADDING.top} x2={tick.x} y2={CHART_HEIGHT - PADDING.bottom}
                  stroke="var(--border)" strokeWidth="0.5" strokeDasharray="2,4" opacity="0.3" />
            <text x={tick.x} y={CHART_HEIGHT - PADDING.bottom + 16} textAnchor="middle"
                  fill="var(--text-dim)" fontSize="9" fontFamily="var(--font-mono)">
              {tick.label}
            </text>
          </g>
        ))}

        <path d={areaD} fill="url(#areaGrad)" />
        <path d={pathD} fill="none" stroke="url(#lineGrad)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

        {entryPoint && (
          <g className="entry-marker">
            <line x1={entryPoint.x} y1={PADDING.top} x2={entryPoint.x} y2={CHART_HEIGHT - PADDING.bottom}
                  stroke="#e8a838" strokeWidth="1.5" strokeDasharray="4,4" opacity="0.7" />
            <circle cx={entryPoint.x} cy={entryPoint.y} r={6} fill="#e8a838" stroke="#060b14" strokeWidth="2" />
            <text x={entryPoint.x} y={entryPoint.y - 10} textAnchor="middle"
                  fill="#e8a838" fontSize="10" fontWeight="600" fontFamily="var(--font-mono)">
              ENTRY ${entryPoint.price.toLocaleString('en-US', { minimumFractionDigits: 0 })}
            </text>
          </g>
        )}

        {pos && (
          <g className="current-marker">
            <line x1={points[points.length - 1].x} y1={PADDING.top} x2={points[points.length - 1].x} y2={CHART_HEIGHT - PADDING.bottom}
                  stroke={lineColor} strokeWidth="1" strokeDasharray="2,2" opacity="0.5" />
            <circle cx={points[points.length - 1].x} cy={points[points.length - 1].y} r={5}
                    fill={lineColor} stroke="#060b14" strokeWidth={2} />
          </g>
        )}

        {pos && entryPoint && (
          <rect x={PADDING.left} y={entryPoint.y}
                width={points[points.length - 1].x - PADDING.left}
                height={Math.abs(entryPoint.y - (CHART_HEIGHT - PADDING.bottom))}
                fill={lineColor} fillOpacity="0.04" />
        )}
      </svg>

      <div className="chart-legend">
        <div className="legend-item">
          <span className="legend-dot" style={{ background: lineColor }} />
          <span>Precio actual: <strong>${cp.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong></span>
        </div>
        {pos && (
          <div className="legend-item">
            <span className="legend-dot" style={{ background: '#e8a838' }} />
            <span>Entrada: <strong>${pos.entry?.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong></span>
          </div>
        )}
        <div className="legend-item pnl-badge" style={{ color: pc >= 0 ? '#22c55e' : '#ef4444' }}>
          {pc >= 0 ? '▲' : '▼'} {Math.abs(pc).toFixed(2)}%
        </div>
      </div>
    </div>
  )
}