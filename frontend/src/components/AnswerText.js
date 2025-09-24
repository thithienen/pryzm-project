import React, { useState, useCallback } from 'react';
import './AnswerText.css';

const AnswerText = ({ 
  text, 
  context = [], 
  onCitationClick,
  usedModel,
  latencyMs 
}) => {
  const [toastMessage, setToastMessage] = useState(null);
  const [lastClickTime, setLastClickTime] = useState({});

  // Debounce citation clicks to prevent API spam
  const handleCitationClick = useCallback((citationNum) => {
    console.log('📖 CITATION LINK CLICKED:', citationNum);
    console.log('📖 Context length:', context.length);
    const now = Date.now();
    const lastClick = lastClickTime[citationNum] || 0;
    
    // Debounce by 200ms
    if (now - lastClick < 200) {
      console.log('⏱️ Citation click debounced');
      return;
    }
    
    setLastClickTime(prev => ({ ...prev, [citationNum]: now }));
    
    // Check if citation exists in context
    if (citationNum < 1 || citationNum > context.length) {
      console.warn('⚠️ Invalid citation:', citationNum, 'Context length:', context.length);
      setToastMessage(`Source [${citationNum}] not found.`);
      setTimeout(() => setToastMessage(null), 3000);
      return;
    }
    
    // Call the citation click handler
    console.log('📞 Calling onCitationClick with:', citationNum);
    if (onCitationClick) {
      onCitationClick(citationNum);
    } else {
      console.warn('⚠️ onCitationClick handler not provided');
    }
  }, [context.length, lastClickTime, onCitationClick]);

  // Parse text and convert [n] citations to clickable links
  const renderTextWithCitations = (text) => {
    const citationPattern = /\[(\d+)\]/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = citationPattern.exec(text)) !== null) {
      // Add text before citation
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index));
      }
      
      const citationNum = parseInt(match[1]);
      const isValid = citationNum >= 1 && citationNum <= context.length;
      
      // Add clickable citation
      parts.push(
        <button
          key={`citation-${match.index}-${citationNum}`}
          className={`citation-link ${isValid ? 'valid' : 'invalid'}`}
          onClick={() => handleCitationClick(citationNum)}
          aria-label={`Go to source ${citationNum}`}
          tabIndex={0}
        >
          [{citationNum}]
        </button>
      );
      
      lastIndex = match.index + match[0].length;
    }
    
    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }
    
    return parts;
  };

  // Check for citation warnings
  const citationPattern = /\[(\d+)\]/g;
  const citationsFound = text.match(citationPattern) || [];
  const validCitations = citationsFound.filter(citation => {
    const num = parseInt(citation.match(/\d+/)[0]);
    return num >= 1 && num <= context.length;
  });

  const showNoCitationsWarning = citationsFound.length === 0;
  const showUnmappedWarning = citationsFound.length > 0 && validCitations.length === 0;

  return (
    <div className="answer-text-container">
      {/* Citation warnings */}
      {showNoCitationsWarning && (
        <div className="citation-warning no-citations">
          This response contains no citations and may not meet project standards.
        </div>
      )}
      
      {showUnmappedWarning && (
        <div className="citation-warning unmapped-citations">
          Citations did not map to returned sources.
        </div>
      )}
      
      {/* Answer text with clickable citations */}
      <div className="answer-text">
        {renderTextWithCitations(text)}
      </div>
      
      {/* Meta information */}
      {usedModel && context.length > 0 && (
        <div className="answer-meta">
          Generated via {usedModel}; {context.length} sources; {latencyMs ? `generated in ${(latencyMs / 1000).toFixed(3)}s` : ''}
        </div>
      )}
      
      {/* Toast notification */}
      {toastMessage && (
        <div className="citation-toast">
          {toastMessage}
        </div>
      )}
    </div>
  );
};

export default AnswerText;
