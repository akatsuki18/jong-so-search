import googlemaps
from typing import List, Dict, Any
from ..config import settings
from ..utils.text_analyzer import TextAnalyzer
import requests
from bs4 import BeautifulSoup

class GoogleMapsService:
    def __init__(self):
        self.client = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
        self.text_analyzer = TextAnalyzer()

    def search_nearby_places(self, latitude: float, longitude: float) -> Dict[str, Any]:
        return self.client.places_nearby(
            location=(latitude, longitude),
            radius=3000,
            keyword="麻雀",
            type="establishment",
            language="ja"
        )

    def search_nearby_places_by_keyword(self, keyword: str) -> dict:
        return self.client.places(
            query=f"{keyword} 麻雀",
            max_results=10,
            language="ja"
        )

    def get_place_reviews(self, place_id: str) -> List[str]:
        details = self.client.place(
            place_id=place_id,
            language="ja"
        )
        reviews = details.get("result", {}).get("reviews", [])
        return [r.get("text", "") for r in reviews[:5]]  # 最初の5レビューだけ使用

    async def get_smoking_status(self, name: str, address: str) -> str:
        urls = self._search_google_places(f"{name} {address} 雀荘 禁煙")
        texts = []
        for url in urls:
            page_text = self._fetch_page_text(url)
            if page_text:
                texts.append(page_text)

        combined_text = "\n".join(texts)
        if combined_text:
            return await self.text_analyzer.analyze_smoking_info(combined_text)
        return "情報なし"

    def _search_google_places(self, query: str) -> List[str]:
        url = "https://google.serper.dev/search"
        payload = {
            "q": query,
            "gl": "jp",
            "hl": "ja"
        }
        headers = {
            "X-API-KEY": settings.SERPER_API_KEY,
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            return [item.get('link') for item in data.get('organic', [])[:3]]
        return []

    def _fetch_page_text(self, url: str) -> str:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                return soup.get_text(separator="\n", strip=True)
            return ""
        except Exception as e:
            print(f"クロールエラー: {url}, {e}")
            return ""