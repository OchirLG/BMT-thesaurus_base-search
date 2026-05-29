import React, { useState, useRef } from 'react';
import axios from 'axios';
import { Edit } from 'lucide-react';
import './ThesaurusManager.css';

const API_BASE = 'http://localhost:8000/api/thesaurus';

function ThesaurusManager() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [suggestion, setSuggestion] = useState({ term: '', expansion: '', definition: '' });
  const [newTerm, setNewTerm] = useState({ term: '', expansion: '', definition: '' });
  const [message, setMessage] = useState('');
  const suggestFormRef = useRef(null);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const res = await axios.post(`${API_BASE}/search`, { query: searchQuery, limit: 50 });
      setSearchResults(res.data);
      setMessage('');
    } catch (err) {
      setMessage('Ошибка поиска: ' + err.message);
    }
  };

  const openSuggestionForm = (term, expansion = '', definition = '') => {
    setSuggestion({ term, expansion, definition });
    if (suggestFormRef.current) {
      suggestFormRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const handleSuggest = async () => {
    if (!suggestion.term.trim()) {
      setMessage('Укажите термин для изменения');
      return;
    }
    try {
      await axios.post(`${API_BASE}/suggest`, {
        term: suggestion.term,
        suggested_expansion: suggestion.expansion,
        suggested_definition: suggestion.definition,
      });
      setMessage('Предложение отправлено!');
      setSuggestion({ term: '', expansion: '', definition: '' });
    } catch (err) {
      setMessage('Ошибка: ' + err.message);
    }
  };

  const handleAddTerm = async () => {
    if (!newTerm.term.trim()) {
      setMessage('Укажите название нового термина');
      return;
    }
    try {
      await axios.post(`${API_BASE}/add`, newTerm);
      setMessage('Термин добавлен в тезаурус!');
      setNewTerm({ term: '', expansion: '', definition: '' });
      handleSearch();
    } catch (err) {
      setMessage('Ошибка: ' + (err.response?.data?.detail || err.message));
    }
  };

  const clearSuggestion = () => {
    setSuggestion({ term: '', expansion: '', definition: '' });
  };

  return (
    <div className="thesaurus-manager">
      <h2>Управление тезаурусом</h2>
      
      {/* Поиск терминов */}
      <section className="search-section">
        <h3>Поиск терминов</h3>
        <div className="search-bar">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Введите термин или часть..."
          />
          <button onClick={handleSearch}>Найти</button>
        </div>
        {searchResults.length > 0 && (
          <table className="results-table">
            <thead>
              <tr><th>Термин</th><th>Расшифровка</th><th>Определение</th><th></th></tr>
            </thead>
            <tbody>
              {searchResults.map((term, idx) => (
                <tr key={idx}>
                  <td>{term.term}</td>
                  <td>{term.expansion || '-'}</td>
                  <td>{term.definition ? term.definition.substring(0, 100) + (term.definition.length > 100 ? '…' : '') : '-'}</td>
                  <td>
                    <button 
                      className="edit-btn" 
                      onClick={() => openSuggestionForm(term.term, term.expansion, term.definition)}
                      title="Редактировать"
                    >
                      <Edit size={18} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Форма предложения изменений */}
      <section className="suggest-section" ref={suggestFormRef}>
        <h3>Предложить изменение термина</h3>
        <div className="form-group">
          <input
            type="text"
            placeholder="Термин (обязательно)"
            value={suggestion.term}
            onChange={(e) => setSuggestion({...suggestion, term: e.target.value})}
          />
          <input
            type="text"
            placeholder="Новая расшифровка (необязательно)"
            value={suggestion.expansion}
            onChange={(e) => setSuggestion({...suggestion, expansion: e.target.value})}
          />
          <textarea
            placeholder="Новое определение (необязательно)"
            value={suggestion.definition}
            onChange={(e) => setSuggestion({...suggestion, definition: e.target.value})}
            rows="3"
          />
          <div className="form-buttons">
            <button onClick={handleSuggest}>Отправить предложение</button>
            <button onClick={clearSuggestion} className="secondary">Очистить</button>
          </div>
        </div>
      </section>

      {/* Добавление нового термина */}
      <section className="add-section">
        <h3>Добавить новый термин</h3>
        <div className="form-group">
          <input
            type="text"
            placeholder="Термин (обязательно)"
            value={newTerm.term}
            onChange={(e) => setNewTerm({...newTerm, term: e.target.value})}
          />
          <input
            type="text"
            placeholder="Расшифровка (необязательно)"
            value={newTerm.expansion}
            onChange={(e) => setNewTerm({...newTerm, expansion: e.target.value})}
          />
          <textarea
            placeholder="Определение (необязательно)"
            value={newTerm.definition}
            onChange={(e) => setNewTerm({...newTerm, definition: e.target.value})}
            rows="3"
          />
          <button onClick={handleAddTerm}>Добавить</button>
        </div>
      </section>

      {message && <div className="message">{message}</div>}
    </div>
  );
}

export default ThesaurusManager;