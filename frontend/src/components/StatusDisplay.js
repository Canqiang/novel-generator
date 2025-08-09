import React from 'react';

const StatusDisplay = ({ status }) => {
  if (!status) return null;

  const getStatusColor = (s) => {
    const colors = {
      pending: 'text-yellow-600',
      outlining: 'text-blue-600',
      writing: 'text-purple-600',
      polishing: 'text-indigo-600',
      completed: 'text-green-600',
      failed: 'text-red-600',
    };
    return colors[s] || 'text-gray-600';
  };

  const getStatusText = (s) => {
    const texts = {
      pending: '等待处理',
      outlining: '生成大纲中',
      writing: '创作内容中',
      polishing: '润色优化中',
      completed: '生成完成',
      failed: '生成失败',
    };
    return texts[s] || '未知状态';
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">生成进度</h3>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(status.status)}`}>
          {getStatusText(status.status)}
        </span>
      </div>

      <div className="w-full bg-gray-200 rounded-full h-3">
        <div
          className="bg-gradient-to-r from-purple-600 to-blue-600 h-3 rounded-full transition-all duration-500"
          style={{ width: `${status.progress || 0}%` }}
        />
      </div>

      <p className="text-sm text-gray-600 mt-2">
        {status.current_stage || '准备中...'}
      </p>
    </div>
  );
};

export default StatusDisplay;

