import React, { useState, useRef, useEffect } from 'react';
import { Search, X } from 'lucide-react';

const SearchBox = ({
  placeholder = '搜索...',
  onSearch,
  onClear,
  suggestions = [],
  showSuggestions = false,
  debounceDelay = 300
}) => {
  const [query, setQuery] = useState('');
  const [showSuggestionList, setShowSuggestionList] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const searchRef = useRef(null);
  const suggestionsRef = useRef(null);

  // 防抖搜索
  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.trim()) {
        onSearch && onSearch(query);
      }
    }, debounceDelay);

    return () => clearTimeout(timer);
  }, [query, debounceDelay, onSearch]);

  // 处理键盘事件
  const handleKeyDown = (e) => {
    if (!showSuggestionList || suggestions.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev =>
          prev < suggestions.length - 1 ? prev + 1 : prev
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => prev > 0 ? prev - 1 : -1);
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0) {
          setQuery(suggestions[selectedIndex]);
          setShowSuggestionList(false);
        }
        break;
      case 'Escape':
        setShowSuggestionList(false);
        setSelectedIndex(-1);
        break;
    }
  };

  // 清空搜索
  const handleClear = () => {
    setQuery('');
    setShowSuggestionList(false);
    setSelectedIndex(-1);
    onClear && onClear();
    searchRef.current?.focus();
  };

  // 点击外部关闭建议列表
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (suggestionsRef.current && !suggestionsRef.current.contains(event.target)) {
        setShowSuggestionList(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative w-full" ref={suggestionsRef}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          ref={searchRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (showSuggestions && e.target.value) {
              setShowSuggestionList(true);
            }
          }}
          onFocus={() => {
            if (showSuggestions && query) {
              setShowSuggestionList(true);
            }
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full pl-10 pr-10 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
        />
        {query && (
          <button
            onClick={handleClear}
            className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* 搜索建议 */}
      {showSuggestionList && suggestions.length > 0 && (
        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {suggestions.map((suggestion, index) => (
            <div
              key={index}
              className={`px-4 py-2 cursor-pointer transition-colors ${
                index === selectedIndex 
                  ? 'bg-purple-100 text-purple-900' 
                  : 'hover:bg-gray-50'
              }`}
              onClick={() => {
                setQuery(suggestion);
                setShowSuggestionList(false);
                setSelectedIndex(-1);
              }}
            >
              {suggestion}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SearchBox;