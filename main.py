from dotenv import load_dotenv

load_dotenv(override=True)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.connection import create_db_and_tables
from routers import upload
from routers import esselte


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)

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

app.include_router(upload.router, prefix="/api/v1")
app.include_router(esselte.router, prefix="/api/v1")
