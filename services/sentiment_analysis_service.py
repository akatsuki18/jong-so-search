import logging
import openai

logger = logging.getLogger(__name__)

class SentimentAnalysisService:
    """テキストのセンチメント分析と要約を行うサービスクラス"""
    def __init__(self, api_key: str | None = None):
        if not api_key:
            logger.warning("OpenAI API Key is not provided. Summarization feature will be disabled.")
            self.client = None
        else:
            try:
                self.client = openai.OpenAI(api_key=api_key)
                logger.info("OpenAI client initialized successfully for SentimentAnalysisService.")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
                self.client = None

    def _check_client(self):
        """OpenAIクライアントが初期化されているかチェック"""
        if not self.client:
            logger.warning("OpenAI client is not initialized. Cannot perform operation.")
            return False
        return True

    def analyze_text_list(self, text_list):
        """複数のテキストのセンチメントスコアを OpenAI を使って計算する"""
        if not self._check_client():
            logger.warning("OpenAI client not available, returning dummy sentiment scores.")
            # クライアントがない場合は、以前のダミーロジックを簡易的に返すか、デフォルト値を返す
            return [{'text': text, 'positive_score': 5, 'negative_score': 5} for text in text_list]

        logger.info(f"Analyzing sentiment for {len(text_list)} texts using OpenAI.")
        results = []
        for text in text_list:
            if not text or len(text.strip()) < 10: # 短すぎるテキストは分析スキップ
                logger.debug(f"Skipping sentiment analysis for short/empty text: '{text[:20]}...'")
                results.append({'text': text, 'positive_score': 5, 'negative_score': 5})
                continue

            # トークン数削減のため、長すぎるレビューは切り詰める
            MAX_TEXT_LENGTH = 500 # センチメント分析対象の最大文字数 (調整可能)
            truncated_text = text[:MAX_TEXT_LENGTH]
            if len(text) > MAX_TEXT_LENGTH:
                logger.debug(f"Truncating long text for sentiment analysis: '{truncated_text[:20]}...'")

            prompt = f"以下のレビュー文のセンチメントを分析し、ポジティブ度を0から10の数値で評価してください。0が非常にネガティブ、10が非常にポジティブです。数値のみを回答してください。\n\nレビュー: {truncated_text}"

            positive_score = 5 # デフォルトは中立
            negative_score = 5

            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "あなたはテキストのセンチメントを0から10の数値で評価するAIです。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2, # 低めの温度で安定した評価を促す
                    max_tokens=10 # 数値だけを期待
                )

                content = response.choices[0].message.content.strip()
                # 数値のみを抽出する試み (より頑健なパースが必要な場合もある)
                extracted_score = None
                try:
                    # 小数点を含む場合も考慮
                    score_float = float(content)
                    # 0から10の範囲に収める (可読性のため段階的に処理)
                    score_rounded = round(score_float)
                    extracted_score = max(0, min(10, score_rounded))
                except ValueError:
                     # f-string を使わない形式に変更
                     log_message = "Failed to parse sentiment score from OpenAI response: '{}'. Using default score.".format(content)
                     logger.warning(log_message)

                if extracted_score is not None:
                    positive_score = extracted_score
                    negative_score = 10 - positive_score # ポジティブ度からネガティブ度を算出
                    logger.debug(f"OpenAI sentiment score for '{truncated_text[:20]}...': {positive_score}/10")
                else:
                    logger.warning(f"Could not extract a valid score (0-10) from response: '{content}'. Using default 5/10.")

            except openai.APIError as e:
                logger.error(f"OpenAI API error during sentiment analysis for '{truncated_text[:20]}...': {e}")
                # エラー時はデフォルト値を使用
            except Exception as e:
                logger.error(f"Unexpected error during sentiment analysis for '{truncated_text[:20]}...': {e}", exc_info=True)
                # エラー時はデフォルト値を使用

            results.append({
                'text': text, # 元のテキストを返す
                'positive_score': positive_score,
                'negative_score': negative_score
            })

        return results

    def get_smoking_status_from_reviews(self, reviews):
        """レビューリストから OpenAI を使って喫煙情報を判定する"""
        if not self._check_client():
            logger.warning("OpenAI client not available, cannot determine smoking status.")
            return "不明" # クライアントがない場合は不明を返す
        if not reviews:
            logger.debug("No reviews provided to determine smoking status.")
            return "不明"

        logger.info(f"Determining smoking status from {len(reviews)} reviews using OpenAI.")

        # プロンプト用にレビューテキストを結合・整形
        MAX_REVIEW_LENGTH = 300 # 1レビューあたりの最大文字数
        review_texts = "\n".join([f"- {r.get('text', '')[:MAX_REVIEW_LENGTH]}" for r in reviews if r.get('text')])

        if not review_texts:
             logger.warning("No valid review texts found to determine smoking status.")
             return "不明"

        MAX_TOTAL_LENGTH = 3000 # プロンプトに含めるレビューの合計最大文字数
        if len(review_texts) > MAX_TOTAL_LENGTH:
            logger.warning(f"Review texts length ({len(review_texts)}) exceeds limit ({MAX_TOTAL_LENGTH}) for smoking status check, truncating.")
            review_texts = review_texts[:MAX_TOTAL_LENGTH] + "... (一部省略)"

        prompt = f"""以下の麻雀店に関する複数のレビューを読み、喫煙情報を判定してください。
レビュー内容から判断できる場合、「喫煙可」「禁煙」「分煙」のいずれか該当するものを、最も可能性が高いもの一つだけ選んでください。
判断できない場合は「不明」と回答してください。回答は「喫煙可」「禁煙」「分煙」「不明」のいずれかのみとしてください。

レビュー:
{review_texts}
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini", # 喫煙情報判定に適したモデルを選択
                messages=[
                    {"role": "system", "content": "あなたはユーザーレビューから麻雀店の喫煙情報を「喫煙可」「禁煙」「分煙」「不明」のいずれかで判定するAIアシスタントです。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1, # 低めの温度で安定した判定を促す
                max_tokens=10 # 「喫煙可」「禁煙」「分煙」「不明」のいずれかの単語のみを期待
            )

            smoking_status_raw = response.choices[0].message.content.strip()
            # 判定結果を正規化
            if "喫煙可" in smoking_status_raw:
                smoking_status = "喫煙可"
            elif "禁煙" in smoking_status_raw:
                smoking_status = "禁煙"
            elif "分煙" in smoking_status_raw:
                smoking_status = "分煙"
            else:
                smoking_status = "不明" # 想定外の応答や判定不能の場合

            logger.info(f"Determined smoking status using OpenAI: {smoking_status} (Raw: '{smoking_status_raw}')")
            return smoking_status
        except openai.APIError as e:
            logger.error(f"OpenAI API returned an API Error during smoking status check: {e}")
            return "不明" # エラー時は不明
        except Exception as e:
            logger.error(f"An unexpected error occurred during OpenAI smoking status check: {e}", exc_info=True)
            return "不明" # エラー時は不明

    def get_summary_from_reviews(self, reviews):
        """レビューリストから OpenAI を使って要約を生成する"""
        if not self._check_client():
            return "要約機能は利用できません (APIキー未設定)"
        if not reviews:
            return "レビューがありません。"

        logger.info(f"Generating summary from {len(reviews)} reviews using OpenAI.")

        # プロンプト用にレビューテキストを結合・整形
        # 長すぎるレビューは切り詰めるなど、トークン数制限への配慮が必要
        MAX_REVIEW_LENGTH = 300 # 1レビューあたりの最大文字数 (調整可能)
        review_texts = "\n".join([f"- {r.get('text', '')[:MAX_REVIEW_LENGTH]}" for r in reviews if r.get('text')])

        if not review_texts:
             logger.warning("No valid review texts found to generate summary.")
             return "要約対象のレビューが見つかりません。"

        # トークン数を考慮してレビュー数を制限する方が安全
        # ここでは簡易的に文字数で制限
        MAX_TOTAL_LENGTH = 3000 # プロンプトに含めるレビューの合計最大文字数 (調整可能)
        if len(review_texts) > MAX_TOTAL_LENGTH:
            logger.warning(f"Review texts length ({len(review_texts)}) exceeds limit ({MAX_TOTAL_LENGTH}), truncating.")
            review_texts = review_texts[:MAX_TOTAL_LENGTH] + "... (一部省略)"

        prompt = f"以下の麻雀店に関する複数のレビューを読み、ポジティブな点とネガティブな点を簡潔に1〜2文で要約してください。箇条書きではなく、自然な文章でお願いします。:\n\n{review_texts}"

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo", # または他の適切なモデル
                messages=[
                    {"role": "system", "content": "あなたはユーザーレビューを要約するAIアシスタントです。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5, # 低めの温度で事実に基づいた要約を促す
                max_tokens=150 # 要約の最大長 (調整可能)
            )

            summary = response.choices[0].message.content.strip()
            logger.info(f"Successfully generated summary using OpenAI: {summary[:50]}...")
            return summary
        except openai.APIError as e:
            logger.error(f"OpenAI API returned an API Error: {e}")
            return "レビューの要約中にAPIエラーが発生しました。"
        except Exception as e:
            logger.error(f"An unexpected error occurred during OpenAI summarization: {e}", exc_info=True)
            return "レビューの要約中に予期せぬエラーが発生しました。"