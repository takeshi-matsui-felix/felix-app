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
# 2. UI設定: スマホ完全最適化
# ==========================================
st.set_page_config(page_title="Felix検査App", layout="wide")

st.markdown("""
<style>
    /* 画面全体 */
    .stApp { background-color: #121212; color: #FFFFFF !important; }
    
    /* 【重点修正1】サイドバー（メニュー）背景を黒、文字を白に強制 */
    [data-testid="stSidebar"] {
        background-color: #121212 !important;
        border-right: 1px solid #333;
    }
    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }

    /* カメラボタンの視認性 */
    [data-testid="stFileUploadDropzone"] {
        background-color: #262730 !important;
        border: 2px dashed #555 !important;
        border-radius: 10px !important;
    }
    [data-testid="stFileUploadDropzone"] p, [data-testid="stFileUploadDropzone"] span {
        color: #FFFFFF !important;
        font-weight: bold !important;
    }
    
    /* 報告書エリア（白背景） */
    #print-report-wrapper, #print-report-wrapper * {
        color: #000000 !important;
    }
    
    /* 全体ボタン */
    div.stButton > button {
        background-color: #1E1E1E; color: #00E5FF !important; border: 1px solid #00E5FF;
        border-radius: 6px; height: 50px; font-weight: bold; width: 100%;
    }
    
    footer {visibility: hidden;}
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
        if st.button("管理者としてログイン"):
            st.session_state.role = "admin"
            st.session_state.active_menu = "物件登録（管理者）"
            st.rerun()
        if st.button("協力業者としてログイン"):
            st.session_state.role = "partner"
            st.session_state.active_menu = "是正実施（協力業者）"
            st.rerun()
        return

    # サイドバー
    st.sidebar.markdown(f"ユーザー: {st.session_state.role}")
    if st.sidebar.button("ログアウト"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    menu_options = ["物件登録（管理者）", "検査実施（管理者）", "是正実施（協力業者）", "是正確認（管理者）", "完了分一覧（共通）"] if st.session_state.role == "admin" else ["<td>是正実施（協力業者）</td>", "完了分一覧（共通）"]
    selected_menu = st.sidebar.radio("機能メニュー", menu_options, index=menu_options.index(st.session_state.active_menu) if st.session_state.active_menu in menu_options else 0)

    if selected_menu != st.session_state.active_menu:
        st.session_state.active_menu = selected_menu
        st.session_state.drill_insp_id = None
        st.rerun()

    # 1. 物件登録
    if st.session_state.active_menu == "物件登録（管理者）":
        st.header("物件登録")
        name = st.text_input("物件名")
        if st.button("新規登録"):
            if name: db_post("properties", {"property_id": str(uuid.uuid4()), "property_name": name}); st.success("登録完了")
        
        props = db_get("properties", "select=*")
        for p in props:
            c1, c2 = st.columns([8, 2])
            if c1.button(f"{p['property_name']} 検査へ", key=f"p_{p['property_id']}"): jump_to_menu("検査実施（管理者）", p['property_id'])
            if c2.button("✕", key=f"d_{p['property_id']}"): db_delete_property(p['property_id']); st.rerun()

    # 2. 検査実施
    elif st.session_state.active_menu == "検査実施（管理者）":
        st.header("検査実施")
        if st.session_state.current_box is None:
            props = db_get("properties", "select=*")
            target = st.selectbox("物件", props, format_func=lambda x: x['property_name'])
            ins_type = st.selectbox("種別", INSP_OPTS)
            if st.button("検査開始"):
                nid = str(uuid.uuid4())
                db_post("inspections", {"inspection_id": nid, "property_id": target['property_id'], "property_name": target['property_name'], "inspection_type": ins_type, "inspection_date": str(datetime.date.today()), "inspector": "松井", "status": "検査中"})
                st.session_state.current_box = {"id": nid, "property_id": target['property_id'], "name": f"{target['property_name']} / {ins_type}"}
                st.rerun()
        else:
            st.subheader(st.session_state.current_box['name'])
            f = st.selectbox("階層", FLOOR_OPTS); a = st.selectbox("部位", AREA_OPTS); w = st.selectbox("工種", WORK_OPTS)
            desc = st.text_area("内容")
            photo = st.file_uploader("撮影")
            if photo: st.image(photo)
            if st.button("保存"):
                db_post("inspection_records", {"record_id": str(uuid.uuid4()), "inspection_id": st.session_state.current_box['id'], "property_id": st.session_state.current_box['property_id'], "floor_level": f, "area": a, "work_type": w, "issue_detail": desc, "issue_photo_url": process_photo(photo), "progress_status": "是正待ち"})
                st.success("保存完了"); st.session_state.issue_saved = True; st.rerun()
            if st.button("終了"): st.session_state.current_box = None; st.rerun()

    # 3. 是正実施
    elif st.session_state.active_menu == "是正実施（協力業者）":
        st.header("是正実施")
        if st.session_state.drill_insp_id is None:
            recs = db_get("inspection_records", "progress_status=eq.是正待ち&select=inspection_id")
            ids = list(set([r['inspection_id'] for r in recs]))
            for iid in ids:
                ins = db_get("inspections", f"inspection_id=eq.{iid}")[0]
                if st.button(f"{ins['property_name']} / {ins['inspection_type']}", key=f"f_{iid}"): st.session_state.drill_insp_id = iid; st.rerun()
        else:
            if st.button("＜ 戻る"): st.session_state.drill_insp_id = None; st.rerun()
            recs = db_get("inspection_records", f"inspection_id=eq.{st.session_state.drill_insp_id}&progress_status=eq.是正待ち")
            for r in recs:
                with st.expander(f"{r['floor_level']} {r['area']}"):
                    st.write(r['issue_detail'])
                    if r['issue_photo_url']: st.image(r['issue_photo_url'])
                    fix = st.file_uploader("是正後", key=f"up_{r['record_id']}")
                    if fix: st.image(fix)
                    if st.button("報告", key=f"s_{r['record_id']}"):
                        db_patch("inspection_records", r['record_id'], {"progress_status": "是正確認中", "fix_photo_url": process_photo(fix)})
                        st.rerun()

    # 4. 是正確認
    elif st.session_state.active_menu == "是正確認（管理者）":
        st.header("是正確認")
        if st.session_state.drill_insp_id is None:
            recs = db_get("inspection_records", "progress_status=eq.是正確認中&select=inspection_id")
            ids = list(set([r['inspection_id'] for r in recs]))
            for iid in ids:
                ins = db_get("inspections", f"inspection_id=eq.{iid}")[0]
                if st.button(f"{ins['property_name']} / {ins['inspection_type']}", key=f"c_{iid}"): st.session_state.drill_insp_id = iid; st.rerun()
        else:
            if st.button("＜ 戻る"): st.session_state.drill_insp_id = None; st.rerun()
            recs = db_get("inspection_records", f"inspection_id=eq.{st.session_state.drill_insp_id}&progress_status=eq.是正確認中")
            for r in recs:
                with st.expander(f"{r['floor_level']} {r['area']}"):
                    c1, c2 = st.columns(2)
                    c1.image(r['issue_photo_url'], caption="Before"); c2.image(r['fix_photo_url'], caption="After")
                    if st.button("承認", key=f"ok_{r['record_id']}"): db_patch("inspection_records", r['record_id'], {"progress_status": "完了"}); st.rerun()
                    if st.button("否認", key=f"ng_{r['record_id']}"): db_patch("inspection_records", r['record_id'], {"progress_status": "是正待ち"}); st.rerun()

    # 【重点修正2】完了分一覧 (写真表示の確実な実装)
    elif st.session_state.active_menu == "完了分一覧（共通）":
        if st.session_state.drill_insp_id is None:
            st.header("完了分一覧")
            inspections = db_get("inspections", "select=*")
            for ins in inspections:
                if st.button(f"{ins['property_name']} / {ins['inspection_type']}", key=f"done_{ins['inspection_id']}"):
                    st.session_state.drill_insp_id = ins['inspection_id']; st.rerun()
        else:
            if st.button("＜ 戻る"): st.session_state.drill_insp_id = None; st.rerun()
            ins = db_get("inspections", f"inspection_id=eq.{st.session_state.drill_insp_id}")[0]
            recs = db_get("inspection_records", f"inspection_id=eq.{st.session_state.drill_insp_id}&progress_status=eq.完了")

            html = f"""
            <div id="print-report-wrapper" style="background-color: white; padding: 20px; border-radius: 8px;">
                <h2 style="text-align: center;">{ins['property_name']}</h2><h3 style="text-align: center;">{ins['inspection_type']}報告書</h3>
                <table style="width:100%; border-collapse: collapse; border: 2px solid black;">
                    <tr style="background:#eee;">
                        <th style="border:1px solid black; padding:5px;">検査日</th><td style="border:1px solid black; padding:5px;">{ins['inspection_date']}</td>
                        <th style="border:1px solid black; padding:5px;">検査員</th><td style="border:1px solid black; padding:5px;">{ins['inspector']}</td>
                    </tr>
                </table>
                <table style="width:100%; border-collapse: collapse; margin-top:20px; border: 2px solid black; font-size:12px;">
                    <tr style="background:#eee;">
                        <th style="border:1px solid black; padding:5px;">No.</th><th style="border:1px solid black; padding:5px;">場所</th>
                        <th style="border:1px solid black; padding:5px;">Before</th><th style="border:1px solid black; padding:5px;">詳細</th>
                        <th style="border:1px solid black; padding:5px;">After</th>
                    </tr>"""
            for idx, r in enumerate(recs):
                img_b = f'<img src="{r.get("issue_photo_url")}" style="width:120px;">' if r.get("issue_photo_url") else "なし"
                img_a = f'<img src="{r.get("fix_photo_url")}" style="width:120px;">' if r.get("fix_photo_url") else "なし"
                html += f"""
                    <tr>
                        <td style="border:1px solid black; text-align:center; padding:5px;">{idx+1}</td>
                        <td style="border:1px solid black; text-align:center; padding:5px;">{r.get('floor_level','')}<br>{r.get('area','')}</td>
                        <td style="border:1px solid black; text-align:center; padding:5px;">{img_b}</td>
                        <td style="border:1px solid black; padding:5px;">{r.get('issue_detail','')}</td>
                        <td style="border:1px solid black; text-align:center; padding:5px;">{img_a}</td>
                    </tr>"""
            html += "</table></div>"
            st.markdown(html, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
