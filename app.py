import streamlit as st
import requests
import uuid
import datetime
import base64
import io
import re

# 画像圧縮用のライブラリ
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

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

def db_get(table, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    res = requests.get(url, headers=HEADERS)
    return res.json() if res.status_code == 200 else []

def db_post(table, data):
    requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=data)

def db_patch(table, record_id, data):
    requests.patch(f"{SUPABASE_URL}/rest/v1/{table}?record_id=eq.{record_id}", headers=HEADERS, json=data)

def db_delete_property(prop_id):
    requests.delete(f"{SUPABASE_URL}/rest/v1/inspection_records?property_id=eq.{prop_id}", headers=HEADERS)
    requests.delete(f"{SUPABASE_URL}/rest/v1/inspections?property_id=eq.{prop_id}", headers=HEADERS)
    requests.delete(f"{SUPABASE_URL}/rest/v1/properties?property_id=eq.{prop_id}", headers=HEADERS)

def process_photo(upload_file):
    if upload_file is None: return None
    if HAS_PIL:
        try:
            img = Image.open(upload_file)
            img.thumbnail((800, 800))
            img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{b64}"
        except Exception:
            pass
    b64 = base64.b64encode(upload_file.getvalue()).decode("utf-8")
    return f"data:{upload_file.type};base64,{b64}"

# ==========================================
# 2. UI設定: 印刷対応 Black Edition
# ==========================================
st.set_page_config(page_title="Felix検査App", layout="wide") # 報告書を広く見せるためwide化

st.markdown("""
<style>
    /* --- 画面用（ダークモード） --- */
    .stApp { background-color: #121212; color: #FFFFFF !important; font-family: sans-serif; }
    h1, h2, h3, h4, h5, p, span, label, .stMarkdown { color: #FFFFFF !important; }
    
    /* 報告書エリア内は、強制的にすべての文字を黒にする */
    #print-report-wrapper, #print-report-wrapper * {
        color: #000000 !important;
    }
    
    /* 【一発改善】写真アップロードエリア（写真ボタン）の白背景・黒文字化 */
    #print-report-wrapper [data-testid="stFileUploadDropzone"] {
        background-color: #FFFFFF !important; /* 背景を白に */
        border: 1px solid #000000 !important; /* 罫線を黒に */
    }
    #print-report-wrapper [data-testid="stFileUploadDropzone"] p,
    #print-report-wrapper [data-testid="stFileUploadDropzone"] small {
        color: #000000 !important; /* 文字を黒に */
    }
    
    div.stButton > button {
        background-color: #1E1E1E; color: #00E5FF !important; border: 1px solid #00E5FF;
        border-radius: 6px; height: 45px; font-weight: bold; width: 100%;
    }
    div.stButton > button:hover { background-color: #00E5FF; color: #121212 !important; }
    
    input, textarea, div[data-baseweb="select"] > div, div[data-baseweb="datepicker"] > div {
        background-color: #1E1E1E !important; color: white !important; border: 1px solid #333 !important;
    }
    
    /* カメラボタンの完全漆黒化ハック */
    [data-testid="stFileUploadDropzone"] {
        background-color: #2D2D2D !important; border: 1px solid #444 !important;
        border-radius: 8px !important; width: 100px !important; height: 100px !important;
        min-height: 100px !important; padding: 0 !important; margin: 10px 0 !important; position: relative;
    }
    [data-testid="stFileUploadDropzone"] * { opacity: 0 !important; }
    [data-testid="stFileUploadDropzone"]::before {
        content: "📷"; font-size: 40px; position: absolute; top: 50%; left: 50%;
        transform: translate(-50%, -50%); opacity: 1 !important; z-index: 10;
    }
    
    div[data-testid="stExpander"] { background-color: #1E1E1E !important; border: 1px solid #444 !important; border-radius: 8px; margin-bottom: 10px; }
    div[data-testid="stExpander"] summary { background-color: #222 !important; border-radius: 8px; }
    div[data-testid="stExpander"] summary p { color: #00E5FF !important; font-weight: bold; font-size: 1.0em; }
    
    [data-testid="stSidebar"] { background-color: #1E1E1E; border-right: 1px solid #333; }
    header, footer {visibility: hidden;}

    /* --- 印刷用（プリント時は白黒になり、表を綺麗に出力する） --- */
    @media print {
        @page { size: A4 landscape; margin: 10mm; } /* 横向き印刷で広々と */
        [data-testid="stSidebar"], header, footer, .stButton, button, .stAlert, .stInfo { display: none !important; }
        .stApp, .block-container { background-color: white !important; padding: 0 !important; max-width: 100% !important; }
        * { background: transparent !important; }
        table { width: 100%; border-collapse: collapse; font-size: 10pt; }
        th, td { border: 1px solid black !important; padding: 5px; text-align: center; vertical-align: middle; }
        th { background-color: #f0f0f0 !important; -webkit-print-color-adjust: exact; }
        tr { page-break-inside: avoid; }
        img { max-width: 150px; max-height: 150px; object-fit: contain; }
    }
</style>
""", unsafe_allow_html=True)

