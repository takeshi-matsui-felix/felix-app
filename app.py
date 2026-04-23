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
    try:
        from PIL import Image
        img = Image.open(upload_file)
        img.thumbnail((800, 800))
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
    except:
        return f"data:image/jpeg;base64,{base64.b64encode(upload_file.getvalue()).decode('utf-8')}"

# ==========================================
# 2. UI設定 (漆黒テーマ・ヘッダー修正)
# ==========================================
st.set_page_config(page_title="Felix検査App", layout="wide")

st.markdown("""
<style>
    /* 全体背景 */
    .stApp { background-color: #121212; color: #FFFFFF !important; font-family: sans-serif; }
    
    /* 上部バー（ヘッダー）を黒に強制 */
    header[data-testid="stHeader"] { background-color: #121212 !important; }
    [data-testid="stHeader"] * { color: #FFFFFF !important; }

    /* サイドバー */
    [data-testid="stSidebar"] { background-color: #121212 !important; border-right: 1px solid #333; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    /* ボタン */
    div.stButton > button {
        background-color: #1E1E1E; color: #00E5FF !important; border: 1px solid #00E5FF;
        border-radius: 6px; height: 50px; font-weight: bold; width: 100%; margin-bottom: 5px;
    }
    
    /* カメラボタンの視認性 */
    [data-testid="stFileUploadDropzone"] {
        background-color: #262730 !important; border: 2px dashed #555 !important; border-radius: 10px !important;
    }
    [data-testid="stFileUploadDropzone"] p, [data-testid="stFileUploadDropzone"] span {
        color: #FFFFFF !important; font-weight: bold !important;
    }
    
    /* 折り畳み枠（Expander） */
    div[data-testid="stExpander"] { background-color: #1E1E1E !important; border: 1px solid #444 !important; }
    
    /* 報告書エリア内の文字色を黒に固定 */
    #print-report-wrapper, #print-report-wrapper * { color: #000000 !important; }
    
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- セッションステート管理 ---
if "role" not in st.session_state: st.session_state.role = None
if "current_box" not in st.session_state: st.session_state.current_box = None
if "active_menu" not in st.session_state: st.session_state.active_menu = "物件登録（管理者）"
if "drill_target" not in st.session_state: st.session_state.drill_target = None
if "pre_selected_prop" not in st.session_state: st.session_state.pre_selected_prop = None

def jump_to_menu(menu_name, prop_id=None):
    st.session_state.active_menu = menu_name
    st.session_state.drill_target = None
    if prop_id: 
        st.session_state.pre_selected_prop = prop_id
    st.rerun()

FLOOR_OPTS = ["-- 選択 --", "101","102","103","201","202","203","301","302","303","共用部","外部"]
AREA_OPTS = ["-- 選択 --", "LDK","洋室","SK","UB","WC","洗面","玄関","SCL"]
WORK_OPTS = ["-- 選択 --", "FM","造作","内装","電気","設備","ガス","清掃","SK","サッシ","外壁","外構","コーキング","その他"]
INSP_OPTS = ["-- 選択 --", "配筋検査","躯体検査","断熱検査","中間検査","社内検査(設計)","社内検査(建設)","社内検査(マーケ)","社内検査(不動産)"]

# ==========================================
# 3. アプリケーション本体
# ==========================================
def main():
    if st.session_state.role is None:
        st.markdown("<h1 style='text-align: center;'>Felix検査App</h1>", unsafe_allow_html=True)
        if st.button("管理者としてログイン"): st.session_state.role = "admin"; st.rerun()
        if st.button("協力業者としてログイン"): st.session_state.role = "partner"; st.session_state.active_menu = "是正実施（協力業者）"; st.rerun()
        return

    st.sidebar.markdown(f"ユーザー: {st.session_state.role}")
    if st.sidebar.button("ログアウト"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    menu_opts = ["物件登録（管理者）", "検査実施（管理者）", "是正実施（協力業者）", "是正確認（管理者）", "完了分一覧（共通）"] if st.session_state.role == "admin" else ["是正実施（協力業者）", "完了分一覧（共通）"]
    selected_menu = st.sidebar.radio("機能メニュー", menu_opts, index=menu_opts.index(st.session_state.active_menu) if st.session_state.active_menu in menu_opts else 0)

    if selected_menu != st.session_state.active_menu:
        st.session_state.active_menu = selected_menu; st.session_state.drill_target = None; st.rerun()

    # ------------------------------------------
    # 1. 物件登録
    # ------------------------------------------
    if st.session_state.active_menu == "物件登録（管理者）":
        st.header("物件登録")
        name = st.text_input("新規物件名")
        if st.button("登録する"):
            if name: db_post("properties", {"property_id": str(uuid.uuid4()), "property_name": name}); st.success("登録完了")
        
        st.markdown("<hr>", unsafe_allow_html=True)
        props = db_get("properties", "select=*")
        for p in props:
            c1, c2 = st.columns([8, 2])
            if c1.button(f"{p['property_name']} 検査へ", key=f"p_{p['property_id']}"): jump_to_menu("検査実施（管理者）", p['property_id'])
            if c2.button("✕", key=f"d_{p['property_id']}"): db_delete_property(p['property_id']); st.rerun()

    # ------------------------------------------
    # 2. 検査実施
    # ------------------------------------------
    elif st.session_state.active_menu == "検査実施（管理者）":
        st.header("検査実施")
        if st.session_state.current_box is None:
            props = db_get("properties", "select=*")
            
            # 物件の初期選択位置を計算
            prop_idx = 0
            if st.session_state.pre_selected_prop:
                for i, p in enumerate(props):
                    if p['property_id'] == st.session_state.pre_selected_prop:
                        prop_idx = i
                        break
            
            target = st.selectbox("物件を選択", props, index=prop_idx, format_func=lambda x: x['property_name'])
            ins_type = st.selectbox("検査種類", INSP_OPTS)
            if st.button("検査スタート"):
                if target and ins_type != "-- 選択 --":
                    nid = str(uuid.uuid4())
                    db_post("inspections", {"inspection_id": nid, "property_id": target['property_id'], "property_name": target['property_name'], "inspection_type": ins_type, "inspection_date": str(datetime.date.today()), "inspector": "管理者"})
                    st.session_state.current_box = {"id": nid, "prop_id": target['property_id'], "name": target['property_name'], "type": ins_type}
                    st.rerun()
        else:
            st.subheader(f"{st.session_state.current_box['name']} / {st.session_state.current_box['type']}")
            col1, col2 = st.columns(2)
            f = col1.selectbox("階層", FLOOR_OPTS)
            a = col2.selectbox("部位", AREA_OPTS)
            w = st.selectbox("工種", WORK_OPTS)
            desc = st.text_area("指摘内容")
            
            photo = st.file_uploader("指摘箇所を撮影", type=['jpg','png','jpeg'])
            if photo: st.image(photo, caption="プレビュー")
            
            if st.button("この指摘を保存"):
                if f != "-- 選択 --" and a != "-- 選択 --" and w != "-- 選択 --":
                    db_post("inspection_records", {"record_id": str(uuid.uuid4()), "inspection_id": st.session_state.current_box['id'], "property_id": st.session_state.current_box['prop_id'], "floor_level": f, "area": a, "work_type": w, "issue_detail": desc, "issue_photo_url": process_photo(photo), "progress_status": "是正待ち"})
                    st.success("保存完了")
                else:
                    st.error("階層・部位・工種を選択してください。")
            
            if st.button("検査を終了する"): st.session_state.current_box = None; st.rerun()

    # ------------------------------------------
    # 3. 是正実施 (工種別グルーピング・写真ボタン完全復旧)
    # ------------------------------------------
    elif st.session_state.active_menu == "是正実施（協力業者）":
        st.header("是正実施")
        if st.session_state.drill_target is None:
            all_recs = db_get("inspection_records", "progress_status=eq.是正待ち")
            all_ins = db_get("inspections", "select=*")
            ins_map = {i['inspection_id']: i for i in all_ins}
            
            groups = {}
            for r in all_recs:
                ins = ins_map.get(r['inspection_id'])
                if ins:
                    key = (ins['property_name'], ins['inspection_type'])
                    groups[key] = groups.get(key, 0) + 1
            
            if not groups: st.info("現在、対応が必要な是正項目はありません。")
            for (p_name, i_type), count in groups.items():
                if st.button(f"{p_name} / {i_type} ({count}件)", key=f"f_{p_name}_{i_type}"):
                    st.session_state.drill_target = {"prop": p_name, "type": i_type}; st.rerun()
        else:
            if st.button("＜ 戻る"): st.session_state.drill_target = None; st.rerun()
            sel = st.session_state.drill_target
            t_ids = [i['inspection_id'] for i in db_get("inspections", f"property_name=eq.{sel['prop']}&inspection_type=eq.{sel['type']}")]
            recs = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.是正待ち")
            
            w_groups = {}
            for r in recs:
                w = r.get('work_type', 'その他')
                if w not in w_groups: w_groups[w] = []
                w_groups[w].append(r)
            
            for w_name, w_recs in w_groups.items():
                st.subheader(f"■ 工種: {w_name}")
                for r in w_recs:
                    with st.expander(f"{r.get('floor_level')} {r.get('area')} - {r.get('issue_detail','')[:10]}..."):
                        if r.get('reject_reason'): st.error(f"否認理由: {r['reject_reason']}")
                        st.write("【指摘内容】", r.get('issue_detail',''))
                        if r.get('issue_photo_url'): st.image(r['issue_photo_url'], caption="指摘時")
                        
                        up = st.file_uploader("是正写真をアップロード", type=['jpg','png','jpeg'], key=f"up_{r['record_id']}")
                        if up: st.image(up, caption="プレビュー")
                        if st.button("報告する", key=f"s_{r['record_id']}"):
                            db_patch("inspection_records", r['record_id'], {"progress_status": "是正確認中", "fix_photo_url": process_photo(up)})
                            st.rerun()

    # ------------------------------------------
    # 4. 是正確認 (工種別グルーピング完全復旧)
    # ------------------------------------------
    elif st.session_state.active_menu == "是正確認（管理者）":
        st.header("是正確認")
        if st.session_state.drill_target is None:
            all_recs = db_get("inspection_records", "progress_status=eq.是正確認中")
            all_ins = db_get("inspections", "select=*")
            ins_map = {i['inspection_id']: i for i in all_ins}
            
            groups = {}
            for r in all_recs:
                ins = ins_map.get(r['inspection_id'])
                if ins:
                    key = (ins['property_name'], ins['inspection_type'])
                    groups[key] = groups.get(key, 0) + 1
            
            if not groups: st.info("確認待ちの項目はありません。")
            for (p_name, i_type), count in groups.items():
                if st.button(f"{p_name} / {i_type} ({count}件)", key=f"c_{p_name}_{i_type}"):
                    st.session_state.drill_target = {"prop": p_name, "type": i_type}; st.rerun()
        else:
            if st.button("＜ 戻る"): st.session_state.drill_target = None; st.rerun()
            sel = st.session_state.drill_target
            t_ids = [i['inspection_id'] for i in db_get("inspections", f"property_name=eq.{sel['prop']}&inspection_type=eq.{sel['type']}")]
            recs = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.是正確認中")
            
            w_groups = {}
            for r in recs:
                w = r.get('work_type', 'その他')
                if w not in w_groups: w_groups[w] = []
                w_groups[w].append(r)
            
            for w_name, w_recs in w_groups.items():
                st.subheader(f"■ 工種: {w_name}")
                for r in w_recs:
                    with st.expander(f"{r.get('floor_level')} {r.get('area')} - {r.get('issue_detail','')[:10]}..."):
                        st.write("【指摘内容】", r.get('issue_detail',''))
                        c1, c2 = st.columns(2)
                        if r.get('issue_photo_url'): c1.image(r['issue_photo_url'], caption="Before")
                        if r.get('fix_photo_url'): c2.image(r['fix_photo_url'], caption="After")
                        
                        if st.button("承認（完了へ）", key=f"ok_{r['record_id']}"): 
                            db_patch("inspection_records", r['record_id'], {"progress_status": "完了"})
                            st.rerun()
                        reason = st.text_input("否認理由", key=f"re_{r['record_id']}")
                        if st.button("否認（差し戻し）", key=f"ng_{r['record_id']}"): 
                            db_patch("inspection_records", r['record_id'], {"progress_status": "是正待ち", "reject_reason": reason})
                            st.rerun()

    # ------------------------------------------
    # 5. 完了分一覧 (絶対統合 + 工種別整理 + アイコン排除)
    # ------------------------------------------
    elif st.session_state.active_menu == "完了分一覧（共通）":
        if st.session_state.drill_target is None:
            st.header("完了報告書")
            all_recs = db_get("inspection_records", "progress_status=eq.完了")
            all_ins = db_get("inspections", "select=*")
            ins_map = {i['inspection_id']: i for i in all_ins}
            
            tree = {}
            for r in all_recs:
                ins = ins_map.get(r['inspection_id'])
                if ins:
                    p = ins['property_name']
                    if p not in tree: tree[p] = set()
                    tree[p].add(ins['inspection_type'])
            
            if not tree: st.info("完了した報告書はありません。")
            for p_name, types in tree.items():
                with st.expander(p_name):
                    for t_name in sorted(list(types)):
                        if st.button(t_name, key=f"d_{p_name}_{t_name}"):
                            st.session_state.drill_target = {"prop": p_name, "type": t_name}; st.rerun()
        else:
            if st.button("＜ 戻る"): st.session_state.drill_target = None; st.rerun()
            sel = st.session_state.drill_target
            
            t_ids = [i['inspection_id'] for i in db_get("inspections", f"property_name=eq.{sel['prop']}&inspection_type=eq.{sel['type']}")]
            recs = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.完了")
            
            html = f"""<div id="print-report-wrapper" style="background:white; padding:20px; border-radius:8px; font-family:sans-serif;">
                <h2 style="text-align:center; margin-bottom:5px;">{sel['prop']}</h2><h3 style="text-align:center; margin-top:0;">{sel['type']}報告書</h3>"""
            
            w_groups = {}
            for r in recs:
                w = r.get('work_type', 'その他')
                if w not in w_groups: w_groups[w] = []
                w_groups[w].append(r)
                
            for w_name, w_recs in w_groups.items():
                html += f"<h4 style='margin-top:20px; border-bottom:1px solid #000;'>工種: {w_name}</h4>"
                html += """<table style="width:100%; border-collapse:collapse; border:2px solid black; font-size:12px; text-align:center; margin-bottom:20px;">
                    <tr style="background:#eee;"><th style="border:1px solid black; padding:8px; width:5%;">No</th><th style="border:1px solid black; padding:8px; width:15%;">場所</th><th style="border:1px solid black; padding:8px; width:25%;">Before</th><th style="border:1px solid black; padding:8px; width:30%;">詳細</th><th style="border:1px solid black; padding:8px; width:25%;">After</th></tr>"""
                for idx, r in enumerate(w_recs):
                    img_b = f'<img src="{r.get("issue_photo_url")}" style="width:100%; max-width:150px;">' if r.get("issue_photo_url") else ""
                    img_a = f'<img src="{r.get("fix_photo_url")}" style="width:100%; max-width:150px;">' if r.get("fix_photo_url") else ""
                    html += f"""<tr><td style="border:1px solid black; padding:8px;">{idx+1}</td><td style="border:1px solid black; padding:8px;">{r.get('floor_level','')}<br>{r.get('area','')}</td><td style="border:1px solid black; padding:8px;">{img_b}</td><td style="border:1px solid black; padding:8px; text-align:left;">{r.get('issue_detail','')}</td><td style="border:1px solid black; padding:8px;">{img_a}</td></tr>"""
                html += "</table>"
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
