
import React from 'react';
import Modal from './Modal';
import { AlertTriangle } from 'lucide-react';

const ConfirmDialog = ({ isOpen, onClose, onConfirm, title, message, confirmText = '确认', cancelText = '取消', type = 'warning' }) => {
  const getIcon = () => {
    switch (type) {
      case 'danger': return <AlertTriangle className="h-6 w-6 text-red-600" />;
      case 'warning': return <AlertTriangle className="h-6 w-6 text-yellow-600" />;
      default: return <AlertTriangle className="h-6 w-6 text-blue-600" />;
    }
  };

  const getConfirmButtonStyle = () => {
    switch (type) {
      case 'danger': return 'bg-red-600 hover:bg-red-700 text-white';
      case 'warning': return 'bg-yellow-600 hover:bg-yellow-700 text-white';
      default: return 'bg-blue-600 hover:bg-blue-700 text-white';
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} size="sm">
      <div className="text-center">
        <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-gray-100 mb-4">
          {getIcon()}
        </div>

        <p className="text-gray-600 mb-6">{message}</p>

        <div className="flex space-x-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
          >
            {cancelText}
          </button>
          <button
            onClick={() => {
              onConfirm();
              onClose();
            }}
            className={`flex-1 px-4 py-2 rounded-lg transition-colors ${getConfirmButtonStyle()}`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </Modal>
  );
};

export default ConfirmDialog;