# --- セッションステート管理 ---
if "role" not in st.session_state: st.session_state.role = None
if "current_box" not in st.session_state: st.session_state.current_box = None
if "issue_saved" not in st.session_state: st.session_state.issue_saved = False
if "pre_selected_prop" not in st.session_state: st.session_state.pre_selected_prop = None
if "active_menu" not in st.session_state: st.session_state.active_menu = "物件登録（管理者）"
if "drill_insp_id" not in st.session_state: st.session_state.drill_insp_id = None

def jump_to_menu(menu_name, prop_id=None):
    st.session_state.active_menu = menu_name
    if prop_id: st.session_state.pre_selected_prop = prop_id
    st.session_state.drill_insp_id = None
    st.rerun()

DEF_SEL = "-- 選択してください --"
FLOOR_OPTS = [DEF_SEL, "101","102","103","201","202","203","301","302","303","共用部","外部"]
AREA_OPTS = [DEF_SEL, "LDK","洋室","SK","UB","WC","洗面","玄関","SCL"]
WORK_OPTS = [DEF_SEL, "FM","造作","内装","電気","設備","ガス","清掃","SK","サッシ","外壁","外構","コーキング","その他"]
INSP_OPTS = [DEF_SEL, "配筋検査","躯体検査","断熱検査","中間検査","社内検査(設計)","社内検査(建設)","社内検査(マーケ)","社内検査(不動産)"]

