
import React, { useState, useRef } from 'react';
import { Upload, File, X, CheckCircle } from 'lucide-react';

const FileUpload = ({ onFileSelect, accept = '*', maxSize = 10 * 1024 * 1024, multiple = false }) => {
  const [dragOver, setDragOver] = useState(false);
  const [files, setFiles] = useState([]);
  const fileInputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    handleFiles(droppedFiles);
  };

  const handleFiles = (selectedFiles) => {
    const validFiles = selectedFiles.filter(file => {
      if (file.size > maxSize) {
        window.showToast && window.showToast(`文件 ${file.name} 超过大小限制`, 'error');
        return false;
      }
      return true;
    });

    if (!multiple && validFiles.length > 1) {
      validFiles.splice(1);
    }

    setFiles(prev => multiple ? [...prev, ...validFiles] : validFiles);
    onFileSelect(multiple ? [...files, ...validFiles] : validFiles[0]);
  };

  const removeFile = (index) => {
    const newFiles = files.filter((_, i) => i !== index);
    setFiles(newFiles);
    onFileSelect(multiple ? newFiles : null);
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="w-full">
      {/* 拖拽上传区域 */}
      <div
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${
          dragOver ? 'border-purple-500 bg-purple-50' : 'border-gray-300 hover:border-purple-400'
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={(e) => handleFiles(Array.from(e.target.files))}
          className="hidden"
        />

        <Upload className="h-8 w-8 text-gray-400 mx-auto mb-2" />
        <p className="text-gray-600 mb-1">
          点击上传或拖拽文件到这里
        </p>
        <p className="text-xs text-gray-500">
          最大文件大小: {formatFileSize(maxSize)}
        </p>
      </div>

      {/* 文件列表 */}
      {files.length > 0 && (
        <div className="mt-4 space-y-2">
          {files.map((file, index) => (
            <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-3">
                <File className="h-5 w-5 text-gray-500" />
                <div>
                  <p className="text-sm font-medium text-gray-900">{file.name}</p>
                  <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <CheckCircle className="h-5 w-5 text-green-500" />
                <button
                  onClick={() => removeFile(index)}
                  className="text-gray-400 hover:text-red-500 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FileUpload;