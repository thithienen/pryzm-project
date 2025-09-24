# Pryzm Frontend

React-based frontend for the Pryzm document Q&A system.

## Features

- **Real-time Health Monitoring**: Visual status indicators for API and LLM services
- **Document Q&A Interface**: Chat interface with retrieval-augmented generation
- **Error Handling**: Global timeout handling and user-friendly error messages
- **Source Citations**: Display of document sources and page references
- **Responsive Design**: Mobile-friendly interface

## Configuration

### Environment Variables

Create a `.env` file in the frontend directory:

```bash
# API Base URL - points to your FastAPI backend
REACT_APP_API_BASE=http://localhost:8000
```

### Default Configuration

- **API Base URL**: `http://localhost:8000`
- **Fetch Timeout**: 15 seconds
- **CORS Origins**: `http://localhost:3000`

## Development

1. **Install Dependencies:**
   ```bash
   npm install
   ```

2. **Start Development Server:**
   ```bash
   npm start
   ```

3. **Build for Production:**
   ```bash
   npm run build
   ```

## Components

### HealthStatus
Displays real-time status of API and LLM services with visual indicators.

### ErrorBanner
Shows error messages for timeouts and server errors with dismiss functionality.

### App
Main chat interface with message handling and API integration.

## API Integration

The frontend integrates with the following backend endpoints:

- `GET /health` - API health check
- `GET /llm/health` - LLM service health check
- `POST /answer` - Submit questions and receive answers

## Error Handling

- **Timeout Handling**: 15-second timeout for all API calls
- **Error Display**: User-friendly error messages with retry suggestions
- **Health Monitoring**: Real-time status indicators for service availability
