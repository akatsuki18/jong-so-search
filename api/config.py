import os
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

class Settings:
    """アプリケーション設定"""
    # 環境変数から読み込む、なければ空文字
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")

settings = Settings()