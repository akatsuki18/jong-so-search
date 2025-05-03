from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import json
import logging
import os
import asyncio
from pydantic import BaseModel
from supabase import create_client, Client
# from supabase_async import create_client as create_async_client, AsyncClient # 非同期クライアントのインポートをコメントアウト
import googlemaps
from config import settings
from services.google_maps_service import GoogleMapsService
from services.location_service import LocationService
from services.sentiment_analysis_service import SentimentAnalysisService

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# CORSミドルウェア
origins = [
    "http://localhost:3000",  # Next.jsアプリのオリジン
    # 他に必要なオリジンがあれば追加
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# サービスの初期化
google_maps_service = GoogleMapsService(api_key=settings.GOOGLE_MAPS_API_KEY)
sentiment_service = SentimentAnalysisService(api_key=settings.OPENAI_API_KEY)

# Supabase 同期クライアントの初期化に戻す
if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
    logger.error("Supabase URLまたはKeyが設定されていません。")
    supabase_client = None
else:
    # create_client を使用して同期クライアントを初期化
    supabase_client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# LocationServiceに同期クライアントを渡す
if supabase_client:
    location_service = LocationService(google_maps_service, sentiment_service, supabase_client)
else:
    logger.warning("Supabaseクライアントが初期化できなかったため、保存機能なしで LocationService をセットアップします。")
    location_service = None

# --- リクエストボディのモデル定義を追加 ---
class SearchRequest(BaseModel):
    latitude: float
    longitude: float
# -------------------------------------

@app.get("/")
async def root():
    return {"message": "雀荘検索API", "version": "1.0"}

@app.get("/api/search_by_keyword")
async def api_search_by_keyword(keyword: str = Query(...)):
    # LocationServiceが初期化されているかチェック
    if not location_service:
        logger.error("LocationServiceが初期化されていません（Supabase設定不備の可能性）。")
        raise HTTPException(status_code=500, detail="サーバー内部エラー: サービスが利用できません。")

    logger.info(f"Keyword search request received: keyword={keyword}")
    try:
        # LocationService にキーワード検索メソッドを呼び出す (後で LocationService に実装)
        results = await location_service.search_by_keyword(keyword)
        logger.info(f"Keyword search completed. Found {len(results)} results.")
        return {"results": results}
    except googlemaps.exceptions.ApiError as e: # googlemaps をインポートする必要がある
        logger.error(f"Google Maps API error: {e}")
        raise HTTPException(status_code=500, detail="Google Maps API エラーが発生しました。")
    except ValueError as e: # 地名が見つからない場合など LocationService で発生させる想定
        logger.warning(f"Keyword search warning: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred during keyword search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="予期せぬエラーが発生しました。")

@app.post("/api/search")
async def search_nearby(request: SearchRequest):
    # LocationServiceが初期化されているかチェック
    if not location_service:
        logger.error("LocationServiceが初期化されていません（Supabase設定不備の可能性）。")
        raise HTTPException(status_code=500, detail="サーバー内部エラー: サービスが利用できません。")

    logger.info(f"Search request received: lat={request.latitude}, lng={request.longitude}")
    try:
        results = await location_service.search_nearby_jongso(
            latitude=request.latitude,
            longitude=request.longitude
        )
        logger.info(f"Search completed. Found {len(results)} results.")
        return {"results": results}
    except googlemaps.exceptions.ApiError as e:
        logger.error(f"Google Maps API error: {e}")
        raise HTTPException(status_code=500, detail="Google Maps API エラーが発生しました。")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="予期せぬエラーが発生しました。")

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Vercelのサーバーレス関数として動作するためのハンドラー
def handler(request: Request):
    return app