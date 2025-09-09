import os
import json # JSONを扱うためのライブラリをインポート
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key="ATaUFUNikSdtQUyMebj00TkeQ8R1syEAATbLJADUWJJOH2QJhupnJQQJ99BHACfhMk5XJ3w3AAAAACOGj7Ue",
    api_version="2024-12-01-preview",
    azure_endpoint="https://nnfu-meusquzj-swedencentral.cognitiveservices.azure.com/",
)

def generate_followup(user_answer: str) -> str:
    """ユーザーの回答を元に、深掘りする質問を1つだけ生成し、JSON形式で返す"""
    
    # プロンプトをJSON形式の出力に特化させる
    system_prompt = """
    あなたは経験豊富な面接官です。
    面接者の回答に対して、さらに深掘りするような質問を1つだけ考えてください。
    質問の答えは尋ねないでください。
    出力は必ず以下のJSON形式で行ってください。
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
        max_tokens=100,
        response_format={"type": "json_object"} # APIにJSON形式で応答を要求する
    )
    
    # 応答をJSON文字列として直接返す
    return response.choices[0].message.content

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

    return response.choices[0].message.content
