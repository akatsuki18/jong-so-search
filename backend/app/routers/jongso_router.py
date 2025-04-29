from fastapi import APIRouter, Query
from app.dependencies import jongso_service
from app.models.schemas import Location, SearchResponse

jongso_router = APIRouter()

@jongso_router.get("/search_by_keyword")
async def search_by_keyword(keyword: str = Query(...)):
    results = await jongso_service.search_shops_by_keyword(keyword)
    return {"results": results}

@jongso_router.post("/search", response_model=SearchResponse)
async def search_jongso(location: Location):
    results = await jongso_service.search_nearby_shops(
        latitude=location.latitude,
        longitude=location.longitude
    )
    return {"results": results}
