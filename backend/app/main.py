# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.jongso_router import jongso_router
from app.dependencies import jongso_repository

app = FastAPI()

# ルーターを登録
app.include_router(jongso_router)

# CORSミドルウェア
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では制限した方が安全です！
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB接続管理
@app.on_event("startup")
async def startup():
    await jongso_repository.connect()

@app.on_event("shutdown")
async def shutdown():
    await jongso_repository.disconnect()
