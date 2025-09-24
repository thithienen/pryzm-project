import React from 'react';
import './SourcesPane.css';

const SourcesPane = ({ 
  context = [], 
  isLoading = false, 
  hasError = false, 
  errorMessage = null 
}) => {
  // Check if we should show empty state
  const showEmptyState = !isLoading && !hasError && (context.length === 0 || 
    context.some(item => item.snippet && item.snippet.includes('Insufficient evidence')));

  return (
    <div className="sources-pane">
      <div className="sources-header">
        <h3>Sources</h3>
      </div>
      
      <div className="sources-content">
        {isLoading && (
          <div className="sources-loading">
            <div className="sources-spinner"></div>
            <span>Retrieving sources...</span>
          </div>
        )}
        
        {hasError && (
          <div className="sources-error">
            {errorMessage || "Couldn't load sources (answer request failed)."}
          </div>
        )}
        
        {showEmptyState && (
          <div className="sources-empty">
            No supporting sources returned for this query.
          </div>
        )}
        
        {!isLoading && !hasError && !showEmptyState && context.length > 0 && (
          <div className="sources-list">
            {context.map((item, index) => (
              <div 
                key={`${item.doc_id}-${item.pageno}-${index}`}
                className="source-card"
                data-doc-id={item.doc_id}
                data-pageno={item.pageno}
              >
                <div className="source-number">[{item.rank || index + 1}]</div>
                <div className="source-content">
                  <div className="source-title">{item.title}</div>
                  <div className="source-meta">
                    {item.doc_date} • p.{item.pageno}
                  </div>
                  <div className="source-snippet">
                    {item.snippet ? 
                      (item.snippet.length > 200 ? 
                        `${item.snippet.substring(0, 200)}...` : 
                        item.snippet
                      ) : 
                      'No snippet available'
                    }
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SourcesPane;
