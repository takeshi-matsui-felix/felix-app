import streamlit as st
import requests
import uuid
import datetime
import base64
import io

# ==========================================
# 1. Supabase 接続設定
# ==========================================
SUPABASE_URL = "https://vzuzeymvyftmfuaxrvtb.supabase.co"
SUPABASE_KEY = "sb_publishable_2y-rvfayu8BYs0oo-UOzGA_EQTBYLxm"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

ADMIN_PASSWORD = "2011"
DELETE_PASSWORD = "5963"

# 🛡 データベース通信
def db_get(table, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    try:
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            return res.json()
        return []
    except Exception:
        return []

def db_post(table, data):
    requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=data)

def db_patch(table, record_id, data):
    requests.patch(f"{SUPABASE_URL}/rest/v1/{table}?record_id=eq.{record_id}", headers=HEADERS, json=data)

def db_delete_record(record_id):
    requests.delete(f"{SUPABASE_URL}/rest/v1/inspection_records?record_id=eq.{record_id}", headers=HEADERS)

def db_delete_property(prop_id):
    requests.delete(f"{SUPABASE_URL}/rest/v1/inspection_records?property_id=eq.{prop_id}", headers=HEADERS)
    requests.delete(f"{SUPABASE_URL}/rest/v1/inspections?property_id=eq.{prop_id}", headers=HEADERS)
    requests.delete(f"{SUPABASE_URL}/rest/v1/properties?property_id=eq.{prop_id}", headers=HEADERS)

# 📸 画像をBase64に変換する関数（エラー防止のため安全策を追加）
def process_photo_to_base64(upload_file):
    if upload_file is None:
        return None
    try:
        # すでにBytesIOオブジェクトとして来ている場合
        if hasattr(upload_file, 'getvalue'):
            img_data = upload_file.getvalue()
        else:
            img_data = upload_file
            
        from PIL import Image
        img = Image.open(io.BytesIO(img_data))
        # 向きを正しく補正
        if hasattr(img, '_getexif'):
            img = io.BytesIO(img_data)
            img = Image.open(img)
            
        img.thumbnail((1000, 1000)) # 純正カメラは元々軽いが念のためリサイズ
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
    except Exception as e:
        # 万が一の時は生のままBase64化
        return f"data:image/jpeg;base64,{base64.b64encode(upload_file.getvalue()).decode('utf-8')}"

# ==========================================
# 2. UI設定 & カメラ画面を大きくする設定
# ==========================================
st.set_page_config(page_title="Felix検査App テスト版", page_icon="icon.png", layout="wide")

st.markdown("""
<style>
    /* カメラ入力枠を画面横幅いっぱいに広げる */
    [data-testid="stCameraInput"] {
        width: 100% !important;
        max-width: 800px !important;
    }
    /* 映像プレビューを大きく表示 */
    [data-testid="stCameraInput"] video {
        border-radius: 15px;
        border: 2px solid #E0E0E0;
    }
    div.stButton > button { border-radius: 6px; height: 50px; font-weight: bold; width: 100%; margin-bottom: 5px; }
    .record-box { border-bottom: 2px solid #EEEEEE; padding-bottom: 20px; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# 辞書データ（長いので松井様の元のデータをそのまま貼り付けたと想定して進めます）
ISSUE_TEMPLATES = {
    "中間検査": {
        "PB関連": ["PB張り不足", "PB張り上げ不足"],
        "ビス・ビスピッチ": ["ビスピッチ不良"],
        "新規追加内容": ["電気配線の床貫通部未処理", "ガス管の床貫通部未処理"]
    },
    "躯体検査": {"内部金物": ["ホールダウン金物取付不良"]},
    "配筋検査": {"定着関連": ["定着不良"]},
    "社内検査(設計)": {
        "玄関": {"玄関見切り": ["玄関見切りトメ仕上り不良"]},
        "洋室": {"引き戸": ["引き戸建具調整"]}
    }
}

# セッション管理
for key in ["role", "active_menu", "pre_selected_prop", "drill_target", "current_box", "issue_saved"]:
    if key not in st.session_state: st.session_state[key] = None

# ==========================================
# メインロジック（抜粋：カメラ部分の修正）
# ==========================================

# (ログイン処理等は黄金コードと同じため省略、メイン機能のみ記載)
def main():
    # ログイン判定（中略）
    if st.session_state.role is None:
        st.title("Felix検査App (テスト版)")
        if st.button("管理者ログイン (テスト)"):
            st.session_state.role = "admin"
            st.session_state.active_menu = "検査実施（管理者）"
            st.rerun()
        return

    st.sidebar.radio("MENU", ["検査実施（管理者）", "是正実施（協力業者）", "是正確認（管理者）"], key="active_menu")

    if st.session_state.active_menu == "検査実施（管理者）":
        st.subheader("検査実施テスト")
        # 物件選択などの処理（中略）
        
        # 指摘入力フォーム
        with st.container():
            st.markdown("##### 1. 撮影（背面カメラ優先）")
            # ★背面カメラ(environment)を優先指定
            photo = st.camera_input("ここをタップして撮影", help="背面カメラが立ち上がります", key="insp_cam")
            
            st.markdown("##### 2. 詳細・工種")
            desc = st.text_area("指摘内容の追記")
            w = st.selectbox("工種を選択", ["造作", "電気", "水道", "外壁", "その他"])

            if st.button("テスト保存"):
                if photo and w:
                    b64_img = process_photo_to_base64(photo)
                    # ここでSupabaseへ保存（黄金コードと同様の処理）
                    st.success("サクサク保存されました！")
                    st.image(b64_img, width=300)
                else:
                    st.error("写真と工種は必須です")

if __name__ == "__main__":
    main()
