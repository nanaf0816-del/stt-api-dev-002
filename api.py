import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional
import random
import os
import json

from ai_question import generate_followup, review_answer, summarize_and_review_conversation
from manual_questions import questions_by_stage, INITIAL_QUESTION
from skillsheet_parser import parse_skillsheet

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

# --- Pydantic モデル定義 ---

class CompanyInfoRequest(BaseModel):
    """面接開始時の企業情報リクエスト"""
    company_info: str

class AnswerRequest(BaseModel):
    """次の質問生成リクエスト"""
    user_answer: str
    current_question: str
    company_info: str
    skillsheet_info: Optional[str] = None  # 新規追加

class ConversationItem(BaseModel):
    """会話履歴の単一要素"""
    type: str  # 'question' or 'answer'
    text: str

class ConversationHistoryRequest(BaseModel):
    """全体レビューリクエスト"""
    conversation_history: List[ConversationItem]

# グローバル変数
current_stage = 1
skillsheet_data = ""  # スキルシート情報を保持

# --- API エンドポイント ---

@app.post("/upload_skillsheet", summary="スキルシート（Excel）をアップロード")
async def upload_skillsheet(file: UploadFile = File(...)):
    """
    Excelファイルをアップロードし、スキルシート情報を解析・保存
    """
    global skillsheet_data
    
    try:
        # ファイルの拡張子チェック
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            raise HTTPException(status_code=400, detail="Excel形式のファイル（.xlsx または .xls）をアップロードしてください。")
        
        # ファイルを読み込む
        contents = await file.read()
        
        # スキルシートを解析
        skillsheet_data = parse_skillsheet(contents)
        
        print(f"--- Skillsheet Uploaded: {file.filename} ---")
        print(f"Parsed Data:\n{skillsheet_data[:500]}...")  # デバッグ用（最初の500文字）
        
        return {
            "message": "スキルシートのアップロードが完了しました",
            "filename": file.filename,
            "preview": skillsheet_data[:200] + "..." if len(skillsheet_data) > 200 else skillsheet_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"スキルシートの解析に失敗しました: {str(e)}")


@app.post("/", response_model=dict, summary="面接開始時の最初の質問を生成")
def get_initial_question(request: CompanyInfoRequest):
    """
    面接開始時に、設定情報を受け取りますが、既存のINITIAL_QUESTIONを返します。
    """
    global current_stage
    current_stage = 1
    print(f"--- API Call: / --- Current Stage: {current_stage}, Received Info: {request.company_info}")
    return {"question": INITIAL_QUESTION}


@app.post("/generate_next_question")
async def generate_next_question(request: AnswerRequest):
    """
    ユーザーの回答、前回の質問、企業設定情報、スキルシート情報に基づき、次の質問を生成します。
    """
    global current_stage, skillsheet_data
    user_answer = request.user_answer
    current_question = request.current_question
    company_info = request.company_info
    
    # スキルシート情報を取得（リクエストに含まれていればそれを、なければグローバル変数を使用）
    skillsheet_info = request.skillsheet_info if request.skillsheet_info else skillsheet_data

    print(f"--- API Call: /generate_next_question --- Stage: {current_stage}")
    print(f"Answer: {user_answer[:20]}..., Has Skillsheet: {bool(skillsheet_info)}")

    if not user_answer:
        return {"error": "回答が空です。テキストを入力してください。", "is_error": True}

    # 添削ロジック
    review_result = None
    rules_file_path = "review_rules.txt"
    if os.path.exists(rules_file_path):
        with open(rules_file_path, "r", encoding="utf-8") as f:
            rules_content = f.read().strip()
            # review_result = review_answer(rules_content, user_answer)

    # 企業情報とスキルシート情報を統合
    combined_context = company_info
    if skillsheet_info:
        combined_context += "\n\n" + skillsheet_info

    # 質問生成ロジック
    next_question = ""
    is_error = False
    
    try:
        if current_stage == 1:
            # ステージ1: 自己紹介の次の質問（ステージ2へ移行）
            current_stage = 2
            next_question = random.choice(questions_by_stage["stage_2_experience"])
            
        elif current_stage == 2:
            # ステージ2: 職務経歴の次の質問（ステージ3へ移行）
            if current_question in questions_by_stage["stage_2_experience"]:
                current_stage = 3
                # スキルシート情報を含めてAI質問を生成
                ai_response_json = generate_followup(user_answer, current_question, combined_context)
                ai_data = json.loads(ai_response_json)
                next_question = ai_data.get("question", "AIが質問を生成できませんでした。")
            else:
                current_stage = 3
                ai_response_json = generate_followup(user_answer, current_question, combined_context)
                ai_data = json.loads(ai_response_json)
                next_question = ai_data.get("question", "AIが質問を生成できませんでした。")

        elif current_stage >= 3:
            # ステージ3以降: AIによる深堀り質問（スキルシート情報を活用）
            ai_response_json = generate_followup(user_answer, current_question, combined_context)
            ai_data = json.loads(ai_response_json)
            
            if ai_data.get("is_error", False):
                raise Exception(ai_data.get("question", "AI質問生成エラー：詳細不明"))

            next_question = ai_data.get("question", "AIが質問を生成できませんでした。")
            
        else:
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


@app.post("/get_full_review")
async def get_full_review(request: ConversationHistoryRequest):
    """
    全会話履歴のリストを受け取り、総合レビューを生成します。
    """
    print("--- API Call: /get_full_review ---")
    try:
        conversation_list = [item.model_dump() for item in request.conversation_history]
        review = summarize_and_review_conversation(conversation_list) 
        
    except Exception as e:
        review = f"レビュー生成でエラーが発生しました: {e}"

    return {
        "full_review": review
    }


@app.get("/get_skillsheet_info", summary="現在保存されているスキルシート情報を取得")
def get_skillsheet_info():
    """
    現在メモリに保存されているスキルシート情報を返す（デバッグ用）
    """
    global skillsheet_data
    return {
        "has_skillsheet": bool(skillsheet_data),
        "preview": skillsheet_data[:300] + "..." if len(skillsheet_data) > 300 else skillsheet_data
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
