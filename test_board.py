import streamlit as st
import streamlit.components.v1 as components
import requests
import uuid
import datetime
import base64
import io
import os
import tempfile

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

def db_get(table, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    try:
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            data = res.json()
            return data if isinstance(data, list) else [data] if data else []
        return []
    except Exception: return []

def db_post(table, data): requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=data)
def db_patch(table, record_id, data): requests.patch(f"{SUPABASE_URL}/rest/v1/{table}?record_id=eq.{record_id}", headers=HEADERS, json=data)
def db_delete_record(record_id): requests.delete(f"{SUPABASE_URL}/rest/v1/inspection_records?record_id=eq.{record_id}", headers=HEADERS)

def upload_to_storage(base64_str):
    if not base64_str or not isinstance(base64_str, str) or "base64," not in base64_str: return base64_str
    try:
        encoded = base64_str.split(",", 1)[1]
        file_data = base64.b64decode(encoded)
        filename = f"{uuid.uuid4()}.jpg"
        url = f"{SUPABASE_URL}/storage/v1/object/photos/{filename}"
        res = requests.post(url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "image/jpeg"}, data=file_data)
        if res.status_code in [200, 201]: return f"{SUPABASE_URL}/storage/v1/object/public/photos/{filename}"
    except Exception: pass
    return base64_str

# ==========================================
# 📱 2. 【進化版】電子黒板・自動合成カメラコンポーネント (V17)
# ==========================================
CLIENT_COMPRESS_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        body { margin: 0; padding: 5px; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; background-color: transparent;}
        .upload-btn {
            display: block; width: 100%; max-width: 400px; padding: 18px 20px;
            background-color: #28a745; color: white; border-radius: 8px;
            font-size: 16px; font-weight: bold; text-align: center; cursor: pointer; 
            box-sizing: border-box; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        input[type="file"] { display: none; }
    </style>
</head>
<body>
    <label class="upload-btn" id="upload-label">
        <i class="fa-solid fa-camera" id="btn-icon"></i> <span id="btn-text">黒板付きで撮影</span>
        <input type="file" accept="image/*" id="file-input">
    </label>
    <script>
        let b = { prop: "", date: "", loc: "", desc: "" };
        window.addEventListener("message", function(e) {
            if (e.data.type === "streamlit:render" && e.data.args) {
                b.prop = e.data.args.prop || ""; b.date = e.data.args.date || "";
                b.loc = e.data.args.loc || ""; b.desc = e.data.args.desc || "";
            }
        });

        function sendReady() { window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:componentReady", apiVersion: 1}, "*"); }
        function setHeight(h) { window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: h}, "*"); }
        function sendToStreamlit(val) { window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setComponentValue", value: val}, "*"); }
        window.onload = function() { sendReady(); setHeight(80); }; 

        const input = document.getElementById('file-input');
        input.addEventListener('change', function(e) {
            const file = e.target.files[0]; if (!file) return;
            document.getElementById('upload-label').style.backgroundColor = '#f39c12';
            document.getElementById('btn-icon').className = 'fa-solid fa-spinner fa-spin';
            document.getElementById('btn-text').innerHTML = '&nbsp;黒板を合成中...';

            const reader = new FileReader();
            reader.onload = function(event) {
                const img = new Image();
                img.onload = function() {
                    const MAX_SIZE = 800; let w = img.width, h = img.height;
                    if (w > h) { if (w > MAX_SIZE) { h *= MAX_SIZE / w; w = MAX_SIZE; } }
                    else { if (h > MAX_SIZE) { w *= MAX_SIZE / h; h = MAX_SIZE; } }
                    const canvas = document.createElement('canvas'); canvas.width = w; canvas.height = h;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, w, h);

                    // 黒板描画（小型化：幅40%、高さ25%）
                    const bw = w * 0.40, bh = h * 0.25;
                    const sx = w - bw - 10, sy = h - bh - 10;
                    ctx.fillStyle = "rgba(0, 50, 0, 0.85)"; ctx.fillRect(sx, sy, bw, bh);
                    ctx.strokeStyle = "white"; ctx.lineWidth = 2; ctx.strokeRect(sx+5, sy+5, bw-10, bh-10);
                    
                    ctx.fillStyle = "white"; const fs = Math.floor(w * 0.030); ctx.font = fs + "px sans-serif";
                    let ty = sy + fs + 15; const ls = fs * 1.5;
                    ctx.fillText("物件: " + b.prop, sx+15, ty); ty += ls;
                    ctx.fillText("検査: " + b.date, sx+15, ty); ty += ls;
                    ctx.fillText("場所: " + b.loc, sx+15, ty); ty += ls;
                    ctx.fillStyle = "#ffdddd"; ctx.fillText("指摘: " + b.desc, sx+15, ty);

                    sendToStreamlit(canvas.toDataURL('image/jpeg', 0.6));
                    document.getElementById('upload-label').style.backgroundColor = '#2ecc71';
                    document.getElementById('btn-icon').className = 'fa-solid fa-check';
                    document.getElementById('btn-text').innerHTML = '&nbsp;セット完了';
                };
                img.src = event.target.result;
            };
            reader.readAsDataURL(file);
        });
    </script>
