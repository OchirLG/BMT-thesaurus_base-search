import React from 'react';
import './LoadingSpinner.css';

function LoadingSpinner() {
  return (
    <div className="spinner-container">
      <div className="spinner"></div>
      <p>Поиск медицинских записей...</p>
    </div>
  );
}

export default LoadingSpinner;