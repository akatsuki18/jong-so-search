import logging
import googlemaps
from fastapi import HTTPException
from geopy.distance import geodesic
from datetime import datetime, timezone, timedelta # timedelta を追加
from postgrest.exceptions import APIError
# 外部サービスのインポートパスはプロジェクト構造に合わせて調整が必要
# from .google_maps_service import GoogleMapsService
# from .sentiment_analysis_service import SentimentAnalysisService
# from supabase import Client
from supabase import Client
# from supabase_async import AsyncClient # 非同期クライアントをインポート

logger = logging.getLogger(__name__)

# --- 仮の Service クラス定義 ---
# 依存関係エラーを避けるため、一時的にダミークラスを定義
# 実際の Service クラスが別ファイルにある場合はそちらをインポートする
class GoogleMapsService:
    def geocode(self, address):
        # ダミー実装
        print(f"[Dummy] Geocoding: {address}")
        # 例: "銀座" の場合にダミーの緯度経度を返す
        if "銀座" in address:
            return [{'geometry': {'location': {'lat': 35.6716, 'lng': 139.7666}}}]
        return []

    def text_search(self, query, language):
        # ダミー実装
        print(f"[Dummy] Text searching: {query} ({language})")
        # ダミーの結果を返す
        return {
            'results': [
                {
                    'place_id': 'dummy_place_id_1',
                    'name': f'{query} 結果1',
                    'formatted_address': 'ダミー住所1',
                    'geometry': {'location': {'lat': 35.67, 'lng': 139.76}},
                    'rating': 4.0,
                    'user_ratings_total': 50
                }
            ]
        }

class SentimentAnalysisService:
    # ダミー実装
    pass

class Client:
    # ダミー実装 (Supabase クライアントの模倣)
    pass
# -----------------------------


