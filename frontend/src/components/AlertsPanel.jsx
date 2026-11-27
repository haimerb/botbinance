import { memo } from 'react'

const NIVELES = {
  critical: 'Crítica',
  warning: 'Aviso',
  info: 'Info',
}

function formatTime(ts) {
  if (!ts) return '—'
  const ms = ts < 1e12 ? ts * 1000 : ts
  return new Date(ms).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
}

function AlertsPanel({ alerts = [] }) {
  return (
    <div className="section glass alerts-section">
      <div className="section-header">
        <h2>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.7 21a2 2 0 0 1-3.4 0" />
          </svg>
          Alertas de monitoreo
        </h2>
      </div>
      {alerts.length === 0 ? (
        <div className="empty">Sin alertas recientes</div>
      ) : (
        <div className="alerts-list">
          {alerts.slice(0, 20).map((alert, index) => {
            const nivel = NIVELES[alert.severity] || alert.severity || 'Info'
            return (
              <div key={`${alert.fingerprint || alert.alertname}-${index}`} className="alert-item">
                <div className="alert-head">
                  <span className={`badge ${alert.severity === 'critical' ? 'stopped' : 'running'}`}>
                    {alert.status === 'resolved' ? 'Resuelta' : nivel}
                  </span>
                  <strong className="mono">{alert.alertname || 'Alerta'}</strong>
                  <span className="alert-time">{formatTime(alert.received_at)}</span>
                </div>
                {alert.summary && <div className="alert-summary">{alert.summary}</div>}
                {alert.description && <div className="alert-description">{alert.description}</div>}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default memo(AlertsPanel)
