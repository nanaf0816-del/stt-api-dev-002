import os
import json
from openai import AzureOpenAI
from typing import List, Dict, Any

# AzureOpenAIクライアントの初期化
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-12-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
# デプロイメント名は環境に合わせて調整してください
DEPLOYMENT_NAME = "gpt-4o-mini"

# ----------------------------------------------------
# 新規追加: 最初の質問を生成する関数
# ----------------------------------------------------
def generate_initial_question(company_info: str) -> str:
    """
    企業情報に基づいて、面接開始時の最初の質問を生成します。
    必ずJSON形式で返す: {"question": "生成された質問"}
    """
    system_prompt = (
        "あなたは経験豊富な面接官です。以下の企業情報を考慮し、面接の導入として適切な、最初の一問だけを生成してください。\n"
        "応答は質問文のみとし、他の挨拶や説明は含めないでください。\n"
        "出力は必ず以下のJSON形式にしてください。余計な説明文は出力しないこと。\n"
        "{\n"
        "  \"question\": \"ここに生成した質問を記述\"\n"
        "}"
    )
    
    user_prompt = f"面接設定情報:\n{company_info}\n\nこの情報に基づいた面接の導入となる質問を生成してください。"

    try:
        response = client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=200,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content.strip()
        return content
        
    except Exception as e:
        # エラー発生時はエラーフラグ付きのJSONを返す
        return json.dumps({"question": f"AI質問生成エラー: {e}", "is_error": True}, ensure_ascii=False)


# ----------------------------------------------------
# 修正: generate_followup に引数を追加し、プロンプトに組み込む
# ----------------------------------------------------
def generate_followup(user_answer: str, current_question: str, company_info: str) -> str:
    """
    企業情報と会話の流れを考慮し、深掘りする質問を1つだけ生成。
    必ずJSON形式で返す: {"question": "生成された質問"}
    """
    system_prompt = (
        "あなたは経験豊富な面接官です。以下の企業情報と、前回の質問と回答を考慮し、さらに深掘りするような質問を1つだけ考えてください。\n"
        "出力は必ず以下のJSON形式にしてください。余計な説明文は出力しないこと。\n"
        "{\n"
        "  \"question\": \"ここに生成した質問を記述\"\n"
        "}"
    )
    
    # 企業情報をプロンプトに組み込む
    user_prompt = (
        f"面接設定情報:\n{company_info}\n\n"
        f"前回の質問: {current_question}\n"
        f"面接者の回答: {user_answer}\n\n"
        "この一連の流れを受けて、次に何を聞きますか？"
    )

    try:
        response = client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=200,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content.strip()
        return content
        
    except Exception as e:
        return json.dumps({"question": f"AI質問生成エラー: {e}", "is_error": True}, ensure_ascii=False)

# ----------------------------------------------------
# 修正なし: review_answer (引数やロジックの変更なし)
# ----------------------------------------------------
def review_answer(rules: str, answer: str) -> str:
    """面談の注意事項を基に回答を添削する"""
    
    prompt = f"""
    以下の面談の注意事項を参考に、面接者の回答がルールに違反していないかチェックしてください。
    特に、ルールに違反している場合は、その点を指摘し、修正案を簡潔に提示してください。

    ---
    面談の注意事項:
    {rules}
    ---

    面接者の回答:
    {answer}
    ---
    添削結果:
    """
    
    response = client.chat.completions.create(
        model=DEPLOYMENT_NAME,
        messages=[
            {"role": "system", "content": "あなたはプロの面接官であり、面談の指導者です。面接者の回答を冷静かつ客観的に添削してください。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=250
    )

    return response.choices[0].message.content.strip()

# ----------------------------------------------------
# 修正: summarize_and_review_conversation (引数名を修正し、より適切な入力形式に対応)
# ----------------------------------------------------
def summarize_and_review_conversation(conversation_history: List[Dict[str, str]]) -> str:
    """
    全体の会話履歴を基に、要約と総合的なレビューを生成する
    """
    # 会話履歴を整形
    formatted_history = []
    for item in conversation_history:
        # itemは通常、{"type": "question" or "answer", "text": "..."} の形式を想定
        speaker = "面接官 (質問)" if item.get('type') == 'question' else "あなた (回答)"
        formatted_history.append(f"{speaker}: {item.get('text', '')}")
    
    full_conversation = "\n".join(formatted_history)

    prompt = f"""
    あなたはプロの面接コンサルタントです。
    以下に示された面接での全会話履歴を読み、
    以下の項目について総合的にレビューしてください。
    
    1. 会話の全体的な流れと構成の評価
    2. 回答の論理性、説得力、一貫性
    3. 改善すべき具体的な点
    
    レビューは簡潔に、かつ具体的なフィードバックを含めてください。
    ---
    会話履歴:
    {full_conversation}
    ---
    総合レビュー:
    """

    response = client.chat.completions.create(
        model=DEPLOYMENT_NAME,
        messages=[
            {"role": "system", "content": "あなたはプロの面接官であり、面接者の能力を客観的に評価する役割を担っています。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=500
    )
    
    return response.choices[0].message.content.strip()
