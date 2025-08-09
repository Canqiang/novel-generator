
import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({
      error: error,
      errorInfo: errorInfo
    });

    // 可以将错误日志发送到服务端
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6 text-center">
            <AlertTriangle className="h-16 w-16 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              页面出现错误
            </h2>
            <p className="text-gray-600 mb-6">
              很抱歉，页面遇到了一些问题。请尝试刷新页面或联系技术支持。
            </p>

            {process.env.NODE_ENV === 'development' && (
              <div className="text-left bg-gray-100 p-3 rounded mb-4 text-sm">
                <strong>错误详情:</strong>
                <pre className="mt-2 text-xs overflow-auto">
                  {this.state.error && this.state.error.toString()}
                  {this.state.errorInfo.componentStack}
                </pre>
              </div>
            )}

            <div className="flex space-x-3">
              <button
                onClick={this.handleRetry}
                className="flex-1 bg-purple-600 text-white py-2 px-4 rounded-lg hover:bg-purple-700 transition-colors flex items-center justify-center"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                重试
              </button>
              <button
                onClick={() => window.location.reload()}
                className="flex-1 bg-gray-600 text-white py-2 px-4 rounded-lg hover:bg-gray-700 transition-colors"
              >
                刷新页面
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;