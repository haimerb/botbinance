export default function TradeTable({ trades, tradeLimit, onLimitChange }) {
  if (trades.length === 0) {
    return (
      <div className="empty">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.3">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
        <p>No hay operaciones registradas</p>
        <span>Inicia el bot para comenzar a operar</span>
      </div>
    )
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Hora</th>
            <th>Símbolo</th>
            <th>Tipo</th>
            <th>Lado</th>
            <th>Precio</th>
            <th>Cantidad</th>
            <th>P&L</th>
          </tr>
        </thead>
        <tbody>
          {trades.slice().reverse().map((t) => (
            <tr key={t.id || t.timestamp} className={t.pnl_pct != null ? (t.pnl_pct >= 0 ? 'row-win' : 'row-loss') : ''}>
              <td className="dim">{t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : '--'}</td>
              <td><span className="mono">{t.symbol || 'BTCUSDT'}</span></td>
              <td><span className={`tag ${t.type}`}>{t.type === 'entry' ? 'ENTRADA' : t.type === 'exit' ? 'SALIDA' : t.type === 'stop_loss' ? 'STOP LOSS' : t.type === 'take_profit' ? 'TAKE PROFIT' : t.type}</span></td>
              <td className={t.side === 'BUY' ? 'green' : 'red'}>{t.side}</td>
              <td className="mono">${Number(t.price).toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
              <td className="mono">{t.qty}</td>
              <td className={`mono ${t.pnl_pct != null ? (t.pnl_pct >= 0 ? 'green' : 'red') : ''}`}>
                {t.pnl_pct != null ? `${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct}%` : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
