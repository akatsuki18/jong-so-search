import googlemaps
import asyncio
from functools import partial
from typing import Dict, Any, List, Optional
import logging
from config import settings
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import os

logger = logging.getLogger(__name__)

class SentimentAnalysisService:
    def __init__(self):
        chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-3.5-turbo")
        if not settings.OPENAI_API_KEY:
            logger.error("OpenAI APIキーが設定されていません。感情分析はスキップされます。")
            self.llm = None
        else:
            self.llm = ChatOpenAI(
                openai_api_key=settings.OPENAI_API_KEY,
                temperature=0,
                model=chat_model,
            )
        self.prompt = ChatPromptTemplate.from_template("""
あなたは{genre}の専門家です。

以下のレビューを読み、以下のフォーマットに厳密に従って要約とスコアリングをしてください。
レビューが少ない、または情報がない場合は、要約は「情報なし」とし、スコアはnullとしてください。

【出力フォーマット】
要約: （要約文）
ポジティブ度: （半角数字のみ、%はつけない）
ネガティブ度: （半角数字のみ、%はつけない）

レビュー:
{combined_reviews}
""")

    async def analyze_reviews(self, reviews: List[str]) -> Dict[str, Any]:
        if not self.llm:
            return {"summary": "APIキー未設定", "positive_score": None, "negative_score": None}

        if not reviews:
            return {"summary": "情報なし", "positive_score": None, "negative_score": None}

        combined_reviews = "\n".join(reviews)
        if len(combined_reviews) > 3000:
            combined_reviews = combined_reviews[:3000]

        logger.info(f"感情分析実行: レビュー数={len(reviews)}, 文字数={len(combined_reviews)}")
        try:
            response = await self.llm.ainvoke(
                self.prompt.format(genre="雀荘", combined_reviews=combined_reviews)
            )
            content = response.content
            logger.info(f"感情分析 応答: {content}")

            lines = content.splitlines()
            summary = "情報なし"
            positive_score = None
            negative_score = None

            logger.debug("LLMレスポンスのパース開始")
            for line in lines:
                logger.debug(f"パース中の行: {line}")
                if "要約:" in line:
                    summary = line.split("要約:")[-1].strip()
                    logger.debug(f"  -> 要約抽出: {summary}")
                if "ポジティブ度:" in line:
                    try:
                        score_str = line.split("ポジティブ度:")[-1].replace("%", "").strip()
                        if score_str.isdigit():
                            positive_score = int(score_str)
                            logger.debug(f"  -> ポジティブ度抽出: {positive_score}")
                        else:
                            logger.warning(f"ポジティブ度の値が数字ではありません: '{score_str}' (元行: {line})")
                    except Exception as parse_e:
                        logger.warning(f"ポジティブ度のパース中にエラー: {parse_e} (元行: {line})")
                if "ネガティブ度:" in line:
                    try:
                        score_str = line.split("ネガティブ度:")[-1].replace("%", "").strip()
                        if score_str.isdigit():
                            negative_score = int(score_str)
                            logger.debug(f"  -> ネガティブ度抽出: {negative_score}")
                        else:
                            logger.warning(f"ネガティブ度の値が数字ではありません: '{score_str}' (元行: {line})")
                    except Exception as parse_e:
                        logger.warning(f"ネガティブ度のパース中にエラー: {parse_e} (元行: {line})")
            logger.debug("LLMレスポンスのパース完了")

            if not summary:
                summary = "情報なし"

            result_data = {"summary": summary, "positive_score": positive_score, "negative_score": negative_score}
            logger.info(f"感情分析結果: {result_data}")
            return result_data

        except Exception as e:
            logger.error(f"感情分析API呼び出しエラー: {e}", exc_info=True)
            return {"summary": "分析エラー", "positive_score": None, "negative_score": None}

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
        logger.info(f"場所詳細取得開始: place_id={place_id}")
        loop = asyncio.get_event_loop()
        try:
            details = await loop.run_in_executor(
                None,
                partial(
                    self.client.place,
                    place_id=place_id,
                    fields=["name", "vicinity", "geometry", "rating", "user_ratings_total", "review"],
                    language="ja"
                )
            )
            logger.info(f"場所詳細取得完了: place_id={place_id}, ステータス: {details.get('status')}")
            return details
        except Exception as e:
            logger.error(f"場所詳細取得エラー: place_id={place_id}, {e}", exc_info=True)
            return {"result": {}, "status": "ERROR"}

    async def get_place_reviews(self, place_id: str) -> List[str]:
        """場所IDからレビューテキストのリストを取得する"""
        details = await self.get_place_details(place_id)
        reviews_data = details.get("result", {}).get("reviews", [])
        reviews_text = [r.get("text", "") for r in reviews_data[:5] if r.get("text")]
        logger.info(f"口コミ取得: place_id={place_id}, 件数={len(reviews_text)}")
        return reviews_text

class LocationService:
    def __init__(self, google_maps_service: GoogleMapsService, sentiment_service: SentimentAnalysisService):
        self.google_maps_service = google_maps_service
        self.sentiment_service = sentiment_service

    async def search_nearby_jongso(self, latitude: float, longitude: float) -> List[Dict[str, Any]]:
        """位置情報に基づいて雀荘を検索し、感情分析結果を含めて返す"""
        logger.info("LocationService: search_nearby_jongso 呼び出し")
        places_result = await self.google_maps_service.search_nearby_places(latitude, longitude)

        results = []
        place_list = places_result.get("results", [])
        logger.info(f"Google Mapsから {len(place_list)} 件の結果を取得")

        tasks = []
        for place in place_list:
            place_id = place.get("place_id")
            if place_id:
                tasks.append(self._process_place(place))

        processed_results = await asyncio.gather(*tasks)

        results = [res for res in processed_results if res is not None]

        logger.info(f"最終的な結果件数: {len(results)}")
        return self._sort_results(results)

    async def _process_place(self, place: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """個々の店舗情報を処理（口コミ取得、感情分析）"""
        place_id = place.get("place_id")
        name = place.get("name", "")
        logger.info(f"店舗処理開始: {name} (place_id={place_id})")

        try:
            reviews = await self.google_maps_service.get_place_reviews(place_id)

            sentiment_result = await self.sentiment_service.analyze_reviews(reviews)

            address = place.get("vicinity", "")
            rating = place.get("rating", 0)
            user_ratings_total = place.get("user_ratings_total", 0)
            location = place.get("geometry", {}).get("location", {})
            lat = location.get("lat")
            lng = location.get("lng")

            shop_data = {
                "id": place_id,
                "name": name,
                "address": address,
                "lat": lat,
                "lng": lng,
                "rating": rating,
                "user_ratings_total": user_ratings_total,
                "positive_score": sentiment_result["positive_score"],
                "negative_score": sentiment_result["negative_score"],
                "summary": sentiment_result["summary"],
            }
            logger.info(f"店舗処理完了: {name}")
            return shop_data

        except Exception as e:
            logger.error(f"店舗処理エラー: {name} (place_id={place_id}), {e}", exc_info=True)
            return None

    def _sort_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """評価とレビュー数でソートする"""
        return sorted(
            results,
            key=lambda x: (-x.get("rating", 0), -x.get("user_ratings_total", 0))
        )