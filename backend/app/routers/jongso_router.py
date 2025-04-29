from fastapi import APIRouter, Query
from app.dependencies import jongso_service

jongso_router = APIRouter()

@jongso_router.get("/search_by_keyword")
async def search_by_keyword(keyword: str = Query(...)):
    results = await jongso_service.search_shops_by_keyword(keyword)
    return {"results": results}
