import React from 'react';
import './ErrorBanner.css';

const ErrorBanner = ({ error, onDismiss }) => {
  if (!error) return null;

  return (
    <div className="error-banner">
      <div className="error-content">
        <div className="error-icon">⚠️</div>
        <div className="error-message">
          <strong>Backend unavailable or timed out.</strong>
          <span>Please retry.</span>
        </div>
        <button 
          className="error-dismiss" 
          onClick={onDismiss}
          aria-label="Dismiss error"
        >
          ✕
        </button>
      </div>
    </div>
  );
};

export default ErrorBanner;
