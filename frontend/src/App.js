import React, { useState, useEffect } from 'react';
import { BookOpen, Sparkles, Clock, FileText, TrendingUp } from 'lucide-react';
import GeneratorForm from './components/GeneratorForm';
import StatusDisplay from './components/StatusDisplay';
import ResultPreview from './components/ResultPreview';

const API_BASE = 'http://localhost:8000/api';

// 主应用组件
function NovelGenerator() {
  const [theme, setTheme] = useState('');
  const [genre, setGenre] = useState('');
  const [style, setStyle] = useState('知乎风格');
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [activeTab, setActiveTab] = useState('generator');
  const [stats, setStats] = useState(null);

  // 加载模板
  useEffect(() => {
    fetchTemplates();
    fetchStats();
  }, []);

  const fetchTemplates = async () => {
    try {
      const response = await fetch(`${API_BASE}/templates`);
      const data = await response.json();
      setTemplates(data);
    } catch (err) {
      console.error('加载模板失败:', err);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE}/stats`);
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error('加载统计失败:', err);
    }
  };

  // 轮询任务状态
  useEffect(() => {
    if (taskId && status?.status !== 'completed' && status?.status !== 'failed') {
      const interval = setInterval(async () => {
        try {
          const response = await fetch(`${API_BASE}/novel/status/${taskId}`);
          const data = await response.json();
          setStatus(data);

          if (data.status === 'completed') {
            const resultResponse = await fetch(`${API_BASE}/novel/result/${taskId}`);
            const resultData = await resultResponse.json();
            setResult(resultData);
            clearInterval(interval);
          } else if (data.status === 'failed') {
            setError(data.error);
            clearInterval(interval);
          }
        } catch (err) {
          console.error('状态查询失败:', err);
        }
      }, 2000);

      return () => clearInterval(interval);
    }
  }, [taskId, status]);

  // 提交生成任务
  const handleGenerate = async () => {
    if (!theme.trim()) {
      setError('请输入故事主题');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${API_BASE}/novel/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          theme,
          genre: genre || null,
          style,
          word_count: 30000,
          chapter_count: 12,
        }),
      });

      const data = await response.json();
      setTaskId(data.task_id);
      setStatus({ status: 'pending', progress: 0 });
    } catch (err) {
      setError('生成请求失败：' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // 导出小说
  const handleExport = async (format) => {
    if (!taskId || !result) return;

    try {
      const response = await fetch(`${API_BASE}/novel/export/${taskId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ format }),
      });

      const data = await response.json();

      // 创建下载
      const blob = new Blob([JSON.stringify(data.content)], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = data.filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('导出失败：' + err.message);
    }
  };

  // 使用模板
  const handleUseTemplate = (template) => {
    setSelectedTemplate(template);
    setTheme(template.example);
    setGenre(template.id);
  };



  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50">
      {/* 头部 */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <BookOpen className="h-8 w-8 text-purple-600 mr-3" />
              <h1 className="text-2xl font-bold text-gray-900">AI小说创作系统</h1>
              <span className="ml-3 px-2 py-1 text-xs bg-purple-100 text-purple-700 rounded-full">
                Beta
              </span>
            </div>
            <nav className="flex space-x-4">
              <button
                onClick={() => setActiveTab('generator')}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  activeTab === 'generator'
                    ? 'bg-purple-100 text-purple-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                创作中心
              </button>
              <button
                onClick={() => setActiveTab('library')}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  activeTab === 'library'
                    ? 'bg-purple-100 text-purple-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                作品库
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* 统计信息 */}
      {stats && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center">
                <FileText className="h-8 w-8 text-blue-500 mr-3" />
                <div>
                  <p className="text-sm text-gray-600">总创作数</p>
                  <p className="text-2xl font-bold">{stats.total_tasks}</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center">
                <TrendingUp className="h-8 w-8 text-green-500 mr-3" />
                <div>
                  <p className="text-sm text-gray-600">成功率</p>
                  <p className="text-2xl font-bold">{stats.success_rate}</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center">
                <Clock className="h-8 w-8 text-yellow-500 mr-3" />
                <div>
                  <p className="text-sm text-gray-600">处理中</p>
                  <p className="text-2xl font-bold">{stats.pending}</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center">
                <Sparkles className="h-8 w-8 text-purple-500 mr-3" />
                <div>
                  <p className="text-sm text-gray-600">已完成</p>
                  <p className="text-2xl font-bold">{stats.completed}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'generator' && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* 左侧：输入区域 */}
            <GeneratorForm
              theme={theme}
              setTheme={setTheme}
              genre={genre}
              setGenre={setGenre}
              style={style}
              setStyle={setStyle}
              handleGenerate={handleGenerate}
              loading={loading}
              status={status}
              error={error}
              templates={templates}
              handleUseTemplate={handleUseTemplate}
            />

            {/* 右侧：预览区域 */}
            <div className="lg:col-span-2">
              {/* 进度显示 */}
              <StatusDisplay status={status} />
              {/* 结果显示 */}
              <ResultPreview result={result} handleExport={handleExport} />
              {/* 空状态 */}
              {!status && !result && (
                <div className="bg-white rounded-xl shadow-lg p-12 text-center">
                  <BookOpen className="h-16 w-16 text-gray-300 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    准备开始创作
                  </h3>
                  <p className="text-gray-600 max-w-md mx-auto">
                    输入你的故事灵感，AI将为你创作一部精彩的中篇小说。
                    整个过程大约需要10-15分钟。
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'library' && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="bg-white rounded-xl shadow-lg p-8 text-center">
            <BookOpen className="h-16 w-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              作品库功能开发中
            </h3>
            <p className="text-gray-600">
              这里将展示你所有的创作历史
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default NovelGenerator;
