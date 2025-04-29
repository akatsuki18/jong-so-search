from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class Location(BaseModel):
    latitude: float
    longitude: float

class JongsoShop(BaseModel):
    id: str
    name: str
    address: str
    lat: float
    lng: float
    rating: Optional[float]
    user_ratings_total: Optional[int]
    smoking_status: Optional[str]
    positive_score: Optional[int]
    negative_score: Optional[int]
    summary: Optional[str]
    last_fetched_at: datetime

class SearchResponse(BaseModel):
    results: List[JongsoShop]