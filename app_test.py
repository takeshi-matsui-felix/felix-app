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
import json
import time

# 外部辞書ファイルの読み込み
from new_dictionary import ISSUE_TEMPLATES

# ==========================================
# 1. Supabase 接続設定 ＆ キャッシュ機構（AM3:00クリア対応）
# ==========================================
SUPABASE_URL = "https://vzuzeymvyftmfuaxrvtb.supabase.co"
SUPABASE_KEY = "sb_publishable_2y-rvfayu8BYs0oo-UOzGA_EQTBYLxm"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

DELETE_PASSWORD = "5963"

if "db_cache" not in st.session_state:
    st.session_state.db_cache = {}
if "last_cache_clear_date" not in st.session_state:
    st.session_state.last_cache_clear_date = None

def check_and_clear_am3_cache():
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    if now.hour >= 3 and st.session_state.last_cache_clear_date != today_str:
        st.session_state.db_cache = {}
        st.session_state.last_cache_clear_date = today_str
        print("\n【定期クリーンアップ発動】毎朝AM3:00のキャッシュ初期化が正常に完了しました。\n")

def get_cached_data(cache_key, fetch_func, *args, **kwargs):
    check_and_clear_am3_cache()
    if cache_key in st.session_state.db_cache: return st.session_state.db_cache[cache_key]
    data = fetch_func(*args, **kwargs)
    st.session_state.db_cache[cache_key] = data
    return data

def clear_specific_cache(target_prefix):
    keys_to_del = [k for k in st.session_state.db_cache.keys() if k.startswith(target_prefix)]
    for k in keys_to_del: del st.session_state.db_cache[k]

# DB操作関数群
def _raw_db_get(table, params):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    try:
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list): return [d for d in data if isinstance(d, dict)]
            elif isinstance(data, dict): return [data]
        return []
    except Exception: return []

def db_get(table, params=""):
    cache_key = f"{table}_{params}"
    return get_cached_data(cache_key, _raw_db_get, table, params)

def db_post(table, data): 
    requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=data)
    clear_specific_cache(table)

def db_patch(table, record_id, data): 
    requests.patch(f"{SUPABASE_URL}/rest/v1/{table}?record_id=eq.{record_id}", headers=HEADERS, json=data)
    clear_specific_cache(table)

def db_patch_property(prop_id, data): 
    requests.patch(f"{SUPABASE_URL}/rest/v1/properties?property_id=eq.{prop_id}", headers=HEADERS, json=data)
    clear_specific_cache("properties")

def db_patch_inspections_by_prop(prop_id, new_name):
    requests.patch(f"{SUPABASE_URL}/rest/v1/inspections?property_id=eq.{prop_id}", headers=HEADERS, json={"property_name": new_name})
    clear_specific_cache("inspections")

def db_patch_inspection(ins_id, data):
    requests.patch(f"{SUPABASE_URL}/rest/v1/inspections?inspection_id=eq.{ins_id}", headers=HEADERS, json=data)
    clear_specific_cache("inspections")

def db_delete_record(record_id): 
    requests.delete(f"{SUPABASE_URL}/rest/v1/inspection_records?record_id=eq.{record_id}", headers=HEADERS)
    clear_specific_cache("inspection_records")

def db_delete_property(prop_id):
    requests.delete(f"{SUPABASE_URL}/rest/v1/inspection_records?property_id=eq.{prop_id}", headers=HEADERS)
    requests.delete(f"{SUPABASE_URL}/rest/v1/inspections?property_id=eq.{prop_id}", headers=HEADERS)
    requests.delete(f"{SUPABASE_URL}/rest/v1/properties?property_id=eq.{prop_id}", headers=HEADERS)
    clear_specific_cache("inspection_records")
    clear_specific_cache("inspections")
    clear_specific_cache("properties")

def upload_to_storage(base64_str):
    if not base64_str or not isinstance(base64_str, str): return None
    if base64_str.startswith("http://") or base64_str.startswith("https://"): return base64_str
    try:
        encoded = base64_str.split(",", 1)[1] if "," in base64_str else base64_str
        file_data = base64.b64decode(encoded)
        filename = f"{uuid.uuid4()}.jpg"
        url = f"{SUPABASE_URL}/storage/v1/object/photos/{filename}"
        res = requests.post(url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "image/jpeg"}, data=file_data)
        if res.status_code not in [200, 201]: return base64_str
        return f"{SUPABASE_URL}/storage/v1/object/public/photos/{filename}"
    except Exception: return base64_str

def bg_save_inspection(photo_b64, record_data):
    saved_url = upload_to_storage(photo_b64)
    if saved_url: record_data["issue_photo_url"] = saved_url
    db_post("inspection_records", record_data)

def bg_save_correction(rec_id, fix_photo_b64):
    fix_url = upload_to_storage(fix_photo_b64)
    db_patch("inspection_records", rec_id, {"progress_status": "是正確認中", "fix_photo_url": fix_url})

def bg_patch_record(rec_id, photo_b64, up_data):
    if photo_b64:
        url = upload_to_storage(photo_b64)
        if url: up_data["issue_photo_url"] = url
    db_patch("inspection_records", rec_id, up_data)

# ==========================================
# 物件・指摘の並び替えアルゴリズム
# ==========================================
AREA_ORDER = ["玄関", "トイレ", "キッチン", "バルコニー", "LDK", "洋室", "洗面室", "UB", "廊下・階段・ENT", "外部", "フリー項目"]
WORK_ORDER = ["A.リペア", "B.清掃", "C.クロス", "D.造作", "E.水道", "F.電気", "G.キッチン", "H.サッシ", "I.外壁", "J.外構", "K.コーキング", "L.ガス", "板金", "Z.その他"]

def sort_records(records):
    def get_sort_key(r):
        area = r.get('area', '')
        work = r.get('work_type', '')
        area_idx = AREA_ORDER.index(area) if area in AREA_ORDER else 999
        work_idx = WORK_ORDER.index(work) if work in WORK_ORDER else 999
        return (area_idx, work_idx)
    return sorted(records, key=get_sort_key)

def sort_properties_by_handover(props_list):
    if not props_list: return []
    def get_handover_key(p):
        h_date = p.get('handover_date')
        if h_date and h_date.strip(): return (0, h_date)
        return (1, "9999-12-31")
    return sorted(props_list, key=get_handover_key)

# ==========================================
# 2. スマート電子黒板カメラ
# ==========================================
SMART_CAMERA_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        body { margin: 0; padding: 5px; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; background-color: transparent;}
        .upload-btn {
            display: block; width: 100%; max-width: 400px; padding: 18px 20px;
            color: white; border-radius: 8px; font-size: 16px; font-weight: bold; text-align: center; cursor: pointer; 
            box-sizing: border-box; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        input[type="file"] { display: none; }
    </style>
</head>
<body>
    <label class="upload-btn" id="upload-label" style="background-color: #28a745;">
        <span id="btn-text">黒板付きで撮影 ／ 選択</span>
        <input type="file" accept="image/*" id="file-input">
    </label>
    <script>
        let b = { propName: "", inspType: "", inspDate: "", locationText: "", issueDetail: "", mode: "insp" };
        window.addEventListener("message", function(e) {
            if (e.data.type === "streamlit:render" && e.data.args) {
                b.propName = e.data.args.propName || ""; b.inspType = e.data.args.inspType || ""; 
                b.inspDate = e.data.args.inspDate || ""; b.locationText = e.data.args.locationText || ""; 
                b.issueDetail = e.data.args.issueDetail || ""; b.mode = e.data.args.mode || "insp";
                if(b.mode === 'fix') {
                    document.getElementById('upload-label').style.backgroundColor = '#007bff';
                    document.getElementById('btn-text').innerText = '是正写真を撮影';
                }
            }
        });

        function wrapTextAndReturnY(context, text, x, y, maxWidth, lineHeight, maxLines) {
            if (!text) return y;
            var words = text.split(''); var line = ''; var lineCount = 0;
            for(var n = 0; n < words.length; n++) {
                var testLine = line + words[n];
                if (context.measureText(testLine).width > maxWidth && n > 0) {
                    context.fillText(line, x, y); line = words[n]; y += lineHeight; lineCount++;
                    if (lineCount >= maxLines) return y;
                } else { line = testLine; }
            }
            context.fillText(line, x, y); return y + lineHeight;
        }

        function sendToStreamlit(val) { window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setComponentValue", value: val}, "*"); }

        const input = document.getElementById('file-input');
        input.addEventListener('change', function(e) {
            const file = e.target.files[0]; if (!file) return;
            document.getElementById('upload-label').style.backgroundColor = '#f39c12';
            document.getElementById('btn-text').innerHTML = '合成中...お待ちください';

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

                    const bw = w * 0.40, bh = h * 0.32;
                    const sx = w - bw - 10, sy = h - bh - 10;
                    
                    ctx.fillStyle = (b.mode === 'fix') ? "rgba(0, 40, 80, 0.9)" : "rgba(0, 50, 0, 0.85)";
                    ctx.fillRect(sx, sy, bw, bh);
                    ctx.strokeStyle = "white"; ctx.lineWidth = 2; ctx.strokeRect(sx+5, sy+5, bw-10, bh-10);
                    
                    ctx.fillStyle = "white"; const fs = Math.floor(w * 0.022); 
                    ctx.font = fs + "px 'Yu Gothic Medium', 'Hiragino Kaku Gothic ProN', sans-serif";
                    
                    let ty = sy + fs + 12; const ls = fs * 1.4; const textX = sx + 10; const dw = bw - 20;

                    ty = wrapTextAndReturnY(ctx, b.propName, textX, ty, dw, ls, 2);
                    ty = wrapTextAndReturnY(ctx, b.inspType + "  " + b.inspDate, textX, ty, dw, ls, 2);
                    ty = wrapTextAndReturnY(ctx, b.locationText, textX, ty, dw, ls, 2);
                    ctx.fillStyle = "#ffdddd";
                    wrapTextAndReturnY(ctx, b.issueDetail, textX, ty, dw, ls, 3);

                    sendToStreamlit(canvas.toDataURL('image/jpeg', 0.6));
                    document.getElementById('upload-label').style.backgroundColor = '#2ecc71';
                    document.getElementById('btn-text').innerHTML = 'セット完了';
                };
                img.src = event.target.result;
            };
            reader.readAsDataURL(file);
        });
        window.onload = function() {
            window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:componentReady", apiVersion: 1}, "*");
            window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: 80}, "*");
        };
    </script>
