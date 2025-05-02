from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import json
import logging
import os
import asyncio
from pydantic import BaseModel
from supabase import create_client, Client
from config import settings
from services import GoogleMapsService, LocationService, SentimentAnalysisService

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
sentiment_service = SentimentAnalysisService()

# Supabaseクライアントの初期化
if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
    logger.error("Supabase URLまたはKeyが設定されていません。")
    # ここでエラー処理またはデフォルトの動作を決定
    # 例: アプリケーションを終了させる、または機能制限モードで起動
    # raise SystemExit("Supabaseの設定が不十分です。") # アプリを停止する場合
    supabase_client = None # またはNoneを設定し、後続処理でNoneチェック
else:
    supabase_client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# LocationServiceにSupabaseクライアントを渡す
if supabase_client: # クライアントが正常に初期化された場合のみ
    location_service = LocationService(google_maps_service, sentiment_service, supabase_client)
else:
    # Supabaseが使えない場合の代替処理（例: 保存機能なしで起動）
    logger.warning("Supabaseクライアントが初期化できなかったため、保存機能なしで LocationService をセットアップします。")
    # ここでは LocationService の初期化自体をスキップするか、
    # Supabaseクライアントを必要としないダミー実装を渡すなどの対応が必要になる場合があります。
    # 今回は初期化せず、エンドポイント側でチェックすることにします。
    location_service = None

# モックデータ
mock_shops = [
    {
        "id": "mock1",
        "name": "雀荘A",
        "address": "東京都新宿区1-1-1",
        "lat": 35.6895,
        "lng": 139.6917,
        "rating": 4.5,
        "user_ratings_total": 123,
        "smoking_status": "全面禁煙",
        "positive_score": 8,
        "negative_score": 2,
        "summary": "きれいな雀荘です。全卓禁煙。",
        "last_fetched_at": "2023-11-01T12:00:00"
    },
    {
        "id": "mock2",
        "name": "雀荘B",
        "address": "東京都渋谷区2-2-2",
        "lat": 35.6580,
        "lng": 139.7016,
        "rating": 4.0,
        "user_ratings_total": 89,
        "smoking_status": "分煙",
        "positive_score": 6,
        "negative_score": 4,
        "summary": "広い店内で快適に遊べます。",
        "last_fetched_at": "2023-11-02T14:30:00"
    }
]

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
    # キーワード検索の処理
    filtered_shops = [shop for shop in mock_shops if keyword.lower() in shop["name"].lower()]
    return {"results": filtered_shops}

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