import { Component, ReactNode } from 'react';

interface Props { children: ReactNode; fallback?: ReactNode; }
interface State { hasError: boolean; }

export class ErrorBoundary extends Component<Props, State> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  componentDidCatch(error: Error) { console.error('[ErrorBoundary]', error); }
  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="flex flex-col items-center justify-center p-8 text-center gap-3">
          <span className="text-2xl">⚠️</span>
          <p className="text-sm font-medium text-foreground">Something went wrong loading this section.</p>
          <p className="text-xs text-muted-foreground">Check your connection and refresh the page.</p>
          <button className="text-xs underline text-muted-foreground" onClick={() => this.setState({ hasError: false })}>Try again</button>
        </div>
      );
    }
    return this.props.children;
  }
}
