import googlemaps
import logging

logger = logging.getLogger(__name__)

class GoogleMapsService:
    """Google Maps API とのやり取りを担当するサービスクラス"""
    def __init__(self, api_key: str):
        if not api_key:
            logger.error("Google Maps API Key is not provided.")
            # APIキーがない場合、クライアントを初期化しないか、エラーを発生させる
            # ここでは None を設定し、各メソッドでチェックする方針とする
            self.client = None
            logger.warning("GoogleMapsService initialized without a client due to missing API key.")
        else:
            self.client = googlemaps.Client(key=api_key) # 実際のクライアント初期化
            logger.info("GoogleMapsService initialized successfully.")

    def _check_client(self):
        """APIクライアントが初期化されているかチェックするヘルパーメソッド"""
        if self.client is None:
            logger.error("Google Maps client is not initialized. Check API Key.")
            # 例外を発生させて処理を中断させる
            raise ValueError("Google Maps client is not available due to missing API key.")

    def geocode(self, address):
        """住所から緯度経度を取得する"""
        self._check_client() # クライアントが利用可能かチェック
        logger.info(f"Geocoding address: {address}")
        try:
            result = self.client.geocode(address, language='ja') # 日本語結果を優先
            logger.debug(f"Geocode result for {address}: {result}")
            return result
        except googlemaps.exceptions.ApiError as e:
            logger.error(f"Google Maps Geocoding API error for '{address}': {e}")
            raise # エラーを呼び出し元に伝播させる
        except Exception as e:
            logger.error(f"Unexpected error during geocoding for '{address}': {e}", exc_info=True)
            raise

    def text_search(self, query, language='ja'):
        """テキストクエリで場所を検索する"""
        self._check_client()
        logger.info(f"Text searching for: '{query}' with language '{language}'")
        try:
            result = self.client.places(query=query, language=language)
            logger.debug(f"Text search result for '{query}': {len(result.get('results', []))} places found.")
            return result
        except googlemaps.exceptions.ApiError as e:
            logger.error(f"Google Maps Text Search API error for query '{query}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during text search for '{query}': {e}", exc_info=True)
            raise

    def nearby_search(self, location, radius, type=None, keyword=None, language='ja'):
        """指定地点の周辺を検索する"""
        self._check_client()
        # location は (lat, lng) のタプルであることを想定
        logger.info(f"Nearby search at {location} (radius: {radius}, type: {type}, keyword: {keyword}, lang: {language})")
        try:
            result = self.client.places_nearby(location=location, radius=radius, type=type, keyword=keyword, language=language)
            logger.debug(f"Nearby search result for {location}: {len(result.get('results', []))} places found.")
            return result
        except googlemaps.exceptions.ApiError as e:
            logger.error(f"Google Maps Nearby Search API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during nearby search at {location}: {e}", exc_info=True)
            raise

    def place_details(self, place_id, fields, language='ja'):
        """場所の詳細情報を取得する"""
        self._check_client()
        logger.info(f"Fetching details for place_id: {place_id} (fields: {fields}, lang: {language})")
        try:
            result = self.client.place(place_id=place_id, fields=fields, language=language)
            logger.debug(f"Place details result for {place_id}: {result.get('result', {}).get('name')}")
            return result
        except googlemaps.exceptions.ApiError as e:
            logger.error(f"Google Maps Place Details API error for {place_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during place details fetch for {place_id}: {e}", exc_info=True)
            raise