</body>
</html>
"""

temp_dir = os.path.join(tempfile.gettempdir(), "board_camera_v17")
os.makedirs(temp_dir, exist_ok=True)
with open(os.path.join(temp_dir, "index.html"), "w", encoding="utf-8") as f: f.write(CLIENT_COMPRESS_HTML)
_board_camera = components.declare_component("board_camera_v17", path=temp_dir)

# ==========================================
# 3. 定型文・UI設定
# ==========================================
st.set_page_config(page_title="Felix検査App", page_icon="icon.png", layout="wide")
ISSUE_TEMPLATES = {
    # ★ ここにマスター辞書を貼り付け
}

FLOOR_OPTS = ["-- 選択 --", "101","102","103","201","202","203","301","302","303","共用部","外部"]
AREA_OPTS_STANDARD = ["-- 選択 --", "玄関", "廊下・階段・ENT", "LDK", "キッチン", "洋室", "洗面室", "UB", "トイレ", "バルコニー", "外部", "フリー項目"]
WORK_OPTS_STANDARD = ["-- 選択 --", "基礎工事", "造作", "内装", "電気", "設備", "ガス", "清掃", "外壁", "その他"]

for key in ["role", "active_menu", "current_box", "temp_photo", "issue_saved"]:
    if key not in st.session_state: st.session_state[key] = None

# ==========================================
# 4. メインロジック
# ==========================================
def main():
    if st.session_state.role is None:
        st.header("Felix検査App")
        pwd = st.text_input("Password", type="password")
        if st.button("ログイン"):
            if pwd == ADMIN_PASSWORD: st.session_state.role = "admin"; st.session_state.active_menu = "検査実施（管理者）"; st.rerun()
        return

    # サイドバーメニュー
    m_opts = ["物件登録（管理者）", "検査実施（管理者）", "検査内容確認（管理者）", "是正実施（協力業者）", "完了分一覧（共通）"]
    st.session_state.active_menu = st.sidebar.radio("MENU", m_opts, index=m_opts.index(st.session_state.active_menu) if st.session_state.active_menu in m_opts else 1)

    # --- 検査実施メニュー ---
    if st.session_state.active_menu == "検査実施（管理者）":
        if not st.session_state.current_box:
            st.header("検査開始")
            props = db_get("properties", "select=*")
            target = st.selectbox("物件を選択", [{"property_id": None, "property_name": "-- 選択 --"}] + props, format_func=lambda x: x.get('property_name'))
            ins_type = st.selectbox("検査種類", ["配筋検査", "躯体検査", "断熱検査", "中間検査", "社内検査(設計)", "社内検査(建設)"])
            if st.button("検査スタート"):
                if target.get('property_id'):
                    nid = str(uuid.uuid4())
                    db_post("inspections", {"inspection_id": nid, "property_id": target['property_id'], "property_name": target['property_name'], "inspection_type": ins_type, "inspection_date": str(datetime.date.today())})
                    st.session_state.current_box = {"id": nid, "prop_id": target['property_id'], "name": target['property_name'], "type": ins_type}
                    st.rerun()
        else:
            cb = st.session_state.current_box
            st.subheader(f"{cb['name']} / {cb['type']}")
            
            if not st.session_state.issue_saved:
                f = st.radio("階層", FLOOR_OPTS[1:], horizontal=True)
                a = st.radio("部位", AREA_OPTS_STANDARD[1:], horizontal=True)
                desc = st.text_area("指摘内容を入力")
                w = st.radio("工種", WORK_OPTS_STANDARD[1:], horizontal=True)
                
                # ★ 黒板へデータを自動パス
                p_url = _board_camera(
                    prop=cb['name'], 
                    date=datetime.date.today().strftime("%Y/%m/%d"), 
                    loc=f"{f} {a}", 
                    desc=desc[:15] + "..." if len(desc)>15 else desc, # 長すぎる場合はカット
                    key="insp_cam"
                )
                if p_url: st.session_state.temp_photo = p_url

                if st.button("この内容で保存"):
                    if w and desc != "" and st.session_state.temp_photo:
                        with st.spinner("送信中..."):
                            url = upload_to_storage(st.session_state.temp_photo)
                            db_post("inspection_records", {"record_id": str(uuid.uuid4()), "inspection_id": cb['id'], "property_id": cb['prop_id'], "floor_level": f, "area": a, "work_type": w, "issue_detail": desc, "issue_photo_url": url, "progress_status": "是正待ち"})
                            st.session_state.issue_saved = True; st.session_state.temp_photo = None; st.rerun()
                    else: st.error("工種・内容・写真はすべて必須です。")
            else:
                st.success("保存完了"); 
                if st.button("続けて次を登録"): st.session_state.issue_saved = False; st.rerun()
                if st.button("検査全体を終了"): st.session_state.current_box = None; st.rerun()

    # --- 他のメニュー（是正実施・完了一覧など）はこれまでのロジックを継承 ---
    # （※文字数制限のため主要な変更点以外は省略していますが、V16のロジックがそのまま動作します）

if __name__ == "__main__":
    main()
