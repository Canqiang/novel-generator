import React, { useState, useEffect, useCallback } from 'react';
import { AlertCircle, BookOpen, Download, Loader2, Sparkles, ChevronRight, Clock, FileText, TrendingUp } from 'lucide-react';

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

  // 获取状态颜色
  const getStatusColor = (status) => {
    const colors = {
      pending: 'text-yellow-600',
      outlining: 'text-blue-600',
      writing: 'text-purple-600',
      polishing: 'text-indigo-600',
      completed: 'text-green-600',
      failed: 'text-red-600',
    };
    return colors[status] || 'text-gray-600';
  };

  // 获取状态文本
  const getStatusText = (status) => {
    const texts = {
      pending: '等待处理',
      outlining: '生成大纲中',
      writing: '创作内容中',
      polishing: '润色优化中',
      completed: '生成完成',
      failed: '生成失败',
    };
    return texts[status] || '未知状态';
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
            <div className="lg:col-span-1">
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h2 className="text-lg font-semibold mb-4">创作设置</h2>

                {/* 主题输入 */}
                <div className="mb-6">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    故事主题或灵感
                  </label>
                  <textarea
                    value={theme}
                    onChange={(e) => setTheme(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    rows="4"
                    placeholder="例如：一个程序员发现自己开发的AI产生了自我意识..."
                  />
                </div>

                {/* 类型选择 */}
                <div className="mb-6">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    故事类型
                  </label>
                  <select
                    value={genre}
                    onChange={(e) => setGenre(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="">自动判断</option>
                    <option value="urban_romance">都市情感</option>
                    <option value="mystery">悬疑推理</option>
                    <option value="scifi">科幻</option>
                    <option value="workplace">职场成长</option>
                    <option value="fantasy">奇幻</option>
                  </select>
                </div>

                {/* 风格选择 */}
                <div className="mb-6">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    写作风格
                  </label>
                  <select
                    value={style}
                    onChange={(e) => setStyle(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="知乎风格">知乎风格</option>
                    <option value="轻松幽默">轻松幽默</option>
                    <option value="文艺细腻">文艺细腻</option>
                    <option value="紧张刺激">紧张刺激</option>
                  </select>
                </div>

                {/* 生成按钮 */}
                <button
                  onClick={handleGenerate}
                  disabled={loading || (status && status.status !== 'completed' && status.status !== 'failed')}
                  className="w-full bg-gradient-to-r from-purple-600 to-blue-600 text-white py-3 rounded-lg font-medium hover:from-purple-700 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 transform hover:scale-105"
                >
                  {loading ? (
                    <span className="flex items-center justify-center">
                      <Loader2 className="animate-spin mr-2" />
                      处理中...
                    </span>
                  ) : (
                    <span className="flex items-center justify-center">
                      <Sparkles className="mr-2" />
                      开始创作
                    </span>
                  )}
                </button>

                {/* 错误提示 */}
                {error && (
                  <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                    <div className="flex items-start">
                      <AlertCircle className="h-5 w-5 text-red-500 mr-2 flex-shrink-0 mt-0.5" />
                      <p className="text-sm text-red-700">{error}</p>
                    </div>
                  </div>
                )}
              </div>

              {/* 模板推荐 */}
              <div className="bg-white rounded-xl shadow-lg p-6 mt-6">
                <h3 className="text-lg font-semibold mb-4">灵感模板</h3>
                <div className="space-y-3">
                  {templates.map((template) => (
                    <div
                      key={template.id}
                      className="p-3 border border-gray-200 rounded-lg hover:border-purple-300 hover:bg-purple-50 cursor-pointer transition-colors"
                      onClick={() => handleUseTemplate(template)}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="font-medium text-gray-900">{template.name}</h4>
                          <p className="text-sm text-gray-600 mt-1">{template.description}</p>
                        </div>
                        <ChevronRight className="h-5 w-5 text-gray-400" />
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {template.keywords.map((keyword) => (
                          <span
                            key={keyword}
                            className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded"
                          >
                            {keyword}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 右侧：预览区域 */}
            <div className="lg:col-span-2">
              {/* 进度显示 */}
              {status && (
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
              )}

              {/* 结果显示 */}
              {result && (
                <div className="bg-white rounded-xl shadow-lg p-6">
                  <div className="flex items-center justify-between mb-6">
                    <div>
                      <h2 className="text-2xl font-bold text-gray-900">{result.title}</h2>
                      <p className="text-gray-600 mt-1">{result.author_note}</p>
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => handleExport('markdown')}
                        className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 flex items-center"
                      >
                        <Download className="h-4 w-4 mr-2" />
                        Markdown
                      </button>
                      <button
                        onClick={() => handleExport('zhihu')}
                        className="px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 flex items-center"
                      >
                        <Download className="h-4 w-4 mr-2" />
                        知乎格式
                      </button>
                    </div>
                  </div>

                  {/* 元数据 */}
                  <div className="grid grid-cols-3 gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
                    <div>
                      <p className="text-sm text-gray-600">总字数</p>
                      <p className="text-lg font-semibold">{result.metadata.total_words}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-600">章节数</p>
                      <p className="text-lg font-semibold">{result.chapters.length}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-600">Token消耗</p>
                      <p className="text-lg font-semibold">{result.metadata.total_tokens}</p>
                    </div>
                  </div>

                  {/* 章节预览 */}
                  <div className="space-y-4">
                    <h3 className="text-lg font-semibold mb-3">章节预览</h3>
                    {result.chapters.map((chapter, index) => (
                      <details key={index} className="border border-gray-200 rounded-lg">
                        <summary className="p-4 cursor-pointer hover:bg-gray-50 font-medium">
                          {chapter.title}
                        </summary>
                        <div className="p-4 border-t border-gray-200">
                          <div className="prose max-w-none">
                            {chapter.content.substring(0, 500)}...
                          </div>
                        </div>
                      </details>
                    ))}
                  </div>
                </div>
              )}

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