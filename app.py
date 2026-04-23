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
# 2. UI設定: スマホ＆クラウド最適化
# ==========================================
st.set_page_config(page_title="Felix検査App", layout="wide")

st.markdown("""
<style>
    /* 画面全体の設定 */
    .stApp { background-color: #121212; color: #FFFFFF !important; }
    
    /* 報告書エリア内の文字色（黒固定） */
    #print-report-wrapper, #print-report-wrapper * {
        color: #000000 !important;
    }
    
    /* ボタンの装飾 */
    div.stButton > button {
        background-color: #1E1E1E; color: #00E5FF !important; border: 1px solid #00E5FF;
        border-radius: 6px; height: 50px; font-weight: bold; width: 100%;
    }
    
    /* 是正・確認リストの折り畳み（Expander） */
    div[data-testid="stExpander"] { 
        background-color: #1E1E1E !important; 
        border: 1px solid #444 !important; 
        border-radius: 8px; 
    }
    
    /* 写真アップロードエリアの文字色ハック */
    [data-testid="stFileUploadDropzone"] p {
        color: #FFFFFF !important;
    }
    
    /* 不要なフッターのみを非表示にする（ヘッダーはメニューボタンのために残す） */
    footer {visibility: hidden;}
    
    /* サイドバーの背景 */
    [data-testid="stSidebar"] { background-color: #1E1E1E; }
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

    # サイドバーメニュー
    st.sidebar.markdown(f"ユーザー: {st.session_state.role}")
    if st.sidebar.button("ログアウト"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    if st.session_state.role == "admin":
        menu_options = ["物件登録（管理者）", "検査実施（管理者）", "是正実施（協力業者）", "是正確認（管理者）", "完了分一覧（共通）"]
    else:
        menu_options = ["是正実施（協力業者）", "完了分一覧（共通）"]
    
    current_index = menu_options.index(st.session_state.active_menu) if st.session_state.active_menu in menu_options else 0
    selected_menu = st.sidebar.radio("機能メニュー", menu_options, index=current_index)

    if selected_menu != st.session_state.active_menu:
        st.session_state.active_menu = selected_menu
        st.session_state.drill_insp_id = None
        st.rerun()

    # ------------------------------------------
    # 1. 物件登録
    # ------------------------------------------
    if st.session_state.active_menu == "物件登録（管理者）":
        st.header("物件登録")
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

    # ------------------------------------------
    # 2. 検査実施
    # ------------------------------------------
    elif st.session_state.active_menu == "検査実施（管理者）":
        st.header("検査実施")
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
                
                if st.button("検査を開始する"):
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
            st.subheader(f"対象: {st.session_state.current_box['name']}")
            if not st.session_state.issue_saved:
                f = st.selectbox("階層", FLOOR_OPTS)
                a = st.selectbox("部位", AREA_OPTS)
                work = st.selectbox("工種", WORK_OPTS)
                desc = st.text_area("指摘内容", placeholder="具体的な指摘内容を入力してください")
                photo = st.file_uploader("指摘箇所を撮影", type=['jpg','png','jpeg'])
                
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
                st.success("保存完了！")
                if st.button("続けて別の箇所を撮影"):
                    st.session_state.issue_saved = False
                    st.rerun()
                if st.button("検査を終了して一覧へ"):
                    st.session_state.current_box = None
                    st.session_state.issue_saved = False
                    jump_to_menu("物件登録（管理者）")

    # ------------------------------------------
    # 3. 是正実施
    # ------------------------------------------
    elif st.session_state.active_menu == "是正実施（協力業者）":
        st.header("是正実施")
        if st.session_state.drill_insp_id is None:
            slim_recs = db_get("inspection_records", "progress_status=eq.是正待ち&select=inspection_id")
            if not slim_recs:
                st.info("現在、対応が必要な是正項目はありません。")
            else:
                count_map = {}
                for r in slim_recs: count_map[r['inspection_id']] = count_map.get(r['inspection_id'], 0) + 1
                inspections = db_get("inspections", "select=*")
                for ins in inspections:
                    iid = ins['inspection_id']
                    if iid in count_map:
                        if st.button(f"{ins['property_name']} / {ins['inspection_type']} ({count_map[iid]}件)"):
                            st.session_state.drill_insp_id = iid
                            st.rerun()
        else:
            if st.button("＜ 戻る"):
                st.session_state.drill_insp_id = None
                st.rerun()
            full_recs = db_get("inspection_records", f"inspection_id=eq.{st.session_state.drill_insp_id}&progress_status=eq.是正待ち")
            for r in full_recs:
                with st.expander(f"{r['floor_level']} {r['area']} - {r['work_type']}"):
                    st.write(f"【指摘】{r['issue_detail']}")
                    if r.get('issue_photo_url'): st.image(r['issue_photo_url'], use_container_width=True)
                    fix_photo = st.file_uploader("是正写真をアップロード", key=f"fix_{r['record_id']}")
                    if st.button("是正完了を報告", key=f"send_{r['record_id']}"):
                        db_patch("inspection_records", r['record_id'], {
                            "progress_status": "是正確認中", "fix_photo_url": process_photo(fix_photo)
                        })
                        st.rerun()

    # ------------------------------------------
    # 4. 是正確認
    # ------------------------------------------
    elif st.session_state.active_menu == "是正確認（管理者）":
        st.header("是正確認")
        if st.session_state.drill_insp_id is None:
            slim_recs = db_get("inspection_records", "progress_status=eq.是正確認中&select=inspection_id")
            if not slim_recs: st.info("確認待ちの項目はありません。")
            else:
                count_map = {}
                for r in slim_recs: count_map[r['inspection_id']] = count_map.get(r['inspection_id'], 0) + 1
                inspections = db_get("inspections", "select=*")
                for ins in inspections:
                    iid = ins['inspection_id']
                    if iid in count_map:
                        if st.button(f"{ins['property_name']} / {ins['inspection_type']} ({count_map[iid]}件)"):
                            st.session_state.drill_insp_id = iid
                            st.rerun()
        else:
            if st.button("＜ 戻る"):
                st.session_state.drill_insp_id = None
                st.rerun()
            full_recs = db_get("inspection_records", f"inspection_id=eq.{st.session_state.drill_insp_id}&progress_status=eq.是正確認中")
            for r in full_recs:
                with st.expander(f"{r['floor_level']} {r['area']} - {r['work_type']}"):
                    c1, c2 = st.columns(2)
                    c1.image(r['issue_photo_url'], caption="Before")
                    if r.get('fix_photo_url'): c2.image(r['fix_photo_url'], caption="After")
                    if st.button("承認", key=f"ok_{r['record_id']}"):
                        db_patch("inspection_records", r['record_id'], {"progress_status": "完了"})
                        st.rerun()
                    reason = st.text_input("否認理由", key=f"re_{r['record_id']}")
                    if st.button("否認", key=f"ng_{r['record_id']}"):
                        db_patch("inspection_records", r['record_id'], {"progress_status": "是正待ち", "reject_reason": reason})
                        st.rerun()

    # ------------------------------------------
    # 5. 完了分一覧 (報告書)
    # ------------------------------------------
    elif st.session_state.active_menu == "完了分一覧（共通）":
        if st.session_state.drill_insp_id is None:
            st.header("完了分一覧")
            inspections = db_get("inspections", "select=*")
            for ins in inspections:
                if st.button(f"{ins['property_name']} / {ins['inspection_type']}"):
                    st.session_state.drill_insp_id = ins['inspection_id']
                    st.rerun()
        else:
            if st.button("＜ 戻る"):
                st.session_state.drill_insp_id = None
                st.rerun()
            
            ins = next(i for i in db_get("inspections", f"inspection_id=eq.{st.session_state.drill_insp_id}"))
            recs = db_get("inspection_records", f"inspection_id=eq.{st.session_state.drill_insp_id}&progress_status=eq.完了")

            html = f"""
            <div id="print-report-wrapper" style="background-color: white; padding: 10px; border-radius: 8px;">
                <h2 style="text-align: center;">{ins['property_name']}</h2>
                <h3 style="text-align: center;">{ins['inspection_type']}報告書</h3>
                <table style="width:100%; border-collapse: collapse; margin-top:10px; border: 2px solid black;">
                    <tr style="background:#eee;">
                        <th style="border:1px solid black; padding:5px;">検査日</th><td>{ins['inspection_date']}</td>
                        <th style="border:1px solid black; padding:5px;">検査員</th><td>{ins['inspector']}</td>
                    </tr>
                </table>
                <table style="width:100%; border-collapse: collapse; margin-top:20px; border: 2px solid black; font-size:12px;">
                    <tr style="background:#eee;">
                        <th style="border:1px solid black;">No.</th><th style="border:1px solid black;">場所</th>
                        <th style="border:1px solid black;">Before</th><th style="border:1px solid black;">詳細</th>
                        <th style="border:1px solid black;">After</th>
                    </tr>
            """
            for idx, r in enumerate(recs):
                img_b = f'<img src="{r["issue_photo_url"]}" style="width:100px;">' if r.get("issue_photo_url") else ""
                img_a = f'<img src="{r["fix_photo_url"]}" style="width:100px;">' if r.get("fix_photo_url") else ""
                html += f"""
                    <tr>
                        <td style="border:1px solid black; text-align:center;">{idx+1}</td>
                        <td style="border:1px solid black; text-align:center;">{r['floor_level']}<br>{r['area']}</td>
                        <td style="border:1px solid black; text-align:center;">{img_b}</td>
                        <td style="border:1px solid black;">{r['issue_detail']}</td>
                        <td style="border:1px solid black; text-align:center;">{img_a}</td>
                    </tr>
                """
            html += "</table></div>"
            st.markdown(html, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
