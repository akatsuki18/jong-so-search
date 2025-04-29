from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from ..config import settings

class SentimentService:
    def __init__(self):
        self.llm = ChatOpenAI(
            openai_api_key=settings.OPENAI_API_KEY,
            temperature=0,
            model=settings.CHAT_MODEL,
        )
        self.prompt = ChatPromptTemplate.from_template("""
あなたは{genre}の専門家です。

以下のレビューを読み、以下のフォーマットに厳密に従って要約とスコアリングをしてください。

【出力フォーマット】
要約: （要約文）
ポジティブ度: （半角数字のみ、%はつける）
ネガティブ度: （半角数字のみ、%はつける）

レビュー:
{combined_reviews}
""")

    async def analyze_reviews(self, reviews: List[str]) -> Dict[str, Any]:
        if not reviews:
            return {
                "summary": "",
                "positive_score": None,
                "negative_score": None
            }

        combined_reviews = "\n".join(reviews)
        try:
            response = await self.llm.ainvoke(
                self.prompt.format(genre="雀荘", combined_reviews=combined_reviews)
            )

            lines = response.content.splitlines()
            summary = ""
            positive_score = None
            negative_score = None

            for line in lines:
                if "要約" in line:
                    summary = line.split("要約:")[-1].strip()
                if "ポジティブ度" in line:
                    positive_score = int(line.split("ポジティブ度:")[-1].replace("%", "").strip())
                if "ネガティブ度" in line:
                    negative_score = int(line.split("ネガティブ度:")[-1].replace("%", "").strip())

            return {
                "summary": summary,
                "positive_score": positive_score,
                "negative_score": negative_score
            }

        except Exception as e:
            print(f"Sentiment analysis error: {e}")
            return {
                "summary": "",
                "positive_score": None,
                "negative_score": None
            }