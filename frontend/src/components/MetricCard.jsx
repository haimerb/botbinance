export default function MetricCard({ title, value, sub, trend }) {
  return (
    <div className="metric glass">
      <div className="metric-label">{title}</div>
      <div className={`metric-value ${trend || ''}`}>{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  )
}
