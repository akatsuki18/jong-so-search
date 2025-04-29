from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import googlemaps
import os
from dotenv import load_dotenv

load_dotenv()
# 環境変数からOpenAI APIキーを取得
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHAT_MODEL = os.getenv("CHAT_MODEL")

llm = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    temperature=0,
    model=CHAT_MODEL,
)

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番では限定した方が安全（今は * でOK）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Location(BaseModel):
    latitude: float
    longitude: float

# Google Maps APIクライアント初期化
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

@app.get("/")
def read_root():
    return {"message": "Hello World"}

# 口コミも取得するバージョン
@app.post("/search")
def search_jongso(location: Location):
    places_result = gmaps.places_nearby(
        location=(location.latitude, location.longitude),
        radius=3000,
        keyword="麻雀",
        type="establishment",
        language="ja"
    )

    results = []
    non_smoking_keywords = ["禁煙", "ノンスモーキング", "non-smoking", "クリーン"]

    for place in places_result.get("results", []):
        name = place.get("name", "")
        address = place.get("vicinity", "")
        rating = place.get("rating", 0)
        user_ratings_total = place.get("user_ratings_total", 0)
        place_id = place.get("place_id", "")

        # 口コミ取得
        details = gmaps.place(
            place_id=place_id,
            language="ja"
        )
        reviews = details.get("result", {}).get("reviews", [])
        review_texts = [r.get("text", "") for r in reviews]

        # 禁煙判定
        text = (name + " " + address).lower()
        is_non_smoking = any(keyword.lower() in text for keyword in non_smoking_keywords)

        # ★ ここでLangChain使ってレビュー感情分析
        summary = ""
        positive_score = None
        negative_score = None

        if review_texts:
            combined_reviews = "\n".join(review_texts[:5])  # 最初の5レビューだけ使う
            prompt = ChatPromptTemplate.from_template("""
あなたは{genre}の専門家です。

以下のレビューを読み、以下のフォーマットに厳密に従って要約とスコアリングをしてください。

【出力フォーマット】
要約: （要約文）
ポジティブ度: （半角数字のみ、%はつける）
ネガティブ度: （半角数字のみ、%はつける）

レビュー:
{reviews}
""")
            chain = prompt | llm
            try:
                response = chain.invoke({
                    "genre": "雀荘",
                    "style": "親しみやすく、カジュアルにまとめる",
                    "reviews": combined_reviews,
                })
                # ★ここでレスポンスをパース！
                lines = response.content.splitlines()
                for line in lines:
                    if "要約" in line:
                        summary = line.split("要約:")[-1].strip()
                    if "ポジティブ度" in line:
                        positive_score = int(line.split("ポジティブ度:")[-1].replace("%", "").strip())
                    if "ネガティブ度" in line:
                        negative_score = int(line.split("ネガティブ度:")[-1].replace("%", "").strip())

                print("lines", lines)

            except Exception as e:
                print(f"Sentiment analysis error: {e}")

        location = place.get("geometry", {}).get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")

        results.append({
            "name": name,
            "address": address,
            "rating": rating,
            "user_ratings_total": user_ratings_total,
            "lat": lat,
            "lng": lng,
            "summary": summary,
            "positive_score": positive_score,
            "negative_score": negative_score
        })

    results.sort(
        key=lambda x: (-calculate_adjusted_rating(x), -x["user_ratings_total"])
    )

    return {
        "results": results
    }

def calculate_adjusted_rating(place):
    base_rating = place["rating"]
    positive_score = place.get("positive_score")

    if positive_score is not None:
        return base_rating + (positive_score / 100)  # ポジティブ度を少し加算
    else:
        return base_rating
