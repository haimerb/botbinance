import { memo } from 'react'

function formatMoney(value) {
  const number = Number(value) || 0
  return `${number >= 0 ? '+' : '-'}$${Math.abs(number).toLocaleString('en-US', {
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  })}`
}

function formatRate(value) {
  const number = Number(value) || 0
  return `${(number * 100).toFixed(4)}%`
}

function formatScan(value) {
  if (!value) return '--'
  const ms = value < 1e12 ? value * 1000 : value
  return new Date(ms).toLocaleTimeString()
}

function FundingPanel({ funding, error, onStart, onStop }) {
  const status = funding?.status || 'stopped'
  const running = status === 'running'
  const opportunities = funding?.opportunities || []
  const position = funding?.position || null
  const accounting = funding?.accounting || {}
  const gate = funding?.gate || {}
  const net = Number(accounting.net) || 0

  return (
    <section className="section glass funding-section">
      <div className="section-header">
        <h2>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 3v18h18"/>
            <path d="M7 16l4-4 4 4 4-4"/>
          </svg>
          Arbitraje de Funding
        </h2>
        <div className="section-header-right">
          <span className={`badge ${running ? 'running' : 'stopped'}`}>
            <span className="badge-dot" />
            {running ? 'Activo' : 'Detenido'}
          </span>
          <button className="btn-primary btn-icon" onClick={onStart} disabled={running}>
            Iniciar
          </button>
          <button className="btn-danger btn-icon" onClick={onStop} disabled={!running}>
            Detener
          </button>
        </div>
      </div>

      {error && <div className="form-error funding-error">{error}</div>}
      {funding?.last_error && (
        <div className="form-error funding-error">{funding.last_error}</div>
      )}

      <div className="funding-summary">
        <div className="stat-item">
          <span className="stat-label">Ciclos</span>
          <span className="stat-value">{funding?.cycles ?? 0}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Último scan</span>
          <span className="stat-value">{formatScan(funding?.last_scan)}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Persistencia</span>
          <span className={`stat-value ${gate.persistence_trained ? 'green' : ''}`}>
            {gate.persistence_trained ? 'Entrenada' : 'Pendiente'}
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Liquidaciones</span>
          <span className="stat-value">{gate.liquidation_enabled ? 'Activas' : 'Off'}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">P&L neto</span>
          <span className={`stat-value ${net >= 0 ? 'green' : 'red'}`}>{formatMoney(net)}</span>
        </div>
      </div>

      {position && (
        <div className="funding-position">
          <span className="funding-position-symbol">{position.symbol}</span>
          <span className="mono">Qty {position.quantity}</span>
          <span className="mono">Funding {formatRate(position.funding_rate)}</span>
          <span className={`funding-tag ${position.is_hedged ? 'ok' : 'bad'}`}>
            {position.is_hedged ? 'Cubierta' : 'Sin cubrir'}
          </span>
        </div>
      )}

      <div className="funding-opps">
        <div className="funding-opps-title">
          Oportunidades <span className="count">{opportunities.length}</span>
        </div>
        {opportunities.length === 0 ? (
          <div className="empty funding-empty">
            <span>Sin oportunidades en el último escaneo</span>
          </div>
        ) : (
          <div className="funding-opps-list">
            {opportunities.map((opportunity) => (
              <div className="funding-opp" key={opportunity.symbol}>
                <span className="mono funding-opp-symbol">{opportunity.symbol}</span>
                <span className="mono">{Number(opportunity.annual_net_pct || 0).toFixed(2)}% neto</span>
                <span className="mono">Base {Number(opportunity.basis_pct || 0).toFixed(3)}%</span>
                <span className="mono">
                  Liq {Number(opportunity.liquidation_pressure || 0).toFixed(3)}
                </span>
                <span className={`funding-tag ${opportunity.gate_allowed ? 'ok' : 'bad'}`}>
                  {opportunity.gate_reason || (opportunity.gate_allowed ? 'ok' : 'rechazado')}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

export default memo(FundingPanel)
