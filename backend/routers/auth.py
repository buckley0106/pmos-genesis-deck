"""Auth router — register, login, me."""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from deps import (
    create_access_token, db, get_current_user, hash_password, now_iso, verify_password,
)
from models import LoginRequest, RegisterRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
async def register(body: RegisterRequest):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = {
        "email": email, "name": body.name or email.split("@")[0],
        "password_hash": hash_password(body.password), "role": "member", "created_at": now_iso(),
    }
    res = await db.users.insert_one(doc)
    uid = str(res.inserted_id)
    token = create_access_token(uid, email, "member")
    return {"token": token, "user": {"id": uid, "email": email, "name": doc["name"], "role": "member"}}


@router.post("/login")
async def login(body: LoginRequest):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    uid = str(user["_id"])
    token = create_access_token(uid, email, user.get("role", "member"))
    return {"token": token, "user": {"id": uid, "email": email, "name": user.get("name"), "role": user.get("role", "member")}}


@router.get("/me")
async def me(user: Dict[str, Any] = Depends(get_current_user)):
    return user
