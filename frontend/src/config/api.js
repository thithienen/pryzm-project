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

// Answer question function
export const askQuestion = async (prompt) => {
  console.log('🔵 FRONTEND: Starting askQuestion with prompt:', prompt);
  console.log('🔵 FRONTEND: API_BASE_URL:', API_BASE_URL);
  console.log('🔵 FRONTEND: Full endpoint:', `${API_BASE_URL}/v1/answer`);
  console.log('🔵 FRONTEND: Timeout set to:', FETCH_TIMEOUT, 'ms');
  
  const startTime = Date.now();
  try {
    console.log('🔵 FRONTEND: Making POST request...');
    const response = await apiFetch('/v1/answer', {
      method: 'POST',
      body: JSON.stringify({ prompt })
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
