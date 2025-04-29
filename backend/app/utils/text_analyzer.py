from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from ..config import settings

class TextAnalyzer:
    def __init__(self):
        self.llm = ChatOpenAI(
            openai_api_key=settings.OPENAI_API_KEY,
            temperature=0,
            model=settings.CHAT_MODEL,
        )
        self.smoking_prompt = ChatPromptTemplate.from_template("""
以下のページ内容を読み、この施設が「禁煙」「分煙」「喫煙可」のどれに該当するかを必ず1語で答えてください。
もし情報が明確に記載されていない場合は、「情報なし」と答えてください。
また、その判定の根拠も簡単に1文で説明してください。

【出力フォーマット】
禁煙状況: （禁煙 or 分煙 or 喫煙可 or 情報なし）
根拠: （本文から要点を1文で）

ページ内容:
{page_text}
""")

    async def analyze_smoking_info(self, page_text: str) -> str:
        try:
            response = await self.llm.ainvoke(
                self.smoking_prompt.format(page_text=page_text)
            )
            lines = response.content.splitlines()
            smoking_status = None

            for line in lines:
                if "禁煙状況" in line:
                    smoking_status = line.split("禁煙状況:")[-1].strip()
                    break

            return smoking_status or "情報なし"

        except Exception as e:
            print(f"禁煙判定エラー: {e}")
            return "情報なし"