import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import random
import os
import json
from ai_question import generate_followup, review_answer, summarize_and_review_conversation
from manual_questions import questions

# FastAPIのインスタンスを作成
app = FastAPI()

# CORS設定
origins = [
    "http://localhost",
    "http://localhost:8080",
    "https://nanaf0816-del.github.io",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# リクエストボディのデータモデルを定義
class AnswerRequest(BaseModel):
    user_answer: str
    current_question: str

# 全体の会話履歴を受け取るためのデータモデル
class ConversationHistoryRequest(BaseModel):
    conversation_history: list

# 初期質問を返すエンドポイント
@app.get("/")
def get_initial_question():
    """初期質問をランダムに返すAPIエンドポイント"""
    initial_question = random.choice(questions)
    return {"question": initial_question}

# 次の質問を生成するエンドポイント
@app.post("/generate_next_question")
async def generate_next_question(request: AnswerRequest):
    """回答を受け取り、次の質問と添削結果を返すAPIエンドポイント"""
    
    user_answer = request.user_answer
    current_question = request.current_question

    if not user_answer:
        return {"error": "回答が空です。テキストを入力してください。"}

    rules_file_path = "review_rules.txt"
    review_result = None
    if os.path.exists(rules_file_path):
        with open(rules_file_path, "r", encoding="utf-8") as f:
            rules_content = f.read().strip()
            review_result = review_answer(rules_content, user_answer)
    
    ai_response_json = generate_followup(user_answer)
    
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

# 全体のレビューを生成する新しいエンドポイントを追加
@app.post("/get_full_review")
async def get_full_review(request: ConversationHistoryRequest):
    """
    全体の会話履歴を受け取り、その全文とレビュー結果を返すAPIエンドポイント
    """
    full_conversation_text = ""
    for item in request.conversation_history:
        if item["type"] == "question":
            full_conversation_text += f"質問: {item['text']}\n"
        elif item["type"] == "answer":
            full_conversation_text += f"あなたの回答: {item['text']}\n\n"
    
    review = summarize_and_review_conversation(full_conversation_text)
    
    return {
        "full_review": review
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
