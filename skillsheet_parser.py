import pandas as pd
from io import BytesIO
from typing import Dict, Any, List
import json

def parse_skillsheet(file_bytes: bytes) -> str:
    """
    特定フォーマットのスキルシートExcelを解析し、構造化されたテキストを返す
    
    Args:
        file_bytes: アップロードされたExcelファイルのバイトデータ
        
    Returns:
        str: 構造化されたスキルシート情報（テキスト形式）
    """
    try:
        excel_file = BytesIO(file_bytes)
        
        # 「スキルシート」シートを読み込む（ヘッダーなしで読み込み）
        df = pd.read_excel(excel_file, sheet_name='スキルシート', header=None)
        
        skillsheet_data = {
            "basic_info": {},
            "self_pr": "",
            "certifications": [],
            "projects": []
        }
        
        # 基本情報の抽出（3-5行目あたり）
        skillsheet_data["basic_info"] = extract_basic_info_from_format(df)
        
        # 自己PRの抽出
        skillsheet_data["self_pr"] = extract_self_pr_from_format(df)
        
        # 資格情報の抽出
        skillsheet_data["certifications"] = extract_certifications_from_format(df)
        
        # プロジェクト情報の抽出（10行目以降）
        skillsheet_data["projects"] = extract_projects_from_format(df)
        
        # 構造化されたデータをテキスト形式に整形
        formatted_text = format_skillsheet_for_ai(skillsheet_data)
        
        return formatted_text
        
    except Exception as e:
        return f"スキルシート解析エラー: {str(e)}"


def extract_basic_info_from_format(df: pd.DataFrame) -> Dict[str, Any]:
    """
    特定フォーマットから基本情報を抽出
    Row 3: ふりがな、性別、年齢、生年月日
    Row 4: 氏名、国籍、配偶者、最寄駅
    Row 5: 学歴
    """
    basic_info = {}
    
    try:
        # 3行目（インデックス2）: ふりがな
        if len(df) > 2:
            furigana = df.iloc[2, 1] if pd.notna(df.iloc[2, 1]) else ""
            basic_info["ふりがな"] = str(furigana)
            
            gender = df.iloc[2, 3] if pd.notna(df.iloc[2, 3]) else ""
            basic_info["性別"] = str(gender)
            
            age = df.iloc[2, 5] if pd.notna(df.iloc[2, 5]) else ""
            basic_info["年齢"] = str(age)
            
            birth_date = df.iloc[2, 7] if pd.notna(df.iloc[2, 7]) else ""
            basic_info["生年月日"] = str(birth_date)
        
        # 4行目（インデックス3）: 氏名
        if len(df) > 3:
            name = df.iloc[3, 1] if pd.notna(df.iloc[3, 1]) else ""
            basic_info["氏名"] = str(name)
            
            nationality = df.iloc[3, 3] if pd.notna(df.iloc[3, 3]) else ""
            basic_info["国籍"] = str(nationality)
            
            spouse = df.iloc[3, 5] if pd.notna(df.iloc[3, 5]) else ""
            basic_info["配偶者"] = str(spouse)
            
            station = df.iloc[3, 7] if pd.notna(df.iloc[3, 7]) else ""
            basic_info["最寄駅"] = str(station)
        
        # 5行目（インデックス4）: 学歴
        if len(df) > 4:
            education = df.iloc[4, 1] if pd.notna(df.iloc[4, 1]) else ""
            basic_info["学歴"] = str(education)
            
    except Exception as e:
        print(f"基本情報抽出エラー: {e}")
    
    return basic_info


def extract_self_pr_from_format(df: pd.DataFrame) -> str:
    """
    自己PR欄を抽出（7-8行目あたり）
    """
    self_pr = ""
    
    try:
        # 7-8行目あたりの自己PR欄
        for row_idx in range(6, 9):  # 7-9行目をチェック
            if len(df) > row_idx:
                # B列あたりに自己PRが記載されている
                pr_text = df.iloc[row_idx, 1] if pd.notna(df.iloc[row_idx, 1]) else ""
                if pr_text and str(pr_text).strip():
                    self_pr += str(pr_text) + " "
                    
    except Exception as e:
        print(f"自己PR抽出エラー: {e}")
    
    return self_pr.strip()


def extract_certifications_from_format(df: pd.DataFrame) -> List[str]:
    """
    資格情報を抽出（5行目の取得年月・資格欄）
    """
    certifications = []
    
    try:
        # 5行目（インデックス4）の資格欄（8列目以降）
        if len(df) > 4:
            for col_idx in range(7, len(df.columns)):
                cert = df.iloc[4, col_idx]
                if pd.notna(cert) and str(cert).strip() and str(cert) != "資格":
                    # 取得年月と資格名を結合
                    acquisition_date = df.iloc[4, 6] if col_idx == 7 and pd.notna(df.iloc[4, 6]) else ""
                    cert_text = f"{acquisition_date} {cert}".strip() if acquisition_date else str(cert)
                    certifications.append(cert_text)
                    
    except Exception as e:
        print(f"資格抽出エラー: {e}")
    
    return certifications


