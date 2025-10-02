import React, { useState, useRef, useEffect, useCallback } from 'react';
import './SourcesPane.css';
import { getSourcePage } from '../config/api';

const SourcesPane = ({ 
  context = [], 
  isLoading = false, 
  hasError = false, 
  errorMessage = null,
  highlightedSource = null,
  onSourceHighlightComplete = null,
  onCitationClick = null,
  width = 480
}) => {
  const [expandedSources, setExpandedSources] = useState({});
  const [loadingSources, setLoadingSources] = useState({});
  const [sourceErrors, setSourceErrors] = useState({});
  const [sourceData, setSourceData] = useState({});
  const sourceRefs = useRef({});

  // Debug: Log context changes
  useEffect(() => {
    console.log('📋 SOURCES: Context received:', context);
    console.log('📋 SOURCES: Context length:', context.length);
    console.log('📋 SOURCES: Context type:', typeof context);
    console.log('📋 SOURCES: Is context array?', Array.isArray(context));
    if (context.length > 0) {
      console.log('📋 SOURCES: First context item:', context[0]);
      console.log('📋 SOURCES: First context item keys:', Object.keys(context[0]));
      console.log('📋 SOURCES: First context item types:', Object.keys(context[0]).reduce((acc, key) => {
        acc[key] = typeof context[0][key];
        return acc;
      }, {}));
    } else {
      console.log('📋 SOURCES: Empty context - this will cause red sources panel');
    }
  }, [context]);

  // Handle source expansion
  const handleSourceExpand = useCallback(async (docId, pageno, rank) => {
    console.log('🔍 SOURCE EXPAND CLICKED:', { docId, pageno, rank });
    const sourceKey = `${docId}-${pageno}`;
    console.log('🔑 Source key:', sourceKey);
    
    if (expandedSources[sourceKey]) {
      // Collapse
      console.log('📁 Collapsing source:', sourceKey);
      setExpandedSources(prev => ({ ...prev, [sourceKey]: false }));
      return;
    }

    // Check if we already have the data
    if (sourceData[sourceKey]) {
      console.log('💾 Using cached data for:', sourceKey);
      setExpandedSources(prev => ({ ...prev, [sourceKey]: true }));
      return;
    }

    // Fetch the source data
    console.log('🌐 Fetching source data for:', { docId, pageno, sourceKey });
    setLoadingSources(prev => ({ ...prev, [sourceKey]: true }));
    setSourceErrors(prev => ({ ...prev, [sourceKey]: null }));

    try {
      console.log('📡 Calling getSourcePage API with docId:', docId, 'pageno:', pageno);
      const response = await getSourcePage(docId, pageno);
      console.log('📡 API response received:', response);
      
      if (response.status === 'ok') {
        console.log('✅ Source data received successfully:', response.data);
        setSourceData(prev => ({ ...prev, [sourceKey]: response.data }));
        setExpandedSources(prev => ({ ...prev, [sourceKey]: true }));
        console.log('📂 Source expanded successfully');
      } else {
        console.error('❌ API error:', response.error);
        setSourceErrors(prev => ({ 
          ...prev, 
          [sourceKey]: `Source not found: ${response.error}` 
        }));
      }
    } catch (error) {
      console.error('💥 Fetch error:', error);
      console.error('💥 Error details:', error.message, error.stack);
      setSourceErrors(prev => ({ 
        ...prev, 
        [sourceKey]: `Error loading source: ${error.message}` 
      }));
    } finally {
      console.log('🏁 Loading complete for:', sourceKey);
      setLoadingSources(prev => ({ ...prev, [sourceKey]: false }));
    }
  }, [expandedSources, sourceData]);

  // Handle citation click - scroll to source and highlight
  const handleCitationClick = useCallback((citationNum) => {
    console.log('🎯 CITATION CLICKED:', citationNum);
    const sourceElement = sourceRefs.current[citationNum];
    console.log('🔍 Source element found:', !!sourceElement);
    if (sourceElement) {
      console.log('📍 Scrolling to source element');
      // Scroll to the source
      sourceElement.scrollIntoView({ 
        behavior: 'smooth', 
        block: 'center' 
      });
      
      // Add highlight class
      console.log('✨ Adding highlight class');
      sourceElement.classList.add('highlighted');
      
      // Remove highlight after 2 seconds
      setTimeout(() => {
        console.log('⏰ Removing highlight class');
        sourceElement.classList.remove('highlighted');
        if (onSourceHighlightComplete) {
          onSourceHighlightComplete();
        }
      }, 2000);
    } else {
      console.warn('⚠️ Source element not found for citation:', citationNum);
    }
  }, [onSourceHighlightComplete]);

  // Handle highlighted source prop
  useEffect(() => {
    console.log('🎯 SOURCES: highlightedSource prop changed:', highlightedSource);
    if (highlightedSource) {
      console.log('🎯 SOURCES: Calling handleCitationClick with:', highlightedSource);
      handleCitationClick(highlightedSource);
    }
  }, [highlightedSource, handleCitationClick]);


  // Handle keyboard navigation
  const handleKeyDown = useCallback((e, docId, pageno, rank) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleSourceExpand(docId, pageno, rank);
    }
  }, [handleSourceExpand]);

  // Check if we should show empty state
  const showEmptyState = !isLoading && !hasError && (context.length === 0 || 
    context.some(item => item.snippet && item.snippet.includes('Insufficient evidence')));

  return (
    <div className="sources-pane" style={{ width: `${width}px`, minWidth: `${width}px`, maxWidth: `${width}px` }}>
      <div className="sources-header">
        <h3>Relevant Sources</h3>
      </div>
      
      <div className="sources-content">
        {isLoading && context.length === 0 && (
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
        
        {!hasError && !showEmptyState && context.length > 0 && (
          <div className="sources-list">
            {context.map((item, index) => {
              const rank = item.rank || index + 1;
              const sourceKey = `${item.doc_id}-${item.pageno}`;
              const isExpanded = expandedSources[sourceKey];
              const isLoadingSource = loadingSources[sourceKey];
              const sourceError = sourceErrors[sourceKey];
              const fullSourceData = sourceData[sourceKey];
              
              return (
                <div 
                  key={`${item.doc_id}-${item.pageno}-${index}`}
                  ref={el => {
                    console.log('🔗 Setting ref for rank:', rank, 'Element:', !!el);
                    sourceRefs.current[rank] = el;
                  }}
                  className="source-card"
                  data-doc-id={item.doc_id}
                  data-pageno={item.pageno}
                  tabIndex={0}
                  onKeyDown={(e) => handleKeyDown(e, item.doc_id, item.pageno, rank)}
                  onClick={(e) => {
                    console.log('🖱️ SOURCE CARD CLICKED:', { docId: item.doc_id, pageno: item.pageno, rank });
                    console.log('🖱️ Click target:', e.target.className);
                    // Check if clicking on the source number (don't trigger twice)
                    if (e.target.closest('.source-number')) {
                      console.log('🖱️ Click was on source number, ignoring card click');
                      return;
                    }
                    console.log('🖱️ Triggering source expansion from card click');
                    handleSourceExpand(item.doc_id, item.pageno, rank);
                  }}
                  role="button"
                  aria-expanded={isExpanded}
                  aria-label={`Source ${rank}: ${item.title}`}
                >
                  <div 
                    className="source-number clickable"
                    onClick={(e) => {
                      console.log('🖱️ SOURCE NUMBER CLICKED:', { docId: item.doc_id, pageno: item.pageno, rank });
                      e.stopPropagation();
                      e.preventDefault();
                      console.log('🖱️ Triggering source expansion from number click');
                      handleSourceExpand(item.doc_id, item.pageno, rank);
                    }}
                    title="Click to expand full page"
                  >
                    [{rank}]
                  </div>
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
                    
                    {/* Loading state for source expansion */}
                    {isLoadingSource && (
                      <div className="source-loading-inline">
                        <div className="inline-spinner"></div>
                        <span>Loading page text...</span>
                      </div>
                    )}
                    
                    {/* Error state for source expansion */}
                    {sourceError && (
                      <div className="source-error-inline">
                        {sourceError}
                        <button 
                          className="retry-button"
                          onClick={() => handleSourceExpand(item.doc_id, item.pageno, rank)}
                        >
                          Retry
                        </button>
                      </div>
                    )}
                    
                    {/* Expanded source content */}
                    {isExpanded && fullSourceData && (
                      <div className="source-expanded">
                        <div className="source-expanded-header">
                          <div className="source-expanded-meta">
                            {fullSourceData.doc_date} • Page {fullSourceData.pageno}
                            {fullSourceData.url && (
                              <button 
                                className="source-url-button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  window.open(fullSourceData.url, '_blank', 'noopener,noreferrer');
                                }}
                                title="Open original document in new tab"
                              >
                                Open Original
                              </button>
                            )}
                          </div>
                        </div>
                        <div className="source-expanded-text">
                          {fullSourceData.text}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default SourcesPane;
