from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import json
import logging

# モデルをインポート（相対インポートに変更）
from models import Location, JongsoShop, SearchResponse
from services import GoogleMapsService, LocationService, SentimentAnalysisService
from config import settings

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORSミドルウェア
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# サービスの初期化
google_maps_service = GoogleMapsService(settings.GOOGLE_MAPS_API_KEY)
sentiment_service = SentimentAnalysisService()
location_service = LocationService(google_maps_service, sentiment_service)

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

@app.get("/")
async def root():
    return {"message": "雀荘検索API", "version": "1.0"}

@app.get("/api/search_by_keyword")
async def api_search_by_keyword(keyword: str = Query(...)):
    # キーワード検索の処理
    filtered_shops = [shop for shop in mock_shops if keyword.lower() in shop["name"].lower()]
    return {"results": filtered_shops}

@app.post("/api/search")
async def api_search_jongso(location: Location):
    logger.info(f"位置情報による検索: 緯度 {location.latitude}, 経度 {location.longitude}")
    try:
        # 感情分析を含む検索処理
        shops = await location_service.search_nearby_jongso(
            latitude=location.latitude,
            longitude=location.longitude
        )
        logger.info(f"検索結果: {len(shops)}件の雀荘が見つかりました")
        return {"results": shops}
    except Exception as e:
        logger.error(f"Error searching jongso: {str(e)}", exc_info=True)
        # エラー時は空のリストを返す方が良いかもしれない
        return {"results": []} # エラー時は空リストを返すように変更

# Vercelのサーバーレス関数として動作するためのハンドラー
def handler(request: Request):
    return app