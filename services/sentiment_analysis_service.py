import logging

logger = logging.getLogger(__name__)

class SentimentAnalysisService:
    """テキストのセンチメント分析を行うサービスクラス（ダミー実装）"""
    def __init__(self):
        logger.info("Dummy SentimentAnalysisService initialized.")
        # ここで実際のクライアント初期化などを行う
        # 例: from google.cloud import language_v1
        # self.client = language_v1.LanguageServiceClient()

    def analyze_text_list(self, text_list):
        """複数のテキストのセンチメントスコアを計算する（ダミー実装）"""
        logger.info(f"[Dummy] Analyzing sentiment for {len(text_list)} texts.")
        results = []
        for i, text in enumerate(text_list):
            # ダミーロジック: テキストの長さや特定の単語でスコアを決定
            positive_score = 0.5 + (len(text) % 5) * 0.1 # 0.5 から 0.9
            negative_score = 0.5 - (len(text) % 5) * 0.1 # 0.5 から 0.1
            if "悪い" in text or "ひどい" in text:
                positive_score = 0.1
                negative_score = 0.9
            elif "良い" in text or "最高" in text:
                positive_score = 0.9
                negative_score = 0.1

            results.append({
                'text': text,
                'positive_score': round(positive_score, 2),
                'negative_score': round(negative_score, 2)
            })
            logger.debug(f"[Dummy] Text: '{text[:20]}...' -> Pos: {results[-1]['positive_score']}, Neg: {results[-1]['negative_score']}")
        return results

    def get_summary_from_reviews(self, reviews):
        """レビューリストから要約を生成する（ダミー実装）"""
        logger.info(f"[Dummy] Generating summary from {len(reviews)} reviews.")
        if not reviews:
            return "レビューがありません。"

        # ダミーロジック: 最初のレビューを要約として返す
        first_review_text = reviews[0].get('text', '' )
        summary = f"(ダミー要約) {first_review_text[:50]}..."
        logger.debug(f"[Dummy] Generated summary: {summary}")
        return summary