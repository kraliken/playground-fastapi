from fastapi import APIRouter, Response, status, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import OperationalError
from database.models import (
    Player,
    PlayerCreate,
    PlayerRead,
    Role,
    TokenWithUser,
)
from database.connection import SessionDep
from sqlmodel import select

from datetime import datetime, timezone
from typing import Annotated

from routers.auth.oauth2 import create_access_token, get_current_user
from utils.hashing import Hash


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=PlayerRead)
def create_user(credetials: PlayerCreate, session: SessionDep):

    statement = select(Player).where(Player.username == credetials.username)
    existing_user = session.exec(statement).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User name already exists"
        )

    hashed_password = Hash.bcrypt(credetials.password)

    new_player = Player(
        username=credetials.username,
        hashed_password=hashed_password,
        created_at=datetime.now(timezone.utc),
    )

    session.add(new_player)
    session.commit()
    session.refresh(new_player)

    return PlayerRead.model_validate(new_player)


@router.post("/signin")
def sign_in(
    request: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
    response: Response,
):
    statement = select(Player).where(Player.username == request.username)
    user = session.exec(statement).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not Hash.verify(user.hashed_password, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.role != Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Csak admin felhasználók jelentkezhetnek be.",
        )

    access_token = create_access_token(
        data={
            "sub": user.username,  # vagy user.name ha az a meződ neve
        }
    )

    return TokenWithUser(
        access_token=access_token,
        token_type="bearer",
        user=PlayerRead.model_validate(user),
    )

    # response.set_cookie(
    #     key="access_token",
    #     value=access_token,
    #     httponly=True,
    #     secure=False,  # csak HTTPS! (fejlesztés alatt lehet False)
    #     samesite="lax",
    #     max_age=60 * 60,
    #     # path="/",
    # )


@router.get("/me")
def read_users_me(current_user: Annotated[PlayerRead, Depends(get_current_user)]):
    return current_user
