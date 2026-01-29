import { Component, ErrorInfo, ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

/**
 * Global Error Boundary Component
 *
 * Catches JavaScript errors anywhere in the child component tree,
 * logs those errors, and displays a fallback UI instead of crashing
 * the whole app with a blank page.
 *
 * This helps diagnose issues like #49 (Windows blank page after clean install).
 */
export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  }

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
    this.setState({ errorInfo })

    // Log to console in a format that's easy to copy for bug reports
    console.error('=== ERROR BOUNDARY REPORT ===')
    console.error('Error:', error.message)
    console.error('Stack:', error.stack)
    console.error('Component Stack:', errorInfo.componentStack)
    console.error('=== END REPORT ===')
  }

  private handleReload = () => {
    window.location.reload()
  }

  private handleClearAndReload = () => {
    try {
      localStorage.clear()
      sessionStorage.clear()
    } catch {
      // Ignore storage errors
    }
    window.location.reload()
  }

  public render() {
    if (this.state.hasError) {
      // Custom fallback UI
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="min-h-screen bg-gray-100 dark:bg-gray-900 flex items-center justify-center p-4">
          <div 
            className="max-w-2xl w-full bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6"
            role="alert"
            aria-live="assertive"
          >
            <h1 className="text-2xl font-bold text-red-600 dark:text-red-400 mb-4">
              Something went wrong
            </h1>

            <p className="text-gray-600 dark:text-gray-300 mb-4">
              AutoCoder encountered an unexpected error. This information can help diagnose the issue:
            </p>

            <div className="bg-gray-100 dark:bg-gray-900 rounded p-4 mb-4 overflow-auto max-h-64">
              <pre className="text-sm text-red-600 dark:text-red-400 whitespace-pre-wrap">
                {this.state.error?.message || 'Unknown error'}
              </pre>
              {this.state.error?.stack && (
                <pre className="text-xs text-gray-500 dark:text-gray-400 mt-2 whitespace-pre-wrap">
                  {this.state.error.stack}
                </pre>
              )}
            </div>

            <div className="flex gap-3">
              <button
                onClick={this.handleReload}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
              >
                Reload Page
              </button>
              <button
                onClick={this.handleClearAndReload}
                className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
              >
                Clear Cache & Reload
              </button>
            </div>

            <p className="text-sm text-gray-500 dark:text-gray-400 mt-4">
              If this keeps happening, please report the error at{' '}
              <a
                href="https://github.com/leonvanzyl/autocoder/issues"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500 hover:underline"
              >
                GitHub Issues
              </a>
            </p>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
