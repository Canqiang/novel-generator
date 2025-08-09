
import React from 'react';
import { Loader2, Brain, Edit, FileText, CheckCircle } from 'lucide-react';

const Loading = ({ status, message, showAgentProgress = false }) => {
  const agents = [
    { id: 'planner', name: '策划师', icon: Brain, active: ['planning', 'outlining'] },
    { id: 'writer', name: '创作者', icon: Edit, active: ['writing'] },
    { id: 'editor', name: '编辑', icon: FileText, active: ['reviewing', 'polishing'] },
    { id: 'reviewer', name: '评审者', icon: CheckCircle, active: ['reviewing'] }
  ];

  const getAgentStatus = (agent) => {
    if (!status) return 'waiting';
    if (agent.active.includes(status.status)) return 'active';
    return 'waiting';
  };

  return (
    <div className="flex items-center justify-center p-8">
      <div className="text-center">
        {/* 主要加载动画 */}
        <div className="relative mb-6">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto"></div>
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className="h-6 w-6 text-purple-600 animate-pulse" />
          </div>
        </div>

        {/* 状态信息 */}
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          {message || '处理中...'}
        </h3>

        {status && (
          <div className="mb-4">
            <div className="w-64 bg-gray-200 rounded-full h-2 mx-auto">
              <div
                className="bg-gradient-to-r from-purple-600 to-blue-600 h-2 rounded-full transition-all duration-500"
                style={{ width: `${status.progress || 0}%` }}
              />
            </div>
            <p className="text-sm text-gray-600 mt-2">
              {status.progress || 0}% 完成
            </p>
          </div>
        )}

        {/* Agent协作进度 */}
        {showAgentProgress && (
          <div className="mt-6">
            <p className="text-sm text-gray-600 mb-3">AI团队协作中</p>
            <div className="flex justify-center space-x-4">
              {agents.map((agent) => {
                const AgentIcon = agent.icon;
                const agentStatus = getAgentStatus(agent);

                return (
                  <div key={agent.id} className="text-center">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-1 transition-all ${
                      agentStatus === 'active' 
                        ? 'bg-purple-600 text-white animate-pulse' 
                        : 'bg-gray-200 text-gray-500'
                    }`}>
                      <AgentIcon className="h-5 w-5" />
                    </div>
                    <span className={`text-xs ${
                      agentStatus === 'active' ? 'text-purple-600 font-medium' : 'text-gray-500'
                    }`}>
                      {agent.name}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 提示文本 */}
        <p className="text-sm text-gray-500 mt-4">
          请耐心等待，AI正在为您精心创作...
        </p>
      </div>
    </div>
  );
};

export default Loading;