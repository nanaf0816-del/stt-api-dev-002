import os
import json
from openai import AzureOpenAI

# AzureOpenAIクライアントの初期化
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-12-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

def generate_followup(user_answer: str) -> str:
    """
    ユーザーの回答を元に、深掘りする質問を1つだけ生成。
    必ずJSON形式で返す: {"question": "生成された質問"}
    """
    
    system_prompt = """
    あなたは経験豊富な面接官です。
    面接者の回答に対して、さらに深掘りするような質問を1つだけ考えてください。
    出力は必ず以下のJSON形式にしてください。余計な説明文は出力しないこと。
    {
      "question": "ここに生成した質問を記述"
    }
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"面接者の回答: {user_answer}\nこの回答を受けて、次に何を聞きますか？"}
        ],
        temperature=0.7,
        max_tokens=100
    )
    
    content = response.choices[0].message.content.strip()
    try:
        data = json.loads(content)
        # ここで必ずJSON文字列として返す
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return json.dumps({"error": "JSON変換に失敗しました", "raw": content}, ensure_ascii=False)

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
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたはプロの面接官であり、面談の指導者です。面接者の回答を冷静かつ客観的に添削してください。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=250
    )

    return response.choices[0].message.content.strip()

def summarize_and_review_conversation(full_conversation: str) -> str:
    """
    全体の会話履歴を基に、要約と総合的なレビューを生成する
    """
    
    prompt = f"""
    あなたはプロの面接官です。
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
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたはプロの面接官であり、面接者の能力を客観的に評価する役割を担っています。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=500
    )
    
    return response.choices[0].message.content.strip()
