import googlemaps
import asyncio
from functools import partial
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class GoogleMapsService:
    def __init__(self, api_key: str):
        self.client = googlemaps.Client(key=api_key)

    async def search_nearby_places(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """位置情報に基づいて近くの雀荘を検索する"""
        logger.info(f"Google Maps API検索開始: lat={latitude}, lng={longitude}")
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                partial(
                    self.client.places_nearby,
                    location=(latitude, longitude),
                    radius=3000,
                    keyword="麻雀",
                    type="establishment",
                    language="ja"
                )
            )
            logger.info(f"Google Maps API検索完了. ステータス: {result.get('status')}, 結果件数: {len(result.get('results', []))}")
            # logger.debug(f"Google Maps API Raw Response: {result}") # 詳細デバッグ用
            return result
        except Exception as e:
            logger.error(f"Google Maps API エラー: {e}", exc_info=True)
            raise

    async def search_by_keyword(self, keyword: str) -> dict:
        """キーワードで雀荘を検索する"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(
                self.client.places,
                query=f"{keyword} 麻雀",
                language="ja"
            )
        )

    async def get_place_details(self, place_id: str) -> Dict[str, Any]:
        """場所の詳細情報を取得する"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(
                self.client.place,
                place_id=place_id,
                language="ja"
            )
        )

class LocationService:
    def __init__(self, google_maps_service: GoogleMapsService):
        self.google_maps_service = google_maps_service

    async def search_nearby_jongso(self, latitude: float, longitude: float) -> List[Dict[str, Any]]:
        """位置情報に基づいて雀荘を検索し、整形したデータを返す"""
        logger.info("LocationService: search_nearby_jongso 呼び出し")
        places_result = await self.google_maps_service.search_nearby_places(latitude, longitude)

        results = []
        place_list = places_result.get("results", [])
        logger.info(f"Google Mapsから {len(place_list)} 件の結果を取得")

        for i, place in enumerate(place_list):
            logger.debug(f"Processing place {i+1}/{len(place_list)}: {place.get('name')}")
            name = place.get("name", "")
            address = place.get("vicinity", "")
            rating = place.get("rating", 0)
            user_ratings_total = place.get("user_ratings_total", 0)
            place_id = place.get("place_id", "")
            location = place.get("geometry", {}).get("location", {})
            lat = location.get("lat")
            lng = location.get("lng")

            # 基本情報のみ返す
            shop_data = {
                "id": place_id,
                "name": name,
                "address": address,
                "lat": lat,
                "lng": lng,
                "rating": rating,
                "user_ratings_total": user_ratings_total,
            }
            results.append(shop_data)
            logger.debug(f"Added shop: {name}")

        logger.info(f"整形後の結果件数: {len(results)}")
        sorted_results = self._sort_results(results)
        logger.info(f"ソート後の結果件数: {len(sorted_results)}")
        return sorted_results

    def _sort_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """評価とレビュー数でソートする"""
        return sorted(
            results,
            key=lambda x: (-x.get("rating", 0), -x.get("user_ratings_total", 0))
        )