def extract_projects_from_format(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    プロジェクト情報を抽出（11行目以降）
    
    列の構造:
    - B列: No.
    - C列: 期間(年数)
    - D列: プロジェクト名・業務概要
    - E列: 役割/規模
    - F列: サーバーOS
    - G列: DB
    - H列: FW,MW,ツール等
    - I列: 使用言語
    - J-O列: 作業工程（●で表示）
    """
    projects = []
    
    try:
        # ヘッダー行を探す（10行目あたり）
        header_row = 9  # 10行目（インデックス9）
        
        # 11行目以降のプロジェクトデータを読み込む
        for row_idx in range(11, len(df)):
            # No.が空でない行のみ処理
            no_value = df.iloc[row_idx, 1]  # B列
            
            if pd.notna(no_value) and str(no_value).strip():
                project = {}
                
                # No.
                project["No"] = str(no_value).strip()
                
                # 期間（C列）
                period = df.iloc[row_idx, 2]
                if pd.notna(period):
                    project["期間"] = str(period).strip()
                
                # プロジェクト名・業務概要（D列）
                project_name = df.iloc[row_idx, 3]
                if pd.notna(project_name):
                    project["プロジェクト名・業務概要"] = str(project_name).strip()
                
                # 役割/規模（E列）
                role = df.iloc[row_idx, 4]
                if pd.notna(role):
                    project["役割/規模"] = str(role).strip()
                
                # サーバーOS（F列）
                server_os = df.iloc[row_idx, 5]
                if pd.notna(server_os) and str(server_os).strip() and str(server_os) != "ー":
                    project["サーバーOS"] = str(server_os).strip()
                
                # DB（G列）
                db = df.iloc[row_idx, 6]
                if pd.notna(db) and str(db).strip() and str(db) != "ー":
                    project["DB"] = str(db).strip()
                
                # FW,MW,ツール等（H列）
                tools = df.iloc[row_idx, 7]
                if pd.notna(tools) and str(tools).strip() and str(tools) != "ー":
                    project["FW/MW/ツール"] = str(tools).strip()
                
                # 使用言語（I列）
                language = df.iloc[row_idx, 8]
                if pd.notna(language) and str(language).strip():
                    project["使用言語"] = str(language).strip()
                
                # 作業工程（J-O列）を抽出
                phases = []
                phase_columns = {
                    9: "要件定義",
                    10: "基本設計",
                    11: "詳細設計",
                    12: "実装/テスト",
                    13: "結合テスト",
                    14: "保守/運用"
                }
                
                for col_idx, phase_name in phase_columns.items():
                    if col_idx < len(df.columns):
                        cell_value = df.iloc[row_idx, col_idx]
                        # ●があれば担当フェーズとして記録
                        if pd.notna(cell_value) and str(cell_value).strip() in ["●", "○"]:
                            phases.append(phase_name)
                
                if phases:
                    project["担当工程"] = "、".join(phases)
                
                projects.append(project)
                
            # 空行が続いたら終了
            elif row_idx > 15:  # 最低でも15行目まではチェック
                # 連続5行が空なら終了
                empty_count = 0
                for check_idx in range(row_idx, min(row_idx + 5, len(df))):
                    if pd.isna(df.iloc[check_idx, 1]) or not str(df.iloc[check_idx, 1]).strip():
                        empty_count += 1
                if empty_count >= 5:
                    break
                    
    except Exception as e:
        print(f"プロジェクト抽出エラー: {e}")
    
    return projects


def format_skillsheet_for_ai(data: Dict[str, Any]) -> str:
    """
    構造化されたスキルシートデータをAIプロンプト用のテキスト形式に整形
    """
    formatted = "【スキルシート情報】\n\n"
    
    # 基本情報
    if data["basic_info"]:
        formatted += "■ 基本情報\n"
        for key, value in data["basic_info"].items():
            if value:
                formatted += f"  {key}: {value}\n"
        formatted += "\n"
    
    # 自己PR
    if data["self_pr"]:
        formatted += "■ 自己PR\n"
        formatted += f"  {data['self_pr']}\n\n"
    
    # 資格
    if data["certifications"]:
        formatted += "■ 保有資格\n"
        for cert in data["certifications"]:
            formatted += f"  - {cert}\n"
        formatted += "\n"
    
    # プロジェクト経歴
    if data["projects"]:
        formatted += "■ プロジェクト経歴\n"
        for i, proj in enumerate(data["projects"], 1):
            formatted += f"\n  【プロジェクト {proj.get('No', i)}】\n"
            
            if "期間" in proj:
                formatted += f"    期間: {proj['期間']}\n"
            
            if "プロジェクト名・業務概要" in proj:
                formatted += f"    概要: {proj['プロジェクト名・業務概要']}\n"
            
            if "役割/規模" in proj:
                formatted += f"    役割: {proj['役割/規模']}\n"
            
            # 技術スタック
            tech_stack = []
            if "サーバーOS" in proj:
                tech_stack.append(f"OS: {proj['サーバーOS']}")
            if "DB" in proj:
                tech_stack.append(f"DB: {proj['DB']}")
            if "FW/MW/ツール" in proj:
                tech_stack.append(f"ツール: {proj['FW/MW/ツール']}")
            if "使用言語" in proj:
                tech_stack.append(f"言語: {proj['使用言語']}")
            
            if tech_stack:
                formatted += f"    技術: {', '.join(tech_stack)}\n"
            
            if "担当工程" in proj:
                formatted += f"    担当工程: {proj['担当工程']}\n"
        
        formatted += "\n"
    
    return formatted
