import streamlit as st
import streamlit.components.v1 as components
import requests
import uuid
import datetime
import base64
import io
import os
import tempfile
import threading
import urllib.parse

# ==========================================
# 1. Supabase & LINE 接続設定
# ==========================================
SUPABASE_URL = "https://vzuzeymvyftmfuaxrvtb.supabase.co"
SUPABASE_KEY = "sb_publishable_2y-rvfayu8BYs0oo-UOzGA_EQTBYLxm"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# 🔑 LINE APIの設定（個別送信用）
LINE_ACCESS_TOKEN = "XwqNwZuN4ruE09xplLcq21zyruMyZDwi1r41J0HyXtD34XRb2D+RL6wskoCdRh2qgQ2R6IbbxQJDYKoUSiH+i2a+pgKaTJjwawe6u0XdRDxD0VOOGeMMBKdRq6E6OMTkg3yvurB+BOUB5k98bcaBgwdB04t89/1O/w1cDnyilFU="

# 🔑 LINE ログイン（業者登録連携用）
LINE_CLIENT_ID = "2010108828"
LINE_CLIENT_SECRET = "2c73ce25e71858bcb09c89c79fa6bbe0"

# 実験環境のURL（確定分）
REDIRECT_URI = "https://felix-app-prbmr4ghbjai7n7hzfyahj.streamlit.app/"

ADMIN_PASSWORD = "2011"
DELETE_PASSWORD = "5963"

def db_get(table, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    try:
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list): return [d for d in data if isinstance(d, dict)]
            elif isinstance(data, dict): return [data]
        return []
    except Exception: return []

def db_post(table, data): requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=data)
def db_patch(table, record_id, data): 
    pk_col = "partner_id" if table == "partners" else "record_id"
    requests.patch(f"{SUPABASE_URL}/rest/v1/{table}?{pk_col}=eq.{record_id}", headers=HEADERS, json=data)

def db_delete_record(record_id): requests.delete(f"{SUPABASE_URL}/rest/v1/inspection_records?record_id=eq.{record_id}", headers=HEADERS)
def db_delete_property(prop_id):
    requests.delete(f"{SUPABASE_URL}/rest/v1/inspection_records?property_id=eq.{prop_id}", headers=HEADERS)
    requests.delete(f"{SUPABASE_URL}/rest/v1/inspections?property_id=eq.{prop_id}", headers=HEADERS)
    requests.delete(f"{SUPABASE_URL}/rest/v1/properties?property_id=eq.{prop_id}", headers=HEADERS)

def upload_to_storage(base64_str):
    if not base64_str or not isinstance(base64_str, str): return None
    if base64_str.startswith("http://") or base64_str.startswith("https://"): return base64_str
    try:
        encoded = base64_str.split(",", 1)[1] if "," in base64_str else base64_str
        file_data = base64.b64decode(encoded)
        filename = f"{uuid.uuid4()}.jpg"
        url = f"{SUPABASE_URL}/storage/v1/object/photos/{filename}"
        res = requests.post(url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "image/jpeg"}, data=file_data)
        if res.status_code in [200, 201]: return f"{SUPABASE_URL}/storage/v1/object/public/photos/{filename}"
        else: return base64_str
    except Exception: return base64_str

def bg_save_inspection(photo_b64, record_data):
    saved_url = upload_to_storage(photo_b64)
    if saved_url: record_data["issue_photo_url"] = saved_url
    db_post("inspection_records", record_data)

def bg_save_correction(rec_id, fix_photo_b64, partner_id=None, company_name=None):
    fix_url = upload_to_storage(fix_photo_b64)
    up_data = {"progress_status": "是正確認中", "fix_photo_url": fix_url}
    if partner_id and company_name:
        up_data["partner_id"] = partner_id
        up_data["company_name"] = company_name
    db_patch("inspection_records", rec_id, up_data)

def bg_patch_record(rec_id, photo_b64, up_data):
    if photo_b64:
        url = upload_to_storage(photo_b64)
        if url: up_data["issue_photo_url"] = url
    db_patch("inspection_records", rec_id, up_data)

def send_line_push_message(to_user_id, text_message):
    if not to_user_id: return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"}
    data = {"to": to_user_id, "messages": [{"type": "text", "text": text_message}]}
    try: requests.post(url, headers=headers, json=data)
    except Exception: pass

def get_line_login_url(partner_id):
    encoded_uri = urllib.parse.quote(REDIRECT_URI, safe='')
    return f"https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id={LINE_CLIENT_ID}&redirect_uri={encoded_uri}&state={partner_id}&scope=profile%20openid"

def get_line_profile(code):
    token_url = "https://api.line.me/oauth2/v2.1/token"
    payload = {
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
        "client_id": LINE_CLIENT_ID, "client_secret": LINE_CLIENT_SECRET
    }
    res = requests.post(token_url, data=payload)
    if res.status_code != 200: return None, f"Tokenエラー({res.status_code}): {res.text}"
    access_token = res.json().get("access_token")
    profile_res = requests.get("https://api.line.me/v2/profile", headers={"Authorization": f"Bearer {access_token}"})
    if profile_res.status_code != 200: return None, f"Profileエラー({profile_res.status_code}): {profile_res.text}"
    return profile_res.json().get("userId"), "成功"

