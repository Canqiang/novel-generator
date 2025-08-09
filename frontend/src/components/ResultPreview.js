import React from 'react';
import { Download } from 'lucide-react';

const ResultPreview = ({ result, handleExport }) => {
  if (!result) return null;

  return (
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
  );
};

export default ResultPreview;

