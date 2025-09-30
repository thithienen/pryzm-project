from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from settings import CORS_ORIGINS, PORT
from routes import health, answer, source, debug

# Create FastAPI app
app = FastAPI(
    title="Pryzm Project API", 
    version="1.0.0",
    description="Document retrieval and Q&A API"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/v1")
app.include_router(answer.router, prefix="/v1")
app.include_router(source.router, prefix="/v1")
app.include_router(debug.router)

# Legacy routes for backward compatibility
app.include_router(health.router)
app.include_router(answer.router)
app.include_router(source.router)

# Root endpoint
@app.get("/")
async def read_root():
    print("🟣 APP: Root endpoint hit")
    return {
        "message": "Pryzm Project API", 
        "version": "1.0.0",
        "docs": "/docs"
    }

# Add middleware to log all requests
@app.middleware("http")
async def log_requests(request, call_next):
    print(f"🟣 APP: Incoming {request.method} request to {request.url.path}")
    response = await call_next(request)
    print(f"🟣 APP: Response status: {response.status_code}")
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
