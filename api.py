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

# リクエストボディのデータモデル
class AnswerRequest(BaseModel):
    user_answer: str
    current_question: str

class ConversationHistoryRequest(BaseModel):
    conversation_history: list

# 初期質問を返す
@app.get("/")
def get_initial_question():
    initial_question = random.choice(questions)
    return {"question": initial_question}

# 次の質問を生成
@app.post("/generate_next_question")
async def generate_next_question(request: AnswerRequest):
    user_answer = request.user_answer
    current_question = request.current_question

    if not user_answer:
        return {"error": "回答が空です。テキストを入力してください。", "is_error": True}

    # 添削結果
    review_result = None
    rules_file_path = "review_rules.txt"
    if os.path.exists(rules_file_path):
        with open(rules_file_path, "r", encoding="utf-8") as f:
            rules_content = f.read().strip()
            review_result = review_answer(rules_content, user_answer)

    # AIに次の質問を生成
    try:
        ai_response_json = generate_followup(user_answer)
        try:
            ai_data = json.loads(ai_response_json)
            next_question = ai_data.get("question", "AIが質問を生成できませんでした。")
            is_error = False
        except json.JSONDecodeError:
            next_question = "AIからのレスポンスが不正なJSON形式です。"
            is_error = True
    except Exception as e:
        next_question = "AIの質問生成でエラーが発生しました。"
        is_error = True
        return {
            "current_question": current_question,
            "user_answer": user_answer,
            "next_question": next_question,
            "review": review_result,
            "is_error": is_error,
            "error_message": str(e)
        }

    return {
        "current_question": current_question,
        "user_answer": user_answer,
        "next_question": next_question,
        "review": review_result,
        "is_error": is_error
    }

# 全体レビュー
@app.post("/get_full_review")
async def get_full_review(request: ConversationHistoryRequest):
    full_conversation_text = ""
    for item in request.conversation_history:
        if item["type"] == "question":
            full_conversation_text += f"質問: {item['text']}\n"
        elif item["type"] == "answer":
            full_conversation_text += f"あなたの回答: {item['text']}\n\n"
    
    try:
        review = summarize_and_review_conversation(full_conversation_text)
    except Exception as e:
        review = f"レビュー生成でエラーが発生しました: {e}"

    return {
        "full_review": review
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
