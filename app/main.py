# main.py file, contains app instance and main function

from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager
from app.api.subscriptions import subscriptions_router
from app.core.config import settings as stngs

# Decorated lofespan, activates database
# on app launch
@asynccontextmanager
async def lifespan(app:FastAPI):
    print(f"Connected to {stngs.POSTGRES_DB}")
    yield
    print(f"Disconnected to {stngs.POSTGRES_DB}")

# Creating app
app = FastAPI(lifespan = lifespan,
              title="News-Monitoring API",
              description="App monitores news and sends data via subscription",
              version="1.0.0")

#Connect router
app.include_router(subscriptions_router)

# Default wellcome root GET endpoint
@app.get("/")
async def root():
    return {"message":"API app is on, wellcome!"}


# App autostart with uvicorn server.
# Localhost and port are set for local PC work only.
# Reload is turned on for adaptive change/reload.
if __name__ == "__main__":
    uvicorn.run("app.main:app",
                host = "127.0.0.1",
                port = 8000,
                reload = True)