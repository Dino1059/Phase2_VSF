import { Component, type ReactNode, type ErrorInfo } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('DataTrust OS UI Exception:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-screen bg-background text-text-primary p-6 text-center">
          <div className="w-14 h-14 rounded-full bg-status-error/10 text-status-error flex items-center justify-center mb-4">
            <AlertTriangle className="w-7 h-7" />
          </div>
          <h2 className="text-lg font-semibold mb-2">DataTrust OS UI Recovered from an Error</h2>
          <p className="text-xs text-text-muted max-w-md mb-4 font-mono bg-surface p-3 rounded border border-border">
            {this.state.error?.message || 'An unexpected rendering error occurred.'}
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            className="flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-agent-orchestrator hover:bg-agent-orchestrator/80 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Reload Workspace
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