</body>
</html>
"""
temp_dir = os.path.join(tempfile.gettempdir(), "felix_components_planb")
os.makedirs(temp_dir, exist_ok=True)
with open(os.path.join(temp_dir, "index.html"), "w", encoding="utf-8") as f: f.write(SMART_CAMERA_HTML)
_smart_camera = components.declare_component("smart_cam_planb", path=temp_dir)

# ==========================================
# 3. UI設定 (プランB: 上部メニュー ＆ 印刷最適化)
# ==========================================
st.set_page_config(page_title="Felix検査App", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    [data-testid="collapsedControl"] { display: none !important; }
    [data-testid="stSidebar"] { display: none !important; }

    div.stButton > button { border-radius: 6px; height: 50px; font-weight: bold; width: 100%; margin-bottom: 5px; }
    footer {visibility: hidden;}
    [data-testid="stStatusWidget"] { display: none; }
    .record-box { border-bottom: 2px solid #EEEEEE; padding-bottom: 20px; margin-bottom: 20px; }
    .badge-wrap { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; font-weight: bold; margin-left: 5px; color: #d93025; }
    
    /* 🌟 差し戻し等のインライン小ボタン用の調整 */
    div[data-testid="column"] button { height: 35px !important; font-size: 12px !important; font-weight: normal !important; padding: 0 !important; }

    @media print {
        .stButton, .stTextInput, .stRadio, .stSelectbox, .stCheckbox, [data-testid="stExpander"] { display: none !important; }
        .admin-delete-box, hr { display: none !important; }
        .main .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
    }
</style>
""", unsafe_allow_html=True)

FLOOR_OPTS = ["-- 選択 --", "101","102","103","201","202","203","301","302","303","共用部","外部"]
AREA_OPTS_STANDARD = ["-- 選択 --", "玄関", "廊下・階段・ENT", "LDK", "キッチン", "洋室", "洗面室", "UB", "トイレ", "バルコニー", "外部", "フリー項目"]
AREA_OPTS_SHANAI = ["-- 選択 --", "玄関", "トイレ", "キッチン", "LDK", "バルCor", "洋室", "洗面室", "UB", "廊下・階段・ENT", "外部", "フリー項目"]
WORK_OPTS_STANDARD = ["-- 選択 --", "基礎工事(鉄筋)", "基礎工事(型枠)", "フレーミング", "FM", "造作", "内装", "電気", "設備", "ガス", "清掃", "サッシ", "外壁", "外構", "コーキング", "リペア", "その他"]
WORK_OPTS_HAIKIN = ["-- 選択 --", "基礎工事(鉄筋)", "水道", "ガス", "その他"]
WORK_OPTS_KUTAI = ["-- 選択 --", "フレーミング", "電気", "水道", "防水", "その他"]
WORK_OPTS_DANNETSU = ["-- 選択 --", "断熱", "造作", "電気", "設備", "その他"]
WORK_OPTS_CHUKAN = ["-- 選択 --", "造作", "電気", "水道", "外壁", "ガス", "足場", "その他"]
WORK_OPTS_SHANAI = ["-- 選択 --", "A.リペア", "B.清掃", "C.クロス", "D.造作", "E.水道", "F.電気", "G.キッチン", "H.サッシ", "I.外壁", "J.外構", "K.コーキング", "L.ガス", "板金", "Z.その他"]
WORK_OPTS_KIKAN = ["基礎工事", "フレーミング", "防水", "造作", "内装", "電気", "設備", "ガス", "サッシ", "外壁", "足場", "外構", "その他"]
INSP_OPTS = [
    "-- 選択 --", "配筋検査", "躯体検査", "断熱検査", "中間検査", 
    "社内検査(設計)", "社内検査(建設)", "社内検査(マーケ)", "社内検査(不動産)",
    "【検査機関】配筋検査", "【検査機関】躯体検査", "【検査機関】断熱検査", "【検査機関】中間検査", "【検査機関】完了検査"
]
SHANAI_KENSA_TYPES = ["社内検査(設計)", "社内検査(建設)", "社内検査(マーケ)", "社内検査(不動産)"]
INSPECTOR_OPTS = ["工事監理チーム", "建設部", "不動産事業部", "マーケティング部"]

# ==========================================
# 5. セッション管理 
# ==========================================
for key in ["role", "active_menu", "pre_selected_prop", "delete_target", "edit_prop_target", "skip_render_ids", "show_bulk_confirm", "edit_saved_records", "cached_records", "cached_target_id", "temp_photo", "prev_floor", "prev_area", "splash_done"]:
    if key not in st.session_state: st.session_state[key] = None

if st.session_state.skip_render_ids is None: st.session_state.skip_render_ids = []
if "issue_saved" not in st.session_state: st.session_state.issue_saved = False
if "drill_target" not in st.session_state or not isinstance(st.session_state.drill_target, dict): st.session_state.drill_target = None
if "current_box" not in st.session_state or not isinstance(st.session_state.current_box, dict): st.session_state.current_box = None
if st.session_state.splash_done is None: st.session_state.splash_done = False

qp = st.query_params
if "target_area" not in st.session_state: st.session_state.target_area = None
if qp.get("area") == "tokai": st.session_state.target_area = "東海エリア"
elif qp.get("area") == "kanto": st.session_state.target_area = "関東エリア"

def jump_to_menu(menu_name, prop_id=None):
    st.session_state.active_menu = menu_name
    st.session_state.pre_selected_prop = prop_id
    st.session_state.drill_target = None
    st.session_state.current_box = None
    st.session_state.delete_target = None
    st.session_state.edit_prop_target = None
    st.session_state.issue_saved = False
    st.session_state.skip_render_ids = []
    st.session_state.show_bulk_confirm = False
    st.session_state.edit_saved_records = False
    st.session_state.cached_records = None
    st.session_state.cached_target_id = None
    st.session_state.temp_photo = None
    st.session_state.prev_floor = None
    st.session_state.prev_area = None
    st.rerun()

