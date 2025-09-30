import React, { useState, useEffect } from 'react';
import { checkApiHealth, checkLlmHealth } from '../config/api';
import './HealthStatus.css';

const HealthStatus = () => {
  const [apiStatus, setApiStatus] = useState({ status: 'checking' });
  const [llmStatus, setLlmStatus] = useState({ status: 'checking' });

  useEffect(() => {
    // Check API health
    checkApiHealth().then(setApiStatus);
    
    // Check LLM health
    checkLlmHealth().then(setLlmStatus);
  }, []);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'ok':
        return '✅';
      case 'error':
        return '❌';
      case 'checking':
        return '⏳';
      default:
        return '❓';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'ok':
        return 'OK';
      case 'error':
        return 'Error';
      case 'checking':
        return 'Checking...';
      default:
        return 'Unknown';
    }
  };

  const getModelName = () => {
    if (llmStatus.status === 'ok' && llmStatus.data?.model) {
      // Split by '/' and take the last part
      const modelParts = llmStatus.data.model.split('/');
      return modelParts[modelParts.length - 1];
    }
    return null;
  };

  return (
    <div className="health-status">
      <div className="status-badge">
        <span className="status-icon">{getStatusIcon(apiStatus.status)}</span>
        <span className="status-label">API:</span>
        <span className="status-text">{getStatusText(apiStatus.status)}</span>
      </div>
      
      <div className="status-badge">
        <span className="status-icon">{getStatusIcon(llmStatus.status)}</span>
        <span className="status-label">LLM:</span>
        {llmStatus.status === 'ok' && getModelName() ? (
          <span className="model-name">{getModelName()}</span>
        ) : (
          <span className="status-text">{getStatusText(llmStatus.status)}</span>
        )}
      </div>
    </div>
  );
};

export default HealthStatus;
