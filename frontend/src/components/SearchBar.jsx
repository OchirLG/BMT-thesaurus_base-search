// components/SearchBar.jsx
import React, { useState } from 'react';
import './SearchBar.css';

function SearchBar({ onSearch, onClear, isLoading, initialQuery, threshold, onThresholdChange }) {
  const [query, setQuery] = useState(initialQuery || '');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim(), threshold);  // передаём порог
    }
  };

  const handleClear = () => {
    setQuery('');
    onClear();
  };

  const handleThresholdChange = (e) => {
    const value = parseFloat(e.target.value);
    onThresholdChange(value);
  };

  return (
    <div className="search-container">
      <form onSubmit={handleSubmit} className="search-form">
        <textarea
          className="search-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Введите медицинский запрос на русском языке..."
          rows="4"
          disabled={isLoading}
        />
        
        {/* Добавляем блок с ползунком порога */}
        <div className="threshold-control">
          <label htmlFor="threshold-slider">
            Минимальная релевантность: <strong>{(threshold * 100).toFixed(0)}%</strong>
          </label>
          <input
            id="threshold-slider"
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={threshold}
            onChange={handleThresholdChange}
            disabled={isLoading}
          />
          <div className="threshold-hint">
            <span>0% (все результаты)</span>
            <span>50%</span>
            <span>100% (только точные)</span>
          </div>
        </div>

        <div className="search-buttons">
          <button 
            type="submit" 
            className="btn btn-primary"
            disabled={isLoading || !query.trim()}
          >
            {isLoading ? 'Поиск...' : 'Найти'}
          </button>
          <button 
            type="button" 
            className="btn btn-secondary"
            onClick={handleClear}
            disabled={isLoading}
          >
            Очистить
          </button>
        </div>
      </form>
    </div>
  );
}

export default SearchBar;