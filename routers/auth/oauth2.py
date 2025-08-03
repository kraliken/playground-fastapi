from typing import Annotated
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import select
from database.connection import SessionDep
from datetime import datetime, timezone, timedelta
from jose import JWTError, jwt
import os
from pathlib import Path

from database.models import Player, PlayerRead, TokenData

secret_key = os.getenv("SECRET_KEY")
algorithm = os.getenv("ALGORITHM")
access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/signin", auto_error=False)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: SessionDep,
):

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_from_cookie = request.cookies.get("access_token")

    if not token_from_cookie:
        raise credentials_exception

    try:
        payload = jwt.decode(token_from_cookie, secret_key, algorithms=[algorithm])
        username = payload.get("sub")

        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    statement = select(Player).where(Player.username == token_data.username)
    user = session.exec(statement).first()

    if user is None:
        raise credentials_exception

    return PlayerRead.model_validate(user)


# def verify_token(token: str):
#     try:
#         payload = jwt.decode(token, secret_key, algorithms=[algorithm])
#         username: str = payload.get("sub")
#         if username is None:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Invalid token",
#                 headers={"WWW-Authenticate": "Bearer"},
#             )
#         return username
#     except JWTError:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid token",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
