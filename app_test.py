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
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict)]
            elif isinstance(data, dict):
                return [data]
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

def upload_to_storage(base64_str):
    """Base64画像を受け取り、Supabase Storageへ保存してパブリックURLを返す"""
    if not base64_str or not isinstance(base64_str, str):
        return None
    if base64_str.startswith("http://") or base64_str.startswith("https://"):
        return base64_str
        
    try:
        encoded = base64_str.split(",", 1)[1] if "," in base64_str else base64_str
        file_data = base64.b64decode(encoded)
        filename = f"{uuid.uuid4()}.jpg"
        
        url = f"{SUPABASE_URL}/storage/v1/object/photos/{filename}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "image/jpeg",
        }
        res = requests.post(url, headers=headers, data=file_data)
        
        if res.status_code in [200, 201]:
            return f"{SUPABASE_URL}/storage/v1/object/public/photos/{filename}"
        else:
            return base64_str
    except Exception:
        return base64_str

# ==========================================
# 📱 2. スマホ内・瞬間圧縮コンポーネント
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
            background-color: #FF4B4B; color: white; border-radius: 8px;
            font-size: 16px; font-weight: bold; text-align: center; cursor: pointer; 
            box-sizing: border-box; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        input[type="file"] { display: none; }
    </style>
</head>
<body>
    <label class="upload-btn" id="upload-label">
        <i class="fa-solid fa-camera" id="btn-icon"></i> <span id="btn-text">現場写真を撮影 ／ 選択</span>
        <input type="file" accept="image/*" id="file-input">
    </label>
    <script>
        function sendReady() { window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:componentReady", apiVersion: 1}, "*"); }
        function setHeight(h) { window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: h}, "*"); }
        function sendToStreamlit(val) { window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setComponentValue", value: val}, "*"); }
        window.onload = function() { sendReady(); setHeight(80); }; 

        const input = document.getElementById('file-input');
        const uploadLabel = document.getElementById('upload-label');
        const btnIcon = document.getElementById('btn-icon');
        const btnText = document.getElementById('btn-text');

        input.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) return;

            uploadLabel.style.backgroundColor = '#f39c12';
            btnIcon.className = 'fa-solid fa-spinner fa-spin';
            btnText.innerHTML = '&nbsp;高速圧縮中...';

            const reader = new FileReader();
            reader.onload = function(event) {
                const img = new Image();
                img.onload = function() {
                    const MAX_SIZE = 600; 
                    let width = img.width; let height = img.height;
                    if (width > height) {
                        if (width > MAX_SIZE) { height *= MAX_SIZE / width; width = MAX_SIZE; }
                    } else {
                        if (height > MAX_SIZE) { width *= MAX_SIZE / height; height = MAX_SIZE; }
                    }
                    const canvas = document.createElement('canvas');
                    canvas.width = width; canvas.height = height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);
                    const compressedDataUrl = canvas.toDataURL('image/jpeg', 0.5);

                    uploadLabel.style.backgroundColor = '#2ecc71';
                    btnIcon.className = 'fa-solid fa-check';
                    btnText.innerHTML = '&nbsp;セット完了';
                    sendToStreamlit(compressedDataUrl);
                };
                img.src = event.target.result;
            };
            reader.readAsDataURL(file);
        });
    </script>
