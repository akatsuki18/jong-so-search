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
        self.sentiment_prompt = ChatPromptTemplate.from_template("""
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

        # --- 喫煙状況分析用プロンプトを追加 ---
        self.smoking_prompt = ChatPromptTemplate.from_template("""
あなたは以下の日本の雀荘に関するレビューを読む専門家です。
レビュー全体の文脈を考慮し、この雀荘の喫煙状況を最も適切に表すものを、以下の選択肢の中から**一つだけ**選んでください。

選択肢:
- 禁煙 (完全に禁煙されている場合)
- 分煙 (喫煙エリアと禁煙エリアが分かれている、またはそのように試みられている場合。例：「禁煙席もある」「分煙だが煙が流れてくる」など)
- 喫煙可 (特に制限がない、または喫煙に関する苦情が多い場合)
- 情報なし (レビューから喫煙状況が判断できない場合)

注意点:
- 「禁煙」という単語があっても、レビュー全体で煙の匂いや流れ込みに関する不満が述べられている場合は「分煙」または「喫煙可」と判断してください。
- 単に「タバコ」や「煙」という単語があるだけでは判断せず、それが許可されている状況か、問題となっている状況かを考慮してください。
- 最終的な回答は、選択肢の中の文字列**一つだけ**にしてください。余計な説明は不要です。

レビュー:
{combined_reviews}
""")
        # -------------------------------------\n

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
                self.sentiment_prompt.format(genre="雀荘", combined_reviews=combined_reviews)
            )
            content = response.content
            logger.info(f"感情分析 応答: {content}")

            lines = content.splitlines()
            summary = "情報なし"
            positive_score = None
            negative_score = None

            logger.debug("感情分析レスポンスのパース開始")
            for line in lines:
                logger.debug(f"パース中の行(感情): {line}")
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
            logger.debug("感情分析レスポンスのパース完了")

            if not summary:
                summary = "情報なし"

            result_data = {"summary": summary, "positive_score": positive_score, "negative_score": negative_score}
            logger.info(f"感情分析結果: {result_data}")
            return result_data

        except Exception as e:
            logger.error(f"感情分析API呼び出しエラー: {e}", exc_info=True)
            return {"summary": "分析エラー", "positive_score": None, "negative_score": None}

    # --- 喫煙状況分析メソッドを追加 ---
    async def analyze_smoking_status(self, reviews: List[str]) -> str:
        """レビューから喫煙状況を分析する"""
        if not self.llm:
            return "情報なし" # APIキーがない

        if not reviews:
            return "情報なし" # レビューがない

        combined_reviews = "\n".join(reviews)
        if len(combined_reviews) > 3000:
            combined_reviews = combined_reviews[:3000]

        logger.info(f"喫煙状況分析実行: レビュー数={len(reviews)}, 文字数={len(combined_reviews)}")
        try:
            response = await self.llm.ainvoke(
                self.smoking_prompt.format(combined_reviews=combined_reviews) # 喫煙状況用プロンプトを使用
            )
            result_text = response.content.strip()
            logger.info(f"喫煙状況分析 応答: {result_text}")

            # 応答が選択肢のいずれかに合致するか確認
            valid_statuses = ["禁煙", "分煙", "喫煙可", "情報なし"]
            if result_text in valid_statuses:
                logger.info(f"喫煙状況分析結果: {result_text}")
                return result_text
            else:
                logger.warning(f"喫煙状況分析の応答が予期せぬ形式です: '{result_text}'. '情報なし'として扱います。")
                return "情報なし" # 予期せぬ応答の場合はデフォルト

        except Exception as e:
            logger.error(f"喫煙状況分析API呼び出しエラー: {e}", exc_info=True)
            return "情報なし" # エラー時もデフォルト
    # ----------------------------------\n

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
            # 口コミ取得 (並列化も可能だが、ここでは逐次)
            reviews = await self.google_maps_service.get_place_reviews(place_id)

            # 感情分析と喫煙状況分析を並列実行
            sentiment_task = self.sentiment_service.analyze_reviews(reviews)
            smoking_task = self.sentiment_service.analyze_smoking_status(reviews)

            sentiment_result, smoking_status_result = await asyncio.gather(
                sentiment_task,
                smoking_task
            )

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
                "smoking_status": smoking_status_result # AIによる判定結果で上書き
            }
            logger.info(f"店舗処理完了: {name} - Sentiment: P{sentiment_result['positive_score']} N{sentiment_result['negative_score']}, Smoking: {smoking_status_result}")
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