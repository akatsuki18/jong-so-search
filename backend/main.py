from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from bs4 import BeautifulSoup
import googlemaps
import requests
import os
from dotenv import load_dotenv

load_dotenv()
# 環境変数からOpenAI APIキーを取得
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHAT_MODEL = os.getenv("CHAT_MODEL")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

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

        # 🔥 禁煙情報取得する！
        urls = search_google_places(f"{name} {address} 雀荘 禁煙")
        texts = []
        for url in urls:
            page_text = fetch_page_text(url)
            if page_text:
                texts.append(page_text)

        combined_text = "\n".join(texts)
        if combined_text:
            smoking_chain = smoking_check_prompt | llm
            try:
                response = smoking_chain.invoke({"text": combined_text})
                smoking_judgement = response.content.strip()
            except Exception as e:
                print(f"禁煙判定エラー: {e}")

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
            "negative_score": negative_score,
            "smoking": smoking_judgement,
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


def search_google_places(query):
    url = "https://google.serper.dev/search"

    payload = {
        "q": query,
        "gl": "jp",  # 日本優先
        "hl": "ja"   # 日本語優先
    }

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json()
        # 上位3件くらいのURLだけ取る例
        urls = [item.get('link') for item in data.get('organic', [])[:3]]
        return urls
    else:
        print(f"Serper検索エラー: {response.text}")
        return []

def fetch_page_text(url):
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # 余計なJSや広告は省いて、本文だけ抽出
            return soup.get_text(separator="\n", strip=True)
        else:
            print(f"ページ取得エラー: {url}")
            return ""
    except Exception as e:
        print(f"クロールエラー: {url}, {e}")
        return ""

def analyze_smoking_info(page_text):
    prompt = ChatPromptTemplate.from_template("""
以下のページ内容を読み、この施設が「禁煙」「分煙」「喫煙可」のどれに該当するかを必ず1語で答えてください。
もし情報が明確に記載されていない場合は、「情報なし」と答えてください。
また、その判定の根拠も簡単に1文で説明してください。

【出力フォーマット】
禁煙状況: （禁煙 or 分煙 or 喫煙可 or 情報なし）
根拠: （本文から要点を1文で）

ページ内容:
{page_text}
""")

    chain = prompt | llm

    try:
        response = chain.invoke({
            "page_text": page_text,
        })
        lines = response.content.splitlines()
        smoking_status = None
        reason = ""

        for line in lines:
            if "禁煙状況" in line:
                smoking_status = line.split("禁煙状況:")[-1].strip()
            if "根拠" in line:
                reason = line.split("根拠:")[-1].strip()

        return smoking_status, reason

    except Exception as e:
        print(f"禁煙判定エラー: {e}")
        return None, ""

# 禁煙判定用プロンプト
smoking_check_prompt = ChatPromptTemplate.from_template("""
次の文章を読んで、この雀荘の喫煙状況を判定してください。

【出力形式】（必ずこの4つから選んでください）
- 禁煙
- 分煙
- 喫煙可
- 情報なし

文章:
{text}
""")
