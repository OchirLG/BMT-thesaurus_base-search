import React, { useState, useCallback } from 'react';
import SearchBar from './components/SearchBar';
import ResultsTable from './components/ResultsTable';
import TermClusters from './components/TermClusters';
import LoadingSpinner from './components/LoadingSpinner';
import ThesaurusManager from './components/ThesaurusManager'; // импорт
import { searchMedical } from './api';
import './App.css';

function App() {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [currentQuery, setCurrentQuery] = useState('');
  const [threshold, setThreshold] = useState(0.8);
  const [activeTab, setActiveTab] = useState('search');

  const handleSearch = useCallback(async (query, thresholdValue) => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setCurrentQuery(query);
    try {
      const data = await searchMedical(query, thresholdValue);
      setResults(data);
    } catch (err) {
      setError(err.message || 'Произошла ошибка при поиске');
      console.error('Search failed:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleClear = () => {
    setResults(null);
    setCurrentQuery('');
    setError(null);
    setThreshold(0.8);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Медицинский поиск</h1>
        <p>Поиск врачебных обходов пациентов после трансплантации костного мозга</p>
      </header>
      
      <main className="app-main">
        <div className="tabs">
          <button 
            className={activeTab === 'search' ? 'tab active' : 'tab'} 
            onClick={() => setActiveTab('search')}
          >
            Поиск
          </button>
          <button 
            className={activeTab === 'thesaurus' ? 'tab active' : 'tab'} 
            onClick={() => setActiveTab('thesaurus')}
          >
            Тезаурус
          </button>
        </div>

        {activeTab === 'search' && (
          <>
            <SearchBar 
              onSearch={handleSearch} 
              onClear={handleClear}
              isLoading={loading}
              initialQuery={currentQuery}
              threshold={threshold}
              onThresholdChange={setThreshold}
            />
            {loading && <LoadingSpinner />}
            {error && <div className="error-message">Ошибка: {error}</div>}
            {results && !loading && (
              <>
                <div className="results-info">
                  <div className="query-stats">
                    <span className="query-text">Запрос: <strong>"{results.query}"</strong></span>
                    <span className="results-count">Найдено: {results.total_count} результатов</span>
                    <span className="processing-time"> Время: {results.processing_time_ms} мс</span>
                  </div>
                  <TermClusters clusters={results.term_clusters} />
                </div>
                <ResultsTable 
                  results={results.results} 
                  totalCount={results.total_count}
                />
              </>
            )}
          </>
        )}

        {activeTab === 'thesaurus' && <ThesaurusManager />}
      </main>
      
      <footer className="app-footer">
        <p>Медицинский поиск | Трансплантация костного мозга</p>
      </footer>
    </div>
  );
}

export default App;