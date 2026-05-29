from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager
from .database import db
from .routers import search
from .routers import thesaurus
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    await db.connect()
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    await db.disconnect()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Medical Rounds Search API",
    description="API для поиска врачебных обходов с использованием LLM и векторных эмбеддингов",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search.router)
app.include_router(thesaurus.router)

@app.get("/")
async def root():
    return {"message": "Medical Rounds Search API", "status": "running"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )