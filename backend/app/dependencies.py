from app.services.google_maps_service import GoogleMapsService
from app.services.sentiment_service import SentimentService
from app.repositories.jongso_repository import JongsoRepository
from app.services.jongso_service import JongsoService

google_maps_service = GoogleMapsService()
sentiment_service = SentimentService()
jongso_repository = JongsoRepository()

jongso_service = JongsoService(
    google_maps_service=google_maps_service,
    sentiment_service=sentiment_service,
    jongso_repository=jongso_repository,
)