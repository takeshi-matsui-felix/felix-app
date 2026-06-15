import requests

# ==========================================
# 鍵情報（Supabase & LINE）
# ==========================================
SUPABASE_URL = "https://vzuzeymvyftmfuaxrvtb.supabase.co"
SUPABASE_KEY = "sb_publishable_2y-rvfayu8BYs0oo-UOzGA_EQTBYLxm"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

LINE_TOKEN = "IqpDy1/OlcfW34pKSF7AXFJSvZ1MM7WpX81wXxwGV/PasCjuQCv33keiCNmucETGgQ2R6IbbxQJDYKoUSiH+i2a+pgKaTJjwawe6u0XdRDxKdQtnOu2pfv9zMcL9mqICMFl6yrapvoJTeL+onHiRSgdB04t89/1O/w1cDnyilFU="
LINE_GROUP_ID_TOKAI = "C6fc8fb79a343fb2e459e3fa5e891e927"
LINE_GROUP_ID_KANTO = "C440062b549a1165d645f61891503e264"

def send_line(group_id, text):
    """LINEにテキストメッセージを1通送信する関数"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"to": group_id, "messages": [{"type": "text", "text": text}]}
    try:
        requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print(f"LINE送信エラー: {e}")

def main():
    # 1. 指摘データ（是正待ち ＆ 否認）を取得
    url_records = f"{SUPABASE_URL}/rest/v1/inspection_records?progress_status=eq.是正待ち&select=*"
    res_records = requests.get(url_records, headers=HEADERS)
    if res_records.status_code != 200:
        print("データ取得に失敗しました。")
        return
        
    records = res_records.json()

    # 2. まだLINEに通知していない（line_notified が True でない）ものだけを抽出
    targets = [r for r in records if r.get('line_notified') is not True]
    if not targets:
        print("未通知のデータはありません。処理を終了します。")
        return

    # 3. 検査データと物件データを取得して紐付け用の辞書を作成
    ins_res = requests.get(f"{SUPABASE_URL}/rest/v1/inspections?select=*", headers=HEADERS).json()
    prop_res = requests.get(f"{SUPABASE_URL}/rest/v1/properties?select=*", headers=HEADERS).json()
    
    ins_map = {i['inspection_id']: i for i in ins_res if isinstance(i, dict)}
    prop_map = {p['property_id']: p for p in prop_res if isinstance(p, dict)}

    tokai_issues = {}
    kanto_issues = {}
    notified_ids = []

    # 4. 東海と関東に振り分けながら、送信用のテキストを整理する
    for r in targets:
        ins = ins_map.get(r.get('inspection_id'))
        if not ins: continue
        prop = prop_map.get(ins.get('property_id'))
        if not prop: continue

        area = prop.get('area', '東海エリア')
        prop_name = prop.get('property_name', '不明')
        w_type = r.get('work_type', '')
        a_name = r.get('area', '')
        detail = r.get('issue_detail', '')
        reason = r.get('reject_reason', 'なし')
        
        # 否認理由が空の場合は表示を調整
        reason_text = f"\n(否認理由: {reason})" if reason and reason != "なし" else ""
        issue_text = f"・{w_type} / {a_name}\n「{detail}」{reason_text}"

        target_dict = tokai_issues if area == "東海エリア" else kanto_issues
        if prop_name not in target_dict:
            target_dict[prop_name] = []
        target_dict[prop_name].append(issue_text)
        
        notified_ids.append(r.get('record_id'))

    # 5. 東海エリアへドカンと1通で送信
    if tokai_issues:
        text = "[本日の是正差し戻し まとめ通知]\n\n"
        for p_name, issues in tokai_issues.items():
            text += f"■物件名: {p_name}\n"
            # 否認内容の間は1行あけ（\n\n）、物件と物件の間は2行あけ（\n\n\n）
            text += "\n\n".join(issues) + "\n\n\n"
        text += "👇 まとめて再提出はこちらからお願いします\nhttps://felix-app-prbmr4ghbjai7n7hzfyahj.streamlit.app/?mode=partner&area=tokai"
        send_line(LINE_GROUP_ID_TOKAI, text)
        print("東海エリアへ通知を送信しました。")

    # 6. 関東エリアへドカンと1通で送信
    if kanto_issues:
        text = "[本日の是正差し戻し まとめ通知]\n\n"
        for p_name, issues in kanto_issues.items():
            text += f"■物件名: {p_name}\n"
            text += "\n\n".join(issues) + "\n\n\n"
        text += "👇 まとめて再提出はこちらからお願いします\nhttps://felix-app-prbmr4ghbjai7n7hzfyahj.streamlit.app/?mode=partner&area=kanto"
        send_line(LINE_GROUP_ID_KANTO, text)
        print("関東エリアへ通知を送信しました。")

    # 7. 送信完了のハンコをつける（line_notified = True に上書き）
    for rid in notified_ids:
        patch_url = f"{SUPABASE_URL}/rest/v1/inspection_records?record_id=eq.{rid}"
        requests.patch(patch_url, headers=HEADERS, json={"line_notified": True})
        
    print(f"合計 {len(notified_ids)} 件のデータを通知済みに更新しました。")

if __name__ == "__main__":
    main()
