// API Configuration
const API_BASE_URL = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

// Global fetch timeout (45 seconds - increased for reranking operations)
const FETCH_TIMEOUT = 45000;

// Create a timeout promise
const timeoutPromise = (ms) => {
  return new Promise((_, reject) => {
    setTimeout(() => reject(new Error('Request timeout')), ms);
  });
};

// Enhanced fetch with timeout and error handling
export const apiFetch = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const fetchOptions = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  try {
    const response = await Promise.race([
      fetch(url, fetchOptions),
      timeoutPromise(FETCH_TIMEOUT)
    ]);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error.message === 'Request timeout') {
      throw new Error('Request timeout');
    }
    throw error;
  }
};

// Health check functions
export const checkApiHealth = async () => {
  try {
    const response = await apiFetch('/health');
    return {
      status: 'ok',
      data: response
    };
  } catch (error) {
    return {
      status: 'error',
      error: error.message
    };
  }
};

export const checkLlmHealth = async () => {
  try {
    const response = await apiFetch('/llm/health');
    return {
      status: 'ok',
      data: response
    };
  } catch (error) {
    return {
      status: 'error',
      error: error.message
    };
  }
};

// Answer question function (non-streaming)
export const askQuestion = async (prompt, useWebSearch = false) => {
  console.log('🔵 FRONTEND: Starting askQuestion with prompt:', prompt);
  console.log('🔵 FRONTEND: useWebSearch:', useWebSearch);
  console.log('🔵 FRONTEND: API_BASE_URL:', API_BASE_URL);
  console.log('🔵 FRONTEND: Full endpoint:', `${API_BASE_URL}/v1/answer`);
  console.log('🔵 FRONTEND: Timeout set to:', FETCH_TIMEOUT, 'ms');
  
  const startTime = Date.now();
  try {
    console.log('🔵 FRONTEND: Making POST request...');
    const response = await apiFetch('/v1/answer', {
      method: 'POST',
      body: JSON.stringify({ 
        prompt,
        use_web_search: useWebSearch
      })
    });
    const elapsed = Date.now() - startTime;
    console.log('🔵 FRONTEND: ✅ Response received after', elapsed, 'ms:', response);
    return {
      status: 'ok',
      data: response
    };
  } catch (error) {
    const elapsed = Date.now() - startTime;
    console.error('🔵 FRONTEND: ❌ Error after', elapsed, 'ms:', error);
    console.error('🔵 FRONTEND: Error message:', error.message);
    console.error('🔵 FRONTEND: Error stack:', error.stack);
    
    let errorMessage = error.message;
    if (error.message === 'Request timeout') {
      errorMessage = `Backend unavailable or timed out.\nPlease retry.`;
    } else if (error.message.includes('Failed to fetch')) {
      errorMessage = `Backend unavailable or timed out.\nPlease retry.`;
    }
    
    return {
      status: 'error',
      error: errorMessage
    };
  }
};

// Answer question function with streaming
export const askQuestionStream = async (prompt, onChunk, onComplete, onError, useWebSearch = false) => {
  console.log('🔵 FRONTEND: Starting streaming askQuestion with prompt:', prompt);
  console.log('🔵 FRONTEND: useWebSearch:', useWebSearch);
  console.log('🔵 FRONTEND: API_BASE_URL:', API_BASE_URL);
  const url = `${API_BASE_URL}/v1/answer/stream`;
  console.log('🔵 FRONTEND: Full endpoint:', url);
  
  const startTime = Date.now();
  let accumulatedText = '';
  let sources = [];
  let metadata = {};
  
  try {
    console.log('🔵 FRONTEND: Making streaming POST request...');
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        prompt,
        use_web_search: useWebSearch
      })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        console.log('🔵 FRONTEND: Stream complete');
        break;
      }
      
      // Decode chunk
      const chunk = decoder.decode(value, { stream: true });
      
      // Split by newlines to handle multiple SSE events
      const lines = chunk.split('\n');
      
      for (const line of lines) {
        if (!line.trim() || !line.startsWith('data: ')) {
          continue;
        }
        
        try {
          const jsonStr = line.substring(6); // Remove "data: " prefix
          const event = JSON.parse(jsonStr);
          
          console.log('🔵 FRONTEND: Received event:', event.type);
          
          if (event.type === 'metadata') {
            // Store sources and metadata
            sources = event.sources;
            metadata = {
              used_model: event.used_model,
              total_sources: event.total_sources,
              total_tokens: event.total_tokens,
              target_tokens: event.target_tokens
            };
            console.log('🔵 FRONTEND: Received', sources.length, 'sources');
          } else if (event.type === 'content') {
            // Accumulate text and call onChunk callback
            accumulatedText += event.chunk;
            if (onChunk) {
              onChunk(accumulatedText, sources);
            }
          } else if (event.type === 'done') {
            const elapsed = Date.now() - startTime;
            console.log('🔵 FRONTEND: ✅ Stream complete after', elapsed, 'ms');
            if (onComplete) {
              onComplete({
                answer_md: accumulatedText,
                sources: sources,
                used_model: metadata.used_model,
                latency_ms: event.latency_ms,
                metadata: metadata
              });
            }
          } else if (event.type === 'error') {
            console.error('🔵 FRONTEND: ❌ Stream error:', event.message);
            if (onError) {
              onError(event.message);
            }
          }
        } catch (parseError) {
          console.warn('🔵 FRONTEND: Failed to parse SSE event:', line, parseError);
        }
      }
    }
  } catch (error) {
    const elapsed = Date.now() - startTime;
    console.error('🔵 FRONTEND: ❌ Error after', elapsed, 'ms:', error);
    
    let errorMessage = error.message;
    if (error.message.includes('Failed to fetch')) {
      errorMessage = 'Backend unavailable or timed out.\nPlease retry.';
    }
    
    if (onError) {
      onError(errorMessage);
    }
  }
};

// Get source page function
export const getSourcePage = async (docId, pageno) => {
  console.log('🌐 API: getSourcePage called with:', { docId, pageno });
  console.log('🌐 API: docId type:', typeof docId, 'pageno type:', typeof pageno);
  try {
    const url = `/v1/source/${encodeURIComponent(docId)}/${pageno}`;
    console.log('🌐 API: Making request to:', `${API_BASE_URL}${url}`);
    const response = await apiFetch(url);
    console.log('🌐 API: ✅ Response received:', response);
    return {
      status: 'ok',
      data: response
    };
  } catch (error) {
    console.error('🌐 API: ❌ Error occurred:', error);
    console.error('🌐 API: Error message:', error.message);
    console.error('🌐 API: Error stack:', error.stack);
    return {
      status: 'error',
      error: error.message
    };
  }
};

export { API_BASE_URL, FETCH_TIMEOUT };
