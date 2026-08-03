export default function SymbolCard({ symbol, price, signal, position, active, onClick }) {
  const priceNum = price || 0
  const sig = signal || {}
  const consensus = sig.consensus || 'HOLD'
  const isBuy = consensus === 'BUY'
  const isSell = consensus === 'SELL'

  return (
    <div className={`symbol-card ${active ? 'active' : ''} ${isBuy ? 'sig-buy' : isSell ? 'sig-sell' : ''}`} onClick={onClick}>
      <div className="symbol-card-top">
        <span className="symbol-card-name">{symbol.replace('USDT', '')}</span>
        {position && <span className="symbol-card-pos" title="Posición abierta" />}
      </div>
      <div className="symbol-card-price mono">${priceNum.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
      <div className="symbol-card-sig">
        {isBuy ? (
          <span className="sig-badge buy">COMPRA</span>
        ) : isSell ? (
          <span className="sig-badge sell">VENTA</span>
        ) : (
          <span className="sig-badge hold">—</span>
        )}
      </div>
    </div>
  )
}
