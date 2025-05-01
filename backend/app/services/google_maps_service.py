import googlemaps
import aiohttp
from typing import List, Dict, Any
from ..config import settings
from .text_analyzer import TextAnalyzer
import requests
from bs4 import BeautifulSoup
import asyncio
from functools import partial
import logging

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
        logger = logging.getLogger(__name__)
        loop = asyncio.get_event_loop()
        all_texts = []

        try:
            # まずGoogle Mapsの口コミを取得
            place_result = await loop.run_in_executor(
                None,
                partial(
                    self.client.places,
                    query=f"{name} {address}",  # 「雀荘」を除去してより正確な検索に
                    language="ja"
                )
            )

            logger.info(f"Google Places API response: {place_result.get('status')}")

            # Google Mapsの口コミを処理
            if place_result.get("results"):
                place_id = place_result["results"][0]["place_id"]
                logger.info(f"Found place_id: {place_id}")

                reviews = await self.get_place_reviews(place_id)
                if reviews:
                    logger.info(f"Found {len(reviews)} reviews")
                    all_texts.append("【Google Maps口コミ情報】")
                    all_texts.extend(reviews)
                else:
                    logger.info("No reviews found")
            else:
                logger.info("No place found in Google Maps")

        except Exception as e:
            logger.error(f"Error fetching Google Maps data: {str(e)}")

        # その他のWebサイトから情報を取得
        try:
            urls = await self._search_google_places(f"{name} {address} 雀荘 禁煙")
            web_texts = []
            async with aiohttp.ClientSession() as session:
                tasks = [self._fetch_page_text(session, url) for url in urls]
                web_texts = await asyncio.gather(*tasks)

            # Webサイトの情報を追加
            if web_texts:
                filtered_web_texts = []
                total_length = 0
                max_total_length = 5000

                all_texts.append("\n【Webサイト情報】")
                for text in web_texts:
                    if text and total_length + len(text) <= max_total_length:
                        filtered_web_texts.append(text)
                        total_length += len(text)

                all_texts.extend(filtered_web_texts)

        except Exception as e:
            logger.error(f"Error fetching web data: {str(e)}")

        combined_text = "\n".join([text for text in all_texts if text])
        logger.info(f"Combined text sections: {len(all_texts)}")

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

                    # 喫煙関連の情報を含む要素を優先的に抽出
                    smoking_related_elements = []
                    for element in soup.find_all(['p', 'div', 'span', 'td']):
                        text = element.get_text(strip=True)
                        if any(keyword in text for keyword in ['禁煙', '喫煙', 'タバコ', '煙草']):
                            smoking_related_elements.append(text)

                    # 喫煙関連の情報が見つからない場合は、最初の1000文字のみを使用
                    if smoking_related_elements:
                        return "\n".join(smoking_related_elements[:10])  # 最大10個の関連要素に制限
                    return soup.get_text(separator="\n", strip=True)[:1000]  # 最初の1000文字に制限
                return ""
        except Exception as e:
            print(f"クロールエラー: {url}, {e}")
            return ""