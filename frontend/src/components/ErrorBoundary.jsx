import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="loading-screen">
          <div className="error-icon">!</div>
          <p>Algo salió mal</p>
          <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem', maxWidth: 400, textAlign: 'center' }}>
            {this.state.error?.message || 'Error desconocido'}
          </span>
          <button
            className="btn-ghost"
            style={{ marginTop: 12 }}
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload() }}
          >
            Recargar
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
