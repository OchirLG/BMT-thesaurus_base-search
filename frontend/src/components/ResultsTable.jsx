import React, { useState, useMemo } from 'react';
import './ResultsTable.css';

const highlightTerms = (text, terms) => {
  if (!text || !terms || terms.length === 0) return text;
  
  const sorted = [...terms].sort((a, b) => b.length - a.length);
  const escaped = sorted.map(term => 
    term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  );
  const pattern = escaped.join('|');
  if (!pattern) return text;
  
  const regex = new RegExp(`(${pattern})`, 'gi');
  const parts = text.split(regex);
  
  return parts.map((part, i) =>
    regex.test(part) ? <mark key={i}>{part}</mark> : part
  );
};

function ResultsTable({ results, totalCount }) {
  const [sortConfig, setSortConfig] = useState({ key: 'score', direction: 'desc' });
  const [expandedRows, setExpandedRows] = useState(new Set());
  const [filterText, setFilterText] = useState('');

  const toggleRowExpand = (roundId) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(roundId)) {
      newExpanded.delete(roundId);
    } else {
      newExpanded.add(roundId);
    }
    setExpandedRows(newExpanded);
  };

  const sortedResults = useMemo(() => {
    if (!results || results.length === 0) return [];
    
    let sortableResults = [...results];
    
    if (sortConfig.key) {
      sortableResults.sort((a, b) => {
        let aVal = a[sortConfig.key];
        let bVal = b[sortConfig.key];
        
        if (sortConfig.key === 'score') {
          aVal = parseFloat(aVal) || 0;
          bVal = parseFloat(bVal) || 0;
        } else if (sortConfig.key === 'timestamp') {
          aVal = aVal ? new Date(aVal).getTime() : 0;
          bVal = bVal ? new Date(bVal).getTime() : 0;
        } else if (sortConfig.key === 'bmt_days') {
          aVal = parseInt(aVal) || 0;
          bVal = parseInt(bVal) || 0;
        } else if (typeof aVal === 'string') {
          aVal = aVal.toLowerCase();
          bVal = bVal.toLowerCase();
        }
        
        if (aVal < bVal) {
          return sortConfig.direction === 'asc' ? -1 : 1;
        }
        if (aVal > bVal) {
          return sortConfig.direction === 'asc' ? 1 : -1;
        }
        return 0;
      });
    }
    
    return sortableResults;
  }, [results, sortConfig]);

  const filteredResults = useMemo(() => {
    if (!filterText) return sortedResults;
    
    const lowerFilter = filterText.toLowerCase();
    return sortedResults.filter(result => 
      (result.descr && result.descr.toLowerCase().includes(lowerFilter)) ||
      (result.reg_id && result.reg_id.toLowerCase().includes(lowerFilter)) ||
      (result.matched_terms && result.matched_terms.some(term => term.toLowerCase().includes(lowerFilter))) ||
      (result.terms_list && result.terms_list.some(term => term.toLowerCase().includes(lowerFilter)))
    );
  }, [sortedResults, filterText]);

  const requestSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const getSortIcon = (key) => {
    if (sortConfig.key !== key) return '↕️';
    return sortConfig.direction === 'asc' ? '↑' : '↓';
  };

  const formatScore = (score) => {
    const percentage = (score * 100).toFixed(1);
    const color = score >= 0.7 ? '#4caf50' : score >= 0.4 ? '#ff9800' : '#f44336';
    return (
      <span className="score-badge" style={{ backgroundColor: color }}>
        {percentage}%
      </span>
    );
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('ru-RU', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      });
    } catch {
      return '-';
    }
  };

  if (!results || results.length === 0) {
    return (
      <div className="no-results">
        Нет результатов для отображения
      </div>
    );
  }

  return (
    <div className="table-container">
      <div className="table-controls">
        {/* <div className="filter-box">
          <input
            type="text"
            placeholder="Фильтр по описанию, пациенту или терминам..."
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            className="filter-input"
          />
        </div> */}
        <div className="table-info">
          Показано {filteredResults.length} из {results.length} результатов
        </div>
      </div>
      
      <div className="table-wrapper">
        <table className="results-table">
          <thead>
            <tr>
              <th onClick={() => requestSort('score')} className="sortable">
                Релевантность {getSortIcon('score')}
              </th>
              <th onClick={() => requestSort('reg_id')} className="sortable">
                Пациент {getSortIcon('reg_id')}
              </th>
              <th onClick={() => requestSort('gender')} className="sortable">
                Пол {getSortIcon('gender')}
              </th>
              <th onClick={() => requestSort('birth_year')} className="sortable">
                Год рожд. {getSortIcon('birth_year')}
              </th>
              <th onClick={() => requestSort('bmt_days')} className="sortable">
                Дней после ТКМ {getSortIcon('bmt_days')}
              </th>
              <th onClick={() => requestSort('timestamp')} className="sortable">
                Дата обхода {getSortIcon('timestamp')}
              </th>
              {/* <th>Найденные термины</th> */}
              <th>Описание</th>
            </tr>
          </thead>
          <tbody>
            {filteredResults.map((result) => (
              <React.Fragment key={result.round_id}>
                <tr className={expandedRows.has(result.round_id) ? 'expanded' : ''}>
                  <td className="score-cell">{formatScore(result.score)}</td>
                  <td className="reg-id">{result.reg_id || '-'}</td>
                  <td>{result.gender || '-'}</td>
                  <td>{result.birth_year || '-'}</td>
                  <td>{result.bmt_days || '-'}</td>
                  <td>{formatDate(result.timestamp)}</td>
                  {/* <td className="terms-cell">
                    <div className="matched-terms">
                      {result.matched_terms && result.matched_terms.slice(0, 3).map((term, i) => (
                        <span key={i} className="term-badge">{term}</span>
                      ))}
                      {result.matched_terms && result.matched_terms.length > 3 && (
                        <span className="term-badge more">+{result.matched_terms.length - 3}</span>
                      )}
                      {(!result.matched_terms || result.matched_terms.length === 0) && '-'}
                    </div>
                  </td> */}
                  <td className="description-cell">
                    <div className="description-preview" style={{ whiteSpace: 'pre-wrap' }}>
                      {result.descr 
                        ? highlightTerms(result.descr.substring(0, 150), result.matched_terms) 
                        : 'Нет описания'}
                      {result.descr && result.descr.length > 150 && '...'}
                      {result.descr && result.descr.length > 100 && (
                        <button className="expand-btn" onClick={() => toggleRowExpand(result.round_id)}>
                          {expandedRows.has(result.round_id) ? 'Свернуть' : 'Подробнее'}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
                {expandedRows.has(result.round_id) && result.descr && (
                  <tr className="expanded-row">
                    <td colSpan="8">
                      <div className="expanded-content">
                        <div className="expanded-section">
                          <h4>Полное описание</h4>
                            <div className="full-description" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
                            {highlightTerms(result.descr, result.matched_terms)}
                          </div>
                        </div>
                        
                        {result.terms_list && result.terms_list.length > 0 && (
                          <div className="expanded-section">
                            <h4>Все термины в обходе</h4>
                            <div className="all-terms">
                              {result.terms_list.map((term, i) => (
                                <span key={i} className="term-badge term-all">{term}</span>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        {result.term_matches && Object.keys(result.term_matches).length > 0 && (
                          <div className="expanded-section">
                            <h4>Детали совпадений</h4>
                            <div className="match-details">
                              {Object.entries(result.term_matches).map(([cluster, match]) => (
                                <div key={cluster} className="match-item">
                                  <div className="match-cluster">Кластер: {cluster}</div>
                                  <div className="match-found">
                                    {match.found ? (
                                      <>Найдено: {match.matched_terms?.join(', ')}</>
                                    ) : (
                                      <>Не найдено</>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        <div className="expanded-section">
                          <h4>Дополнительная информация</h4>
                          <div className="info-grid">
                            <div className="info-item">
                              <span className="info-label">ID обхода:</span>
                              <span className="info-value">{result.round_id}</span>
                            </div>
                            <div className="info-item">
                              <span className="info-label">ID госпитализации:</span>
                              <span className="info-value">{result.case_id || '-'}</span>
                            </div>
                            {result.bmt_timestamp && (
                              <div className="info-item">
                                <span className="info-label">Дата ТКМ:</span>
                                <span className="info-value">{formatDate(result.bmt_timestamp)}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
      
      {filteredResults.length === 0 && (
        <div className="no-results">
          Ничего не найдено. Попробуйте изменить фильтр.
        </div>
      )}
    </div>
  );
}

export default ResultsTable;