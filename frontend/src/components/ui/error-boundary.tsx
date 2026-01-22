import React, { Component, ErrorInfo, ReactNode } from "react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { AlertTriangle, RefreshCw, Home, Bug } from "lucide-react";
import { cn } from "@/lib/utils";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  className?: string;
  variant?: "full" | "section" | "inline";
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    this.props.onError?.(error, errorInfo);
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleGoHome = () => {
    window.location.href = "/";
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const { variant = "section" } = this.props;

      if (variant === "inline") {
        return (
          <div className={cn("flex items-center gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/20", this.props.className)}>
            <AlertTriangle className="w-4 h-4 text-destructive flex-shrink-0" />
            <span className="text-sm text-destructive">Something went wrong</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={this.handleRetry}
              className="ml-auto h-7 text-xs"
            >
              <RefreshCw className="w-3 h-3 mr-1" />
              Retry
            </Button>
          </div>
        );
      }

      return (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className={cn(
            "flex flex-col items-center justify-center text-center p-8",
            variant === "full" && "min-h-screen bg-background",
            variant === "section" && "py-12",
            this.props.className
          )}
        >
          {/* Error Icon */}
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 200, delay: 0.1 }}
            className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mb-6"
          >
            <AlertTriangle className="w-8 h-8 text-destructive" />
          </motion.div>

          {/* Title */}
          <h2 className="text-xl font-semibold text-foreground mb-2">
            {variant === "full" ? "Something Went Wrong" : "Oops! An error occurred"}
          </h2>

          {/* Description */}
          <p className="text-sm text-muted-foreground max-w-md mb-6">
            {variant === "full"
              ? "We're sorry, but something unexpected happened. Please try again or return to the home page."
              : "This section couldn't be loaded. Try refreshing or check back later."}
          </p>

          {/* Error details (collapsible in development) */}
          {process.env.NODE_ENV === "development" && this.state.error && (
            <details className="mb-6 text-left w-full max-w-md">
              <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground flex items-center gap-1">
                <Bug className="w-3 h-3" />
                Error Details
              </summary>
              <pre className="mt-2 p-3 rounded-lg bg-muted text-xs overflow-auto max-h-32">
                {this.state.error.message}
                {this.state.errorInfo?.componentStack && (
                  <>
                    {"\n\nComponent Stack:"}
                    {this.state.errorInfo.componentStack}
                  </>
                )}
              </pre>
            </details>
          )}

          {/* Action buttons */}
          <div className="flex gap-3">
            <Button onClick={this.handleRetry} className="gap-2">
              <RefreshCw className="w-4 h-4" />
              Try Again
            </Button>
            {variant === "full" && (
              <Button variant="outline" onClick={this.handleGoHome} className="gap-2">
                <Home className="w-4 h-4" />
                Go Home
              </Button>
            )}
          </div>
        </motion.div>
      );
    }

    return this.props.children;
  }
}

// Hook for functional component error handling
export function useErrorHandler() {
  const [error, setError] = React.useState<Error | null>(null);

  const resetError = () => setError(null);

  const handleError = (error: Error) => {
    console.error("Error caught:", error);
    setError(error);
  };

  return { error, handleError, resetError };
}

// Async error boundary wrapper
interface AsyncBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  loadingFallback?: ReactNode;
  isLoading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
  className?: string;
}

export function AsyncBoundary({
  children,
  fallback,
  loadingFallback,
  isLoading = false,
  error = null,
  onRetry,
  className,
}: AsyncBoundaryProps) {
  if (isLoading && loadingFallback) {
    return <>{loadingFallback}</>;
  }

  if (error) {
    if (fallback) return <>{fallback}</>;

    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className={cn("flex flex-col items-center justify-center py-8 text-center", className)}
      >
        <div className="w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center mb-4">
          <AlertTriangle className="w-6 h-6 text-destructive" />
        </div>
        <p className="text-sm text-muted-foreground mb-4">
          Failed to load content. Please try again.
        </p>
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry} className="gap-2">
            <RefreshCw className="w-4 h-4" />
            Retry
          </Button>
        )}
      </motion.div>
    );
  }

  return <>{children}</>;
}
