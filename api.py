import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import random
import os
import json
from ai_question import generate_followup, review_answer, summarize_and_review_conversation
from manual_questions import questions_by_stage, INITIAL_QUESTION # 修正：questions_by_stageとINITIAL_QUESTIONをインポート

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

# 面接の質問ステージを管理するためのグローバル変数（セッション管理の代替）
# 実際にはセッションIDなどでの管理が必要ですが、ここでは簡略化
current_stage = 1 # 1:自己紹介, 2:職務経歴, 3:AI深堀り

# 初期質問を返す (ステージ1の固定質問)
@app.get("/")
def get_initial_question():
    global current_stage
    current_stage = 1
    # 最初の質問を固定で返す
    return {"question": INITIAL_QUESTION}

# 次の質問を生成
@app.post("/generate_next_question")
async def generate_next_question(request: AnswerRequest):
    global current_stage
    user_answer = request.user_answer
    current_question = request.current_question

    if not user_answer:
        return {"error": "回答が空です。テキストを入力してください。", "is_error": True}

    # 添削結果 (既存ロジック)
    review_result = None
    rules_file_path = "review_rules.txt"
    if os.path.exists(rules_file_path):
        with open(rules_file_path, "r", encoding="utf-8") as f:
            rules_content = f.read().strip()
            review_result = review_answer(rules_content, user_answer)

    # --- 質問生成ロジックの修正 ---
    next_question = ""
    is_error = False
    
    try:
        if current_stage == 1:
            # ステージ1: 自己紹介の次の質問（ステージ2へ移行）
            current_stage = 2
            # ステージ2の質問をランダムに選ぶ
            next_question = random.choice(questions_by_stage["stage_2_experience"])
            
        elif current_stage == 2:
            # ステージ2: 職務経歴の次の質問（ステージ3へ移行 - AI深堀りの開始）
            # ステージ2の質問リストのいずれかに含まれていれば、次の質問をAIに委ねる
            if current_question in questions_by_stage["stage_2_experience"]:
                current_stage = 3
                # 最初のAI質問を生成
                ai_response_json = generate_followup(user_answer)
                ai_data = json.loads(ai_response_json)
                next_question = ai_data.get("question", "AIが質問を生成できませんでした。")
            else:
                 # 質問がリスト外の場合、次の質問をAIに委ねる（実質ステージ3へ）
                current_stage = 3
                ai_response_json = generate_followup(user_answer)
                ai_data = json.loads(ai_response_json)
                next_question = ai_data.get("question", "AIが質問を生成できませんでした。")


        elif current_stage >= 3:
            # ステージ3以降: AIによる深堀り質問
            ai_response_json = generate_followup(user_answer)
            ai_data = json.loads(ai_response_json)
            next_question = ai_data.get("question", "AIが質問を生成できませんでした。")
            
        else:
            # 想定外のステージ
            next_question = "面接の流れに問題が発生しました。"
            is_error = True

    except json.JSONDecodeError:
        next_question = "AIからのレスポンスが不正なJSON形式です。"
        is_error = True
    except Exception as e:
        next_question = f"質問生成でエラーが発生しました: {str(e)}"
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
    # (省略: 変更なし)
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
