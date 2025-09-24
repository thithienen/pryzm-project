import React, { useState, useRef, useEffect } from 'react';
import './App.css';
import HealthStatus from './components/HealthStatus';
import ErrorBanner from './components/ErrorBanner';
import { askQuestion } from './config/api';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [lastAnswer, setLastAnswer] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Handle sending messages with real API calls
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
    setIsGenerating(true);

    try {
      // Call the actual API
      const response = await askQuestion(message);
      
      if (response.status === 'ok') {
        const botMessage = {
          id: Date.now() + 1,
          text: response.data.answer_md,
          sender: 'bot',
          timestamp: new Date(),
          context: response.data.context || [],
          used_model: response.data.used_model,
          latency_ms: response.data.latency_ms,
          generation_time: (response.data.latency_ms / 1000).toFixed(3)
        };
        setMessages(prev => [...prev, botMessage]);
        setLastAnswer(botMessage);
      } else {
        throw new Error(response.error || 'Failed to get response');
      }
    } catch (err) {
      console.error('Error calling API:', err);
      setError(`Error: ${err.message}`);
      
      // Don't add error message to chat, just show error banner
      // Keep previous answer grayed out
    } finally {
      setIsGenerating(false);
    }
  };

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

  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input on component mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  return (
    <div className="app">
      <HealthStatus />
      <ErrorBanner error={error} onDismiss={handleDismissError} />
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
                <div className="message-avatar">
                  {message.sender === 'user' ? '👤' : '🤖'}
                </div>
                <div className="message-content">
                  <div className="message-text">{message.text}</div>
                  {message.sender === 'bot' && message.used_model && (
                    <div className="generation-caption">
                      Generated in {message.generation_time}s via {message.used_model}
                    </div>
                  )}
                  {message.context && message.context.length > 0 && !message.text.includes('Insufficient evidence') && (
                    <div className="message-context">
                      <div className="context-label">Sources:</div>
                      <div className="context-items">
                        {message.context.map((item, index) => (
                          <div key={index} className="context-item">
                            <span className="context-rank">[{item.rank}]</span>
                            <span className="context-title">{item.title}</span>
                            <span className="context-page">Page {item.pageno}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {isGenerating && (
            <div className="message-wrapper bot">
              <div className="message">
                <div className="message-avatar">🤖</div>
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
                onChange={(e) => setInputValue(e.target.value)}
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
    </div>
  );
}

export default App;
