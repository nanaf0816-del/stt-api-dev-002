import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import random
import os
import json
from ai_question import generate_followup, review_answer
from manual_questions import questions

# FastAPIのインスタンスを作成
app = FastAPI()

# CORS設定
origins = [
    # 既存のオリジンを保持
    "http://localhost",
    "http://localhost:8080",
    # GitHub
    "https://nana0816-del.github.io",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # ワイルドカードからリストに変更
    allow_credentials=True,
    allow_methods=["*"],  # すべてのHTTPメソッドを許可
    allow_headers=["*"],  # すべてのヘッダーを許可
)

# リクエストボディのデータモデルを定義
# 音声認識アプリから受け取るデータ構造
class AnswerRequest(BaseModel):
    user_answer: str
    current_question: str

# 初期質問を返すエンドポイント
# 面接の開始時に、このURLにアクセスして最初の質問を取得します
@app.get("/")
def get_initial_question():
    """初期質問をランダムに返すAPIエンドポイント"""
    initial_question = random.choice(questions)
    return {"question": initial_question}

# 次の質問を生成するエンドポイント
# 音声認識アプリから文字起こしされた回答を受け取り、次の質問を生成して返します
@app.post("/generate_next_question")
async def generate_next_question(request: AnswerRequest):
    """回答を受け取り、次の質問と添削結果を返すAPIエンドポイント"""
    
    user_answer = request.user_answer
    current_question = request.current_question

    if not user_answer:
        return {"error": "回答が空です。テキストを入力してください。"}

    # 添削機能の実行
    rules_file_path = "review_rules.txt"
    review_result = None
    if os.path.exists(rules_file_path):
        with open(rules_file_path, "r", encoding="utf-8") as f:
            rules_content = f.read().strip()
            review_result = review_answer(rules_content, user_answer)
    
    # AIに次の質問をJSON形式で生成させる
    ai_response_json = generate_followup(user_answer)
    
    # JSON文字列を解析し、質問部分を抽出
    next_question = None
    try:
        ai_data = json.loads(ai_response_json)
        next_question = ai_data.get("question")
        if not next_question:
            next_question = "AIが質問を生成できませんでした。"
    except json.JSONDecodeError:
        next_question = "AIからのレスポンスが不正なJSON形式です。"

    return {
        "current_question": current_question,
        "user_answer": user_answer,
        "next_question": next_question,
        "review": review_result,
        "is_error": next_question.startswith("AIが") or next_question.startswith("AIからの")
    }

# このスクリプトを直接実行した場合に、uvicornサーバーを起動
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