# ==========================================
# 6. メイン画面・機能
# ==========================================
def main():
    if st.session_state.role is None:
        if qp.get("mode") == "partner":
            st.session_state.role = "partner"
            st.session_state.active_menu = "ホーム"
        else:
            st.session_state.role = "admin"
            st.session_state.active_menu = "ホーム"
        st.session_state.splash_done = False
        st.rerun()
        return

    confirm_cnt = 0
    if st.session_state.role == "admin":
        wait_conf_recs = db_get("inspection_records", "select=record_id&progress_status=eq.確認待ち")
        confirm_cnt = len(wait_conf_recs)

    def format_menu(m):
        if m == "検査内容確認（管理者）" and confirm_cnt > 0:
            return f"{m} (未確認{confirm_cnt}件)"
        return m

    if st.session_state.role == "admin":
        menu_opts = ["ホーム", "物件登録（管理者）", "検査実施（管理者）", "検査内容確認（管理者）", "是正ダッシュボード（管理者用）", "完了分一覧（共通）"]
    else:
        menu_opts = ["ホーム", "是正実施（協力業者）", "完了分一覧（共通）"]
        
    if st.session_state.active_menu not in menu_opts: st.session_state.active_menu = menu_opts[0]
    
    with st.expander(f"メニューを開く (現在のユーザー: {st.session_state.role})", expanded=False):
        selected_menu = st.radio("移動先を選択", menu_opts, index=menu_opts.index(st.session_state.active_menu), format_func=format_menu, label_visibility="collapsed")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("ログアウト"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.query_params.clear(); st.rerun()

    if selected_menu != st.session_state.active_menu:
        jump_to_menu(selected_menu, st.session_state.pre_selected_prop)

    # ----------------------------------------
    # メニュー: 0. ホーム
    # ----------------------------------------
    if st.session_state.active_menu == "ホーム":
        if not st.session_state.splash_done:
            st.markdown("""
            <style>
            .splash { display: flex; justify-content: center; align-items: center; height: 100vh; font-size: 16px; color: #555; position: fixed; top: 0; left: 0; width: 100vw; background: white; z-index: 999999; letter-spacing: 2px; font-family: sans-serif; }
            </style>
            <div class="splash">FELIX Inspection System...</div>
            """, unsafe_allow_html=True)
            time.sleep(1.5)
            st.session_state.splash_done = True
            st.rerun()
        else:
            role = st.session_state.role
            new_btn_text = "新規検査を開始する" if role == "admin" else "新規是正を開始する"
            ls_key = "felix_session" if role == "admin" else "felix_partner_session"
            
            menu_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <style>
                body {{ margin:0; font-family: sans-serif; display: flex; flex-direction: column; height: 100vh; background: transparent; }}
                .menu-item {{ font-size: 16px; color: #333; cursor: pointer; margin: 24px 0; text-align: center; transition: color 0.2s; user-select: none; }}
                .menu-item:hover {{ color: #888; }}
                .container {{ position: absolute; top: 38.2%; left: 50%; transform: translate(-50%, -50%); width: 100%; }}
            </style>
            </head>
            <body>
            <div class="container">
                <div class="menu-item" onclick="sendVal('new')">{new_btn_text}</div>
                <div class="menu-item" id="resume-btn" style="display:none;" onclick="sendVal('resume')"></div>
            </div>
            <script>
                function sendVal(action) {{
                    let val = {{ action: action }};
                    if(action === 'resume') {{ val.data = JSON.parse(localStorage.getItem('{ls_key}')); }}
                    window.parent.postMessage({{isStreamlitMessage: true, type: "streamlit:setComponentValue", value: val}}, "*");
                }}
                const saved = localStorage.getItem('{ls_key}');
                if(saved) {{
                    try {{
                        const data = JSON.parse(saved);
                        let text = '';
                        if('{role}' === 'admin' && data.name && data.type) {{ text = '前回の続きから再開する（' + data.name + ' / ' + data.type + '）'; }} 
                        else if ('{role}' === 'partner' && data.prop && data.type) {{ text = '前回の続きから再開する（' + data.prop + ' / ' + data.type + '）'; }}
                        if(text) {{
                            const btn = document.getElementById('resume-btn');
                            btn.style.display = 'block'; btn.innerText = text;
                        }}
                    }} catch(e) {{}}
                }}
                window.onload = function() {{
                    window.parent.postMessage({{isStreamlitMessage: true, type: "streamlit:componentReady", apiVersion: 1}}, "*");
                    window.parent.postMessage({{isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: 500}}, "*");
                }};
            </script>
            </body>
            </html>
            """
            temp_dir_menu = os.path.join(tempfile.gettempdir(), f"felix_home_menu_{role}")
            os.makedirs(temp_dir_menu, exist_ok=True)
            with open(os.path.join(temp_dir_menu, "index.html"), "w", encoding="utf-8") as f: f.write(menu_html)
            _home_menu = components.declare_component(f"home_menu_{role}", path=temp_dir_menu)
            res = _home_menu(key=f"home_menu_comp_{role}")
            
            if res:
                if res.get('action') == 'new':
                    st.session_state.active_menu = "検査実施（管理者）" if role == "admin" else "是正実施（協力業者）"
                    st.session_state.current_box = None; st.session_state.drill_target = None; st.rerun()
                elif res.get('action') == 'resume' and res.get('data'):
                    d = res['data']
                    if role == "admin":
                        st.session_state.active_menu = "検査実施（管理者）"
                        st.session_state.current_box = {"id": d.get('id', str(uuid.uuid4())), "prop_id": d.get('prop_id'), "name": d.get('name'), "type": d.get('type'), "inspector": d.get('inspector')}
                        st.session_state.prev_floor = d.get('prev_floor'); st.session_state.prev_area = d.get('prev_area')
                    else:
                        st.session_state.active_menu = "是正実施（協力業者）"
                        st.session_state.drill_target = {"prop": d.get('prop'), "type": d.get('type')}
                    st.rerun()

    # ----------------------------------------
    # メニュー: 1. 物件登録（管理者）
    # ----------------------------------------
    elif st.session_state.active_menu == "物件登録（管理者）":
        st.header("物件登録")
        with st.container():
            input_area = st.selectbox("エリアを選択", ["東海エリア", "関東エリア"])
            name = st.text_input("新規物件名")
            set_handover = st.checkbox("引渡し日を設定する", value=False, key="set_h_new")
            if set_handover: handover_date_val = st.date_input("引渡し日", value=datetime.date.today(), key="h_date_new")
            else: handover_date_val = None
            if st.button("登録"):
                if name:
                    h_str = str(handover_date_val) if set_handover and handover_date_val else None
                    db_post("properties", {"property_id": str(uuid.uuid4()), "property_name": name, "area": input_area, "handover_date": h_str})
                    st.success(f"[{input_area}] に登録完了"); st.rerun()
        st.markdown("---")
        st.subheader("登録済み物件一覧")
        filter_area = st.radio("一覧のエリア絞り込み", ["すべて表示", "東海エリア", "関東エリア"], horizontal=True)
        props = db_get("properties", "select=*")
        props = sort_properties_by_handover(props)
        all_ins = db_get("inspections", "select=property_id")
        prop_ins_counts = {}
        for ins in all_ins:
            pid = ins.get('property_id')
            if pid: prop_ins_counts[pid] = prop_ins_counts.get(pid, 0) + 1
        
        for idx, p in enumerate(props):
            prop_id = p.get('property_id')
            if not prop_id: continue
            p_area = p.get('area', '未設定')
            if filter_area != "すべて表示" and p_area != filter_area: continue
            p_name = p.get('property_name', '不明'); p_hdate = p.get('handover_date')
            hdate_disp = f" (引渡し: {p_hdate})" if p_hdate else " (引渡し日: 未設定)"
            ins_count = prop_ins_counts.get(prop_id, 0)
            count_disp = f"（データ: {ins_count}件）" if ins_count > 0 else "（データなし）"
            btn_text = f"[{p_area}] {p_name}{hdate_disp} {count_disp} 検査へ"
            key_suffix = f"{prop_id}_{idx}"
            
            c1, c2, c3 = st.columns([6, 2, 2])
            if c1.button(btn_text, key=f"p_{key_suffix}"): jump_to_menu("検査実施（管理者）", prop_id)
            if c2.button("変更", key=f"e_{key_suffix}"):
                st.session_state.edit_prop_target = prop_id; st.session_state.delete_target = None; st.rerun()
            if c3.button("削除", key=f"d_{key_suffix}"): 
                st.session_state.delete_target = prop_id; st.session_state.edit_prop_target = None; st.rerun()
            
            if st.session_state.edit_prop_target == prop_id:
                st.warning(f"「{p_name}」の内容を変更します。過去のデータ名も連動して更新されます。")
                new_name = st.text_input("物件名を入力", value=p_name, key=f"new_name_{key_suffix}")
                has_hdate = True if p_hdate and p_hdate.strip() else False
                try: init_d = datetime.datetime.strptime(p_hdate, "%Y-%m-%d").date() if has_hdate else datetime.date.today()
                except: init_d = datetime.date.today(); has_hdate = False
                edit_set_handover = st.checkbox("引渡し日を設定する", value=has_hdate, key=f"eh_cb_{key_suffix}")
                if edit_set_handover: new_hdate = st.date_input("引渡し日を変更", value=init_d, key=f"new_h_{key_suffix}")
                else: new_hdate = None
                
                col_y, col_n = st.columns(2)
                if col_y.button("保存", key=f"save_name_{key_suffix}", type="primary"):
                    nh_str = str(new_hdate) if edit_set_handover and new_hdate else None
                    db_patch_property(prop_id, {"property_name": new_name, "handover_date": nh_str})
                    if new_name != p_name: db_patch_inspections_by_prop(prop_id, new_name)
                    st.success("変更を保存しました"); st.session_state.edit_prop_target = None; st.rerun()
                if col_n.button("キャンセル", key=f"cancel_name_{key_suffix}"): st.session_state.edit_prop_target = None; st.rerun()
                st.markdown("---")
                
            if st.session_state.delete_target == prop_id:
                st.warning(f"本当に「{p_name}」を削除しますか？紐づくすべてのデータが消えます。")
                del_pw = st.text_input("削除用パスワードを入力", type="password", key=f"pw_{key_suffix}", placeholder="2011")
                col_y, col_n = st.columns(2)
                if col_y.button("Yes (削除実行)", key=f"yes_{key_suffix}"):
                    if del_pw == "2011":
                        db_delete_property(prop_id); st.session_state.delete_target = None; st.session_state.current_box = None; st.rerun()
                    else: st.error("パスワードが違います")
                if col_n.button("No (キャンセル)", key=f"no_{key_suffix}"): st.session_state.delete_target = None; st.rerun()
                st.markdown("---")

    # ----------------------------------------
    # メニュー: 2. 検査実施（管理者）
    # ----------------------------------------
    elif st.session_state.active_menu == "検査実施（管理者）":
        if not st.session_state.current_box:
            st.header("検査開始")
            props = db_get("properties", "select=*")
            props = sort_properties_by_handover(props)
            if st.session_state.pre_selected_prop is None:
                if props: st.session_state.pre_selected_prop = props[0].get("property_id")

            area_opts = ["-- 選択 --", "東海エリア", "関東エリア"]; init_area_idx = 0
            if st.session_state.pre_selected_prop:
                pre_prop = next((p for p in props if p.get('property_id') == st.session_state.pre_selected_prop), None)
                if pre_prop and pre_prop.get('area') in area_opts: init_area_idx = area_opts.index(pre_prop.get('area'))
            
            sel_area = st.selectbox("エリアを選択", area_opts, index=init_area_idx)
            search_query = st.text_input("物件名で検索（一部入力でも可）", key="search_insp")
            filtered_props = [p for p in props if p.get('area') == sel_area and p.get('property_id')] if sel_area != "-- 選択 --" else []
            if search_query: filtered_props = [p for p in filtered_props if search_query in p.get('property_name', '')]
                
            opts = [{"property_id": None, "property_name": "-- 選択 --"}] + filtered_props
            idx = next((i for i, p in enumerate(opts) if p.get('property_id') == st.session_state.pre_selected_prop), 0)
            
            def format_prop_selectbox(x):
                if x.get('property_id') is None: return x.get('property_name')
                h_disp = f" (引渡し: {x.get('handover_date')})" if x.get('handover_date') else " (引渡し未設定)"
                return f"{x.get('property_name')}{h_disp}"

            st.markdown("<p style='color:gray; font-size:12px; margin-bottom:0;'>物件は引渡し日が一番近い順に並んでいます</p>", unsafe_allow_html=True)
            target = st.selectbox("物件を選択", opts, index=idx, format_func=format_prop_selectbox)
            ins_type = st.selectbox("検査種類を選択", INSP_OPTS)
            
            c1, c2 = st.columns(2)
            ins_date = c1.date_input("検査日時", datetime.date.today())
            inspector = c2.selectbox("検査員", INSPECTOR_OPTS)
            
            if st.button("検査スタート"):
                prop_name = target.get('property_name'); prop_id = target.get('property_id')
                if prop_name != "-- 選択 --" and ins_type != "-- 選択 --":
                    nid = str(uuid.uuid4())
                    db_post("inspections", {"inspection_id": nid, "property_id": prop_id, "property_name": prop_name, "inspection_type": ins_type, "inspection_date": str(ins_date), "inspector": inspector})
                    st.session_state.current_box = {"id": nid, "prop_id": prop_id, "name": prop_name, "type": ins_type, "inspector": inspector}
                    st.session_state.pre_selected_prop = prop_id
                    st.session_state.issue_saved = False; st.session_state.edit_saved_records = False; st.session_state.cached_records = None; st.session_state.temp_photo = None
                    st.session_state.prev_floor = None; st.session_state.prev_area = None; st.rerun()
                else: st.error("物件と検査種類を選んでください")
        else:
            cb = st.session_state.current_box
            if not isinstance(cb, dict): cb = {}
            c_name = cb.get('name', ''); c_type = cb.get('type', ''); c_id = cb.get('id', ''); c_prop_id = cb.get('prop_id', ''); c_inspector = cb.get('inspector', '')
            st.subheader(f"{c_name} / {c_type}")

            cb_data = cb.copy()
            cb_data['prev_floor'] = st.session_state.prev_floor; cb_data['prev_area'] = st.session_state.prev_area
            json_str = json.dumps(cb_data, ensure_ascii=False)
            components.html(f"<script>localStorage.setItem('felix_session', JSON.stringify({json_str}));</script>", height=0)
            
            if st.session_state.get("edit_saved_records"):
                st.markdown("#### 今回保存した指摘データの確認・修正")
                if st.button("＜ 検査登録に戻る", key="back_top", use_container_width=True): st.session_state.edit_saved_records = False; st.rerun()
                st.markdown("---")
                
                saved_recs = db_get("inspection_records", f"inspection_id=eq.{c_id}")
                if not saved_recs: st.info("まだ保存された指摘データはありません。")
                else:
                    if c_type in SHANAI_KENSA_TYPES:
                        floors_in_recs = sorted(list(set([r.get('floor_level', '一式') for r in saved_recs if r.get('floor_level')])))
                        sel_floor = st.selectbox("部屋（階層）で絞り込み", ["すべて表示"] + floors_in_recs, key="filter_edit_floor")
                        if sel_floor != "すべて表示": saved_recs = [r for r in saved_recs if r.get('floor_level') == sel_floor]
                
                edit_w_opts = WORK_OPTS_KIKAN if c_type.startswith("【検査機関】") else WORK_OPTS_SHANAI if c_type in SHANAI_KENSA_TYPES else WORK_OPTS_KUTAI if c_type == "躯体検査" else WORK_OPTS_HAIKIN if c_type == "配筋検査" else WORK_OPTS_CHUKAN if c_type == "中間検査" else WORK_OPTS_DANNETSU if c_type == "断熱検査" else WORK_OPTS_STANDARD
                saved_recs = sort_records(saved_recs)

                for r in saved_recs:
                    rec_id = r.get('record_id')
                    if not rec_id: continue
                    floor = r.get('floor_level', ''); area = r.get('area', ''); detail = r.get('issue_detail', ''); orig_w = r.get('work_type', '')
                    head_text = "" if c_type.startswith("【検査機関】") or floor == "一式" else f"【{floor} {area}】".strip()
                    title = f"{head_text} {detail}" if head_text else f"【指摘内容】 {detail}"
                    
                    with st.container():
                        st.markdown('<div class="record-box">', unsafe_allow_html=True)
                        st.markdown(f"**{title}**")
                        if r.get('issue_photo_url'): 
                            photo_url = r.get('issue_photo_url')
                            st.markdown(f'<a href="{photo_url}" target="_blank"><img src="{photo_url}" style="width:250px; border-radius:4px; margin-bottom:10px;"></a>', unsafe_allow_html=True)
                            
                        with st.expander("内容を修正・差し替え・削除"):
                            new_f = floor; new_a = area; sel_temp = None; default_w = ""
                            if not c_type.startswith("【検査機関】"):
                                a_opts = AREA_OPTS_SHANAI if c_type in SHANAI_KENSA_TYPES else AREA_OPTS_STANDARD
                                if c_type not in ["配筋検査", "躯体検査", "断熱検査", "中間検査"]:
                                    f_idx = FLOOR_OPTS[1:].index(floor) if floor in FLOOR_OPTS[1:] else 0
                                    new_f = st.radio("階層を変更", FLOOR_OPTS[1:], index=f_idx, horizontal=True, key=f"ef_{rec_id}")
                                    a_idx = a_opts[1:].index(area) if area in a_opts[1:] else 0
                                    new_a = st.radio("部位を変更", a_opts[1:], index=a_idx, horizontal=True, key=f"ea_{rec_id}")
                                
                                cat_dict = ISSUE_TEMPLATES.get(c_type, {}) if c_type in ["配筋検査", "躯体検査", "断熱検査", "中間検査"] else ISSUE_TEMPLATES.get("社内検査(設計)", {}).get(new_a, {}) if c_type in SHANAI_KENSA_TYPES else {}
                                if not isinstance(cat_dict, dict): cat_dict = {}
                                cat_keys = list(cat_dict.keys())
                                sel_cat = st.radio("分類を変更", cat_keys, horizontal=True, key=f"ecat_{rec_id}") if cat_keys else None
                                
                                if sel_cat:
                                    detail_dict = cat_dict.get(sel_cat, {})
                                    temp_list = list(detail_dict.keys()) + ["その他（フリー項目）"]
                                    sel_temp = st.radio("よくある指摘事項", temp_list, key=f"etemp_{rec_id}", horizontal=True)
                                    default_w = detail_dict.get(sel_temp, "") if sel_temp != "その他（フリー項目）" else ""
                            
                            edit_desc_val = detail.split(":", 1)[1] if ":" in detail else detail.split("：", 1)[1] if "：" in detail else detail
                            st.markdown("##### 詳細・場所の追記を変更")
                            new_detail = st.text_area("詳細情報を変更", value=edit_desc_val, label_visibility="collapsed", key=f"ed_desc_{rec_id}")
                            
                            disp_w_opts = edit_w_opts[1:]
                            if default_w in disp_w_opts: w_idx = disp_w_opts.index(default_w)
                            elif orig_w in disp_w_opts: w_idx = disp_w_opts.index(orig_w)
                            else: w_idx = 0
                            new_w = st.radio("工種を変更", disp_w_opts, index=w_idx, horizontal=True, key=f"ed_work_{rec_id}_{sel_cat}_{sel_temp}")
                            
                            if sel_temp == "その他（フリー項目）": final_desc = new_detail.strip()
                            else: final_desc = (sel_temp + ("：" + new_detail.strip() if new_detail.strip() != "" else "")) if sel_temp else new_detail.strip()
                            if final_desc == "": final_desc = detail 
                            
                            loc_parts = [str(new_f), str(new_a)]
                            if not c_type.startswith("【検査機関】") and sel_cat: loc_parts.append(str(sel_cat))
                            loc_str = " ".join(loc_parts).strip()
                            disp_desc = final_desc[:80] + "..." if len(final_desc) > 80 else final_desc
                            
                            st.write("写真を差し替える場合のみ撮影/選択してください")
                            new_photo = _smart_camera(
                                propName=c_name, inspType=c_type, inspDate=datetime.date.today().strftime("%Y/%m/%d"), 
                                locationText=loc_str, issueDetail=disp_desc, mode="insp", key=f"ed_cam_{rec_id}"
                            )
                            
                            c_save, c_del = st.columns(2)
                            if c_save.button("この内容で上書き", key=f"ed_save_{rec_id}", type="primary"):
                                up_data = {"floor_level": new_f, "area": new_a, "work_type": new_w, "issue_detail": final_desc}
                                threading.Thread(target=bg_patch_record, args=(rec_id, new_photo, up_data)).start()
                                st.rerun()
                            if c_del.button("この指摘を削除", key=f"ed_del_{rec_id}"): 
                                db_delete_record(rec_id); st.rerun()
                            if new_photo: 
                                st.markdown("<p style='font-size:12px; color:gray; margin-top:10px;'>▼ 差し替え用プレビュー (縮小表示)</p>", unsafe_allow_html=True)
                                st.image(new_photo, width=250)
                                
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                st.markdown("---")
                if st.button("＜ 検査登録に戻る", key="back_bottom", use_container_width=True): st.session_state.edit_saved_records = False; st.rerun()

            elif not st.session_state.issue_saved:
                prev_f = st.session_state.prev_floor; prev_a = st.session_state.prev_area
                if c_type.startswith("【検査機関】"):
                    f = "一式"; a = "全体"; sel_cat = None; sel_temp = None; default_w = ""
                    st.markdown("##### 詳細・場所の追記（自由入力）")
                    desc = st.text_area("詳細情報を入力", label_visibility="collapsed", placeholder="具体的な指摘内容や場所を入力してください")
                    st.markdown("##### 工種を選択")
                    work_opts = WORK_OPTS_KIKAN; w_idx = 0
                else:
                    f = "一式"; a = "全体"; default_w = ""
                    area_opts = AREA_OPTS_SHANAI if c_type in SHANAI_KENSA_TYPES else AREA_OPTS_STANDARD
                    work_opts = WORK_OPTS_SHANAI if c_type in SHANAI_KENSA_TYPES else WORK_OPTS_KUTAI if c_type == "躯体検査" else WORK_OPTS_HAIKIN if c_type == "配筋検査" else WORK_OPTS_CHUKAN if c_type == "中間検査" else WORK_OPTS_DANNETSU if c_type == "断熱検査" else WORK_OPTS_STANDARD
                    
                    if c_type not in ["配筋検査", "躯体検査", "断熱検査", "中間検査"]:
                        f_idx = FLOOR_OPTS[1:].index(prev_f) if prev_f in FLOOR_OPTS[1:] else 0
                        f = st.radio("階層を選択", FLOOR_OPTS[1:], index=f_idx, horizontal=True)
                        a_idx = area_opts[1:].index(prev_a) if prev_a in area_opts[1:] else 0
                        a = st.radio("部位を選択", area_opts[1:], index=a_idx, horizontal=True)
                    
                    cat_dict = ISSUE_TEMPLATES.get(c_type, {}) if c_type in ["配筋検査", "躯体検査", "断熱検査", "中間検査"] else ISSUE_TEMPLATES.get("社内検査(設計)", {}).get(a, {}) if c_type in SHANAI_KENSA_TYPES else {}
                    if not isinstance(cat_dict, dict): cat_dict = {}
                    cat_keys = list(cat_dict.keys())
                    sel_cat = st.radio("分類を選択", cat_keys, horizontal=True) if cat_keys else None
                    
                    if sel_cat:
                        detail_dict = cat_dict.get(sel_cat, {})
                        temp_list = list(detail_dict.keys()) + ["その他（フリー項目）"]
                        sel_temp = st.radio("よくある指摘事項", temp_list, horizontal=True)
                        default_w = detail_dict.get(sel_temp, "") if sel_temp != "その他（フリー項目）" else ""
                    else: sel_temp = None
                        
                    st.markdown("##### 詳細・場所の追記（自由入力）")
                    desc = st.text_area("詳細情報を入力", label_visibility="collapsed")
                    
                    disp_w_opts = work_opts[1:]
                    if default_w in disp_w_opts: w_idx = disp_w_opts.index(default_w)
                    else: w_idx = 0
                
                disp_w_opts = work_opts if c_type.startswith("【検査機関】") else work_opts[1:]
                w = st.radio("工種を選択", disp_w_opts, index=w_idx, horizontal=True, key=f"w_new_{sel_cat}_{sel_temp}")
                
                if sel_temp == "その他（フリー項目）": final_desc = desc.strip()
                else: final_desc = (sel_temp + ("：" + desc.strip() if desc.strip() != "" else "")) if sel_temp else desc.strip()
                
                loc_parts = [str(f), str(a)]
                if not c_type.startswith("【検査機関】") and sel_cat: loc_parts.append(str(sel_cat))
                loc_str = " ".join(loc_parts).strip()
                disp_desc = final_desc[:80] + "..." if len(final_desc) > 80 else final_desc

                st.markdown("##### 現場写真の追加（黒板自動合成）")
                photo_input = _smart_camera(
                    propName=c_name, inspType=c_type, inspDate=datetime.date.today().strftime("%Y/%m/%d"), 
                    locationText=loc_str, issueDetail=disp_desc, mode="insp", key="insp_cam"
                )
                if photo_input: st.session_state.temp_photo = photo_input

                if st.button("この内容で保存", type="primary"):
                    active_photo = st.session_state.temp_photo
                    if w and final_desc != "" and active_photo is not None:
                        initial_status = "確認待ち" if c_inspector == "工事監理チーム" else "是正待ち"
                        record_data = {
                            "record_id": str(uuid.uuid4()), "inspection_id": c_id, "property_id": c_prop_id, 
                            "floor_level": f, "area": a, "work_type": w, "issue_detail": final_desc, 
                            "progress_status": initial_status, "line_notified": False
                        }
                        threading.Thread(target=bg_save_inspection, args=(active_photo, record_data)).start()
                        st.session_state.issue_saved = True; st.session_state.temp_photo = None
                        st.session_state.prev_floor = f; st.session_state.prev_area = a; st.rerun()
                    else: st.error("工種・内容・写真はすべて必須です")
                
                if st.button("終了"): st.session_state.current_box = None; st.session_state.temp_photo = None; st.session_state.prev_floor = None; st.session_state.prev_area = None; st.rerun()

                if st.session_state.temp_photo:
                    st.markdown("<p style='font-size:12px; color:gray; margin-top:10px;'>▼ プレビュー (1/4縮小表示)</p>", unsafe_allow_html=True)
                    st.image(st.session_state.temp_photo, width=250)

            else:
                st.success("保存完了（次の入力が可能です）") 
                if st.button("続けて次を登録", use_container_width=True): st.session_state.issue_saved = False; st.session_state.temp_photo = None; st.rerun()
                if st.button("保存データを確認・修正", use_container_width=True): st.session_state.edit_saved_records = True; st.rerun()
                if st.button("検査全体を終了", use_container_width=True): st.session_state.current_box = None; st.session_state.issue_saved = False; st.session_state.edit_saved_records = False; st.session_state.cached_records = None; st.temp_photo = None; st.session_state.prev_floor = None; st.session_state.prev_area = None; st.rerun()

    # ----------------------------------------
    # メニュー: 3. 検査内容確認（管理者専用）
    # ----------------------------------------
    elif st.session_state.active_menu == "検査内容確認（管理者）":
        st.header("検査内容確認 ＆ 最終修正")
        sel_area = st.radio("表示エリアで絞り込み", ["すべて表示", "東海エリア", "関東エリア"], horizontal=True, key="area_verify")
        t_area = sel_area if sel_area != "すべて表示" else None
        search_verify = st.text_input("物件名で検索（一部入力でも可）", key="search_verify")
        
        all_recs_for_tree = db_get("inspection_records", "select=inspection_id,progress_status&progress_status=eq.確認待ち")
        all_ins = db_get("inspections", "select=*")
        all_props = db_get("properties", "select=*")
        all_props = sort_properties_by_handover(all_props)
        prop_area_map = {p.get('property_id'): p.get('area') for p in all_props if isinstance(p, dict)}
        prop_hdate_map = {p.get('property_id'): p.get('handover_date') for p in all_props if isinstance(p, dict)}
        
        ins_map = {i.get('inspection_id'): i for i in all_ins if isinstance(i, dict) and i.get('inspection_id')}
        tree = {}
        for r in all_recs_for_tree:
            if not isinstance(r, dict): continue
            ins = ins_map.get(r.get('inspection_id'))
            if ins:
                p_id = ins.get('property_id')
                if t_area and prop_area_map.get(p_id) != t_area: continue
                p = ins.get('property_name', '不明'); t = ins.get('inspection_type', '不明')
                if p not in tree: tree[p] = {"types": {}, "prop_id": p_id}
                tree[p]["types"][t] = tree[p]["types"].get(t, 0) + 1
        if search_verify: tree = {k: v for k, v in tree.items() if search_verify in k}

        # 物件アコーディオンの重複表示を合体排除
        sorted_tree_keys = []
        for p in all_props:
            p_name = p.get('property_name')
            if p_name in tree and p_name not in sorted_tree_keys: 
                sorted_tree_keys.append(p_name)
        for k in tree.keys():
            if k not in sorted_tree_keys: sorted_tree_keys.append(k)

        if not tree: st.info("現在、該当する確認待ちの検査はありません。")
                
        for p_idx, p_name in enumerate(sorted_tree_keys):
            v_data = tree[p_name]; p_id = v_data.get("prop_id"); p_hdate = prop_hdate_map.get(p_id)
            h_disp = f" (引渡し: {p_hdate})" if p_hdate else " (引渡し未設定)"
            with st.expander(f"{p_name}{h_disp}"):
                for t_idx, (t_name, count) in enumerate(v_data["types"].items()):
                    if st.button(f"{t_name} ({count}件)", key=f"f_{p_idx}_{t_idx}"):
                        st.session_state.drill_target = {"prop": p_name, "type": t_name}; st.session_state.cached_records = None; st.rerun()
        
        sel = st.session_state.drill_target
        if not isinstance(sel, dict): sel = {}
        prop_val = sel.get('prop', ''); type_val = sel.get('type', '')
        target_id_str = f"verif_{prop_val}_{type_val}" if prop_val else None

        if prop_val and type_val:
            if st.button("＜ 物件選択に戻る"): st.session_state.drill_target = None; st.session_state.cached_records = None; st.rerun()
            
            t_ids = [str(i.get('inspection_id')) for i in all_ins if isinstance(i, dict) and i.get('property_name') == prop_val and i.get('inspection_type') == type_val and i.get('inspection_id')]
            if t_ids:
                if st.session_state.cached_records is None or st.session_state.cached_target_id != target_id_str:
                    recs = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.確認待ち")
                    st.session_state.cached_records = recs; st.session_state.cached_target_id = target_id_str
                else: recs = st.session_state.cached_records

                if recs and type_val in SHANAI_KENSA_TYPES:
                    floors_in_recs = sorted(list(set([r.get('floor_level', 'one') for r in recs if r.get('floor_level')])))
                    sel_floor = st.selectbox("部屋（階層）で絞り込み", ["すべて表示"] + floors_in_recs, key="filter_verify_floor")
                    if sel_floor != "すべて表示": recs = [r for r in recs if r.get('floor_level') == sel_floor]

                st.info(f"この検査（{prop_val} / {type_val}）には、現在 {len(recs)}件 のデータがあります。")
                if st.button("この検査をすべて承認して業者（是正実施）に送る", type="primary"):
                    for r in recs: db_patch("inspection_records", r['record_id'], {"progress_status": "是正待ち"})
                    st.success("一括承認が完了しました。協力業者へ表示されます。"); st.session_state.drill_target = None; st.session_state.cached_records = None; st.rerun()
                st.markdown("---")
                
                edit_w_opts = WORK_OPTS_KIKAN if type_val.startswith("【検査機関】") else WORK_OPTS_SHANAI if type_val in SHANAI_KENSA_TYPES else WORK_OPTS_KUTAI if type_val == "躯体検査" else WORK_OPTS_HAIKIN if type_val == "配筋検査" else WORK_OPTS_CHUKAN if type_val == "中間検査" else WORK_OPTS_DANNETSU if type_val == "断熱検査" else WORK_OPTS_STANDARD
                edit_a_opts = AREA_OPTS_SHANAI if type_val in SHANAI_KENSA_TYPES else AREA_OPTS_STANDARD
                recs = sort_records(recs)

                w_groups = {}
                for r in recs:
                    if not isinstance(r, dict): continue
                    w = r.get('work_type') or 'その他'
                    if w not in w_groups: w_groups[w] = []
                    w_groups[w].append(r)
                
                for w_name, w_recs in w_groups.items():
                    st.subheader(f"■ 工種: {w_name}")
                    for r in w_recs:
                        rec_id = r.get('record_id')
                        if not rec_id: continue
                        floor = r.get('floor_level', ''); area = r.get('area', ''); detail = r.get('issue_detail', '')
                        head_text = "" if type_val.startswith("【検査機関】") or floor == "一式" else f"【{floor} {area}】".strip()
                        title = f"{head_text} {detail}" if head_text else f"【指摘内容】 {detail}"
                        
                        st.markdown('<div class="record-box">', unsafe_allow_html=True)
                        st.markdown(f"**{title}**")
                        
                        if r.get('issue_photo_url'): 
                            photo_url = r.get('issue_photo_url')
                            st.markdown(f'<a href="{photo_url}" target="_blank"><img src="{photo_url}" style="width:250px; border-radius:4px; margin-bottom:10px;"></a>', unsafe_allow_html=True)
                        
                        with st.expander("指摘内容・写真を直前修正する"):
                            f_idx = FLOOR_OPTS[1:].index(floor) if floor in FLOOR_OPTS[1:] else 0
                            new_f = st.radio("階層", FLOOR_OPTS[1:], index=f_idx, horizontal=True, key=f"vf_{rec_id}")
                            a_idx = edit_a_opts[1:].index(area) if area in edit_a_opts[1:] else 0
                            new_a = st.radio("部位", edit_a_opts[1:], index=a_idx, horizontal=True, key=f"va_{rec_id}")
                            new_d = st.text_area("指摘詳細を変更", value=detail, key=f"vd_{rec_id}")
                            idx_w = edit_w_opts.index(r.get('work_type', '')) if r.get('work_type', '') in edit_w_opts else 0
                            new_w = st.radio("工種を変更", edit_w_opts, index=idx_w, horizontal=True, key=f"vw_{rec_id}")
                            loc_str = f"{new_f} {new_a}".strip()
                            disp_d = new_d[:80] + "..." if len(new_d)>80 else new_d
                            
                            st.write("写真を差し替える場合のみ撮影/選択してください")
                            new_p = _smart_camera(
                                propName=prop_val, inspType=type_val, inspDate=datetime.date.today().strftime("%Y/%m/%d"), 
                                locationText=loc_str, issueDetail=disp_d, mode="insp", key=f"vp_{rec_id}"
                            )
                            if st.button("この内容で修正保存", key=f"vsave_{rec_id}"):
                                up_data = {"floor_level": new_f, "area": new_a, "issue_detail": new_d.strip(), "work_type": new_w}
                                threading.Thread(target=bg_patch_record, args=(rec_id, new_p, up_data)).start(); st.session_state.cached_records = None; st.rerun()
                            if new_p: st.image(new_p, caption="差し替えプレビュー", width=250)

                        c1, c2 = st.columns(2)
                        if c1.button("個別承認（業者へ送る）", key=f"vok_{rec_id}", type="primary"):
                            db_patch("inspection_records", rec_id, {"progress_status": "是正待ち"}); st.session_state.cached_records = None; st.rerun()
                        if c2.button("指摘を削除", key=f"vdel_{rec_id}"):
                            db_delete_record(rec_id); st.session_state.cached_records = None; st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)


    # ----------------------------------------
    # メニュー: 4-A. 是正実施（協力業者専用）
    # ----------------------------------------
    elif st.session_state.active_menu == "是正実施（協力業者）":
        st.header("定是正実施")
        if st.session_state.target_area:
            st.success(f"現在の表示エリア：【 {st.session_state.target_area} 】")
            t_area = st.session_state.target_area
        else:
            st.warning("URLにエリア指定がありません。正しいURLからアクセスしてください。")
            t_area = None
        search_fix = st.text_input("物件名で検索（一部入力でも可）", key="search_fix")

        all_recs_for_tree = db_get("inspection_records", "select=inspection_id,progress_status")
        all_ins = db_get("inspections", "select=*")
        all_props = db_get("properties", "select=*")
        all_props = sort_properties_by_handover(all_props)
        prop_area_map = {p.get('property_id'): p.get('area') for p in all_props if isinstance(p, dict)}
        prop_hdate_map = {p.get('property_id'): p.get('handover_date') for p in all_props if isinstance(p, dict)}
        ins_map = {i.get('inspection_id'): i for i in all_ins if isinstance(i, dict) and i.get('inspection_id')}
        tree = {}; tree_counts = {}
        
        for r in all_recs_for_tree:
            if not isinstance(r, dict): continue
            iid = r.get('inspection_id'); p_stat = r.get('progress_status')
            ins = ins_map.get(iid)
            if ins:
                p_id = ins.get('property_id')
                if t_area and prop_area_map.get(p_id) != t_area: continue
                p = ins.get('property_name', '不明'); t = ins.get('inspection_type', '不明')
                if p not in tree: tree[p] = {"types": set(), "prop_id": p_id}
                tree[p]["types"].add(t)
                
                if p not in tree_counts: tree_counts[p] = {}
                if t not in tree_counts[p]: tree_counts[p][t] = {"total": 0, "done": 0, "wait_conf": 0, "unres": 0, "wait_fix": 0}
                
                tree_counts[p][t]["total"] += 1
                if p_stat == "完了": tree_counts[p][t]["done"] += 1
                elif p_stat == "是正確認中": tree_counts[p][t]["wait_conf"] += 1; tree_counts[p][t]["unres"] += 1
                elif p_stat == "是正待ち": tree_counts[p][t]["wait_fix"] += 1; tree_counts[p][t]["unres"] += 1
                else: tree_counts[p][t]["unres"] += 1

        if search_fix: tree = {k: v for k, v in tree.items() if search_fix in k}
                
        sorted_tree_keys = []
        for p in all_props:
            p_name = p.get('property_name')
            if p_name in tree and p_name not in sorted_tree_keys: 
                sorted_tree_keys.append(p_name)
        for k in tree.keys():
            if k not in sorted_tree_keys: sorted_tree_keys.append(k)

        sel = st.session_state.drill_target
        if not isinstance(sel, dict): sel = {}
        prop_val = sel.get('prop', ''); type_val = sel.get('type', '')
        target_id_str = f"fix_{prop_val}_{type_val}" if prop_val else None
        
        if not (prop_val and type_val):
            has_visible_items = False
            for p_idx, p_name in enumerate(sorted_tree_keys):
                v_data = tree[p_name]; p_id = v_data.get("prop_id"); p_hdate = prop_hdate_map.get(p_id)
                h_disp = f" (引渡し: {p_hdate})" if p_hdate else " (引渡し未設定)"
                
                valid_types = [t for t in v_data["types"] if tree_counts.get(p_name, {}).get(t, {}).get("wait_fix", 0) > 0]
                if valid_types:
                    has_visible_items = True
                    with st.expander(f"{p_name}{h_disp}"):
                        for t_idx, t_name in enumerate(sorted(valid_types)):
                            c_data = tree_counts[p_name][t_name]
                            badge_text = f"全 {c_data['total']} 件 [ 完了：{c_data['done']}件 ／ 未完了：{c_data['unres']}件 ] ※うち是正報告待ち {c_data['wait_fix']}件"
                            t_cols = st.columns([3, 7])
                            if t_cols[0].button(t_name, key=f"f_{p_idx}_{t_idx}", use_container_width=True):
                                st.session_state.drill_target = {"prop": p_name, "type": t_name}; st.session_state.cached_records = None; st.rerun()
                            t_cols[1].markdown(f"<div class='badge-wrap' style='margin-top:15px;'><span style='color:#555;'>{badge_text}</span></div>", unsafe_allow_html=True)
            if not has_visible_items: st.info("該当する対応必要項目はありません。")
        
        if prop_val and type_val:
            if st.button("＜ 物件選択に戻る"): st.session_state.drill_target = None; st.session_state.skip_render_ids = []; st.session_state.cached_records = None; st.rerun()
            
            cb_data = {"prop": prop_val, "type": type_val}
            json_str = json.dumps(cb_data, ensure_ascii=False)
            components.html(f"<script>localStorage.setItem(\"felix_partner_session\", JSON.stringify({json_str}));</script>", height=0)

            t_ids = [str(i.get('inspection_id')) for i in all_ins if isinstance(i, dict) and i.get('property_name') == prop_val and i.get('inspection_type') == type_val and i.get('inspection_id')]
            if t_ids:
                if st.session_state.cached_records is None or st.session_state.cached_target_id != target_id_str:
                    recs = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.是正待ち")
                    st.session_state.cached_records = recs; st.session_state.cached_target_id = target_id_str
                else: recs = st.session_state.cached_records
                
                cnt_data = db_get("inspection_records", f"select=record_id&inspection_id=in.({','.join(t_ids)})")
                total_cnt = len(cnt_data); wait_cnt = len(recs)
                st.info(f"進捗： 指摘総数 {total_cnt}件 ／ 残り（是正報告待ち） {wait_cnt}件")
                
                if recs and type_val in SHANAI_KENSA_TYPES:
                    floors_in_recs = sorted(list(set([r.get('floor_level', 'one') for r in recs if r.get('floor_level')])))
                    sel_floor = st.selectbox("部屋（階層）で絞り込み", ["すべて表示"] + floors_in_recs, key="filter_partner_fix_floor")
                    if sel_floor != "すべて表示": recs = [r for r in recs if r.get('floor_level') == sel_floor]
                
                w_groups = {}
                for r in recs:
                    if not isinstance(r, dict): continue
                    rec_id = r.get('record_id')
                    if rec_id in st.session_state.skip_render_ids: continue
                    w = r.get('work_type') or 'その他'
                    if w not in w_groups: w_groups[w] = []
                    w_groups[w].append(r)
                
                for w_idx, (w_name, w_recs) in enumerate(w_groups.items()):
                    st.subheader(f"■ 工種: {w_name}")
                    for r_idx, r in enumerate(w_recs):
                        rec_id = r.get('record_id')
                        if not rec_id: continue 
                        floor = r.get('floor_level', ''); area = r.get('area', ''); detail = r.get('issue_detail', '')
                        head_text = "" if type_val.startswith("【検査機関】") or floor == "一式" else f"【{floor} {area}】".strip()
                        title = f"{head_text} {detail}" if head_text else f"【指摘内容】 {detail}"
                        
                        c_box = st.container()
                        with c_box:
                            st.markdown('<div class="record-box">', unsafe_allow_html=True)
                            st.markdown(f"**{title}**")
                            if r.get('reject_reason'): st.error(f"否認理由: {r.get('reject_reason')}")

                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown("**【指摘箇所（Before）】**")
                                if r.get('issue_photo_url'): 
                                    photo_url = r.get('issue_photo_url')
                                    st.markdown(f'<a href="{photo_url}" target="_blank"><img src="{photo_url}" style="width:250px; border-radius:4px; margin-bottom:10px;"></a>', unsafe_allow_html=True)
                                else: st.write("写真なし")
                                    
                            with c2:
                                st.markdown("**【是正写真（After）】**")
                                loc_str = f"{floor} {area} {w}".strip()
                                disp_d = detail[:80] + "..." if len(detail)>80 else detail
                                up = _smart_camera(
                                    propName=prop_val, inspType=type_val, inspDate=datetime.date.today().strftime("%Y/%m/%d"), 
                                    locationText=loc_str, issueDetail=disp_d, mode="fix", key=f"fix_cam_{rec_id}"
                                )
                                if st.button("完了報告", key=f"s_{rec_id}", type="primary"):
                                    if up: 
                                        threading.Thread(target=bg_save_correction, args=(rec_id, up)).start()
                                        st.session_state.cached_records = [item for item in st.session_state.cached_records if item.get('record_id') != rec_id]
                                        st.session_state.skip_render_ids.append(rec_id); st.rerun()
                                    else: st.error("写真が必要です")
                                if up: st.image(up, caption="プレビュー", width=250)
                            st.markdown('</div>', unsafe_allow_html=True)


    # ----------------------------------------
    # メニュー: 4-B. 是正ダッシュボード（管理者用）
    # ----------------------------------------
    elif st.session_state.active_menu == "是正ダッシュボード（管理者用）":
        st.header("是正ダッシュボード（確認・実施）")
        sel_area = st.radio("表示エリアで絞り込み", ["すべて表示", "東海エリア", "関東エリア"], horizontal=True, key="area_dash")
        t_area = sel_area if sel_area != "すべて表示" else None
        search_dash = st.text_input("物件名で検索（一部入力でも可）", key="search_dash_admin")

        all_recs_for_tree = db_get("inspection_records", "select=inspection_id,progress_status,area,floor_level,work_type,issue_detail&progress_status=in.(是正待ち,是正確認中)")
        all_ins = db_get("inspections", "select=*")
        all_props = db_get("properties", "select=*")
        all_props = sort_properties_by_handover(all_props)
        prop_area_map = {p.get('property_id'): p.get('area') for p in all_props if isinstance(p, dict)}
        prop_hdate_map = {p.get('property_id'): p.get('handover_date') for p in all_props if isinstance(p, dict)}
        
        ins_map = {i.get('inspection_id'): i for i in all_ins if isinstance(i, dict) and i.get('inspection_id')}
        tree = {}; tree_counts = {}
        
        for r in all_recs_for_tree:
            if not isinstance(r, dict): continue
            iid = r.get('inspection_id'); p_stat = r.get('progress_status')
            ins = ins_map.get(iid)
            if ins:
                p_id = ins.get('property_id')
                if t_area and prop_area_map.get(p_id) != t_area: continue
                p = ins.get('property_name', '不明'); t = ins.get('inspection_type', '不明')
                if p not in tree: tree[p] = {"types": set(), "prop_id": p_id}
                tree[p]["types"].add(t)
                
                if p not in tree_counts: tree_counts[p] = {}
                if t not in tree_counts[p]: tree_counts[p][t] = {"wait_fix": 0, "wait_conf": 0}
                
                if p_stat == "是正待ち": tree_counts[p][t]["wait_fix"] += 1
                elif p_stat == "是正確認中": tree_counts[p][t]["wait_conf"] += 1
                
        if search_dash: tree = {k: v for k, v in tree.items() if search_dash in k}

        sorted_tree_keys = []
        for p in all_props:
            p_name = p.get('property_name')
            if p_name in tree and p_name not in sorted_tree_keys: 
                sorted_tree_keys.append(p_name)
        for k in tree.keys():
            if k not in sorted_tree_keys: sorted_tree_keys.append(k)

        sel = st.session_state.drill_target
        if not isinstance(sel, dict): sel = {}
        prop_val = sel.get('prop', ''); type_val = sel.get('type', '')
        target_id_str = f"dash_{prop_val}_{type_val}" if prop_val else None
        
        if not (prop_val and type_val):
            has_visible_items = False
            for p_idx, p_name in enumerate(sorted_tree_keys):
                v_data = tree[p_name]; p_id = v_data.get("prop_id"); p_hdate = prop_hdate_map.get(p_id)
                
                # ①引渡し日数・超過日数の計算と表示 (❗️アラート用)
                h_disp = " (引渡し未設定)"
                is_overdue = False
                if p_hdate:
                    try:
                        h_date_obj = datetime.datetime.strptime(str(p_hdate), "%Y-%m-%d").date()
                        today = datetime.date.today()
                        diff = (h_date_obj - today).days
                        if diff > 0:
                            h_disp = f" (引渡し: {p_hdate} ⚠️あと{diff}日)"
                        elif diff == 0:
                            h_disp = f" (引渡し: {p_hdate} ⚠️本日引渡し！)"
                        else:
                            h_disp = f" ❗️超過{abs(diff)}日❗️"
                            is_overdue = True
                    except Exception:
                        h_disp = f" (引渡し: {p_hdate})"
                
                if v_data["types"]:
                    has_visible_items = True
                    
                    # ーー ③ 全検査分をまとめたLINE送信用テキスト作成 ーー
                    p_inspections = [i for i in all_ins if isinstance(i, dict) and i.get('property_name') == p_name]
                    p_ins_ids = [str(i.get('inspection_id')) for i in p_inspections]
                    p_recs = [r for r in all_recs_for_tree if str(r.get('inspection_id')) in p_ins_ids]
                    
                    copy_lines = [f"【物件名】 {p_name}", f"【未完了の是正総数】 {len(p_recs)}件", ""]
                    
                    recs_by_type = {}
                    for r in p_recs:
                        iid = str(r.get('inspection_id'))
                        itype = next((i.get('inspection_type') for i in p_inspections if str(i.get('inspection_id')) == iid), "不明")
                        if itype not in recs_by_type: recs_by_type[itype] = {}
                        area = r.get('area', 'その他')
                        if area not in recs_by_type[itype]: recs_by_type[itype][area] = []
                        recs_by_type[itype][area].append(r)
                        
                    for itype, a_dict in recs_by_type.items():
                        copy_lines.append(f"《 {itype} 》")
                        for a_name, a_recs in a_dict.items():
                            copy_lines.append(f"■ 部位: {a_name}")
                            for r in a_recs:
                                c_floor = r.get('floor_level', '')
                                c_w = r.get('work_type', '')
                                c_detail = r.get('issue_detail', '')
                                c_stat = r.get('progress_status')
                                stat_text = "写真待ち" if c_stat in ["is_waiting_fix", "是正待ち"] else "確認待ち"
                                head_text = "" if itype.startswith("【検査機関】") or c_floor == "一式" else f"【{c_floor} {c_w}】".strip()
                                copy_lines.append(f"{head_text} {c_detail} {stat_text}".strip())
                        copy_lines.append("")
                        
                    copy_text = "\n".join(copy_lines)
                    
                    # レイアウト（10:1で分割し、右側にメール送信ボタン）
                    col_ex1, col_ex2 = st.columns([10, 1])
                    with col_ex1:
                        with st.expander(f"{p_name}{h_disp}"):
                            # 超過している場合はExpander直下に赤文字太字で警告
                            if is_overdue:
                                st.markdown(f"<div style='color:#E74C3C; font-weight:bold; margin-bottom:15px; font-size:16px;'>🚨 引渡し日（{p_hdate}）を超過しています！至急対応してください。</div>", unsafe_allow_html=True)
                            
                            for t_idx, t_name in enumerate(sorted(list(v_data["types"]))):
                                c_data = tree_counts[p_name][t_name]
                                badge_text = f"是正写真待ち：{c_data['wait_fix']}件 ／ 管理者確認待ち：{c_data['wait_conf']}件"
                                
                                target_ins_list = [i for i in p_inspections if i.get('inspection_type') == t_name]
                                t_ins_id = target_ins_list[0].get('inspection_id') if target_ins_list else None
                                current_delay_reason = target_ins_list[0].get('delay_reason', '') if target_ins_list else ''
                                
                                t_cols = st.columns([3, 4, 3])
                                if t_cols[0].button(t_name, key=f"d_{p_idx}_{t_idx}", use_container_width=True):
                                    st.session_state.drill_target = {"prop": p_name, "type": t_name}; st.session_state.cached_records = None; st.rerun()
                                t_cols[1].markdown(f"<div class='badge-wrap' style='margin-top:15px;'><span style='color:#E74C3C; font-size: 13px;'>{badge_text}</span></div>", unsafe_allow_html=True)
                                
                                # ②遅延理由の入力と自動保存（コールバック利用）
                                if t_ins_id:
                                    def make_update_reason_cb(ins_id, key):
                                        def _update():
                                            db_patch_inspection(ins_id, {"delay_reason": st.session_state[key]})
                                            st.toast("遅延理由を保存しました")
                                        return _update
                                    
                                    cb_func = make_update_reason_cb(t_ins_id, f"delay_{t_ins_id}")
                                    t_cols[2].text_input("遅延理由", value=current_delay_reason, key=f"delay_{t_ins_id}", on_change=cb_func, label_visibility="collapsed", placeholder="遅延理由を入力してEnter")
                    
                    with col_ex2:
                        with st.popover("✉️"):
                            st.markdown("**LINE送信用テキスト**")
                            st.code(copy_text, language="text")
                            
            if not has_visible_items: st.info("現在、該当する対応必要項目はありません。")
        
        if prop_val and type_val:
            if st.button("＜ 物件選択に戻る"): st.session_state.drill_target = None; st.session_state.skip_render_ids = []; st.session_state.cached_records = None; st.rerun()
            
            t_ids = [str(i.get('inspection_id')) for i in all_ins if isinstance(i, dict) and i.get('property_name') == prop_val and i.get('inspection_type') == type_val and i.get('inspection_id')]
            if t_ids:
                if st.session_state.cached_records is None or st.session_state.cached_target_id != target_id_str:
                    recs = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=in.(是正待ち,是正確認中)")
                    st.session_state.cached_records = recs; st.session_state.cached_target_id = target_id_str
                else: recs = st.session_state.cached_records
                
                if recs and type_val in SHANAI_KENSA_TYPES:
                    floors_in_recs = sorted(list(set([r.get('floor_level', 'one') for r in recs if r.get('floor_level')])))
                    sel_floor = st.selectbox("部屋（階層）で絞り込み", ["すべて表示"] + floors_in_recs, key="filter_dash_floor")
                    if sel_floor != "すべて表示": recs = [r for r in recs if r.get('floor_level') == sel_floor]
                
                recs = sort_records(recs)
                area_groups = {}
                for r in recs:
                    if not isinstance(r, dict): continue
                    rec_id = r.get('record_id')
                    if rec_id in st.session_state.skip_render_ids: continue
                    a = r.get('area') or 'その他'
                    if a not in area_groups: area_groups[a] = []
                    area_groups[a].append(r)
                
                edit_w_opts = WORK_OPTS_KIKAN if type_val.startswith("【検査機関】") else WORK_OPTS_SHANAI if type_val in SHANAI_KENSA_TYPES else WORK_OPTS_KUTAI if type_val == "躯体検査" else WORK_OPTS_HAIKIN if type_val == "配筋検査" else WORK_OPTS_CHUKAN if type_val == "中間検査" else WORK_OPTS_DANNETSU if type_val == "断熱検査" else WORK_OPTS_STANDARD

                for a_name, a_recs in area_groups.items():
                    st.subheader(f"■ 部位: {a_name}")
                    for r_idx, r in enumerate(a_recs):
                        rec_id = r.get('record_id')
                        if not rec_id: continue 
                        floor = r.get('floor_level', ''); area = r.get('area', ''); detail = r.get('issue_detail', '')
                        w = r.get('work_type', ''); p_stat = r.get('progress_status')
                        head_text = "" if type_val.startswith("【検査機関】") or floor == "一式" else f"【{floor} {w}】".strip()
                        title = f"{head_text} {detail}" if head_text else f"【指摘内容】 {detail}"
                        
                        c_box = st.container()
                        with c_box:
                            st.markdown('<div class="record-box">', unsafe_allow_html=True)
                            
                            if p_stat == "is_waiting_fix" or p_stat == "是正待ち": st.markdown(f"**{title}** <span style='background-color:#ffeaea; color:#d93025; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:bold;'>写真待ち</span>", unsafe_allow_html=True)
                            else: st.markdown(f"**{title}** <span style='background-color:#e8f0fe; color:#1a73e8; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:bold;'>確認待ち</span>", unsafe_allow_html=True)
                            
                            if r.get('reject_reason'): st.error(f"否認理由: {r.get('reject_reason')}")
                            
                            if st.checkbox("是正内容編集", key=f"edit_chk_{rec_id}"):
                                st.markdown("#### データ編集")
                                new_detail = st.text_area("指摘内容を変更", value=detail, key=f"edit_d_{rec_id}")
                                idx_w = edit_w_opts.index(w) if w in edit_w_opts else 0
                                new_w = st.radio("工種を変更", edit_w_opts, index=idx_w, horizontal=True, key=f"edit_w_{rec_id}")
                                loc_str = f"{floor} {area}".strip()
                                disp_d = new_detail[:80] + "..." if len(new_detail)>80 else new_detail
                                new_photo = _smart_camera(propName=prop_val, inspType=type_val, inspDate=datetime.date.today().strftime("%Y/%m/%d"), locationText=loc_str, issueDetail=disp_d, mode="insp", key=f"edit_cam_{rec_id}")
                                
                                col_u, col_d = st.columns(2)
                                if col_u.button("更新を保存", key=f"edit_save_{rec_id}"):
                                    up_data = {"work_type": new_w, "issue_detail": new_detail}
                                    threading.Thread(target=bg_patch_record, args=(rec_id, new_photo, up_data)).start()
                                    st.session_state.cached_records = None; st.rerun()
                                if col_d.button("この指摘を削除", key=f"edit_del_{rec_id}"): db_delete_record(rec_id); st.session_state.cached_records = None; st.rerun()

                            c1, c2 = st.columns(2)
                            i_photo = r.get('issue_photo_url'); f_photo = r.get('fix_photo_url')
                            with c1:
                                st.markdown("**【指摘箇所（Before）】**")
                                if i_photo: st.markdown(f'<a href="{i_photo}" target="_blank"><img src="{i_photo}" style="width:250px; border-radius:4px; margin-bottom:10px;"></a>', unsafe_allow_html=True)
                                else: st.write("写真なし")
                            with c2:
                                if p_stat == "是正待ち":
                                    st.markdown("**【是正写真を撮影（After）】**")
                                    loc_str = f"{floor} {area} {w}".strip()
                                    disp_d = detail[:80] + "..." if len(detail)>80 else detail
                                    up = _smart_camera(propName=prop_val, inspType=type_val, inspDate=datetime.date.today().strftime("%Y/%m/%d"), locationText=loc_str, issueDetail=disp_d, mode="fix", key=f"fix_cam_{rec_id}")
                                    
                                    if st.button("写真を保存して完了にする", key=f"s_{rec_id}", type="primary"):
                                        if up: 
                                            fix_url = upload_to_storage(up)
                                            db_patch("inspection_records", rec_id, {"progress_status": "完了", "fix_photo_url": fix_url})
                                            st.session_state.cached_records = [item for item in st.session_state.cached_records if item.get('record_id') != rec_id]
                                            st.session_state.skip_render_ids.append(rec_id); st.rerun()
                                        else: st.error("写真をセットしてください")
                                    if up: st.image(up, width=250)
                                elif p_stat == "是正確認中":
                                    st.markdown("**【是正写真（After）】**")
                                    if f_photo: st.markdown(f'<a href="{f_photo}" target="_blank"><img src="{f_photo}" style="width:250px; border-radius:4px; margin-bottom:10px;"></a>', unsafe_allow_html=True)
                                    ca, cb = st.columns(2)
                                    if ca.button("承認（完了へ）", key=f"ok_{rec_id}", type="primary"): 
                                        db_patch("inspection_records", rec_id, {"progress_status": "完了"})
                                        st.session_state.cached_records = [item for item in st.session_state.cached_records if item.get('record_id') != rec_id]
                                        st.session_state.skip_render_ids.append(rec_id); st.rerun()
                                    reason = cb.text_input("否認理由を入力", key=f"re_{rec_id}", label_visibility="collapsed", placeholder="否認理由があれば入力")
                                    
                                    if cb.button("否認（差し戻し）", key=f"ng_{rec_id}"): 
                                        db_patch("inspection_records", rec_id, {
                                            "progress_status": "是正待ち", 
                                            "reject_reason": reason,
                                            "line_notified": False
                                        })
                                        st.session_state.cached_records = [item for item in st.session_state.cached_records if item.get('record_id') != rec_id]
                                        st.session_state.skip_render_ids.append(rec_id); st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)

                conf_recs = [r for r in recs if r.get('progress_status') == '是正確認中' and r.get('record_id') not in st.session_state.skip_render_ids]
                if conf_recs:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if not st.session_state.get("show_bulk_confirm"):
                        if st.button("写真提出済みの全項目を一括で承認する", type="primary", use_container_width=True):
                            st.session_state.show_bulk_confirm = True; st.rerun()
                    else:
                        st.error(f"最終確認： 写真提出済みの {len(conf_recs)} 件を一括で「完了」にします。本当によろしいですか？")
                        c_yes, c_no = st.columns(2)
                        if c_yes.button("はい、承認を確定します", type="primary", use_container_width=True):
                            with st.spinner("一括処理中..."):
                                for r in conf_recs:
                                    rid = r.get('record_id')
                                    if rid: db_patch("inspection_records", rid, {"progress_status": "完了"})
                            st.success("すべて承認しました"); st.session_state.show_bulk_confirm = False; st.session_state.skip_render_ids = []; st.session_state.cached_records = None; st.rerun()
                        if c_no.button("キャンセル", use_container_width=True): st.session_state.show_bulk_confirm = False; st.rerun()


    # ----------------------------------------
    # メニュー: 5. 完了分一覧
    # ----------------------------------------
    elif st.session_state.active_menu == "完了分一覧（共通）":
        sel = st.session_state.drill_target
        if not isinstance(sel, dict): sel = {}
        prop_val = sel.get('prop', ''); type_val = sel.get('type', '')
        
        if not (prop_val and type_val):
            st.header("完了分一覧")
            if st.session_state.role == "partner":
                t_area = st.session_state.target_area
            else:
                sel_area = st.radio("表示エリアで絞り込み", ["すべて表示", "東海エリア", "関東エリア"], horizontal=True, key="area_done")
                t_area = sel_area if sel_area != "すべて表示" else None
            search_done = st.text_input("物件名で検索（一部入力でも可）", key="search_done_list")

            all_recs_for_tree = db_get("inspection_records", "select=inspection_id,progress_status&progress_status=eq.完了")
            all_ins = db_get("inspections", "select=*")
            all_props = db_get("properties", "select=*")
            all_props = sort_properties_by_handover(all_props)
            prop_area_map = {p.get('property_id'): p.get('area') for p in all_props if isinstance(p, dict)}
            prop_hdate_map = {p.get('property_id'): p.get('handover_date') for p in all_props if isinstance(p, dict)}

            ins_map = {i.get('inspection_id'): i for i in all_ins if isinstance(i, dict) and i.get('inspection_id')}
            tree = {} 
            for r in all_recs_for_tree:
                if not isinstance(r, dict): continue
                iid = r.get('inspection_id')
                ins = ins_map.get(iid)
                if ins:
                    p_id = ins.get('property_id')
                    if t_area and prop_area_map.get(p_id) != t_area: continue
                    p = ins.get('property_name', '不明'); t = ins.get('inspection_type', '不明')
                    if p not in tree: tree[p] = {"types": {}, "prop_id": p_id}
                    tree[p]["types"][t] = tree[p]["types"].get(t, 0) + 1
                    
            if search_done: tree = {k: v for k, v in tree.items() if search_done in k}

            sorted_tree_keys = []
            for p in all_props:
                p_name = p.get('property_name')
                if p_name in tree and p_name not in sorted_tree_keys: 
                    sorted_tree_keys.append(p_name)
            for k in tree.keys():
                if k not in sorted_tree_keys: sorted_tree_keys.append(k)

            has_visible_items = False
            for p_idx, p_name in enumerate(sorted_tree_keys):
                v_data = tree[p_name]; p_id = v_data.get("prop_id"); p_hdate = prop_hdate_map.get(p_id)
                h_disp = f"（引渡し日: {p_hdate}）" if p_hdate else "（引渡し日: 未設定）"
                if v_data["types"]:
                    has_visible_items = True
                    with st.expander(f"{p_name} {h_disp}"):
                        for t_idx, (t_name, count) in enumerate(v_data["types"].items()):
                            if st.button(f"{t_name} (完了: {count}件)", key=f"c_{p_idx}_{t_idx}", use_container_width=True):
                                st.session_state.drill_target = {"prop": p_name, "type": t_name}; st.session_state.cached_records = None; st.rerun()
            if not has_visible_items: st.info("該当する項目はありません。")

        if prop_val and type_val:
            target_id_str = f"done_{prop_val}_{type_val}"
            
            if st.button("＜ 物件選択に戻る"): st.session_state.drill_target = None; st.session_state.skip_render_ids = []; st.session_state.cached_records = None; st.rerun()
            
            target_ins = None; t_ids = []
            all_ins = db_get("inspections", "select=*")
            for i in all_ins:
                if isinstance(i, dict) and i.get('property_name') == prop_val and i.get('inspection_type') == type_val:
                    t_ids.append(str(i.get('inspection_id')))
                    if target_ins is None: target_ins = i
                        
            ins_date_str = target_ins.get('inspection_date', '-') if target_ins else '-'
            inspector_str = target_ins.get('inspector', '-') if target_ins else '-'
            
            if t_ids:
                if st.session_state.cached_records is None or st.session_state.cached_target_id != target_id_str:
                    recs = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.完了")
                    st.session_state.cached_records = recs; st.session_state.cached_target_id = target_id_str
                else: recs = st.session_state.cached_records
                
                recs = sort_records(recs)
                total_cnt = len(recs)
                
                if st.session_state.role == "admin":
                    st.markdown(f"""<div class="admin-delete-box" style="background-color:#FFF0F0; padding:15px; border:2px solid #FF4B4B; border-radius:10px; margin-bottom:20px;">
                        <h3 style="color:#FF4B4B; margin-top:0;">完了物件の保存及び削除（管理者専用）</h3>
                        <p style="font-size:14px; color:#333;">この検査記録の保存（右上の「Print」等）が完了しましたら、システム容量を空けるためにデータを削除してください。<br><b>※一度削除した写真は元に戻せません。</b></p>
                    </div>""", unsafe_allow_html=True)
                    del_pass = st.text_input("削除用パスワードを入力 (5963)", type="password", key=f"del_pass_all")
                    if st.button(f"この検査（{type_val}）のデータを完全に削除する", key=f"del_btn_all"):
                        if del_pass == DELETE_PASSWORD:
                            for iid in t_ids:
                                requests.delete(f"{SUPABASE_URL}/rest/v1/inspection_records?inspection_id=eq.{iid}", headers=HEADERS)
                                requests.delete(f"{SUPABASE_URL}/rest/v1/inspections?inspection_id=eq.{iid}", headers=HEADERS)
                            st.success("すべてのデータの削除が完了しました"); st.session_state.drill_target = None; st.session_state.cached_records = None; st.rerun()
                        else: st.error("パスワードが違います")
                    st.markdown("<hr class='admin-delete-box'>", unsafe_allow_html=True)

                st.markdown(f"""<div style="background:white; padding:0; font-family:sans-serif; width:100%;">
                    <div style="text-align:center; margin-bottom:5px; font-size:24px; font-weight:bold;">{prop_val}</div>
                    <div style="text-align:center; margin-top:0; font-size:20px; font-weight:bold;">{type_val} 報告書</div>
                    <div style="text-align:right; font-size:12px; color:#555; margin-bottom:10px; border-bottom:2px solid #000; padding-bottom:5px;">
                        <strong>検査日:</strong> {ins_date_str} &nbsp;&nbsp; <strong>検査員:</strong> {inspector_str} &nbsp;&nbsp; <strong>完了:</strong> {total_cnt}件
                    </div></div>""", unsafe_allow_html=True)
                
                w_groups = {}
                for r in recs:
                    if not isinstance(r, dict): continue
                    w = r.get('work_type') or 'その他'
                    if w not in w_groups: w_groups[w] = []
                    w_groups[w].append(r)
                    
                issue_count = 1
                for w_name, w_recs in w_groups.items():
                    st.markdown(f"<div style='margin-top:20px; margin-bottom:10px; border-bottom:1px solid #000; font-size:16px; font-weight:bold; padding-bottom:5px;'>■ 工種: {w_name}</div>", unsafe_allow_html=True)
                    for idx, r in enumerate(w_recs):
                        rec_id = r.get('record_id')
                        if not rec_id: continue
                        floor = r.get('floor_level', ''); area = r.get('area')
                        loc_text = "" if type_val.startswith("【検査機関】") or floor == "one" or floor == "一式" else f"【{floor} {area}】"
                        detail = r.get('issue_detail', '')
                        i_photo = r.get("issue_photo_url"); f_photo = r.get("fix_photo_url")
                        no_img_html = '<div style="text-align:center; padding:30px; color:#999; border:1px solid #eee;">写真なし</div>'
                        
                        img_b = f'<a href="{i_photo}" target="_blank"><img src="{i_photo}" style="width:100%; max-height:250px; object-fit:contain; border-radius:4px;"></a>' if i_photo else no_img_html
                        img_a = f'<a href="{f_photo}" target="_blank"><img src="{f_photo}" style="width:100%; max-height:250px; object-fit:contain; border-radius:4px;"></a>' if f_photo else no_img_html
                        
                        st.markdown('<div style="page-break-inside: avoid; border-bottom: 1px dashed #ccc; padding: 15px 0; margin-bottom: 10px;">', unsafe_allow_html=True)
                        
                        col_title, col_undo = st.columns([8, 2])
                        with col_title:
                            st.markdown(f'<div style="font-size:14px; font-weight:bold; margin-top:5px;">No.{issue_count} {loc_text}</div>', unsafe_allow_html=True)
                        with col_undo:
                            if st.session_state.role == "admin":
                                if st.button("↩️ 完了取消", key=f"undo_{rec_id}_{idx}"):
                                    db_patch("inspection_records", rec_id, {"progress_status": "是正確認中"})
                                    st.session_state.cached_records = None
                                    st.success("完了を取り消し、ダッシュボードに復活させました！")
                                    time.sleep(1)
                                    st.rerun()

                        st.markdown(f"""
                            <div style="font-size:14px; margin-bottom:12px; line-height:1.4; margin-top:5px;"><strong>指摘内容：</strong> {detail}</div>
                            <table style="width:100%; table-layout:fixed; border-collapse:collapse; border:none;">
                                <tr>
                                    <td style="width:50%; text-align:center; vertical-align:top; padding-right:5px;"><div style="font-size:12px; color:#555; margin-bottom:4px;">[ Before（指摘時） ]</div>{img_b}</td>
                                    <td style="width:50%; text-align:center; vertical-align:top; padding-left:5px;"><div style="font-size:12px; color:#555; margin-bottom:4px;">[ After（是正後） ]</div>{img_a}</td>
                                </tr>
                            </table>
                        </div>
                        """, unsafe_allow_html=True)
                        issue_count += 1

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error("システムエラーが発生しました。")
        if st.button("システム復旧"): st.session_state.clear(); st.rerun()
