import React from 'react'
import { RefreshCcw, Bug } from 'lucide-react'
import { UI_BUILD_ID } from '../lib/buildInfo'

type Props = {
  children: React.ReactNode
}

type State = {
  hasError: boolean
  message: string
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error: unknown): State {
    const msg =
      error instanceof Error
        ? `${error.name}: ${error.message}`
        : typeof error === 'string'
          ? error
          : 'Unknown UI error'
    return { hasError: true, message: msg }
  }

  componentDidCatch(error: unknown) {
    // Keep console visibility for debugging.
    // eslint-disable-next-line no-console
    console.error('[UI ErrorBoundary]', error)
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="min-h-screen bg-[var(--color-neo-bg)] text-[var(--color-neo-text)] flex items-center justify-center p-6">
        <div className="neo-card p-6 max-w-xl w-full">
          <div className="flex items-start gap-3">
            <div
              className="bg-[var(--color-neo-danger)] border-3 border-[var(--color-neo-border)] p-2"
              style={{ boxShadow: 'var(--shadow-neo-sm)' }}
            >
              <Bug size={18} className="text-white" />
            </div>
            <div className="flex-1">
              <div className="font-display font-bold uppercase">UI crashed</div>
              <div className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                This is usually a stale build or a bad setting. Hit refresh; if it keeps happening, open Diagnostics →
                copy the debug info and paste it into an issue.
              </div>
            </div>
          </div>

          <div className="neo-card p-3 mt-4 border-3 border-[var(--color-neo-danger)] text-sm text-[var(--color-neo-danger)]">
            {this.state.message}
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs font-mono text-[var(--color-neo-text-muted)]">UI build: {UI_BUILD_ID}</div>
            <button
              className="neo-btn neo-btn-primary text-sm"
              onClick={() => window.location.reload()}
              title="Hard refresh"
            >
              <RefreshCcw size={18} />
              Refresh
            </button>
          </div>
        </div>
      </div>
    )
  }
}

