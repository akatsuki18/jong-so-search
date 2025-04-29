from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .models.schemas import Location, SearchResponse
from .services.jongso_service import JongsoService
from .services.google_maps_service import GoogleMapsService
from .services.sentiment_service import SentimentService
from .repositories.jongso_repository import JongsoRepository

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# サービスの初期化
google_maps_service = GoogleMapsService()
sentiment_service = SentimentService()
jongso_repository = JongsoRepository()
jongso_service = JongsoService(
    google_maps_service=google_maps_service,
    sentiment_service=sentiment_service,
    jongso_repository=jongso_repository
)

@app.on_event("startup")
async def startup():
    await jongso_repository.connect()

@app.on_event("shutdown")
async def shutdown():
    await jongso_repository.disconnect()

@app.post("/search", response_model=SearchResponse)
async def search_jongso(location: Location):
    results = await jongso_service.search_nearby_shops(
        latitude=location.latitude,
        longitude=location.longitude
    )
    return {"results": results}