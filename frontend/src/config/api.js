// API Configuration
const API_BASE_URL = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

// Global fetch timeout (15 seconds)
const FETCH_TIMEOUT = 15000;

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
  try {
    const response = await apiFetch('/v1/answer', {
      method: 'POST',
      body: JSON.stringify({ prompt })
    });
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

// Get source page function
export const getSourcePage = async (docId, pageno) => {
  console.log('🌐 API: getSourcePage called with:', { docId, pageno });
  try {
    const url = `/v1/source/${docId}/${pageno}`;
    console.log('🌐 API: Making request to:', url);
    const response = await apiFetch(url);
    console.log('🌐 API: Response received:', response);
    return {
      status: 'ok',
      data: response
    };
  } catch (error) {
    console.error('🌐 API: Error occurred:', error);
    return {
      status: 'error',
      error: error.message
    };
  }
};

export { API_BASE_URL, FETCH_TIMEOUT };
