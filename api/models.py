from pydantic import BaseModel
from typing import Optional, List

class Location(BaseModel):
    latitude: float
    longitude: float

class JongsoShop(BaseModel):
    id: str
    name: str
    address: str
    lat: float
    lng: float
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    smoking_status: Optional[str] = None
    positive_score: Optional[int] = None
    negative_score: Optional[int] = None
    summary: Optional[str] = None
    last_fetched_at: Optional[str] = None  # 文字列として扱う

class SearchResponse(BaseModel):
    results: List[JongsoShop]