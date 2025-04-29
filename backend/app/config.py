import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    CHAT_MODEL = os.getenv("CHAT_MODEL")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

settings = Settings()