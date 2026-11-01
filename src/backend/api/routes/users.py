import uuid
from datetime import timedelta
from typing import Annotated, Any

# from app.utils import generate_new_account_email, send_email
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text
from sqlmodel import col, func, select

from backend.auth.security import create_access_token

from ...auth import crud
from ...auth.security import get_password_hash, verify_password
from ...data_models.car import ModelCar
from ...data_models.users import (
    Message,
    Token,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UsersStatistics,
    UserStatistics,
    UserUpdate,
    UserUpdateMe,
)
from ..deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)

router = APIRouter(tags=["users"])
login_router = APIRouter(tags=["login"])


@router.post("/setup-superuser", response_model=UserPublic)
def setup_first_superuser(user_in: UserCreate, session: SessionDep):
    # Serialize setup requests across workers before checking for an existing user.
    session.execute(text("BEGIN IMMEDIATE"))
    existing_users = session.exec(select(User)).first()
    if existing_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Il sistema è già stato inizializzato. Impossibile creare un altro superuser da questo endpoint.",
        )

    # Forza il flag is_superuser a True per sicurezza
    user_in.is_superuser = True
    user = crud.create_user(session=session, user_create=user_in)
    return user


@login_router.post("/login/access-token", response_model=Token)
def login_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    user = crud.authenticate(
        session=session,
        email=form_data.username,
        password=form_data.password,
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(
        access_token=create_access_token(
            user.id,
            expires_delta=timedelta(minutes=30),
        )
    )


@router.get("/check-setup")
def check_setup(session: SessionDep):
    """Restituisce True se il sistema ha bisogno del setup iniziale (nessun utente)."""
    existing_users = session.exec(select(User)).first()
    return {"needs_setup": existing_users is None}


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """

    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()

    statement = (
        select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    )
    users = session.exec(statement).all()

    users_public = [UserPublic.model_validate(user) for user in users]
    return UsersPublic(data=users_public, count=count)


@router.get(
    "/statistics",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersStatistics,
)
def read_user_statistics(session: SessionDep) -> UsersStatistics:
    statement = (
        select(User, func.count(col(ModelCar.user_id)))
        .outerjoin(ModelCar, col(ModelCar.user_id) == col(User.id))
        .group_by(col(User.id))
        .order_by(col(User.created_at).desc())
    )
    users_with_car_counts = session.exec(statement).all()
    users_statistics = [
        UserStatistics.model_validate(user, update={"cars_count": cars_count})
        for user, cars_count in users_with_car_counts
    ]
    return UsersStatistics(
        data=users_statistics,
        count=len(users_statistics),
        active_users=sum(user.is_active for user, _ in users_with_car_counts),
        total_cars=sum(cars_count for _, cars_count in users_with_car_counts),
    )


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = crud.create_user(session=session, user_create=user_in)
    # if settings.emails_enabled and user_in.email:
    #    email_data = generate_new_account_email(
    #        email_to=user_in.email, username=user_in.email, password=user_in.password
    #    )
    #    send_email(
    #        email_to=user_in.email,
    #        subject=email_data.subject,
    #        html_content=email_data.html_content,
    #    )
    return user


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    has_superuser = session.exec(select(User).where(User.is_superuser == True)).first()
    if not has_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Il setup iniziale deve essere completato prima della registrazione.",
        )

    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    user_create = UserCreate.model_validate(user_in)
    user = crud.create_user(session=session, user_create=user_create)
    return user


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    db_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
    return db_user


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")
