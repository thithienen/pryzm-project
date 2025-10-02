import React, { useState, useCallback } from 'react';
import './AnswerText.css';

const AnswerText = ({ 
  text, 
  context = [], 
  onCitationClick,
  usedModel,
  latencyMs,
  citationMapping = {},
  isStreaming = false,  // NEW: indicates if answer is still streaming
  onWebSearchRetry,     // NEW: callback for web search retry
  usedWebSearch = false, // NEW: indicates if web search was used
  isWebSearching = false, // NEW: indicates if web search is currently in progress
  isLastMessage = false  // NEW: indicates if this is the most recent message
}) => {
  const [toastMessage, setToastMessage] = useState(null);
  const [lastClickTime, setLastClickTime] = useState({});

  // Debounce citation clicks to prevent API spam
  const handleCitationClick = useCallback((citationNum) => {
    console.log('📖 CITATION LINK CLICKED:', citationNum);
    console.log('📖 Context length:', context.length);
    console.log('📖 Context type:', typeof context);
    console.log('📖 Context is array:', Array.isArray(context));
    if (context.length > 0) {
      console.log('📖 Context first item:', context[0]);
      console.log('📖 Context first item keys:', Object.keys(context[0]));
    }
    const now = Date.now();
    const lastClick = lastClickTime[citationNum] || 0;
    
    // Debounce by 200ms
    if (now - lastClick < 200) {
      console.log('⏱️ Citation click debounced');
      return;
    }
    
    setLastClickTime(prev => ({ ...prev, [citationNum]: now }));
    
    // Check if citation exists in context (using renumbered citations)
    if (citationNum < 1 || citationNum > context.length) {
      console.warn('⚠️ Invalid citation:', citationNum, 'Context length:', context.length);
      setToastMessage(`Source [${citationNum}] not found.`);
      setTimeout(() => setToastMessage(null), 3000);
      return;
    }
    
    // Call the citation click handler with the renumbered citation
    console.log('📞 Calling onCitationClick with renumbered citation:', citationNum);
    if (onCitationClick) {
      onCitationClick(citationNum);
    } else {
      console.warn('⚠️ onCitationClick handler not provided');
    }
  }, [context, lastClickTime, onCitationClick]);

  // Simple markdown parser for basic formatting
  const parseMarkdown = (text) => {
    // Handle headers
    text = text.replace(/^### (.*$)/gm, '<h3>$1</h3>');
    text = text.replace(/^## (.*$)/gm, '<h2>$1</h2>');
    text = text.replace(/^# (.*$)/gm, '<h1>$1</h1>');
    
    // Handle bold
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Handle italic
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // Handle links [text](url)
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    
    // Handle line breaks
    text = text.replace(/\n/g, '<br>');
    
    return text;
  };

  // Parse text and convert [n] citations to clickable links + markdown
  const renderTextWithCitations = (text) => {
    const citationPattern = /\[(\d+)\]/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = citationPattern.exec(text)) !== null) {
      // Add text before citation (with markdown parsing)
      if (match.index > lastIndex) {
        const textPart = text.slice(lastIndex, match.index);
        const parsedMarkdown = parseMarkdown(textPart);
        parts.push(
          <span 
            key={`text-${lastIndex}`}
            dangerouslySetInnerHTML={{ __html: parsedMarkdown }}
          />
        );
      }
      
      const citationNum = parseInt(match[1]);
      // During streaming, default to valid (blue) unless we know it's definitely invalid
      // After streaming, validate against context length
      const isValid = isStreaming ? true : (citationNum >= 1 && citationNum <= context.length);
      
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
    
    // Add remaining text (with markdown parsing)
    if (lastIndex < text.length) {
      const textPart = text.slice(lastIndex);
      const parsedMarkdown = parseMarkdown(textPart);
      parts.push(
        <span 
          key={`text-${lastIndex}`}
          dangerouslySetInnerHTML={{ __html: parsedMarkdown }}
        />
      );
    }
    
    return parts;
  };

  // Check for citation warnings
  // const citationPattern = /\[(\d+)\]/g;

  // Check if this is a "no evidence" response that suggests web search
  // const citationsFound = text.match(citationPattern) || [];
  
  // Show web search button for the last message if:
  // 1. Not currently streaming
  // 2. Not already a web search
  // 3. Is the last message (always available for last message)
  const suggestsWebSearch = !isStreaming && !usedWebSearch && isLastMessage;

  // No need for warnings - backend replaces response text when citations are missing
  // const showNoCitationsWarning = !isStreaming && citationsFound.length === 0;
  // const showUnmappedWarning = !isStreaming && citationsFound.length > 0 && validCitations.length === 0;

  return (
    <div className="answer-text-container">
      {/* Citation warnings removed - backend now provides proper "no evidence" message */}
      
      {/* Answer text with clickable citations */}
      <div className="answer-text">
        {renderTextWithCitations(text)}
      </div>
      
      {/* Web search button for no evidence responses */}
      {suggestsWebSearch && onWebSearchRetry && (
        <div className="web-search-suggestion">
          <button 
            className={`web-search-button ${isWebSearching ? 'searching' : ''}`}
            onClick={onWebSearchRetry}
            disabled={isWebSearching}
            aria-label="Search the web for current information"
          >
            {isWebSearching ? (
              <>
                <span className="spinner"></span>
                Searching the Web...
              </>
            ) : (
              '🌐 Search the Web'
            )}
          </button>
        </div>
      )}
      
      {/* Meta information */}
      {usedModel && (
        <div className="answer-meta">
          Generated via {usedModel}{usedWebSearch ? ' (with web search)' : ''}
          {context.length > 0 && `; ${context.length} sources`}
          {latencyMs && `; generated in ${(latencyMs / 1000).toFixed(3)}s`}
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
