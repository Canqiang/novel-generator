
import React, { useState, useEffect } from 'react';
import { CheckCircle, AlertCircle, Info, X } from 'lucide-react';

const Toast = ({ message, type = 'info', duration = 3000, onClose }) => {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false);
      setTimeout(onClose, 300); // 等待动画完成
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onClose]);

  const getIcon = () => {
    switch (type) {
      case 'success': return <CheckCircle className="h-5 w-5" />;
      case 'error': return <AlertCircle className="h-5 w-5" />;
      case 'info': return <Info className="h-5 w-5" />;
      default: return <Info className="h-5 w-5" />;
    }
  };

  const getStyles = () => {
    switch (type) {
      case 'success': return 'bg-green-500 text-white';
      case 'error': return 'bg-red-500 text-white';
      case 'info': return 'bg-blue-500 text-white';
      default: return 'bg-gray-500 text-white';
    }
  };

  return (
    <div className={`fixed top-4 right-4 z-50 transition-all duration-300 ${
      isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-full'
    }`}>
      <div className={`rounded-lg shadow-lg p-4 flex items-center space-x-3 min-w-[300px] ${getStyles()}`}>
        {getIcon()}
        <span className="flex-1">{message}</span>
        <button
          onClick={() => {
            setIsVisible(false);
            setTimeout(onClose, 300);
          }}
          className="hover:opacity-75"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

// Toast管理器
export const ToastManager = () => {
  const [toasts, setToasts] = useState([]);

  const addToast = (message, type = 'info', duration = 3000) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type, duration }]);
  };

  const removeToast = (id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  };

  // 暴露全局方法
  window.showToast = addToast;

  return (
    <>
      {toasts.map(toast => (
        <Toast
          key={toast.id}
          message={toast.message}
          type={toast.type}
          duration={toast.duration}
          onClose={() => removeToast(toast.id)}
        />
      ))}
    </>
  );
};

export default Toast;