import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import random
import os
import json
# 修正: generate_initial_question は使用せず、既存の generate_followup, review_answer, summarize_and_review_conversation を維持
from ai_question import generate_followup, review_answer, summarize_and_review_conversation
# 既存のロジック維持のためインポート
from manual_questions import questions_by_stage, INITIAL_QUESTION 

# FastAPIのインスタンスを作成
app = FastAPI()

# CORS設定 (既存のものを維持)
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

# --- Pydantic モデル定義 ---

class CompanyInfoRequest(BaseModel):
    """面接開始時の企業情報リクエスト (未使用だが、クライアントからのPOSTの型を合わせるため定義を維持)"""
    company_info: str # 企業情報を含む

class AnswerRequest(BaseModel):
    """次の質問生成リクエスト (企業情報と質問履歴を追加)"""
    user_answer: str
    current_question: str
    company_info: str # ai_question.generate_followup のために必要

class ConversationItem(BaseModel):
    """会話履歴の単一要素"""
    type: str  # 'question' or 'answer'
    text: str

class ConversationHistoryRequest(BaseModel):
    """全体レビューリクエスト"""
    conversation_history: List[ConversationItem]

# 面接の質問ステージを管理するためのグローバル変数（セッション管理の代替）
current_stage = 1 # 1:自己紹介, 2:職務経歴, 3:AI深堀り

# --- API エンドポイント ---

# 修正: 初期質問は設定情報を受け取るため POST に変更 (ただし、ここでは企業情報は使用せず、既存のINITIAL_QUESTIONを返す)
@app.post("/", response_model=dict, summary="面接開始時の最初の質問を生成")
def get_initial_question(request: CompanyInfoRequest): # リクエストを受け取るが、内容（company_info）はここでは使用しない
    """
    面接開始時に、設定情報を受け取りますが、既存のINITIAL_QUESTIONを返します。
    """
    global current_stage
    current_stage = 1
    print(f"--- API Call: / --- Current Stage: {current_stage}, Received Info: {request.company_info}") # デバッグ用
    # 最初の質問を固定で返す (既存ロジック維持)
    return {"question": INITIAL_QUESTION}


# 修正: 次の質問を生成
@app.post("/generate_next_question")
async def generate_next_question(request: AnswerRequest):
    """
    ユーザーの回答、前回の質問、そして企業設定情報に基づき、次の質問を生成します。
    """
    global current_stage
    user_answer = request.user_answer
    current_question = request.current_question
    company_info = request.company_info # 新しく追加された項目

    print(f"--- API Call: /generate_next_question --- Stage: {current_stage}") # デバッグ用
    print(f"Answer: {user_answer[:20]}..., Company Info: {company_info}") # デバッグ用

    if not user_answer:
        return {"error": "回答が空です。テキストを入力してください。", "is_error": True}

    # 添削ロジック (既存のものを維持)
    review_result = None
    rules_file_path = "review_rules.txt"
    if os.path.exists(rules_file_path):
        with open(rules_file_path, "r", encoding="utf-8") as f:
            rules_content = f.read().strip()
            # 添削ロジック
            # review_result = review_answer(rules_content, user_answer) # 必要であれば有効化してください

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
                # 修正: generate_followup に必要な3つの引数を渡す
                ai_response_json = generate_followup(user_answer, current_question, company_info)
                ai_data = json.loads(ai_response_json)
                next_question = ai_data.get("question", "AIが質問を生成できませんでした。")
            else:
                 # 質問がリスト外の場合、次の質問をAIに委ねる（実質ステージ3へ）
                current_stage = 3
                # 修正: generate_followup に必要な3つの引数を渡す
                ai_response_json = generate_followup(user_answer, current_question, company_info)
                ai_data = json.loads(ai_response_json)
                next_question = ai_data.get("question", "AIが質問を生成できませんでした。")


        elif current_stage >= 3:
            # ステージ3以降: AIによる深堀り質問 (企業設定情報を活用)
            # 修正: generate_followup に必要な3つの引数を渡す
            ai_response_json = generate_followup(user_answer, current_question, company_info)
            ai_data = json.loads(ai_response_json)
            
            if ai_data.get("is_error", False):
                 raise Exception(ai_data.get("question", "AI質問生成エラー：詳細不明"))

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

# 修正: 全体レビュー (ai_question.py の要件に合わせて引数を修正)
@app.post("/get_full_review")
async def get_full_review(request: ConversationHistoryRequest):
    """
    全会話履歴のリストを受け取り、総合レビューを生成します。
    """
    print("--- API Call: /get_full_review ---") # デバッグ用
    try:
        # Pydanticモデルのリストを辞書のリストに変換して summarize_and_review_conversation に渡す
        conversation_list = [item.model_dump() for item in request.conversation_history]
        review = summarize_and_review_conversation(conversation_list) 
        
    except Exception as e:
        review = f"レビュー生成でエラーが発生しました: {e}"

    return {
        "full_review": review
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
