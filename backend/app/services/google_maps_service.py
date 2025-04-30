import googlemaps
import aiohttp
from typing import List, Dict, Any
from ..config import settings
from ..utils.text_analyzer import TextAnalyzer
import requests
from bs4 import BeautifulSoup
import asyncio
from functools import partial

class GoogleMapsService:
    def __init__(self):
        self.client = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
        self.text_analyzer = TextAnalyzer()

    async def search_nearby_places(self, latitude: float, longitude: float) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
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

    async def search_nearby_places_by_keyword(self, keyword: str) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(
                self.client.places,
                query=f"{keyword} 麻雀",
                language="ja"
            )
        )

    async def get_place_reviews(self, place_id: str) -> List[str]:
        loop = asyncio.get_event_loop()
        details = await loop.run_in_executor(
            None,
            partial(
                self.client.place,
                place_id=place_id,
                language="ja"
            )
        )
        reviews = details.get("result", {}).get("reviews", [])
        return [r.get("text", "") for r in reviews[:5]]  # 最初の5レビューだけ使用

    async def get_smoking_status(self, name: str, address: str) -> str:
        urls = await self._search_google_places(f"{name} {address} 雀荘 禁煙")
        texts = []
        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_page_text(session, url) for url in urls]
            texts = await asyncio.gather(*tasks)

        combined_text = "\n".join([text for text in texts if text])
        if combined_text:
            return await self.text_analyzer.analyze_smoking_info(combined_text)
        return "情報なし"

    async def _search_google_places(self, query: str) -> List[str]:
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

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return [item.get('link') for item in data.get('organic', [])[:3]]
        return []

    async def _fetch_page_text(self, session: aiohttp.ClientSession, url: str) -> str:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    text = await response.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    return soup.get_text(separator="\n", strip=True)
                return ""
        except Exception as e:
            print(f"クロールエラー: {url}, {e}")
            return ""