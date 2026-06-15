import requests

# データベースとLINEの鍵情報
SUPABASE_URL = "https://vzuzeymvyftmfuaxrvtb.supabase.co"
SUPABASE_KEY = "sb_publishable_2y-rvfayu8BYs0oo-UOzGA_EQTBYLxm"
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}

LINE_TOKEN = "IqpDy1/OlcfW34pKSF7AXFJSvZ1MM7WpX81wXxwGV/PasCjuQCv33keiCNmucETGgQ2R6IbbxQJDYKoUSiH+i2a+pgKaTJjwawe6u0XdRDxKdQtnOu2pfv9zMcL9mqICMFl6yrapvoJTeL+onHiRSgdB04t89/1O/w1cDnyilFU="
LINE_GROUP_ID_TOKAI = "C6fc8fb79a343fb2e459e3fa5e891e927"
LINE_GROUP_ID_KANTO = "C440062b549a1165d645f61891503e264"

def send_line(group_id, text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"to": group_id, "messages": [{"type": "text", "text": text}]}
    requests.post(url, headers=headers, json=payload)

def main():
    # 1. 是正待ちのデータを全て取得
    url = f"{SUPABASE_URL}/rest/v1/inspection_records?progress_status=eq.是正待ち&select=*"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200: return
    records = res.json()

    # 2. LINE通知済み(True)ではないものだけを抽出
    targets = [r for r in records if r.get('line_notified') is not True]
    if not targets:
        print("未通知のデータはありません。処理を終了します。")
        return

    # 3. 物件データと検査データを取得して合体させる
    ins_res = requests.get(f"{SUPABASE_URL}/rest/v1/inspections?select=*", headers=HEADERS).json()
    prop_res = requests.get(f"{SUPABASE_URL}/rest/v1/properties?select=*", headers=HEADERS).json()

    ins_map = {i['inspection_id']: i for i in ins_res}
    prop_map = {p['property_id']: p for p in prop_res}

    tokai_issues = {}
    kanto_issues = {}
    notified_ids = []

    # 4. 東海と関東に振り分けながらテキストを整理
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
        reason = r.get('reject_reason', '理由なし')

        # まとめるテキストの形式
        issue_text = f"・{w_type} / {a_name}\n「{detail}」\n(理由: {reason})"

        target_dict = tokai_issues if area == "東海エリア" else kanto_issues
        if prop_name not in target_dict:
            target_dict[prop_name] = []
        target_dict[prop_name].append(issue_text)
        notified_ids.append(r.get('record_id'))

    # 5. 東海エリアへドカンと送信
    if tokai_issues:
        text = "[本日の是正差し戻し まとめ通知]\n\n"
        for p_name, issues in tokai_issues.items():
            text += f"■物件名: {p_name}\n"
            text += "\n".join(issues) + "\n\n"
        text += "👇 まとめて再提出はこちらからお願いします\nhttps://felix-app-prbmr4ghbjai7n7hzfyahj.streamlit.app/?mode=partner&area=tokai"
        send_line(LINE_GROUP_ID_TOKAI, text)

    # 6. 関東エリアへドカンと送信
    if kanto_issues:
        text = "[本日の是正差し戻し まとめ通知]\n\n"
        for p_name, issues in kanto_issues.items():
            text += f"■物件名: {p_name}\n"
            text += "\n".join(issues) + "\n\n"
        text += "👇 まとめて再提出はこちらからお願いします\nhttps://felix-app-prbmr4ghbjai7n7hzfyahj.streamlit.app/?mode=partner&area=kanto"
        send_line(LINE_GROUP_ID_KANTO, text)

    # 7. 送信完了のハンコをつける（line_notified = True）
    for rid in notified_ids:
        patch_url = f"{SUPABASE_URL}/rest/v1/inspection_records?record_id=eq.{rid}"
        requests.patch(patch_url, headers=HEADERS, json={"line_notified": True})

if __name__ == "__main__":
    main()