class LocationService:
    # 実際の Service クラスや Client を受け取るように修正が必要
    def __init__(self, maps_service: GoogleMapsService, sentiment_service: SentimentAnalysisService, db_client: Client):
        self.maps_service = maps_service
        self.sentiment_service = sentiment_service
        self.db_client = db_client
        logger.info("LocationService initialized with provided services.")
        self.walk_speed_km_per_hour = 4.8 # 徒歩速度 (km/h), 例: 80m/分 = 4.8km/h

    async def _get_jongso_from_db(self, place_id: str) -> dict | None:
        """指定された place_id を持つ雀荘情報をDBから取得する"""
        if not self.db_client:
            logger.warning("Supabase client is not available, skipping DB query.")
            return None

        logger.debug(f"Querying DB for place_id: {place_id}")
        try:
            response = self.db_client.table('jongso_shops') \
                .select("place_id, smoking_status, last_fetched_at, positive_score, negative_score, summary") \
                .eq('place_id', place_id) \
                .maybe_single() \
                .execute()

            # response が None でなく、かつ data 属性を持つかチェック
            if response and hasattr(response, 'data') and response.data:
                logger.debug(f"Found DB record for {place_id}: {response.data}")
                return response.data
            else:
                # レスポンスが期待通りでない場合 (None や data 無し含む)
                logger.warning(f"No valid DB record found or unexpected response for {place_id}. Response: {response}")
                return None
        except APIError as e:
            # maybe_single() で結果が0件の場合、PostgREST は 204 を返し、
            # postgrest-py は APIError を発生させる。これはデータが無い正常ケースとして扱う。
            if e.code == '204':
                logger.warning(f"No DB record found for {place_id} (APIError 204 from maybe_single).")
                return None
            else:
                # それ以外の APIError は本来のエラーとしてログ出力
                logger.error(f"APIError querying database for place_id {place_id}: {e}", exc_info=True)
                return None
        except Exception as e:
            logger.error(f"Unexpected error querying database for place_id {place_id}: {e}", exc_info=True)
            return None

    async def _process_place_details(self, place: dict, distanceKm: float | None = None, walkMinutes: int | None = None):
        """Google Place の情報にDB情報やセンチメント分析結果、距離情報を追加する共通処理"""
        place_id = place.get('place_id')
        if not place_id:
            logger.warning("Place details processing skipped: place_id is missing.")
            return place

        logger.debug(f"Processing details for place_id: {place_id}")

        db_data = await self._get_jongso_from_db(place_id)

        smoking_status = "不明"
        last_fetched_at = None
        db_positive_score = None
        db_negative_score = None
        db_summary = None

        if db_data:
            smoking_status = db_data.get('smoking_status', "不明")
            last_fetched_at = db_data.get('last_fetched_at')
            db_positive_score = db_data.get('positive_score')
            db_negative_score = db_data.get('negative_score')
            db_summary = db_data.get('summary')
            logger.debug(f"Using DB info for {place_id}: Smoking={smoking_status}, FetchedAt={last_fetched_at}, Scores=({db_positive_score},{db_negative_score}), Summary={db_summary is not None}")
        else:
            logger.debug(f"No DB data found for {place_id}, using defaults or fetching new.")

        positive_score = db_positive_score
        negative_score = db_negative_score
        summary = db_summary if db_summary else "レビュー情報取得中..."

        should_fetch_reviews = positive_score is None or negative_score is None or summary == "レビュー情報取得中..."
        if should_fetch_reviews:
            logger.debug(f"Fetching reviews/sentiment for {place_id} as DB data is missing or incomplete.")
            try:
                details = self.maps_service.place_details(place_id=place_id, fields=['review'], language='ja')
                reviews = details.get('result', {}).get('reviews', [])
                logger.debug(f"Found {len(reviews)} reviews for {place_id} via place_details.")

                if reviews:
                    review_texts = [review.get('text', '') for review in reviews if review.get('text')]
                    if review_texts:
                        sentiment_results = self.sentiment_service.analyze_text_list(review_texts)
                        positive_score = round(sum(r['positive_score'] for r in sentiment_results) / len(sentiment_results) * 10)
                        negative_score = round(sum(r['negative_score'] for r in sentiment_results) / len(sentiment_results) * 10)
                        logger.debug(f"Calculated Sentiment scores for {place_id}: Pos={positive_score}, Neg={negative_score}")
                        summary = self.sentiment_service.get_summary_from_reviews(reviews)
                        logger.debug(f"Generated summary for {place_id}: {summary[:50]}...")

                        # DBに喫煙情報がない場合にレビューから判定する
                        if smoking_status == "不明":
                            smoking_status = self.sentiment_service.get_smoking_status_from_reviews(reviews)
                            logger.debug(f"Determined smoking status for {place_id} from reviews: {smoking_status}")

                    else:
                        logger.debug(f"No review texts found for {place_id} to analyze.")
                        summary = db_summary if db_summary else "有効なレビューが見つかりませんでした。"
                else:
                    logger.debug(f"No reviews found for {place_id} in place_details result.")
                    summary = db_summary if db_summary else "レビューはありません。"

            except googlemaps.exceptions.ApiError as e:
                logger.error(f"Google Maps Place Details API error for {place_id}: {e}")
                summary = db_summary if db_summary else "レビュー情報の取得中にエラーが発生しました。"
            except Exception as e:
                logger.error(f"Unexpected error during sentiment analysis for {place_id}: {e}", exc_info=True)
                summary = db_summary if db_summary else "センチメント分析中に予期せぬエラーが発生しました。"
        else:
            logger.debug(f"Skipping review fetch/sentiment analysis for {place_id} as sufficient data exists in DB.")

        processed_place = {
            "id": place_id,
            "name": place.get('name'),
            "address": place.get('formatted_address') or place.get('vicinity'),
            "lat": place.get('geometry', {}).get('location', {}).get('lat'),
            "lng": place.get('geometry', {}).get('location', {}).get('lng'),
            "rating": place.get('rating'),
            "user_ratings_total": place.get('user_ratings_total'),
            "smoking_status": smoking_status,
            "positive_score": positive_score if positive_score is not None else 0,
            "negative_score": negative_score if negative_score is not None else 0,
            "summary": summary,
            "last_fetched_at": last_fetched_at,
            "distanceKm": distanceKm,
            "walkMinutes": walkMinutes
        }
        return processed_place

    async def search_nearby_jongso(self, latitude: float, longitude: float):
        """指定された緯度経度の周辺にある雀荘を検索する"""
        logger.info(f"Searching nearby jongso at lat={latitude}, lng={longitude}")
        try:
            location_tuple = (latitude, longitude)
            places_result = self.maps_service.nearby_search(
                location=location_tuple,
                radius=3000,
                keyword='雀荘',
                language='ja'
            )

            if not places_result or 'results' not in places_result:
                logger.warning("No nearby places found with keyword '雀荘'.")
                return []

            potential_places = places_result['results']
            logger.info(f"Nearby search with keyword '雀荘' found {len(potential_places)} potential places.")

            user_location = (latitude, longitude) # ユーザーの現在地

            processed_results = []
            for place in potential_places:
                place_location_data = place.get('geometry', {}).get('location', {})
                place_lat = place_location_data.get('lat')
                place_lng = place_location_data.get('lng')

                distanceKm = None
                walkMinutes = None

                if place_lat is not None and place_lng is not None:
                    place_location = (place_lat, place_lng)
                    try:
                        # 距離計算 (km)
                        distanceKm = geodesic(user_location, place_location).km
                        # 徒歩時間計算 (分)
                        walk_speed_km_per_minute = self.walk_speed_km_per_hour / 60
                        if walk_speed_km_per_minute > 0:
                            walkMinutes = round(distanceKm / walk_speed_km_per_minute)
                        else:
                            walkMinutes = None # 速度が0以下なら計算しない
                    except ValueError:
                        logger.warning(f"Could not calculate distance for place {place.get('name')}. Invalid coordinates?")
                        distanceKm = None
                        walkMinutes = None

                processed_place = await self._process_place_details(place, distanceKm=distanceKm, walkMinutes=walkMinutes)
                processed_results.append(processed_place)

            # レーティングの降順でソート (Noneは末尾に)
            processed_results.sort(key=lambda x: x.get('rating', -1) if x.get('rating') is not None else -1, reverse=True)

            await self._save_results_to_db(processed_results)

            logger.info(f"Finished processing {len(processed_results)} nearby jongso.")
            return processed_results

        except googlemaps.exceptions.ApiError as e:
            logger.error(f"Google Maps Nearby Search API error: {e}")
            raise HTTPException(status_code=503, detail="Google Maps API への接続でエラーが発生しました。") from e
        except Exception as e:
            logger.error(f"Unexpected error during nearby search: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="周辺検索中に予期せぬエラーが発生しました。") from e


    async def search_by_keyword(self, keyword: str):
        """
        キーワード（地名または施設名）で雀荘を検索する。
        地名が指定された場合は、その地点周辺を検索する。
        施設名が指定された場合は、テキスト検索を行う。
        """
        logger.info(f"Attempting to geocode keyword: {keyword}")
        try:
            geocode_result = self.maps_service.geocode(keyword)
            if geocode_result and isinstance(geocode_result, list) and len(geocode_result) > 0:
                location = geocode_result[0]['geometry']['location']
                lat = location['lat']
                lng = location['lng']
                logger.info(f"Geocoding successful for '{keyword}': lat={lat}, lng={lng}. Searching nearby.")
                return await self.search_nearby_jongso(latitude=lat, longitude=lng)
            else:
                logger.info(f"Could not geocode '{keyword}' as a location. Assuming it's a place name/query and performing text search.")
                places_result = self.maps_service.text_search(query=f"雀荘 {keyword}", language='ja')

                if not places_result or 'results' not in places_result or not places_result['results']:
                    logger.warning(f"No places found via text search for keyword: 雀荘 {keyword}")
                    return []

                potential_places = places_result['results']
                logger.info(f"Text search for '雀荘 {keyword}' found {len(potential_places)} potential results.")

                processed_results = []
                for place in potential_places:
                    processed_place = await self._process_place_details(place, distanceKm=None, walkMinutes=None)
                    processed_results.append(processed_place)

                await self._save_results_to_db(processed_results)

                logger.info(f"Finished processing {len(processed_results)} keyword search results.")
                return processed_results

        except googlemaps.exceptions.ApiError as e:
            logger.error(f"Google Maps API error during keyword search for '{keyword}': {e}")
            raise HTTPException(status_code=503, detail="Google Maps API への接続でエラーが発生しました。") from e
        except Exception as e:
            logger.error(f"Unexpected error during keyword search for '{keyword}': {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="キーワード検索中に予期せぬエラーが発生しました。") from e

    async def _save_results_to_db(self, results: list):
        """検索結果リストをDBに保存/更新する。ただし、last_fetched_atが30日以内のレコードは更新しない"""
        if not self.db_client:
            logger.warning("Supabase client is not available, skipping DB save.")
            return
        if not results:
            return

        logger.info(f"Attempting to save/update {len(results)} results to DB table 'jongso_shops', skipping recent records.")

        place_ids = [result['id'] for result in results if result.get('id')]
        if not place_ids:
            logger.warning("No valid place_ids found in results, skipping DB save.")
            return

        # DBから既存レコードのlast_fetched_atを取得
        existing_records = {}
        try:
            response = self.db_client.table('jongso_shops') \
                .select("place_id, last_fetched_at") \
                .in_('place_id', place_ids) \
                .execute()

            if response and hasattr(response, 'data'):
                for record in response.data:
                    existing_records[record['place_id']] = record.get('last_fetched_at')
                logger.debug(f"Fetched last_fetched_at for {len(existing_records)} existing records.")
            else:
                logger.warning(f"Could not fetch existing records or unexpected response: {response}")

        except Exception as e:
            logger.error(f"Error fetching existing records from DB: {e}", exc_info=True)
            # エラーが発生しても、できる限り処理を続行する（既存レコードが見つからなかったものとして扱う）

        records_to_upsert = []
        skipped_count = 0
        current_time_utc = datetime.now(timezone.utc)
        thirty_days_ago = current_time_utc - timedelta(days=30) # 30日前の datetime オブジェクト

        for result in results:
            place_id = result.get('id')
            if not place_id:
                continue # place_id がない結果はスキップ

            existing_last_fetched_at_str = existing_records.get(place_id)

            # 既存レコードがあり、かつ last_fetched_at が30日以内かチェック
            should_skip = False
            if existing_last_fetched_at_str:
                try:
                    # ISO 8601 文字列を aware な datetime オブジェクトに変換
                    existing_last_fetched_at = datetime.fromisoformat(existing_last_fetched_at_str)
                    # タイムゾーン情報がない場合は UTC とみなす (DBの保存形式に依存)
                    if existing_last_fetched_at.tzinfo is None:
                         # 警告: タイムゾーンなしの文字列は予期せぬ挙動の可能性
                         logger.warning(f"last_fetched_at for {place_id} ('{existing_last_fetched_at_str}') lacks timezone info. Assuming UTC.")
                         existing_last_fetched_at = existing_last_fetched_at.replace(tzinfo=timezone.utc)

                    if existing_last_fetched_at > thirty_days_ago:
                        should_skip = True
                        skipped_count += 1
                        logger.debug(f"Skipping update for place_id {place_id}: last_fetched_at ({existing_last_fetched_at}) is within 30 days.")
                except ValueError:
                    logger.warning(f"Could not parse last_fetched_at ('{existing_last_fetched_at_str}') for place_id {place_id}. Proceeding with upsert.")
                except Exception as e:
                    logger.error(f"Error processing last_fetched_at for {place_id}: {e}", exc_info=True)


            if not should_skip:
                record = {
                    'place_id': place_id,
                    'name': result.get('name'),
                    'address': result.get('address'),
                    'lat': result.get('lat'),
                    'lng': result.get('lng'),
                    'rating': result.get('rating'),
                    'user_ratings_total': result.get('user_ratings_total'),
                    'smoking_status': result.get('smoking_status'),
                    'positive_score': result.get('positive_score'),
                    'negative_score': result.get('negative_score'),
                    'summary': result.get('summary'),
                    'last_fetched_at': current_time_utc.isoformat() # 現在時刻を ISO 形式で設定
                }
                records_to_upsert.append(record)

        if not records_to_upsert:
            logger.info(f"No records to upsert after filtering based on last_fetched_at. Skipped {skipped_count} records.")
            return

        logger.info(f"Attempting to upsert {len(records_to_upsert)} records (skipped {skipped_count}).")
        try:
            # upsertのcolumnsパラメータに 'last_fetched_at' を追加する必要はない（デフォルトですべてのカラムが対象）
            self.db_client.table('jongso_shops').upsert(records_to_upsert).execute()
            logger.info(f"Successfully upserted {len(records_to_upsert)} records to DB table 'jongso_shops'.")
        except Exception as e:
            logger.error(f"Error upserting records to database table 'jongso_shops': {e}", exc_info=True)