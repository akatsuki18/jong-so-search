from typing import List, Tuple
import re
import openai
import logging
from ..config import settings

# ロガーの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TextAnalyzer:
    def __init__(self):
        # ネガティブコンテキストを示すキーワード
        self.negative_contexts = [
            "くさい", "臭い", "煙い", "ひどい", "残念", "だめ",
            "不十分", "効果なし", "意味なし", "形だけ"
        ]

        # 喫煙を示すポジティブな表現
        self.smoking_positive = [
            "喫煙可", "喫煙席", "喫煙エリア", "喫煙ルーム",
            "分煙", "喫煙スペース"
        ]

        # 禁煙を示すポジティブな表現
        self.non_smoking_positive = [
            "完全禁煙", "禁煙店", "全席禁煙", "禁煙化",
            "禁煙徹底"
        ]

        openai.api_key = settings.OPENAI_API_KEY
        self.model = settings.CHAT_MODEL or "gpt-3.5-turbo"  # デフォルトモデルを設定
        logger.info(f"TextAnalyzer initialized with model: {self.model}")

    async def analyze_smoking_info(self, text: str) -> str:
        try:
            logger.info("Starting smoking status analysis")
            logger.info(f"Input text: {text[:200]}...")  # 最初の200文字のみ表示

            # GPTに喫煙状況の分析を依頼
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """
雀荘の喫煙状況を分析してください。以下の3つのカテゴリのいずれかで判定してください：
- 禁煙：完全禁煙の場合
- 喫煙可：喫煙可能な場所がある場合、または禁煙と言いながら実質的に喫煙できる状況の場合
- 分煙：喫煙室や喫煙エリアが明確に分かれている場合

以下のような文脈に特に注意してください：
1. 「禁煙」という言葉があっても、「タバコ臭い」「煙が漏れてくる」などのネガティブな表現がある場合は「喫煙可」と判定
2. 「喫煙室あり」「喫煙スペースあり」などの表現がある場合は「分煙」と判定
3. 「完全禁煙」「全席禁煙」などの明確な表現がある場合は「禁煙」と判定

回答は「禁煙」「喫煙可」「分煙」のいずれかの文字列のみを返してください。
情報が不十分な場合は「情報なし」と返してください。
"""
                    },
                    {
                        "role": "user",
                        "content": f"以下の情報から雀荘の喫煙状況を判定してください：\n\n{text}"
                    }
                ],
                temperature=0,
                max_tokens=10
            )

            result = response.choices[0].message.content.strip()
            logger.info(f"Analysis result: {result}")

            # 有効な回答のみを受け付ける
            valid_responses = ["禁煙", "喫煙可", "分煙", "情報なし"]
            final_result = result if result in valid_responses else "情報なし"
            logger.info(f"Final result: {final_result}")
            return final_result

        except Exception as e:
            logger.error(f"禁煙判定エラー: {str(e)}")
            return "情報なし"