# ==========================================
# 📱 2. スマート電子黒板カメラ
# ==========================================
SMART_CAMERA_HTML = """<!DOCTYPE html><html><body></body></html>"""
temp_dir = os.path.join(tempfile.gettempdir(), "smart_cam_final")
os.makedirs(temp_dir, exist_ok=True)
with open(os.path.join(temp_dir, "index.html"), "w", encoding="utf-8") as f: f.write(SMART_CAMERA_HTML)
_smart_camera = components.declare_component("smart_cam_final", path=temp_dir)

st.set_page_config(page_title="Felix検査App", layout="wide")

# =========================================================================
# 👇👇👇👇👇 ここに辞書データを貼り付けてください 👇👇👇👇👇
# =========================================================================
ISSUE_TEMPLATES = {}
# =========================================================================

for key in ["role", "active_menu", "pre_selected_prop", "delete_target", "skip_render_ids", "show_bulk_confirm", "edit_saved_records", "cached_records", "cached_target_id", "temp_photo", "partner_data", "jump_url", "processed_code"]:
    if key not in st.session_state: st.session_state[key] = None
if st.session_state.skip_render_ids is None: st.session_state.skip_render_ids = []

FLOOR_OPTS = ["-- 選択 --"]
AREA_OPTS_STANDARD = ["-- 選択 --"]
AREA_OPTS_SHANAI = ["-- 選択 --"]
WORK_OPTS_STANDARD = ["-- 選択 --"]
WORK_OPTS_HAIKIN = ["-- 選択 --"]
WORK_OPTS_KUTAI = ["-- 選択 --"]
WORK_OPTS_CHUKAN = ["-- 選択 --"]
WORK_OPTS_SHANAI = ["-- 選択 --"]
WORK_OPTS_KIKAN = ["-- 選択 --"]
INSP_OPTS = ["-- 選択 --"]
SHANAI_KENSA_TYPES = []
INSPECTOR_OPTS = ["-- 選択 --"]

# ==========================================
# 5. メイン画面・機能
# ==========================================
def main():
    qp = st.query_params
    line_code = qp.get("code")
    state_str = qp.get("state") # ここには作成時に入力したlogin_idがLINEから返ってきます

    # 🎯 画面最上部：LINEから戻ってきた時の「ID取得 & DB書き込み」視覚化ログ
    if line_code and state_str:
        st.markdown("""
        <div style="background-color:#E6F4EA; padding:15px; border-radius:8px; border:2px solid #137333; margin-bottom:20px;">
            <h2 style="color:#137333; margin-top:0; margin-bottom:10px;">🧪 実験用：LINE ID 取得・書込リアルタイムログ</h2>
            <p style="margin:0;">LINEから認証コードを検知しました。解析を行います。</p>
        </div>
        """, unsafe_allow_html=True)

        # 1. LINEサーバーからIDを剥ぎ取る
        line_user_id, error_msg = get_line_profile(line_code)
        
        col_line, col_supabase = st.columns(2)
        
        with col_line:
            st.markdown("### 1️⃣ LINEからの取得結果")
            if line_user_id:
                st.success(f"【取得成功】\n\nUから始まるLINE ID: `{line_user_id}`")
            else:
                st.error(f"【取得失敗】\n\nLINEサーバーが拒否しました。\nエラー内容: {error_msg}")
                
        with col_supabase:
            st.markdown("### 2️⃣ Supabaseへの書き込み結果")
            if line_user_id:
                # ログインIDを目印に、その行のline_user_id列をピンポイントで更新
                res = requests.patch(
                    f"{SUPABASE_URL}/rest/v1/partners?login_id=eq.{state_str}", 
                    headers=HEADERS, 
                    json={"line_user_id": line_user_id}
                )
                if res.status_code in (200, 204):
                    st.success(f"【書込成功】\n\nログインID「{state_str}」の行に、取得したLINE IDを正常に上書き保存しました！")
                else:
                    st.error(f"【書込失敗】\n\nSupabaseへの通信で拒否されました。\nステータス: {res.status_code}\nエラー内容: {res.text}")
            else:
                st.warning("LINE IDが取得できなかったため、Supabaseへの書き込み処理はスキップされました。")
        st.markdown("---")

    # 以下、通常の登録画面フォーム（本番と全く同じ流れ）
    if st.session_state.role is None:
        st.markdown("<h1 style='text-align: center;'>Felix検査App (実験モード)</h1>", unsafe_allow_html=True)
        
        new_c_name = st.text_input("会社名 (例: A工務店)", key="reg_c")
        new_contact = st.text_input("担当者名 (例: 山田太郎)", key="reg_contact")
        new_id = st.text_input("ログインID (半角英数字)", key="reg_id")
        new_pw = st.text_input("パスワード", type="password", key="reg_pw")
        
        if st.button("🟢 アカウントを作成してLINE連携へ進む", type="primary", use_container_width=True):
            if new_c_name and new_contact and new_id and new_pw:
                # まずはLINE ID抜きの状態でSupabaseへ1行作る
                db_post("partners", {
                    "partner_id": str(uuid.uuid4()), 
                    "company_name": new_c_name, 
                    "contact_name": new_contact, 
                    "login_id": new_id, 
                    "login_password": new_pw
                })
                # LINE認証URLを生成。戻ってきた時の目印として「登録したログインID(new_id)」を背負わせる
                st.session_state.jump_url = get_line_login_url(new_id)
                st.rerun()
            else:
                st.error("すべての項目を入力してください。")
                
        if st.session_state.jump_url:
            st.success("✅ アカウントの土台登録が完了しました！")
            st.markdown(f"### [👉 ここをタップしてLINE連携を完了する]({st.session_state.jump_url})")

if __name__ == "__main__":
    main()