</body>
</html>
"""

temp_dir = os.path.join(tempfile.gettempdir(), "fast_camera_final_v16")
os.makedirs(temp_dir, exist_ok=True)
with open(os.path.join(temp_dir, "index.html"), "w", encoding="utf-8") as f:
    f.write(CLIENT_COMPRESS_HTML)

_client_compress_func = components.declare_component("fast_camera_final_v16", path=temp_dir)

def client_compress_component(key):
    return _client_compress_func(key=key)

# ==========================================
# 3. UI設定
# ==========================================
st.set_page_config(page_title="Felix検査App", page_icon="icon.png", layout="wide")

try:
    with open("icon.png", "rb") as f:
        img_base64 = base64.b64encode(f.read()).decode()
    st.markdown(f'<link rel="apple-touch-icon" href="data:image/png;base64,{img_base64}"><link rel="shortcut icon" sizes="192x192" href="data:image/png;base64,{img_base64}"><link rel="icon" sizes="192x192" href="data:image/png;base64,{img_base64}">', unsafe_allow_html=True)
except FileNotFoundError:
    pass

st.markdown("""
<style>
    div.stButton > button { border-radius: 6px; height: 50px; font-weight: bold; width: 100%; margin-bottom: 5px; }
    footer {visibility: hidden;}
    [data-testid="stStatusWidget"] { display: none; }
    .record-box { border-bottom: 2px solid #EEEEEE; padding-bottom: 20px; margin-bottom: 20px; }
    .badge-wrap { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; font-weight: bold; margin-left: 5px; }
    @media print {
        section[data-testid="stSidebar"], header[data-testid="stHeader"] { display: none !important; }
        .stButton, [data-testid="stTextInput"], .admin-delete-box, hr { display: none !important; }
        .main .block-container { padding-top: 0 !important; margin-top: 0 !important; }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 4. 定型文データ
# ==========================================
# ★★★ ここにマスター辞書（フリー項目完備版）をそのまま貼り付けてください ★★★
ISSUE_TEMPLATES = {
    # マスターデータをここに配置してください
}
# ★★★ 辞書貼り付けエリアはここまで ★★★

# ==========================================
# 5. セッション管理 & 選択肢リスト
# ==========================================
for key in ["role", "active_menu", "pre_selected_prop", "delete_target", "skip_render_ids", "show_bulk_confirm", "edit_saved_records", "cached_records", "cached_target_id", "temp_photo"]:
    if key not in st.session_state:
        st.session_state[key] = None

if st.session_state.skip_render_ids is None: st.session_state.skip_render_ids = []
if "issue_saved" not in st.session_state: st.session_state.issue_saved = False
if "drill_target" not in st.session_state or not isinstance(st.session_state.drill_target, dict): st.session_state.drill_target = None
if "current_box" not in st.session_state or not isinstance(st.session_state.current_box, dict): st.session_state.current_box = None

qp = st.query_params
if qp.get("auth") == ADMIN_PASSWORD:
    st.session_state.role = "admin"
    st.session_state.active_menu = "検査実施（管理者）" if not st.session_state.active_menu else st.session_state.active_menu
elif qp.get("mode") == "partner":
    st.session_state.role = "partner"
    st.session_state.active_menu = "是正実施（協力業者）"

def jump_to_menu(menu_name, prop_id=None):
    st.session_state.active_menu = menu_name
    st.session_state.pre_selected_prop = prop_id
    st.session_state.drill_target = None
    st.session_state.current_box = None
    st.session_state.delete_target = None
    st.session_state.issue_saved = False
    st.session_state.skip_render_ids = []
    st.session_state.show_bulk_confirm = False
    st.session_state.edit_saved_records = False
    st.session_state.cached_records = None
    st.session_state.cached_target_id = None
    st.session_state.temp_photo = None
    st.rerun()

# --- 選択肢の定義 ---
FLOOR_OPTS = ["-- 選択 --", "101","102","103","201","202","203","301","302","303","共用部","外部"]
AREA_OPTS_STANDARD = ["-- 選択 --", "玄関", "廊下・階段・ENT", "LDK", "キッチン", "洋室", "洗面室", "UB", "トイレ", "バルコニー", "外部", "フリー項目"]
AREA_OPTS_SHANAI = ["-- 選択 --", "玄関", "トイレ", "キッチン", "LDK", "バルコニー", "洋室", "洗面室", "UB", "廊下・階段・ENT", "外部", "フリー項目"]

WORK_OPTS_STANDARD = ["-- 選択 --", "基礎工事（鉄筋）", "基礎工事（型枠）", "フレーミング", "FM", "造作", "内装", "電気", "設備", "ガス", "清掃", "サッシ", "外壁", "外構", "コーキング", "リペア", "その他"]
WORK_OPTS_HAIKIN = ["-- 選択 --", "基礎工事(鉄筋)", "水道", "ガス", "その他"]
WORK_OPTS_KUTAI = ["-- 選択 --", "フレーミング", "電気", "水道", "防水", "その他"]
WORK_OPTS_CHUKAN = ["-- 選択 --", "造作", "電気", "水道", "外壁", "ガス", "足場", "その他"]
WORK_OPTS_SHANAI = ["-- 選択 --", "A.リペア", "B.清掃", "C.クロス", "D.造作", "E.水道", "F.電気", "G.キッチン", "H.サッシ", "I.外壁", "J.外構", "K.コーキング", "L.ガス", "板金", "Z.その他"]
WORK_OPTS_KIKAN = ["基礎工事", "フレーミング", "防水", "造作", "内装", "電気", "設備", "ガス", "サッシ", "外壁", "足場", "外構", "その他"]

INSP_OPTS = [
    "-- 選択 --", 
    "配筋検査", "躯体検査", "断熱検査", "中間検査", 
    "社内検査(設計)", "社内検査(建設)", "社内検査(マーケ)", "社内検査(不動産)",
    "【検査機関】配筋検査", "【検査機関】躯体検査", "【検査機関】断熱検査", "【検査機関】中間検査", "【検査機関】完了検査"
]

SHANAI_KENSA_TYPES = ["社内検査(設計)", "社内検査(建設)", "社内検査(マーケ)", "社内検査(不動産)"]
INSPECTOR_OPTS = ["工事監理チーム", "建設部", "不動産事業部", "マーケティング部"]

# ==========================================
# 6. メイン画面・機能
# ==========================================
def main():
    if st.session_state.role is None:
        st.markdown("<h1 style='text-align: center;'>Felix検査App</h1>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["管理者", "協力業者"])
        with t1:
            pwd = st.text_input("Password", type="password")
            if st.button("管理者ログイン"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state.role = "admin"
                    st.query_params.auth = ADMIN_PASSWORD
                    st.session_state.active_menu = "物件登録（管理者）"
                    st.rerun()
                else: st.error("パスワードが違います")
        with t2:
            if st.button("協力業者としてログイン"):
                st.session_state.role = "partner"
                st.query_params.mode = "partner"
                st.session_state.active_menu = "是正実施（協力業者）"
                st.rerun()
        return

    st.sidebar.markdown(f"ユーザー: {st.session_state.role}")
    if st.sidebar.button("ログアウト"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.query_params.clear(); st.rerun()

    confirm_cnt = 0
    if st.session_state.role == "admin":
        wait_conf_recs = db_get("inspection_records", "select=record_id&progress_status=eq.確認待ち")
        confirm_cnt = len(wait_conf_recs)

    def format_menu(m):
        return f"{m} 🔴未確認{confirm_cnt}件" if m == "検査内容確認（管理者）" and confirm_cnt > 0 else m

    if st.session_state.role == "admin":
        menu_opts = ["物件登録（管理者）", "検査実施（管理者）", "検査内容確認（管理者）", "是正実施（協力業者）", "是正確認（管理者）", "完了分一覧（共通）"]
    else:
        menu_opts = ["是正実施（協力業者）", "完了分一覧（共通）"]
        
    if st.session_state.active_menu not in menu_opts: st.session_state.active_menu = menu_opts[0]
    
    selected_menu = st.sidebar.radio("MENU", menu_opts, index=menu_opts.index(st.session_state.active_menu), format_func=format_menu)
    if selected_menu != st.session_state.active_menu:
        jump_to_menu(selected_menu, st.session_state.pre_selected_prop)

    # ----------------------------------------
    # メニュー: 1. 物件登録
    # ----------------------------------------
    if st.session_state.active_menu == "物件登録（管理者）":
        st.header("物件登録")
        name = st.text_input("新規物件名")
        if st.button("登録"):
            if name:
                db_post("properties", {"property_id": str(uuid.uuid4()), "property_name": name})
                st.success("登録完了")
        
        props = db_get("properties", "select=*")
        for idx, p in enumerate(props):
            prop_id = p.get('property_id')
            if not prop_id: continue
            prop_name = p.get('property_name', '不明')
            key_suffix = f"{prop_id}_{idx}"
            
            c1, c2 = st.columns([7, 3])
            if c1.button(f"{prop_name} 検査へ", key=f"p_{key_suffix}"): jump_to_menu("検査実施（管理者）", prop_id)
            if c2.button("削除", key=f"d_{key_suffix}"): st.session_state.delete_target = prop_id; st.rerun()
                
            if st.session_state.delete_target == prop_id:
                st.warning(f"⚠️ 本当に「{prop_name}」を削除しますか？紐づくすべてのデータが消えます。")
                del_pw = st.text_input("削除用パスワードを入力", type="password", key=f"pw_{key_suffix}", placeholder="2011")
                col_y, col_n = st.columns(2)
                if col_y.button("Yes (削除実行)", key=f"yes_{key_suffix}"):
                    if del_pw == "2011":
                        db_delete_property(prop_id)
                        st.session_state.delete_target = None; st.session_state.current_box = None; st.rerun()
                    else: st.error("パスワードが違います")
                if col_n.button("No (キャンセル)", key=f"no_{key_suffix}"): st.session_state.delete_target = None; st.rerun()
                st.markdown("---")

    # ----------------------------------------
    # メニュー: 2. 検査実施
    # ----------------------------------------
    elif st.session_state.active_menu == "検査実施（管理者）":
        if not st.session_state.current_box:
            st.header("検査開始")
            props = db_get("properties", "select=*")
            opts = [{"property_id": None, "property_name": "-- 選択 --"}] + [p for p in props if p.get('property_id')]
            idx = next((i for i, p in enumerate(opts) if p.get('property_id') == st.session_state.pre_selected_prop), 0)
            
            target = st.selectbox("物件を選択", opts, index=idx, format_func=lambda x: x.get('property_name', '不明'))
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
                    st.session_state.pre_selected_prop = None; st.session_state.issue_saved = False; st.session_state.edit_saved_records = False; st.session_state.cached_records = None; st.session_state.temp_photo = None; st.rerun()
                else: st.error("物件と検査種類を選んでください")
        else:
            cb = st.session_state.current_box
            if not isinstance(cb, dict): cb = {}
            c_name = cb.get('name', ''); c_type = cb.get('type', ''); c_id = cb.get('id', ''); c_prop_id = cb.get('prop_id', ''); c_inspector = cb.get('inspector', '')
            st.subheader(f"{c_name} / {c_type}")
            
            if st.session_state.get("edit_saved_records"):
                st.markdown("#### ✏️ 今回保存した指摘データの確認・修正")
                if st.button("＜ 検査登録に戻る", key="back_top", use_container_width=True): st.session_state.edit_saved_records = False; st.rerun()
                st.markdown("---")
                
                saved_recs = db_get("inspection_records", f"inspection_id=eq.{c_id}")
                if not saved_recs: st.info("まだ保存された指摘データはありません。")
                
                edit_w_opts = WORK_OPTS_KIKAN if c_type.startswith("【検査機関】") else WORK_OPTS_SHANAI if c_type in SHANAI_KENSA_TYPES else WORK_OPTS_KUTAI if c_type == "躯体検査" else WORK_OPTS_HAIKIN if c_type == "配筋検査" else WORK_OPTS_CHUKAN if c_type == "中間検査" else WORK_OPTS_STANDARD

                for r in saved_recs:
                    rec_id = r.get('record_id')
                    if not rec_id: continue
                    floor = r.get('floor_level', ''); area = r.get('area', ''); detail = r.get('issue_detail', '')
                    head_text = "" if c_type.startswith("【検査機関】") or floor == "一式" else f"【{floor} {area}】".strip()
                    title = f"{head_text} {detail}" if head_text else f"【指摘内容】 {detail}"
                    
                    with st.container():
                        st.markdown('<div class="record-box">', unsafe_allow_html=True)
                        st.markdown(f"**{title}**")
                        if r.get('issue_photo_url'): st.image(r.get('issue_photo_url'), width=250)
                            
                        with st.expander("⚙️ 内容を修正・差し替え・削除"):
                            new_f = floor; new_a = area; sel_temp = None
                            if not c_type.startswith("【検査機関】"):
                                a_opts = AREA_OPTS_SHANAI if c_type in SHANAI_KENSA_TYPES else AREA_OPTS_STANDARD
                                if c_type not in ["配筋検査", "躯体検査", "中間検査"]:
                                    f_idx = FLOOR_OPTS[1:].index(floor) if floor in FLOOR_OPTS[1:] else 0
                                    new_f = st.radio("階層を変更", FLOOR_OPTS[1:], index=f_idx, horizontal=True, key=f"ef_{rec_id}")
                                    a_idx = a_opts[1:].index(area) if area in a_opts[1:] else 0
                                    new_a = st.radio("部位を変更", a_opts[1:], index=a_idx, horizontal=True, key=f"ea_{rec_id}")
                                
                                cat_dict = ISSUE_TEMPLATES.get(c_type, {}) if c_type in ["配筋検査", "躯体検査", "中間検査"] else ISSUE_TEMPLATES.get("社内検査(設計)", {}).get(new_a, {}) if c_type in SHANAI_KENSA_TYPES else {}
                                if not isinstance(cat_dict, dict): cat_dict = {}
                                cat_keys = list(cat_dict.keys())
                                sel_cat = st.radio("分類を変更（A列）", cat_keys, horizontal=True, key=f"ecat_{rec_id}") if cat_keys else None
                                if sel_cat: sel_temp = st.radio("よくある指摘事項（D列）", cat_dict.get(sel_cat, []), key=f"etemp_{rec_id}")
                            
                            edit_desc_val = detail.split(":", 1)[1] if ":" in detail else detail.split("：", 1)[1] if "：" in detail else detail
                            st.markdown("##### 詳細・場所の追記を変更")
                            new_detail = st.text_area("詳細情報を変更", value=edit_desc_val, label_visibility="collapsed", key=f"ed_desc_{rec_id}")
                            
                            # ★ プルダウンからボタンによる直接選択（ラジオボタン横並び仕様）へ完全修正
                            idx_w = edit_w_opts.index(r.get('work_type', '')) if r.get('work_type', '') in edit_w_opts else 0
                            new_w = st.radio("工種を変更", edit_w_opts, index=idx_w, horizontal=True, key=f"ed_work_{rec_id}")
                            
                            st.write("📷 写真を差し替える場合のみ撮影/選択してください")
                            new_photo = client_compress_component(key=f"ed_cam_{rec_id}")
                            if new_photo and isinstance(new_photo, str) and "base64," in new_photo: st.image(new_photo, caption="差し替え用プレビュー", width=200)
                                
                            c_save, c_del = st.columns(2)
                            if c_save.button("💾 この内容で上書き", key=f"ed_save_{rec_id}", type="primary"):
                                final_desc = (sel_temp + ("：" + new_detail.strip() if new_detail.strip() != "" else "")) if sel_temp else new_detail.strip()
                                if final_desc == "": final_desc = detail 
                                up_data = {"floor_level": new_f, "area": new_a, "work_type": new_w, "issue_detail": final_desc}
                                
                                if new_photo and "base64," in new_photo: 
                                    up_data["issue_photo_url"] = upload_to_storage(new_photo)
                                    
                                db_patch("inspection_records", rec_id, up_data); st.success("更新しました！"); st.rerun()
                                
                            if c_del.button("🗑️ この指摘を削除", key=f"ed_del_{rec_id}"): db_delete_record(rec_id); st.success("削除しました。"); st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                st.markdown("---")
                if st.button("＜ 検査登録に戻る", key="back_bottom", use_container_width=True): st.session_state.edit_saved_records = False; st.rerun()

            elif not st.session_state.issue_saved:
                if c_type.startswith("【検査機関】"):
                    f = "一式"; a = "全体"; sel_temp = None
                    st.markdown("##### 詳細・場所の追記（自由入力）")
                    desc = st.text_area("詳細情報を入力", label_visibility="collapsed", placeholder="具体的な指摘内容や場所を入力してください")
                    st.markdown("##### 工種を選択")
                    w = st.radio("工種を選択", WORK_OPTS_KIKAN, horizontal=True, label_visibility="collapsed")
                else:
                    f = "一式"; a = "全体"
                    area_opts = AREA_OPTS_SHANAI if c_type in SHANAI_KENSA_TYPES else AREA_OPTS_STANDARD
                    work_opts = WORK_OPTS_SHANAI if c_type in SHANAI_KENSA_TYPES else WORK_OPTS_KUTAI if c_type == "躯体検査" else WORK_OPTS_HAIKIN if c_type == "配筋検査" else WORK_OPTS_CHUKAN if c_type == "中間検査" else WORK_OPTS_STANDARD
                    
                    if c_type not in ["配筋検査", "躯体検査", "中間検査"]:
                        f = st.radio("階層を選択", FLOOR_OPTS[1:], horizontal=True)
                        a = st.radio("部位を選択", area_opts[1:], horizontal=True)
                    
                    cat_dict = ISSUE_TEMPLATES.get(c_type, {}) if c_type in ["配筋検査", "躯体検査", "中間検査"] else ISSUE_TEMPLATES.get("社内検査(設計)", {}).get(a, {}) if c_type in SHANAI_KENSA_TYPES else {}
                    if not isinstance(cat_dict, dict): cat_dict = {}
                    cat_keys = list(cat_dict.keys())
                    sel_cat = st.radio("分類を選択（A列）", cat_keys, horizontal=True) if cat_keys else None
                    sel_temp = st.radio("よくある指摘事項（D列）", cat_dict.get(sel_cat, [])) if sel_cat else None
                    
                    st.markdown("##### 詳細・場所の追記（自由入力）")
                    desc = st.text_area("詳細情報を入力", label_visibility="collapsed")
                    w = st.radio("工種を選択", work_opts[1:], horizontal=True)
                
                st.markdown("##### 現場写真の追加")
                photo_input = client_compress_component(key="insp_cam")
                if photo_input:
                    st.session_state.temp_photo = photo_input

                if st.session_state.temp_photo and isinstance(st.session_state.temp_photo, str) and "base64," in st.session_state.temp_photo:
                    st.image(st.session_state.temp_photo, use_container_width=True, caption="セット完了プレビュー")

                if st.button("この内容で保存"):
                    final_desc = (sel_temp + ("：" + desc.strip() if desc.strip() != "" else "")) if sel_temp else desc.strip()
                    active_photo = st.session_state.temp_photo
                    if w and final_desc != "" and active_photo is not None:
                        initial_status = "確認待ち" if c_inspector == "工事監理チーム" else "是正待ち"
                        saved_photo_url = upload_to_storage(active_photo)
                        
                        db_post("inspection_records", {"record_id": str(uuid.uuid4()), "inspection_id": c_id, "property_id": c_prop_id, "floor_level": f, "area": a, "work_type": w, "issue_detail": final_desc, "issue_photo_url": saved_photo_url, "progress_status": initial_status})
                        st.session_state.issue_saved = True; st.session_state.temp_photo = None; st.rerun()
                    else: st.error("工種・内容・写真はすべて必須です（写真が『セット完了』になるまでお待ちください）")
                if st.button("終了"): st.session_state.current_box = None; st.session_state.temp_photo = None; st.rerun()
            else:
                st.success("保存完了") 
                if st.button("続けて次を登録", use_container_width=True): st.session_state.issue_saved = False; st.session_state.temp_photo = None; st.rerun()
                if st.button("✏️ 保存データを確認・修正", use_container_width=True): st.session_state.edit_saved_records = True; st.rerun()
                if st.button("検査全体を終了", use_container_width=True): st.session_state.current_box = None; st.session_state.issue_saved = False; st.session_state.edit_saved_records = False; st.session_state.cached_records = None; st.session_state.temp_photo = None; st.rerun()

    # ----------------------------------------
    # メニュー: 3. 検査内容確認（管理者専用・直前修正も完全ボタン化）
    # ----------------------------------------
    elif st.session_state.active_menu == "検査内容確認（管理者）":
        st.header("検査内容確認 ＆ 最終修正")
        
        all_recs_for_tree = db_get("inspection_records", "select=inspection_id,progress_status&progress_status=eq.確認待ち")
        all_ins = db_get("inspections", "select=*")
        
        ins_map = {i.get('inspection_id'): i for i in all_ins if isinstance(i, dict) and i.get('inspection_id')}
        tree = {}
        for r in all_recs_for_tree:
            if not isinstance(r, dict): continue
            ins = ins_map.get(r.get('inspection_id'))
            if ins:
                p = ins.get('property_name', '不明'); t = ins.get('inspection_type', '不明')
                if p not in tree: tree[p] = {}
                tree[p][t] = tree[p].get(t, 0) + 1
        
        if not tree: st.info("現在、確認待ちの検査はありません。")
                
        for p_idx, (p_name, types) in enumerate(tree.items()):
            with st.expander(p_name):
                for t_idx, (t_name, count) in enumerate(types.items()):
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

                st.info(f"この検査（{prop_val} / {type_val}）には、現在 **{len(recs)}件** の確認待ちデータがあります。")
                if st.button("✅ この検査をすべて承認して業者（是正実施）に送る", type="primary"):
                    for r in recs: db_patch("inspection_records", r['record_id'], {"progress_status": "是正待ち"})
                    st.success("一括承認が完了しました！協力業者へ表示されます。"); st.session_state.drill_target = None; st.session_state.cached_records = None; st.rerun()
                st.markdown("---")
                
                edit_w_opts = WORK_OPTS_KIKAN if type_val.startswith("【検査機関】") else WORK_OPTS_SHANAI if type_val in SHANAI_KENSA_TYPES else WORK_OPTS_KUTAI if type_val == "躯体検査" else WORK_OPTS_HAIKIN if type_val == "配筋検査" else WORK_OPTS_CHUKAN if type_val == "中間検査" else WORK_OPTS_STANDARD
                edit_a_opts = AREA_OPTS_SHANAI if type_val in SHANAI_KENSA_TYPES else AREA_OPTS_STANDARD

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
                        if r.get('issue_photo_url'): st.image(r.get('issue_photo_url'), width=300)
                        
                        # --- ★ 管理者による直前修正もすべてボタン（横並びラジオボタン）仕様へ完全修正 ---
                        with st.expander("✏️ 指摘内容・写真を直前修正する"):
                            f_idx = FLOOR_OPTS[1:].index(floor) if floor in FLOOR_OPTS[1:] else 0
                            new_f = st.radio("階層", FLOOR_OPTS[1:], index=f_idx, horizontal=True, key=f"vf_{rec_id}")
                            
                            a_idx = edit_a_opts[1:].index(area) if area in edit_a_opts[1:] else 0
                            new_a = st.radio("部位", edit_a_opts[1:], index=a_idx, horizontal=True, key=f"va_{rec_id}")
                            
                            new_d = st.text_area("指摘詳細を変更", value=detail, key=f"vd_{rec_id}")
                            
                            idx_w = edit_w_opts.index(r.get('work_type', '')) if r.get('work_type', '') in edit_w_opts else 0
                            new_w = st.radio("工種を変更", edit_w_opts, index=idx_w, horizontal=True, key=f"vw_{rec_id}")
                            
                            st.write("📷 写真を差し替える場合のみ撮影/選択してください")
                            new_p = client_compress_component(key=f"vp_{rec_id}")
                            if new_p and isinstance(new_p, str) and "base64," in new_p: st.image(new_p, caption="差し替えプレビュー", width=200)
                            
                            if st.button("💾 この内容で修正保存", key=f"vsave_{rec_id}"):
                                up_data = {"floor_level": new_f, "area": new_a, "issue_detail": new_d.strip(), "work_type": new_w}
                                if new_p and "base64," in new_p: up_data["issue_photo_url"] = upload_to_storage(new_p)
                                db_patch("inspection_records", rec_id, up_data); st.session_state.cached_records = None; st.success("修正を反映しました"); st.rerun()

                        c1, c2 = st.columns(2)
                        if c1.button("✅ 個別承認（業者へ送る）", key=f"vok_{rec_id}", type="primary"):
                            db_patch("inspection_records", rec_id, {"progress_status": "是正待ち"}); st.session_state.cached_records = None; st.rerun()
                        if c2.button("🗑️ 指摘を削除", key=f"vdel_{rec_id}"):
                            db_delete_record(rec_id); st.session_state.cached_records = None; st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

    # ----------------------------------------
    # メニュー: 4. 是正実施
    # ----------------------------------------
    elif st.session_state.active_menu == "是正実施（協力業者）":
        st.header("是正実施")
        
        all_recs_for_tree = db_get("inspection_records", "select=inspection_id,progress_status")
        all_ins = db_get("inspections", "select=*")
        
        ins_map = {i.get('inspection_id'): i for i in all_ins if isinstance(i, dict) and i.get('inspection_id')}
        tree = {}; tree_counts = {}
        
        for r in all_recs_for_tree:
            if not isinstance(r, dict): continue
            iid = r.get('inspection_id'); p_stat = r.get('progress_status')
            ins = ins_map.get(iid)
            if ins:
                p = ins.get('property_name', '不明'); t = ins.get('inspection_type', '不明')
                if p not in tree: tree[p] = set(); tree_counts[p] = {}
                tree[p].add(t)
                if t not in tree_counts[p]: tree_counts[p][t] = {"total": 0, "done": 0, "wait_conf": 0, "unres": 0, "wait_fix": 0}
                
                tree_counts[p][t]["total"] += 1
                if p_stat == "完了": tree_counts[p][t]["done"] += 1
                elif p_stat == "是正確認中": tree_counts[p][t]["wait_conf"] += 1; tree_counts[p][t]["unres"] += 1
                elif p_stat == "是正待ち": tree_counts[p][t]["wait_fix"] += 1; tree_counts[p][t]["unres"] += 1
                else: tree_counts[p][t]["unres"] += 1
                
        sel = st.session_state.drill_target
        if not isinstance(sel, dict): sel = {}
        prop_val = sel.get('prop', ''); type_val = sel.get('type', '')
        target_id_str = f"fix_{prop_val}_{type_val}" if prop_val else None
        
        if not (prop_val and type_val):
            has_visible_items = False
            for p_idx, (p_name, types) in enumerate(tree.items()):
                valid_types = [t for t in types if tree_counts.get(p_name, {}).get(t, {}).get("wait_fix", 0) > 0]
                if valid_types:
                    has_visible_items = True
                    with st.expander(p_name):
                        for t_idx, t_name in enumerate(sorted(valid_types)):
                            c_data = tree_counts[p_name][t_name]
                            badge_text = f"全 {c_data['total']} 件 ･･･ [ ✅ 完了：{c_data['done']}件 ／ ⚠️ 未完了：{c_data['unres']}件 ] ※うち是正報告待ち {c_data['wait_fix']}件"
                            t_cols = st.columns([3, 7])
                            if t_cols[0].button(t_name, key=f"f_{p_idx}_{t_idx}", use_container_width=True):
                                st.session_state.drill_target = {"prop": p_name, "type": t_name}; st.session_state.cached_records = None; st.rerun()
                            t_cols[1].markdown(f"<div class='badge-wrap' style='margin-top:15px;'><span style='color:#555;'>{badge_text}</span></div>", unsafe_allow_html=True)
            if not has_visible_items: st.info("対象の項目はありません。")
        
        if prop_val and type_val:
            if st.button("＜ 物件選択に戻る"): st.session_state.drill_target = None; st.session_state.skip_render_ids = []; st.session_state.cached_records = None; st.rerun()
            
            t_ids = [str(i.get('inspection_id')) for i in all_ins if isinstance(i, dict) and i.get('property_name') == prop_val and i.get('inspection_type') == type_val and i.get('inspection_id')]
            if t_ids:
                if st.session_state.cached_records is None or st.session_state.cached_target_id != target_id_str:
                    recs = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.是正待ち")
                    st.session_state.cached_records = recs; st.session_state.cached_target_id = target_id_str
                else: recs = st.session_state.cached_records
                
                cnt_data = db_get("inspection_records", f"select=record_id&inspection_id=in.({','.join(t_ids)})")
                total_cnt = len(cnt_data); wait_cnt = len(recs)
                st.info(f"📊 **【進捗】 指摘総数：{total_cnt}件 ／ 残り（是正報告待ち）：{wait_cnt}件**")
                
                w_groups = {}
                for r in recs:
                    if not isinstance(r, dict): continue
                    rec_id = r.get('record_id')
                    if rec_id in st.session_state.skip_render_ids: continue
                    w = r.get('work_type') or 'その他'
                    if w not in w_groups: w_groups[w] = []
                    w_groups[w].append(r)
                
                edit_w_opts = WORK_OPTS_KIKAN if type_val.startswith("【検査機関】") else WORK_OPTS_SHANAI if type_val in SHANAI_KENSA_TYPES else WORK_OPTS_KUTAI if type_val == "躯体検査" else WORK_OPTS_HAIKIN if type_val == "配筋検査" else WORK_OPTS_CHUKAN if type_val == "中間検査" else WORK_OPTS_STANDARD

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
                            
                            if st.session_state.role == "admin":
                                if st.checkbox("⚙️ 是正内容編集 (管理者専用)", key=f"edit_chk_{rec_id}"):
                                    st.markdown("#### 📝 データ編集")
                                    new_detail = st.text_area("指摘内容を変更", value=detail, key=f"edit_d_{rec_id}")
                                    
                                    # ★ ここもボタン（横並びラジオボタン）による直接選択仕様へ修正
                                    idx_w = edit_w_opts.index(r.get('work_type', '')) if r.get('work_type', '') in edit_w_opts else 0
                                    new_w = st.radio("工種を変更", edit_w_opts, index=idx_w, horizontal=True, key=f"edit_w_{rec_id}")
                                    
                                    new_photo = client_compress_component(key=f"edit_cam_{rec_id}")
                                    if new_photo and isinstance(new_photo, str) and "base64," in new_photo: st.image(new_photo, caption="差し替えプレビュー", use_container_width=True)
                                    
                                    col_u, col_d = st.columns(2)
                                    if col_u.button("💾 更新を保存", key=f"edit_save_{rec_id}"):
                                        up_data = {"work_type": new_w, "issue_detail": new_detail}
                                        if new_photo and "base64," in new_photo: up_data["issue_photo_url"] = upload_to_storage(new_photo)
                                        db_patch("inspection_records", rec_id, up_data); st.session_state.cached_records = None; st.success("更新しました！"); st.rerun()
                                    if col_d.button("🗑️ この指摘を削除", key=f"edit_del_{rec_id}"): db_delete_record(rec_id); st.session_state.cached_records = None; st.rerun()
                                    st.markdown("<br>", unsafe_allow_html=True)

                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown("**【指摘箇所（Before）】**")
                                if r.get('issue_photo_url'): st.image(r.get('issue_photo_url'), use_container_width=True)
                                else: st.write("写真なし")
                                    
                            with c2:
                                st.markdown("**【是正写真（After）】**")
                                up = client_compress_component(key=f"fix_cam_{rec_id}")
                                if up and isinstance(up, str) and "base64," in up: st.image(up, caption="アップロード画像プレビュー", use_container_width=True)
                                
                                if st.button("✅ 完了報告", key=f"s_{rec_id}"):
                                    if up and "base64," in up: 
                                        fix_url = upload_to_storage(up)
                                        db_patch("inspection_records", rec_id, {"progress_status": "是正確認中", "fix_photo_url": fix_url})
                                        st.session_state.cached_records = [item for item in st.session_state.cached_records if item.get('record_id') != rec_id]
                                        st.session_state.skip_render_ids.append(rec_id); st.rerun()
                                    else: st.error("写真が必要です（準備完了するまでお待ちください）")
                            st.markdown('</div>', unsafe_allow_html=True)

    # ----------------------------------------
    # メニュー: 5. 是正確認 / 6. 完了分一覧
    # ----------------------------------------
    elif st.session_state.active_menu in ["是正確認（管理者）", "完了分一覧（共通）"]:
        status = "是正確認中" if "確認" in st.session_state.active_menu else "完了"
        
        all_recs_for_tree = db_get("inspection_records", "select=inspection_id,progress_status")
        all_ins = db_get("inspections", "select=*")
        
        ins_map = {i.get('inspection_id'): i for i in all_ins if isinstance(i, dict) and i.get('inspection_id')}
        tree = {}; tree_counts = {} 
        
        for r in all_recs_for_tree:
            if not isinstance(r, dict): continue
            iid = r.get('inspection_id'); p_stat = r.get('progress_status')
            ins = ins_map.get(iid)
            if ins:
                p = ins.get('property_name', '不明'); t = ins.get('inspection_type', '不明')
                if p not in tree: tree[p] = set(); tree_counts[p] = {}
                tree[p].add(t)
                if t not in tree_counts[p]: tree_counts[p][t] = {"total": 0, "done": 0, "wait_conf": 0, "unres": 0}
                
                tree_counts[p][t]["total"] += 1
                if p_stat == "完了": tree_counts[p][t]["done"] += 1
                elif p_stat == "是正確認中": tree_counts[p][t]["wait_conf"] += 1; tree_counts[p][t]["unres"] += 1
                else: tree_counts[p][t]["unres"] += 1

        sel = st.session_state.drill_target
        if not isinstance(sel, dict): sel = {}
        prop_val = sel.get('prop', ''); type_val = sel.get('type', '')
        target_id_str = f"conf_{prop_val}_{type_val}_{status}" if prop_val else None

        if not (prop_val and type_val):
            st.header(st.session_state.active_menu)
            has_visible_items = False
            for p_idx, (p_name, types) in enumerate(tree.items()):
                valid_types = []
                for t_name in types:
                    c_data = tree_counts.get(p_name, {}).get(t_name, {})
                    if status == "是正確認中" and c_data.get("wait_conf", 0) > 0: valid_types.append(t_name)
                    elif status == "完了" and c_data.get("done", 0) > 0: valid_types.append(t_name)
                
                if valid_types:
                    has_visible_items = True
                    with st.expander(p_name):
                        for t_idx, t_name in enumerate(sorted(valid_types)):
                            c_data = tree_counts[p_name][t_name]
                            badge_text = f"全 {c_data['total']} 件 ･･･ [ ✅ 完了：{c_data['done']}件 ／ ⚠️ 未完了：{c_data['unres']}件 ] ※うち確認待ち {c_data['wait_conf']}件"
                            t_cols = st.columns([3, 7])
                            if t_cols[0].button(t_name, key=f"c_{p_idx}_{t_idx}", use_container_width=True):
                                st.session_state.drill_target = {"prop": p_name, "type": t_name}; st.session_state.cached_records = None; st.rerun()
                            t_cols[1].markdown(f"<div class='badge-wrap' style='margin-top:15px;'><span style='color:#555;'>{badge_text}</span></div>", unsafe_allow_html=True)
            if not has_visible_items: st.info("対象の項目はありません。")

        if prop_val and type_val:
            if st.button("＜ 物件選択に戻る"): st.session_state.drill_target = None; st.session_state.skip_render_ids = []; st.session_state.cached_records = None; st.rerun()
            
            target_ins = None; t_ids = []
            for i in all_ins:
                if isinstance(i, dict) and i.get('property_name') == prop_val and i.get('inspection_type') == type_val:
                    t_ids.append(str(i.get('inspection_id')))
                    if target_ins is None: target_ins = i
                        
            ins_date_str = target_ins.get('inspection_date', '-') if target_ins else '-'
            inspector_str = target_ins.get('inspector', '-') if target_ins else '-'
            
            if t_ids:
                if st.session_state.cached_records is None or st.session_state.cached_target_id != target_id_str:
                    recs = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.{status}")
                    st.session_state.cached_records = recs; st.session_state.cached_target_id = target_id_str
                else: recs = st.session_state.cached_records
                
                stats_data = db_get("inspection_records", f"select=record_id,progress_status&inspection_id=in.({','.join(t_ids)})")
                total_cnt = len(stats_data)
                comp_cnt = len([r for r in stats_data if r.get('progress_status') == '完了'])
                unres_cnt = total_cnt - comp_cnt
                report_title = type_val

                if status == "完了":
                    if st.session_state.role == "admin":
                        st.markdown(f"""<div class="admin-delete-box" style="background-color:#FFF0F0; padding:15px; border:2px solid #FF4B4B; border-radius:10px; margin-bottom:20px;">
                            <h3 style="color:#FF4B4B; margin-top:0;">📋 完了物件の保存及び削除（管理者専用）</h3>
                            <p style="font-size:14px; color:#333;">この検査記録の保存（PDF化や印刷）が完了しましたら、システム容量を空けるためにデータを削除してください。<br><b>※一度削除した写真は元に戻せません。</b></p>
                        </div>""", unsafe_allow_html=True)
                        del_pass = st.text_input("削除用パスワードを入力 (5963)", type="password", key=f"del_pass_all")
                        if st.button(f"🚨 この検査（{type_val}）のデータを完全に削除する", key=f"del_btn_all"):
                            if del_pass == DELETE_PASSWORD:
                                for iid in t_ids:
                                    requests.delete(f"{SUPABASE_URL}/rest/v1/inspection_records?inspection_id=eq.{iid}", headers=HEADERS)
                                    requests.delete(f"{SUPABASE_URL}/rest/v1/inspections?inspection_id=eq.{iid}", headers=HEADERS)
                                st.success("すべてのデータの削除が完了しました！"); st.session_state.drill_target = None; st.session_state.cached_records = None; st.rerun()
                            else: st.error("パスワードが違います")
                        st.markdown("<hr class='admin-delete-box'>", unsafe_allow_html=True)

                    st.markdown(f"""<div style="background:white; padding:0; font-family:sans-serif; width:100%;">
                        <div style="text-align:center; margin-bottom:5px; font-size:24px; font-weight:bold;">{prop_val}</div>
                        <div style="text-align:center; margin-top:0; font-size:20px; font-weight:bold;">{report_title} 報告書</div>
                        <div style="text-align:right; font-size:12px; color:#555; margin-bottom:10px; border-bottom:2px solid #000; padding-bottom:5px;">
                            <strong>検査日:</strong> {ins_date_str} &nbsp;&nbsp; <strong>検査員:</strong> {inspector_str} &nbsp;&nbsp; <strong>指摘総数:</strong> {total_cnt}件
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
                            floor = r.get('floor_level', ''); area = r.get('area', '')
                            loc_text = "" if type_val.startswith("【検査機関】") or floor == "一式" else f"【{floor} {area}】"
                            detail = r.get('issue_detail', '')
                            i_photo = r.get("issue_photo_url"); f_photo = r.get("fix_photo_url")
                            no_img_html = '<div style="text-align:center; padding:30px; color:#999; border:1px solid #eee;">写真なし</div>'
                            img_b = f'<img src="{i_photo}" style="width:100%; max-height:250px; object-fit:contain; border-radius:4px;">' if i_photo else no_img_html
                            img_a = f'<img src="{f_photo}" style="width:100%; max-height:250px; object-fit:contain; border-radius:4px;">' if f_photo else no_img_html
                            
                            st.markdown(f"""
                            <div style="page-break-inside: avoid; border-bottom: 1px dashed #ccc; padding: 15px 0; margin-bottom: 10px;">
                                <div style="font-size:14px; font-weight:bold; margin-bottom:5px;">No.{issue_count} {loc_text}</div>
                                <div style="font-size:14px; margin-bottom:12px; line-height:1.4;"><strong>指摘内容：</strong> {detail}</div>
                                <table style="width:100%; table-layout:fixed; border-collapse:collapse; border:none;">
                                    <tr>
                                        <td style="width:50%; text-align:center; vertical-align:top; padding-right:5px;"><div style="font-size:12px; color:#555; margin-bottom:4px;">[ Before（指摘時） ]</div>{img_b}</td>
                                        <td style="width:50%; text-align:center; vertical-align:top; padding-left:5px;"><div style="font-size:12px; color:#555; margin-bottom:4px;">[ After（是正後） ]</div>{img_a}</td>
                                    </tr>
                                </table>
                            </div>
                            """, unsafe_allow_html=True)
                            issue_count += 1
                else:
                    conf_cnt = len(recs)
                    st.info(f"📊 **【進捗】 全 {total_cnt} 件 ･･･ [ ✅ 完了：{comp_cnt}件 ／ ⚠️ 未完了：{unres_cnt}件 ]** \n※うち、現在確認待ちが **{conf_cnt}件** あります。")
                    st.markdown(f"<h3 style='margin-top:0;'>📋 {report_title}</h3>", unsafe_allow_html=True)
                    
                    w_groups = {}
                    for r in recs:
                        if not isinstance(r, dict): continue
                        rec_id = r.get('record_id')
                        if rec_id in st.session_state.skip_render_ids: continue
                        w = r.get('work_type') or 'その他'
                        if w not in w_groups: w_groups[w] = []
                        w_groups[w].append(r)
                    
                    for w_name, w_recs in w_groups.items():
                        st.subheader(f"■ 工種: {w_name}")
                        for r_idx, r in enumerate(w_recs):
                            rec_id = r.get('record_id')
                            if not rec_id: continue
                            floor = r.get('floor_level', ''); area = r.get('area', ''); detail = r.get('issue_detail', '')
                            head_text = "" if type_val.startswith("【検査機関】") or floor == "一式" else f"【{floor} {area}】".strip()
                            title = f"{head_text} {detail}" if head_text else f"【指摘内容】 {detail}"
                            
                            c_box = st.container()
                            with c_box:
                                st.markdown(f"**{title}**")
                                c1, c2 = st.columns(2)
                                i_photo = r.get('issue_photo_url'); f_photo = r.get('fix_photo_url')
                                if i_photo: c1.image(i_photo, caption="Before")
                                if f_photo: c2.image(f_photo, caption="After")
                                
                                ca, cb = st.columns(2)
                                if ca.button("✅ 承認（完了へ）", key=f"ok_{rec_id}"): 
                                    db_patch("inspection_records", rec_id, {"progress_status": "完了"})
                                    st.session_state.cached_records = [item for item in st.session_state.cached_records if item.get('record_id') != rec_id]
                                    st.session_state.skip_render_ids.append(rec_id); st.rerun()
                                
                                reason = cb.text_input("否認理由を入力", key=f"re_{rec_id}", label_visibility="collapsed", placeholder="否認理由があれば入力")
                                if cb.button("❌ 否認（差し戻し）", key=f"ng_{rec_id}"): 
                                    db_patch("inspection_records", rec_id, {"progress_status": "是正待ち", "reject_reason": reason})
                                    st.session_state.cached_records = [item for item in st.session_state.cached_records if item.get('record_id') != rec_id]
                                    st.session_state.skip_render_ids.append(rec_id); st.rerun()
                                st.markdown("---") 
                    
                    if recs:
                        st.markdown("<br><br>", unsafe_allow_html=True)
                        if not st.session_state.get("show_bulk_confirm"):
                            if st.button("🚀 表示中の全項目を一括で承認する", type="primary", use_container_width=True):
                                st.session_state.show_bulk_confirm = True; st.rerun()
                        else:
                            st.error("⚠️ **【最終確認】** 表示中の全項目を一括で「完了」にします。本当によろしいですか？")
                            c_yes, c_no = st.columns(2)
                            if c_yes.button("✅ はい、承認を確定します", type="primary", use_container_width=True):
                                with st.spinner("一括処理中..."):
                                    for r in recs:
                                        rid = r.get('record_id')
                                        if rid: db_patch("inspection_records", rid, {"progress_status": "完了"})
                                st.success("🎉 すべて承認しました！")
                                st.session_state.show_bulk_confirm = False
                                st.session_state.skip_render_ids = [] 
                                st.session_state.cached_records = [] 
                                st.rerun()
                                
                            if c_no.button("キャンセル", use_container_width=True):
                                st.session_state.show_bulk_confirm = False; st.rerun()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error("システムエラーが発生しました。")
        if st.button("システム復旧"): st.session_state.clear(); st.rerun()
