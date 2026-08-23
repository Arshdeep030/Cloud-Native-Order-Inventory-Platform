from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import user_repository
from app.security.auth import (
    hash_password,
    verify_password,
    create_access_token
)


class AuthService:

    def register(
        self,
        db: Session,
        email: str,
        password: str
    ) -> User:

        existing_user = user_repository.get_by_email(
            db,
            email
        )

        if existing_user:
            raise ValueError(
                "User already exists"
            )

        password_hash = hash_password(password)

        user = User(
            email=email,
            password_hash=password_hash,
            role="customer"
        )

        return user_repository.create(
            db,
            user
        )


    def login(
        self,
        db: Session,
        email: str,
        password: str
    ) -> str:

        user = user_repository.get_by_email(
            db,
            email
        )

        if not user:
            raise ValueError(
                "Invalid credentials"
            )

        if not verify_password(
            password,
            user.password_hash
        ):
            raise ValueError(
                "Invalid credentials"
            )

        return create_access_token(
            user.id,
            user.role
        )


auth_service = AuthService()