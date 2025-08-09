import React from 'react';
import { AlertCircle, Sparkles, Loader2, ChevronRight } from 'lucide-react';

const GeneratorForm = ({
  theme,
  setTheme,
  genre,
  setGenre,
  style,
  setStyle,
  handleGenerate,
  loading,
  status,
  error,
  templates,
  handleUseTemplate,
}) => {
  return (
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
  );
};

export default GeneratorForm;