# ==========================================
# 3. アプリケーション本体
# ==========================================
def main():
    if not HAS_PIL:
        st.warning("軽量化のためターミナルで `py -m pip install pillow` を実行してください。")

    if st.session_state.role is None:
        st.markdown("<h1 style='text-align: center;'>Felix検査App</h1>", unsafe_allow_html=True)
        st.write("")
        if st.button("管理者としてログイン"):
            st.session_state.role = "admin"
            st.session_state.active_menu = "物件登録（管理者）"
            st.rerun()
        if st.button("協力業者としてログイン"):
            st.session_state.role = "partner"
            st.session_state.active_menu = "是正実施（協力業者）"
            st.rerun()
        return

    st.sidebar.markdown(f"ユーザー: {st.session_state.role}")
    if st.sidebar.button("ログアウト"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    if st.session_state.role == "admin":
        menu_options = ["物件登録（管理者）", "検査実施（管理者）", "是正実施（協力業者）", "是正確認（管理者）", "完了分一覧（共通）"]
    else:
        menu_options = ["是正実施（協力業者）", "完了分一覧（共通）"]
    
    current_index = menu_options.index(st.session_state.active_menu) if st.session_state.active_menu in menu_options else 0
    selected_menu = st.sidebar.radio("MENU", menu_options, index=current_index)

    if selected_menu != st.session_state.active_menu:
        st.session_state.active_menu = selected_menu
        st.session_state.drill_insp_id = None
        st.rerun()

    if st.session_state.active_menu != "検査実施（管理者）":
        st.session_state.current_box = None
        st.session_state.issue_saved = False

    # ヘッダーは完了分一覧のレポート表示時は消す
    if not (st.session_state.active_menu == "完了分一覧（共通）" and st.session_state.drill_insp_id is not None):
        st.header(st.session_state.active_menu)

    # ------------------------------------------
    # 1. 物件登録
    # ------------------------------------------
    if st.session_state.active_menu == "物件登録（管理者）":
        name = st.text_input("物件名", placeholder="登録する物件名を入力してください")
        if st.button("新規登録"):
            if name:
                db_post("properties", {"property_id": str(uuid.uuid4()), "property_name": name})
                st.success("物件を登録しました")
        
        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("登録済み物件一覧")
        props = db_get("properties", "select=*")
        if props:
            for p in props:
                col1, col2 = st.columns([8, 2])
                with col1:
                    if st.button(f"{p['property_name']} の検査へ進む", key=f"btn_{p['property_id']}"):
                        jump_to_menu("検査実施（管理者）", p['property_id'])
                with col2:
                    if st.button("✕ 削除", key=f"del_{p['property_id']}"):
                        db_delete_property(p['property_id'])
                        st.rerun()
        else:
            st.info("登録されている物件はありません。")

    # ------------------------------------------
    # 2. 検査実施
    # ------------------------------------------
    elif st.session_state.active_menu == "検査実施（管理者）":
        if st.session_state.current_box is None:
            props = db_get("properties", "select=*")
            if props:
                prop_opts = [{"property_id": "", "property_name": DEF_SEL}] + props
                prop_idx = 0
                if st.session_state.pre_selected_prop:
                    for i, p in enumerate(prop_opts):
                        if p['property_id'] == st.session_state.pre_selected_prop:
                            prop_idx = i
                            break
                            
                target = st.selectbox("物件を選択", prop_opts, index=prop_idx, format_func=lambda x: x['property_name'])
                ins_type = st.selectbox("検査種別", INSP_OPTS)
                ins_date = st.date_input("検査実施日", value=datetime.date.today())
                inspector = st.text_input("実施者氏名", placeholder="氏名を入力してください")
                
                if st.button("検査を開始する（詳細登録へ）"):
                    if target['property_name'] == DEF_SEL or ins_type == DEF_SEL:
                        st.error("物件と検査種別を選択してください。")
                    else:
                        new_box_id = str(uuid.uuid4())
                        db_post("inspections", {
                            "inspection_id": new_box_id, "property_id": target['property_id'], 
                            "property_name": target['property_name'], "inspection_type": ins_type,
                            "inspection_date": str(ins_date), "inspector": inspector, "status": "検査中"
                        })
                        st.session_state.current_box = {
                            "id": new_box_id, "property_id": target['property_id'], 
                            "name": f"{target['property_name']} / {ins_type}"
                        }
                        st.rerun()
            else:
                st.warning("先に物件を登録してください。")

        else:
            st.subheader(f"対象: {st.session_state.current_box['name']}")
            
            if not st.session_state.issue_saved:
                col1, col2 = st.columns(2)
                f = col1.selectbox("階層", FLOOR_OPTS)
                a = col2.selectbox("部位", AREA_OPTS)
                work = st.selectbox("工種", WORK_OPTS)
                desc = st.text_area("指摘内容", placeholder="具体的な指摘内容を入力してください")
                
                st.write("指摘箇所を撮影")
                photo = st.file_uploader("写真", type=['jpg','png','jpeg'], key="photo_in", label_visibility="collapsed")
                
                if photo is not None:
                    st.image(photo, caption="撮影された写真", use_container_width=True)
                
                if st.button("この指摘を保存"):
                    if f == DEF_SEL or a == DEF_SEL or work == DEF_SEL:
                        st.error("階層・部位・工種をすべて選択してください。")
                    else:
                        photo_data = process_photo(photo)
                        db_post("inspection_records", {
                            "record_id": str(uuid.uuid4()), "inspection_id": st.session_state.current_box['id'], 
                            "property_id": st.session_state.current_box['property_id'], 
                            "floor_level": f, "area": a, "work_type": work, "issue_detail": desc, 
                            "issue_photo_url": photo_data, "progress_status": "是正待ち"
                        })
                        st.session_state.issue_saved = True
                        st.rerun()

            else:
                st.success("指摘を保存しました。")
                st.markdown("### 続けて別の箇所を指摘しますか？")
                c1, c2 = st.columns(2)
                if c1.button("はい（続けて撮影）"):
                    st.session_state.issue_saved = False
                    st.rerun()
                if c2.button("終了（一覧へ戻る）"):
                    st.session_state.current_box = None
                    st.session_state.issue_saved = False
                    jump_to_menu("物件登録（管理者）")

    # ------------------------------------------
    # 3. 是正実施
    # ------------------------------------------
    elif st.session_state.active_menu == "是正実施（協力業者）":
        if st.session_state.drill_insp_id is None:
            st.caption("物件を選択して是正を行ってください")
            slim_recs = db_get("inspection_records", "progress_status=eq.是正待ち&select=record_id,inspection_id")
            
            if not slim_recs:
                st.info("現在、対応が必要な是正項目はありません。")
            else:
                count_map = {}
                for r in slim_recs:
                    count_map[r['inspection_id']] = count_map.get(r['inspection_id'], 0) + 1
                
                inspections = db_get("inspections", "select=*")
                for ins in inspections:
                    iid = ins['inspection_id']
                    if iid in count_map:
                        count = count_map[iid]
                        label = f"{ins.get('property_name')} / {ins.get('inspection_type')} 　[{count}件] ＞"
                        if st.button(label, key=f"drill_{iid}"):
                            st.session_state.drill_insp_id = iid
                            st.rerun()
        else:
            if st.button("＜ 物件一覧に戻る"):
                st.session_state.drill_insp_id = None
                st.rerun()
            
            inspections = db_get("inspections", "select=*")
            insp_dict = {i['inspection_id']: i for i in inspections}
            target_insp = insp_dict.get(st.session_state.drill_insp_id, {})
            prop_name = target_insp.get('property_name', '不明物件')
            insp_type = target_insp.get('inspection_type', '不明検査')

            full_recs = db_get("inspection_records", f"inspection_id=eq.{st.session_state.drill_insp_id}&progress_status=eq.是正待ち")
            st.markdown("<hr>", unsafe_allow_html=True)
            
            work_groups = {}
            for r in full_recs:
                wt = r.get('work_type', '未分類')
                if wt not in work_groups: work_groups[wt] = []
                work_groups[wt].append(r)
            
            for wt, w_recs in work_groups.items():
                st.markdown(f"<h4 style='color:#00E5FF;'>■ 工種: {wt}</h4>", unsafe_allow_html=True)
                for r in w_recs:
                    expander_title = f"{prop_name} - {insp_type} - 【{r.get('work_type', '未分類')}】 {r['floor_level']} {r['area']}"
                    with st.expander(expander_title):
                        st.write("【指摘内容】")
                        st.write(r['issue_detail'])
                        if r.get('reject_reason'): st.error(f"否認理由: {r['reject_reason']}")
                        
                        if r.get('issue_photo_url'):
                            st.image(r['issue_photo_url'], caption="直す場所（指摘写真）", use_container_width=True)
                        
                        st.write("【是正写真のアップロード】")
                        fix_photo = st.file_uploader("写真", type=['jpg','png','jpeg'], key=f"up_{r['record_id']}", label_visibility="collapsed")
                        
                        if fix_photo is not None:
                            st.image(fix_photo, caption="撮影した是正写真", use_container_width=True)
                        
                        if not st.session_state.get(f"confirm_{r['record_id']}", False):
                            if st.button("報告する", key=f"send_{r['record_id']}"):
                                st.session_state[f"confirm_{r['record_id']}"] = True
                                st.rerun()
                        else:
                            st.warning("この内容で送信してよろしいですか？")
                            c1, c2 = st.columns(2)
                            if c1.button("OK（確認へ送る）", key=f"ok_{r['record_id']}"):
                                fix_data = process_photo(fix_photo)
                                db_patch("inspection_records", r['record_id'], {
                                    "progress_status": "是正確認中",
                                    "fix_photo_url": fix_data
                                })
                                st.session_state[f"confirm_{r['record_id']}"] = False
                                st.rerun()
                            if c2.button("撮り直し", key=f"retake_{r['record_id']}"):
                                st.session_state[f"confirm_{r['record_id']}"] = False
                                st.rerun()

    # ------------------------------------------
    # 4. 是正確認
    # ------------------------------------------
    elif st.session_state.active_menu == "是正確認（管理者）":
        if st.session_state.drill_insp_id is None:
            slim_recs = db_get("inspection_records", "progress_status=eq.是正確認中&select=record_id,inspection_id")
            
            if not slim_recs: 
                st.info("確認待ちの項目はありません。")
            else:
                count_map = {}
                for r in slim_recs:
                    count_map[r['inspection_id']] = count_map.get(r['inspection_id'], 0) + 1
                
                inspections = db_get("inspections", "select=*")
                for ins in inspections:
                    iid = ins['inspection_id']
                    if iid in count_map:
                        count = count_map[iid]
                        label = f"{ins.get('property_name')} / {ins.get('inspection_type')} 　[{count}件] ＞"
                        if st.button(label, key=f"drill_conf_{iid}"):
                            st.session_state.drill_insp_id = iid
                            st.rerun()
        else:
            if st.button("＜ 物件一覧に戻る"):
                st.session_state.drill_insp_id = None
                st.rerun()
                
            inspections = db_get("inspections", "select=*")
            insp_dict = {i['inspection_id']: i for i in inspections}
            target_insp = insp_dict.get(st.session_state.drill_insp_id, {})
            prop_name = target_insp.get('property_name', '不明物件')
            insp_type = target_insp.get('inspection_type', '不明検査')

            full_recs = db_get("inspection_records", f"inspection_id=eq.{st.session_state.drill_insp_id}&progress_status=eq.是正確認中")
            st.markdown("<hr>", unsafe_allow_html=True)

            for r in full_recs:
                expander_title = f"{prop_name} - {insp_type} - 【{r.get('work_type', '未分類')}】 {r['floor_level']} {r['area']}"
                with st.expander(expander_title):
                    st.write("【指摘内容】")
                    st.write(r['issue_detail'])
                    
                    col_img1, col_img2 = st.columns(2)
                    with col_img1:
                        st.write("📷 指摘時 (Before)")
                        if r.get('issue_photo_url'): st.image(r['issue_photo_url'], use_container_width=True)
                    with col_img2:
                        st.write("📷 是正後 (After)")
                        if r.get('fix_photo_url'): st.image(r['fix_photo_url'], use_container_width=True)
                    
                    st.markdown("<hr>", unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    if c1.button("承認(完了へ)", key=f"ok_conf_{r['record_id']}"):
                        db_patch("inspection_records", r['record_id'], {"progress_status": "完了"})
                        st.rerun()
                    reason = st.text_input("否認理由を入力", key=f"re_{r['record_id']}")
                    if c2.button("否認(差し戻し)", key=f"ng_conf_{r['record_id']}"):
                        db_patch("inspection_records", r['record_id'], {"progress_status": "是正待ち", "reject_reason": reason})
                        st.rerun()

    # ------------------------------------------
    # 5. 完了分一覧 (ダイレクト全画面・表出力)
    # ------------------------------------------
    elif st.session_state.active_menu == "完了分一覧（共通）":
        if st.session_state.drill_insp_id is None:
            slim_recs = db_get("inspection_records", "progress_status=eq.完了&select=record_id,inspection_id")
            
            if not slim_recs: 
                st.info("完了したデータはありません。")
            else:
                count_map = {}
                for r in slim_recs:
                    count_map[r['inspection_id']] = count_map.get(r['inspection_id'], 0) + 1
                
                inspections = db_get("inspections", "select=*")
                for ins in inspections:
                    iid = ins['inspection_id']
                    if iid in count_map:
                        count = count_map[iid]
                        label = f"{ins.get('property_name')} / {ins.get('inspection_type')} 　[{count}件] ＞"
                        if st.button(label, key=f"drill_done_{iid}"):
                            st.session_state.drill_insp_id = iid
                            st.rerun()
        else:
            col_btn1, col_btn2 = st.columns([1, 4])
            with col_btn1:
                if st.button("＜ 戻る"):
                    st.session_state.drill_insp_id = None
                    st.rerun()
            with col_btn2:
                st.info("🖨️ PDF保存・印刷する場合はキーボードの Ctrl + P (Macは Cmd + P) を押してください。")
            
            inspections = db_get("inspections", "select=*")
            insp_dict = {i['inspection_id']: i for i in inspections}
            target_insp = insp_dict.get(st.session_state.drill_insp_id, {})
            prop_name = target_insp.get('property_name', '不明物件')
            insp_type = target_insp.get('inspection_type', '不明検査')
            insp_date = target_insp.get('inspection_date', '---')
            inspector_name = target_insp.get('inspector', '---')

            full_recs = db_get("inspection_records", f"inspection_id=eq.{st.session_state.drill_insp_id}&progress_status=eq.完了")

            # 罫線付きの美しいHTML表を構築（余計なインデントによるコード化バグを完全回避）
            html_content = f"""
            <div id="print-report-wrapper" style="background-color: #FFFFFF; padding: 20px; font-family: sans-serif; border-radius: 8px;">
                <div style="text-align: center; margin-bottom: 5px; font-size: 28px; font-weight: bold;">{prop_name}</div>
                <div style="text-align: center; margin-top: 0px; margin-bottom: 30px; font-size: 22px; font-weight: bold;">{insp_type}報告書</div>
                
                <table style="width: 100%; border-collapse: collapse; text-align: center; margin-bottom: 30px; font-size: 14px; border: 2px solid #000;">
                    <tr>
                        <th style="border: 1px solid #000; padding: 10px; background-color: #F0F0F0; width: 15%;">検査日</th>
                        <td style="border: 1px solid #000; padding: 10px; width: 35%;">{insp_date}</td>
                        <th style="border: 1px solid #000; padding: 10px; background-color: #F0F0F0; width: 15%;">検査員</th>
                        <td style="border: 1px solid #000; padding: 10px; width: 35%;">{inspector_name}</td>
                    </tr>
                </table>

                <table style="width: 100%; border-collapse: collapse; text-align: center; font-size: 12px; border: 2px solid #000;">
                    <tr style="background-color: #F0F0F0;">
                        <th style="border: 1px solid #000; padding: 10px; width: 5%;">No.</th>
                        <th style="border: 1px solid #000; padding: 10px; width: 8%;">号室</th>
                        <th style="border: 1px solid #000; padding: 10px; width: 10%;">部位</th>
                        <th style="border: 1px solid #000; padding: 10px; width: 10%;">工種</th>
                        <th style="border: 1px solid #000; padding: 10px; width: 17%;">是正前 (Before)</th>
                        <th style="border: 1px solid #000; padding: 10px; width: 28%;">課題詳細</th>
                        <th style="border: 1px solid #000; padding: 10px; width: 17%;">是正後 (After)</th>
                        <th style="border: 1px solid #000; padding: 10px; width: 5%;">確認</th>
                    </tr>
            """
            
            for idx, r in enumerate(full_recs):
                img_before = f'<img src="{r["issue_photo_url"]}" style="max-width: 100%; max-height: 150px; object-fit: contain;">' if r.get("issue_photo_url") else '写真なし'
                img_after = f'<img src="{r["fix_photo_url"]}" style="max-width: 100%; max-height: 150px; object-fit: contain;">' if r.get("fix_photo_url") else '写真なし'
                
                html_content += f"""
                    <tr>
                        <td style="border: 1px solid #000; padding: 10px;">{idx+1}</td>
                        <td style="border: 1px solid #000; padding: 10px;">{r.get('floor_level','')}</td>
                        <td style="border: 1px solid #000; padding: 10px;">{r.get('area','')}</td>
                        <td style="border: 1px solid #000; padding: 10px;">{r.get('work_type','')}</td>
                        <td style="border: 1px solid #000; padding: 10px;">{img_before}</td>
                        <td style="border: 1px solid #000; padding: 10px; text-align: left;">{r.get('issue_detail','')}</td>
                        <td style="border: 1px solid #000; padding: 10px;">{img_after}</td>
                        <td style="border: 1px solid #000; padding: 10px; font-size: 16px;">☑</td>
                    </tr>
                """
            
            html_content += """
                </table>
            </div>
            """
            
            # 生のHTMLをそのまま流し込み（グレー背景バグを完全回避）
            html_content = re.sub(r'^\s+', '', html_content, flags=re.MULTILINE)
            st.markdown(html_content, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
