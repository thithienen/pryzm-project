import React, { useState, useRef, useEffect, useCallback } from 'react';
import './App.css';
import ErrorBanner from './components/ErrorBanner';
import SourcesPane from './components/SourcesPane';
import AnswerText from './components/AnswerText';
import NavBar from './components/NavBar';
import ReadmeView from './components/ReadmeView';
import Footer from './components/Footer';
import ResizableDivider from './components/ResizableDivider';
import { askQuestionStream } from './config/api';

function App() {
  const [activeTab, setActiveTab] = useState('readme');
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [lastAnswer, setLastAnswer] = useState(null);
  const [highlightedSource, setHighlightedSource] = useState(null);
  const [sourcesWidth, setSourcesWidth] = useState(480);
  const [isWebSearching, setIsWebSearching] = useState(false);
  const [accumulatedSources, setAccumulatedSources] = useState([]);
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

  // Function to merge and rearrange sources
  const mergeAndRearrangeSources = useCallback((newSources, currentSources) => {
    // If no new sources (e.g., web search with no citations), keep current sources
    if (!newSources || newSources.length === 0) {
      return currentSources;
    }

    // Create a map of existing sources by a unique key (doc_id + pageno)
    const sourceMap = new Map();
    currentSources.forEach(source => {
      const key = `${source.doc_id}-${source.pageno}`;
      sourceMap.set(key, source);
    });

    // Add new sources to the map (will overwrite if same key exists)
    newSources.forEach(source => {
      const key = `${source.doc_id}-${source.pageno}`;
      sourceMap.set(key, source);
    });

    // Create array of all unique sources
    const allSources = Array.from(sourceMap.values());

    // Create a set of new source keys for quick lookup
    const newSourceKeys = new Set(
      newSources.map(s => `${s.doc_id}-${s.pageno}`)
    );

    // Separate sources into cited (in new response) and uncited
    const citedSources = [];
    const uncitedSources = [];

    allSources.forEach(source => {
      const key = `${source.doc_id}-${source.pageno}`;
      if (newSourceKeys.has(key)) {
        citedSources.push(source);
      } else {
        uncitedSources.push(source);
      }
    });

    // Sort cited sources by their rank in the new response
    citedSources.sort((a, b) => {
      const aIndex = newSources.findIndex(s => 
        s.doc_id === a.doc_id && s.pageno === a.pageno
      );
      const bIndex = newSources.findIndex(s => 
        s.doc_id === b.doc_id && s.pageno === b.pageno
      );
      return aIndex - bIndex;
    });

    // Combine: cited sources on top, uncited sources below
    const rearrangedSources = [...citedSources, ...uncitedSources];

    // Reassign ranks sequentially
    return rearrangedSources.map((source, index) => ({
      ...source,
      rank: index + 1
    }));
  }, []);

  // Handle sending messages with streaming API calls
  const handleSendMessage = async (message, useWebSearch = false, skipUserMessage = false) => {
    if (!message.trim() || isGenerating) return;

    // Clear any existing errors
    setError(null);
    
    // Debug: Log current sources before starting
    console.log('🔍 DEBUG: Starting new message, current accumulatedSources:', accumulatedSources.length);
    
    // Set web search state
    if (useWebSearch) {
      setIsWebSearching(true);
    }

    // Add user message only if not skipping
    if (!skipUserMessage) {
      const userMessage = {
        id: Date.now(),
        text: message,
        sender: 'user',
        timestamp: new Date()
      };

      setMessages(prev => [...prev, userMessage]);
    }
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
          // Don't update sources during streaming to avoid clearing the sources panel
          // Sources will be updated only when streaming is complete
        },
        // onComplete callback - finalize message with metadata
        (finalData) => {
          // Stop the smooth streaming interval
          if (streamIntervalRef.current) {
            clearInterval(streamIntervalRef.current);
            streamIntervalRef.current = null;
          }
          
          let sources = finalData.sources || [];
          const answerText = finalData.answer_md || '';
          
          console.log('📊 SOURCES: Total sources received:', sources.length);
          console.log('📊 SOURCES: Sources data:', sources);
          console.log('📊 SOURCES: Used web search:', finalData.used_web_search);
          console.log('📊 SOURCES: finalData object keys:', Object.keys(finalData));
          console.log('📊 SOURCES: finalData.metadata:', finalData.metadata);
          
          // FALLBACK: If no sources from streaming, try to get them from metadata
          if (sources.length === 0 && finalData.metadata && finalData.metadata.sources) {
            console.log('📊 SOURCES: 🔄 FALLBACK - Using sources from metadata');
            sources = finalData.metadata.sources;
            console.log('📊 SOURCES: Fallback sources count:', sources.length);
          }
          
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
          console.log('📊 CITATIONS: Types in citationsInText:', citationsInText.map(c => typeof c));
          
          // Debug: Log all sources before filtering
          console.log('📊 SOURCES: All sources before filtering:', sources.length);
          console.log('📊 SOURCES: Source evidence_id values:', sources.map(s => ({ 
            evidence_id: s.evidence_id, 
            type: typeof s.evidence_id,
            doc_id: s.doc_id 
          })));
          
          // Debug: Test the filtering logic step by step
          console.log('📊 FILTERING: Testing each source...');
          sources.forEach((source, index) => {
            const isIncluded = citationsInText.includes(source.evidence_id);
            const isIncludedAsNumber = citationsInText.includes(Number(source.evidence_id));
            const isIncludedAsString = citationsInText.includes(String(source.evidence_id));
            console.log(`📊 FILTERING: Source ${index}: evidence_id=${source.evidence_id} (${typeof source.evidence_id})`, {
              isIncluded,
              isIncludedAsNumber,
              isIncludedAsString,
              citationsInText
            });
          });
          
          // Use all sources returned by the API (filtering disabled due to server issues)
          const filteredSources = sources;
          
          console.log('📊 SOURCES: Filtered sources:', filteredSources.length);
          console.log('📊 SOURCES: Filtered sources details:', filteredSources.map(s => ({ 
            evidence_id: s.evidence_id, 
            type: typeof s.evidence_id,
            doc_id: s.doc_id 
          })));
          
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
          console.log('📊 SOURCES: Mapped context length:', context.length);
          console.log('📊 SOURCES: Mapped context types:', context.map(c => ({
            rank: c.rank,
            rank_type: typeof c.rank,
            doc_id: c.doc_id,
            doc_id_type: typeof c.doc_id,
            pageno: c.pageno,
            pageno_type: typeof c.pageno
          })));
          
          // Update the answer text to use new citation numbers
          let updatedAnswerText = answerText;
          Object.entries(citationMapping).forEach(([originalNum, newNum]) => {
            const regex = new RegExp(`\\[${originalNum}\\]`, 'g');
            updatedAnswerText = updatedAnswerText.replace(regex, `[${newNum}]`);
          });
          
          console.log('📊 TEXT: Updated answer text with new citations');
          
          // For web search, don't update sources - keep the previous ones
          let rearrangedSources = accumulatedSources; // Default to current sources
          if (finalData.used_web_search) {
            console.log('📊 SOURCES: Web search detected - keeping previous sources');
            // Don't update accumulatedSources for web search
          } else {
            // Merge and rearrange sources with accumulated sources
            rearrangedSources = mergeAndRearrangeSources(context, accumulatedSources);
            console.log('📊 SOURCES: Rearranged sources:', rearrangedSources.length);
            
            // Update accumulated sources
            setAccumulatedSources(rearrangedSources);
          }
          
          // Create a new citation mapping based on the rearranged sources
          // Map from the temporary citation numbers to the actual ranks in accumulated sources
          const finalCitationMapping = {};
          let finalAnswerText = updatedAnswerText;
          
          if (finalData.used_web_search) {
            // For web search, don't try to map citations to sources
            console.log('📊 MAPPING: Web search - skipping citation mapping');
          } else {
            Object.entries(citationMapping).forEach(([originalNum, tempNum]) => {
              // Find the source in the rearranged sources
              const sourceInContext = context[tempNum - 1];
              if (sourceInContext) {
                const sourceKey = `${sourceInContext.doc_id}-${sourceInContext.pageno}`;
                const rearrangedIndex = rearrangedSources.findIndex(s => 
                  `${s.doc_id}-${s.pageno}` === sourceKey
                );
                if (rearrangedIndex !== -1) {
                  finalCitationMapping[tempNum] = rearrangedIndex + 1;
                }
              }
            });
            
            console.log('📊 MAPPING: Final citation mapping to accumulated sources:', finalCitationMapping);
            
            // Update the answer text to use the final citation numbers
            Object.entries(finalCitationMapping).forEach(([tempNum, finalNum]) => {
              const regex = new RegExp(`\\[${tempNum}\\]`, 'g');
              finalAnswerText = finalAnswerText.replace(regex, `[${finalNum}]`);
            });
          }
          
          console.log('📊 TEXT: Final answer text with accumulated source citations');
          
          const completedMessage = {
            id: botMessageId,
            text: finalAnswerText,
            sender: 'bot',
            timestamp: new Date(),
            context: context,
            used_model: finalData.used_model,
            latency_ms: finalData.latency_ms,
            generation_time: (finalData.latency_ms / 1000).toFixed(3),
            citation_mapping: finalCitationMapping,
            streaming: false,
            used_web_search: finalData.used_web_search || false
          };
          
          setMessages(prev => prev.map(msg => 
            msg.id === botMessageId ? completedMessage : msg
          ));
          setLastAnswer(completedMessage);
          setIsGenerating(false);
          setIsWebSearching(false);
          
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
          setIsWebSearching(false);
          
          // Clear buffer
          streamBufferRef.current = '';
          displayedTextRef.current = '';
        },
        useWebSearch
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
      setIsWebSearching(false);
      
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

  // Handle web search retry for the last message
  const handleWebSearchRetry = () => {
    if (messages.length > 0) {
      const lastUserMessage = [...messages].reverse().find(msg => msg.sender === 'user');
      if (lastUserMessage) {
        // Don't add user message again, just start web search
        handleSendMessage(lastUserMessage.text, true, true); // Use web search, skip user message
      }
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

  const handleTabChange = (tab) => {
    setActiveTab(tab);
  };

  // Handle starting a new chat
  const handleNewChat = () => {
    setMessages([]);
    setLastAnswer(null);
    setAccumulatedSources([]);
    setError(null);
    setIsGenerating(false);
    setIsWebSearching(false);
    
    // Clear streaming state
    streamBufferRef.current = '';
    displayedTextRef.current = '';
    if (streamIntervalRef.current) {
      clearInterval(streamIntervalRef.current);
      streamIntervalRef.current = null;
    }
    
    // Focus input after clearing
    setTimeout(() => {
      inputRef.current?.focus();
    }, 100);
    
    console.log('✨ New chat started');
  };

  const handleResize = useCallback((newWidth) => {
    setSourcesWidth(newWidth);
  }, []);

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
      <NavBar 
        activeTab={activeTab} 
        onTabChange={handleTabChange}
      />
      <ErrorBanner error={error} onDismiss={handleDismissError} />
      <div className="main-layout">
        {activeTab === 'chat' ? (
          <>
            <div className="chat-container">
              <div className="messages-container">
              {messages.length === 0 && (
                <div className="welcome-screen">
                  <div className="welcome-icon">🐼</div>
                  <h2>Welcome! ~ from Thien</h2>
                  <p>Ask intelligent questions and get not-so-intelligent answers</p>
                </div>
              )}
              
              {messages.map((message) => (
                <div key={message.id} className={`message-wrapper ${message.sender} ${message.isError ? 'error' : ''} ${error && message.sender === 'bot' ? 'grayed-out' : ''}`}>
                  <div className="message">
                    <div className="message-content">
                      {message.sender === 'bot' ? (
                        <AnswerText
                          text={message.text}
                          context={accumulatedSources}
                          onCitationClick={handleCitationClick}
                          usedModel={message.used_model}
                          latencyMs={message.latency_ms}
                          citationMapping={message.citation_mapping || {}}
                          isStreaming={message.streaming || false}
                          onWebSearchRetry={handleWebSearchRetry}
                          usedWebSearch={message.used_web_search || false}
                          isWebSearching={isWebSearching}
                          isLastMessage={message.id === lastAnswer?.id}
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
                    {messages.length > 0 && (
                      <button
                        type="button"
                        className="new-chat-button"
                        onClick={handleNewChat}
                        disabled={isGenerating}
                        title="Start a new chat"
                      >
                        <span className="new-chat-icon">+</span>
                        <span className="new-chat-text">New Chat</span>
                      </button>
                    )}
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
            
            <ResizableDivider onResize={handleResize} />
            
            <SourcesPane 
              context={accumulatedSources}
              isLoading={isGenerating}
              hasError={!!error}
              errorMessage={error}
              highlightedSource={highlightedSource}
              onSourceHighlightComplete={() => setHighlightedSource(null)}
              width={sourcesWidth}
            />
          </>
        ) : (
          <ReadmeView />
        )}
      </div>
      <Footer />
    </div>
  );
}

export default App;
