from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from ..models.schemas import JongsoShop
from .google_maps_service import GoogleMapsService
from .sentiment_service import SentimentService
from ..repositories.jongso_repository import JongsoRepository
from uuid import uuid4

class JongsoService:
    def __init__(
        self,
        google_maps_service: GoogleMapsService,
        sentiment_service: SentimentService,
        jongso_repository: JongsoRepository
    ):
        self.google_maps_service = google_maps_service
        self.sentiment_service = sentiment_service
        self.jongso_repository = jongso_repository

    async def search_nearby_shops(self, latitude: float, longitude: float) -> List[Dict[str, Any]]:
        try:
            places_result = await self.google_maps_service.search_nearby_places(
                latitude=latitude,
                longitude=longitude
            )

            results = []
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

            for place in places_result.get("results", []):
                try:
                    name = place.get("name", "")
                    address = place.get("vicinity", "")
                    rating = place.get("rating", 0)
                    user_ratings_total = place.get("user_ratings_total", 0)
                    place_id = place.get("place_id", "")

                    # 既存チェック
                    existing = await self.jongso_repository.get_by_name_and_address(name, address)

                    if existing and existing.last_fetched_at > thirty_days_ago:
                        results.append(self._format_shop_data(existing))
                        continue

                    # 新規データ取得
                    location = place.get("geometry", {}).get("location", {})
                    lat = location.get("lat")
                    lng = location.get("lng")

                    # 口コミ取得と感情分析
                    reviews = await self.google_maps_service.get_place_reviews(place_id)
                    sentiment_result = await self.sentiment_service.analyze_reviews(reviews)

                    # 禁煙情報取得
                    smoking_status = await self.google_maps_service.get_smoking_status(name, address)

                    # 新規データ保存
                    shop_data = {
                        "id": str(uuid4()),
                        "name": name,
                        "address": address,
                        "lat": lat,
                        "lng": lng,
                        "rating": rating,
                        "user_ratings_total": user_ratings_total,
                        "smoking_status": smoking_status,
                        "positive_score": sentiment_result["positive_score"] if sentiment_result else None,
                        "negative_score": sentiment_result["negative_score"] if sentiment_result else None,
                        "summary": sentiment_result["summary"] if sentiment_result else None,
                        "last_fetched_at": datetime.utcnow()
                    }

                    if not existing:
                        await self.jongso_repository.create(shop_data)

                    results.append(self._format_shop_data(shop_data))
                except Exception as e:
                    print(f"Error processing place {name}: {str(e)}")
                    continue

            return self._sort_results(results)
        except Exception as e:
            print(f"Error in search_nearby_shops: {str(e)}")
            raise

    async def search_shops_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        # まずDBから検索
        results = await self.jongso_repository.search_by_keyword(keyword)

        if results:
            # データがあるならそのまま整形して返す
            formatted_results = [self._format_shop_data(shop) for shop in results]
            return self._sort_results(formatted_results)

        print(f"DBから取得したデータの数: {len(results)}")
        if len(results) > 10:
            return formatted_results

        # ここから "Google Mapsに検索をかける" パート
        print(f"DBに存在しなかったため、Google検索を試みます: {keyword}")
        places_result = await self.google_maps_service.search_nearby_places_by_keyword(keyword)

        fetched_results = []
        for place in places_result.get("results", []):
            name = place.get("name", "")
            address = place.get("vicinity", "")
            rating = place.get("rating", 0)
            user_ratings_total = place.get("user_ratings_total", 0)
            place_id = place.get("place_id", "")
            location = place.get("geometry", {}).get("location", {})
            lat = location.get("lat")
            lng = location.get("lng")

            # 口コミ取得＆感情分析
            reviews = await self.google_maps_service.get_place_reviews(place_id)
            sentiment_result = await self.sentiment_service.analyze_reviews(reviews)

            # 禁煙情報取得
            smoking_status = await self.google_maps_service.get_smoking_status(name, address)

            # DB登録
            shop_data = {
                "id": str(uuid4()),
                "name": name,
                "address": address,
                "lat": lat,
                "lng": lng,
                "rating": rating,
                "user_ratings_total": user_ratings_total,
                "smoking_status": smoking_status,
                "positive_score": sentiment_result["positive_score"],
                "negative_score": sentiment_result["negative_score"],
                "summary": sentiment_result["summary"],
                "last_fetched_at": datetime.utcnow()
            }
            await self.jongso_repository.create(shop_data)

            fetched_results.append(self._format_shop_data(shop_data))

        return self._sort_results(fetched_results)

    def _format_shop_data(self, shop: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(shop["id"]) if "id" in shop else "",
            "name": shop["name"],
            "address": shop["address"],
            "lat": float(shop["lat"]),
            "lng": float(shop["lng"]),
            "rating": float(shop["rating"]) if shop["rating"] else None,
            "user_ratings_total": shop["user_ratings_total"],
            "summary": shop["summary"],
            "positive_score": shop["positive_score"],
            "negative_score": shop["negative_score"],
            "smoking_status": shop["smoking_status"],
            "last_fetched_at": shop["last_fetched_at"],
        }

    def _sort_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(
            results,
            key=lambda x: (-self._calculate_adjusted_rating(x), -x["user_ratings_total"])
        )

    def _calculate_adjusted_rating(self, place: Dict[str, Any]) -> float:
        base_rating = place["rating"]
        if base_rating is None:
            return 0.0

        positive_score = place.get("positive_score")
        if positive_score is not None:
            return base_rating + (positive_score / 100)
        return base_rating