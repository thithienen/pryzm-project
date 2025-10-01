import React, { useState, useRef, useEffect, useCallback } from 'react';
import './App.css';
import ErrorBanner from './components/ErrorBanner';
import SourcesPane from './components/SourcesPane';
import AnswerText from './components/AnswerText';
import { askQuestionStream } from './config/api';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [lastAnswer, setLastAnswer] = useState(null);
  const [highlightedSource, setHighlightedSource] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  
  // Streaming buffer state
  const streamBufferRef = useRef('');
  const displayedTextRef = useRef('');
  const streamIntervalRef = useRef(null);

  // Auto-resize textarea function
  const autoResizeTextarea = useCallback(() => {
    const textarea = inputRef.current;
    if (textarea) {
      // Reset height to auto to get the correct scrollHeight
      textarea.style.height = 'auto';
      // Calculate the new height based on content (24px per line)
      const lineHeight = 24;
      const maxLines = 4;
      const newHeight = Math.min(textarea.scrollHeight, lineHeight * maxLines);
      textarea.style.height = `${Math.max(newHeight, lineHeight)}px`;
    }
  }, []);

  // Handle input change with auto-resize
  const handleInputChange = useCallback((e) => {
    setInputValue(e.target.value);
    autoResizeTextarea();
  }, [autoResizeTextarea]);

  // Handle sending messages with streaming API calls
  const handleSendMessage = async (message) => {
    if (!message.trim() || isGenerating) return;

    // Clear any existing errors
    setError(null);

    // Add user message
    const userMessage = {
      id: Date.now(),
      text: message,
      sender: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    // Reset textarea height after sending
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }
    setIsGenerating(true);

    // Create placeholder bot message for streaming
    const botMessageId = Date.now() + 1;
    const placeholderBotMessage = {
      id: botMessageId,
      text: '',
      sender: 'bot',
      timestamp: new Date(),
      context: [],
      streaming: true
    };
    setMessages(prev => [...prev, placeholderBotMessage]);

    // Initialize streaming buffer
    streamBufferRef.current = '';
    displayedTextRef.current = '';
    
    // Clear any existing interval
    if (streamIntervalRef.current) {
      clearInterval(streamIntervalRef.current);
    }
    
    // Start smooth display interval (30ms = ~33 chars/sec for smooth typing effect)
    streamIntervalRef.current = setInterval(() => {
      const buffer = streamBufferRef.current;
      const displayed = displayedTextRef.current;
      
      if (displayed.length < buffer.length) {
        // Calculate how many characters to add (3-5 chars per tick for smooth flow)
        const charsToAdd = Math.min(
          Math.ceil((buffer.length - displayed.length) / 10), // Adaptive speed
          5 // Max 5 chars per tick
        );
        
        const newDisplayed = buffer.slice(0, displayed.length + charsToAdd);
        displayedTextRef.current = newDisplayed;
        
        setMessages(prev => prev.map(msg => 
          msg.id === botMessageId
            ? { ...msg, text: newDisplayed }
            : msg
        ));
      }
    }, 30);

    try {
      // Call the streaming API
      await askQuestionStream(
        message,
        // onChunk callback - add to buffer instead of directly updating
        (accumulatedText, sources) => {
          streamBufferRef.current = accumulatedText;
          // Update sources immediately
          setMessages(prev => prev.map(msg => 
            msg.id === botMessageId
              ? { ...msg, context: sources }
              : msg
          ));
        },
        // onComplete callback - finalize message with metadata
        (finalData) => {
          // Stop the smooth streaming interval
          if (streamIntervalRef.current) {
            clearInterval(streamIntervalRef.current);
            streamIntervalRef.current = null;
          }
          
          const sources = finalData.sources || [];
          const answerText = finalData.answer_md || '';
          
          console.log('📊 SOURCES: Total sources received:', sources.length);
          
          // Extract citation numbers from the answer text
          const citationPattern = /\[(\d+)\]/g;
          const citationsInText = [];
          let match;
          while ((match = citationPattern.exec(answerText)) !== null) {
            const citationNum = parseInt(match[1]);
            if (!citationsInText.includes(citationNum)) {
              citationsInText.push(citationNum);
            }
          }
          
          console.log('📊 CITATIONS: Found in text:', citationsInText);
          
          // Filter sources to only include those referenced in the text
          const filteredSources = sources.filter(source => 
            citationsInText.includes(source.evidence_id)
          );
          
          console.log('📊 SOURCES: Filtered sources:', filteredSources.length);
          
          // Create a mapping from original citation numbers to new sequential numbers
          const citationMapping = {};
          citationsInText.forEach((originalNum, index) => {
            citationMapping[originalNum] = index + 1;
          });
          
          console.log('📊 MAPPING: Citation mapping:', citationMapping);
          
          // Map filtered sources with renumbered ranks
          const context = filteredSources.map((source, index) => {
            return {
              rank: index + 1,
              original_rank: source.evidence_id,
              doc_id: source.doc_id,
              title: source.doc_title,
              url: source.source_url || '',
              doc_date: source.date || source.doctype || 'Unknown',
              pageno: source.page_range && source.page_range.length > 0 ? source.page_range[0] : 1,
              snippet: source.text || 'No preview available'
            };
          });
          
          console.log('📊 SOURCES: Mapped context:', context);
          
          // Update the answer text to use new citation numbers
          let updatedAnswerText = answerText;
          Object.entries(citationMapping).forEach(([originalNum, newNum]) => {
            const regex = new RegExp(`\\[${originalNum}\\]`, 'g');
            updatedAnswerText = updatedAnswerText.replace(regex, `[${newNum}]`);
          });
          
          console.log('📊 TEXT: Updated answer text with new citations');
          
          const completedMessage = {
            id: botMessageId,
            text: updatedAnswerText,
            sender: 'bot',
            timestamp: new Date(),
            context: context,
            used_model: finalData.used_model,
            latency_ms: finalData.latency_ms,
            generation_time: (finalData.latency_ms / 1000).toFixed(3),
            citation_mapping: citationMapping,
            streaming: false
          };
          
          setMessages(prev => prev.map(msg => 
            msg.id === botMessageId ? completedMessage : msg
          ));
          setLastAnswer(completedMessage);
          setIsGenerating(false);
          
          // Clear buffer
          streamBufferRef.current = '';
          displayedTextRef.current = '';
        },
        // onError callback
        (errorMessage) => {
          // Stop the smooth streaming interval
          if (streamIntervalRef.current) {
            clearInterval(streamIntervalRef.current);
            streamIntervalRef.current = null;
          }
          
          console.error('Streaming error:', errorMessage);
          setError(`Error: ${errorMessage}`);
          // Remove the placeholder message
          setMessages(prev => prev.filter(msg => msg.id !== botMessageId));
          setIsGenerating(false);
          
          // Clear buffer
          streamBufferRef.current = '';
          displayedTextRef.current = '';
        }
      );
    } catch (err) {
      // Stop the smooth streaming interval
      if (streamIntervalRef.current) {
        clearInterval(streamIntervalRef.current);
        streamIntervalRef.current = null;
      }
      
      console.error('Error calling streaming API:', err);
      setError(`Error: ${err.message}`);
      // Remove the placeholder message
      setMessages(prev => prev.filter(msg => msg.id !== botMessageId));
      setIsGenerating(false);
      
      // Clear buffer
      streamBufferRef.current = '';
      displayedTextRef.current = '';
    }
  };

  // Keep the old non-streaming method as backup (commented out)
  /*
  const handleSendMessageNonStreaming = async (message) => {
    if (!message.trim() || isGenerating) return;

    // Clear any existing errors
    setError(null);

    // Add user message
    const userMessage = {
      id: Date.now(),
      text: message,
      sender: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    // Reset textarea height after sending
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }
    setIsGenerating(true);

    try {
      // Call the actual API
      const response = await askQuestion(message);
      
      // ... (old non-streaming code removed for brevity)
    }
  };
  */

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!isGenerating) {
      handleSendMessage(inputValue);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !isGenerating) {
      e.preventDefault();
      handleSendMessage(inputValue);
    }
  };

  const handleDismissError = () => {
    setError(null);
  };

  // Handle citation clicks
  const handleCitationClick = useCallback((citationNum) => {
    console.log('🎯 APP: Citation click received:', citationNum);
    console.log('🎯 APP: Setting highlighted source to:', citationNum);
    setHighlightedSource(citationNum);
    // Clear highlight after handling
    setTimeout(() => {
      console.log('🎯 APP: Clearing highlighted source');
      setHighlightedSource(null);
    }, 100);
  }, []);

  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input on component mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);
  
  // Cleanup streaming interval on unmount
  useEffect(() => {
    return () => {
      if (streamIntervalRef.current) {
        clearInterval(streamIntervalRef.current);
      }
    };
  }, []);

  return (
    <div className="app">
      <ErrorBanner error={error} onDismiss={handleDismissError} />
      <div className="main-layout">
        <div className="chat-container">
          <div className="messages-container">
          {messages.length === 0 && (
            <div className="welcome-screen">
              <div className="welcome-icon">✨</div>
              <h2>Welcome to Pryzm</h2>
              <p>Ask questions about your documents and get intelligent answers</p>
            </div>
          )}
          
          {messages.map((message) => (
            <div key={message.id} className={`message-wrapper ${message.sender} ${message.isError ? 'error' : ''} ${error && message.sender === 'bot' ? 'grayed-out' : ''}`}>
              <div className="message">
                <div className="message-content">
                  {message.sender === 'bot' ? (
                    <AnswerText
                      text={message.text}
                      context={message.context || []}
                      onCitationClick={handleCitationClick}
                      usedModel={message.used_model}
                      latencyMs={message.latency_ms}
                      citationMapping={message.citation_mapping || {}}
                      isStreaming={message.streaming || false}
                    />
                  ) : (
                    <div className="message-text">{message.text}</div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {isGenerating && (
            <div className="message-wrapper bot">
              <div className="message">
                <div className="message-content">
                  <div className="generating-indicator">
                    <div className="spinner"></div>
                    <span>Generating...</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
          </div>

          <div className="input-container">
            <form onSubmit={handleSubmit} className="input-form">
              <div className="input-wrapper">
                <textarea
                  ref={inputRef}
                  value={inputValue}
                  onChange={handleInputChange}
                  onKeyPress={handleKeyPress}
                  placeholder="Type your message here..."
                  className="message-input"
                  rows="1"
                  disabled={isGenerating}
                />
                <button 
                  type="submit" 
                  className="send-button"
                  disabled={!inputValue.trim() || isGenerating}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                    <path 
                      d="M7 11L12 6L17 11M12 18V7" 
                      stroke="currentColor" 
                      strokeWidth="2" 
                      strokeLinecap="round" 
                      strokeLinejoin="round"
                      transform="rotate(90 12 12)"
                    />
                  </svg>
                </button>
              </div>
            </form>
          </div>
        </div>
        
        <SourcesPane 
          context={lastAnswer?.context || []}
          isLoading={isGenerating}
          hasError={!!error}
          errorMessage={error}
          highlightedSource={highlightedSource}
          onSourceHighlightComplete={() => setHighlightedSource(null)}
        />
      </div>
    </div>
  );
}

export default App;
