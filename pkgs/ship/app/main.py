from fastapi import FastAPI
from .components.filesystem import router as fs_router
from .components.ipython import router as ipython_router
from .components.shell import router as shell_router

app = FastAPI(
    title="Ship API",
    description="A containerized execution environment with filesystem, IPython, and shell capabilities",
    version="1.0.0",
)

# Include component routers
app.include_router(fs_router, prefix="/fs", tags=["filesystem"])
app.include_router(ipython_router, prefix="/ipython", tags=["ipython"])
app.include_router(shell_router, prefix="/shell", tags=["shell"])


@app.get("/")
async def root():
    return {"message": "Ship API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
