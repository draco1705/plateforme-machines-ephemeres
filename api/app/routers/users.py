from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.core.security import create_token, hash_password, verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserOut

router = APIRouter()

@router.post("", response_model = UserOut, status_code = 201)
def registre(payload: UserCreate, db: Session = Depends(get_db)):
     if db.query(User).filter_by(email=payload.email).first():
          raise HTTPException(409, "Email deja utilise")
     u = User(email = payload.email, password_hash = hash_password(payload.password))
     db.add(u)
     db.commit()
     db.refresh(u)
     return u

@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    u = db.query(User).filter_by(email=form.username).first()
    if not u or not verify_password(form.password, u.password_hash):
        raise HTTPException(401, "Identifiants invalides")
    return {"access_token": create_token(u.id), "token_type": "bearer"}

@router.post("/logout", status_code=204)
def logout(user: User = Depends(current_user)):
    # JWT stateless: client xoá token. Nếu muốn blacklist → dùng Redis.
    return

@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
