from fastapi import APIRouter

from app.core.placeholders import not_implemented

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register():
    raise not_implemented("User registration")


@router.post("/login")
def login():
    raise not_implemented("Login")


@router.get("/me")
def me():
    raise not_implemented("Current user")
