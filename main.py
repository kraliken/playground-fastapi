from dotenv import load_dotenv


load_dotenv(override=True)

# from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# from database.connection import create_db_and_tables
from routers.auth import authentication
from routers import nijhof
from routers import esselte
from routers import aerozone
from routers import reports


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     create_db_and_tables()
#     yield


# app = FastAPI(lifespan=lifespan)
app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8080",
    "https://playground-kralikdev-client.azurewebsites.net",
    "https://playground.kraliknorbert.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# app.include_router(authentication.router, prefix="/api/v1")
app.include_router(nijhof.router, prefix="/api/v1")
# app.include_router(esselte.router, prefix="/api/v1")
# app.include_router(aerozone.router, prefix="/api/v1")
# app.include_router(reports.router, prefix="/api/v1")
