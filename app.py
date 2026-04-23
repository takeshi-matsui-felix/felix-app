import streamlit as st
import requests
import uuid
import datetime
import base64
import io
import re

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
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"
    except:
        b64 = base64.b64encode(upload_file.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"

# ==========================================
# 2. UI設定 (漆黒テーマ・ヘッダー修正)
# ==========================================
st.set_page_config(page_title="Felix検査App", layout="wide")

st.markdown("""
<style>
    /* 全体背景 */
    .stApp { background-color: #121212; color: #FFFFFF !important; }
    
    /* 上部バー（ヘッダー）を黒に強制 */
    header[data-testid="stHeader"] {
        background-color: #121212 !important;
        color: #FFFFFF !important;
    }

    /* サイドバー背景と文字 */
    [data-testid="stSidebar"] { background-color: #121212 !important; border-right: 1px solid #333; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    /* カメラボタン */
    [data-testid="stFileUploadDropzone"] {
        background-color: #262730 !important;
        border: 2px dashed #555 !important;
        border-radius: 10px !important;
    }
    [data-testid="stFileUploadDropzone"] p, [data-testid="stFileUploadDropzone"] span {
        color: #FFFFFF !important; font-weight: bold !important;
    }
    
    /* 報告書（白背景） */
    #print-report-wrapper, #print-report-wrapper * { color: #000000 !important; }
    
    /* ボタン */
    div.stButton > button {
        background-color: #1E1E1E; color: #00E5FF !important; border: 1px solid #00E5FF;
        border-radius: 6px; height: 50px; font-weight: bold; width: 100%; margin-bottom: 5px;
    }
    
    /* 物件枠（Expander） */
    div[data-testid="stExpander"] { background-color: #1E1E1E !important; border: 1px solid #333 !important; }

    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# セッション管理
if "role" not in st.session_state: st.session_state.role = None
if "current_box" not in st.session_state: st.session_state.current_box = None
if "active_menu" not in st.session_state: st.session_state.active_menu = "物件登録（管理者）"
if "drill_report_key" not in st.session_state: st.session_state.drill_report_key = None

def jump_to_menu(menu_name, prop_id=None):
    st.session_state.active_menu = menu_name
    st.session_state.drill_report_key = None
    st.rerun()

INSP_OPTS = ["-- 選択してください --", "配筋検査","躯体検査","断熱検査","中間検査","社内検査(設計)","社内検査(建設)","社内検査(マーケ)","社内検査(不動産)"]

# ==========================================
# 3. アプリケーション本体
# ==========================================
def main():
    if st.session_state.role is None:
        st.markdown("<h1 style='text-align: center;'>Felix検査App</h1>", unsafe_allow_html=True)
        if st.button("管理者としてログイン"):
            st.session_state.role = "admin"; st.rerun()
        if st.button("協力業者としてログイン"):
            st.session_state.role = "partner"; st.session_state.active_menu = "是正実施（協力業者）"; st.rerun()
        return

    # サイドバー
    st.sidebar.markdown(f"ユーザー: {st.session_state.role}")
    if st.sidebar.button("ログアウト"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    menu_opts = ["物件登録（管理者）", "検査実施（管理者）", "是正実施（協力業者）", "是正確認（管理者）", "完了分一覧（共通）"] if st.session_state.role == "admin" else ["是正実施（協力業者）", "完了分一覧（共通）"]
    selected_menu = st.sidebar.radio("機能メニュー", menu_opts, index=menu_opts.index(st.session_state.active_menu) if st.session_state.active_menu in menu_opts else 0)

    if selected_menu != st.session_state.active_menu:
        st.session_state.active_menu = selected_menu; st.session_state.drill_report_key = None; st.rerun()

    # 1. 物件登録
    if st.session_state.active_menu == "物件登録（管理者）":
        st.header("物件登録")
        name = st.text_input("物件名を入力")
        if st.button("新規登録"):
            if name: db_post("properties", {"property_id": str(uuid.uuid4()), "property_name": name}); st.success("登録完了")
        
        props = db_get("properties", "select=*")
        for p in props:
            c1, c2 = st.columns([8, 2])
            if c1.button(f"{p['property_name']} 検査へ", key=f"p_{p['property_id']}"): jump_to_menu("検査実施（管理者）")
            if c2.button("✕", key=f"d_{p['property_id']}"): db_delete_property(p['property_id']); st.rerun()

    # 2. 検査実施 (通常通り)
    elif st.session_state.active_menu == "検査実施（管理者）":
        st.header("検査実施")
        if st.session_state.current_box is None:
            props = db_get("properties", "select=*")
            target = st.selectbox("物件を選択", props, format_func=lambda x: x['property_name'])
            ins_type = st.selectbox("検査種類を選択", INSP_OPTS)
            if st.button("検査を開始"):
                nid = str(uuid.uuid4())
                db_post("inspections", {"inspection_id": nid, "property_id": target['property_id'], "property_name": target['property_name'], "inspection_type": ins_type, "inspection_date": str(datetime.date.today()), "inspector": "松井", "status": "検査中"})
                st.session_state.current_box = {"id": nid, "prop_id": target['property_id'], "name": target['property_name'], "type": ins_type}
                st.rerun()
        else:
            st.subheader(f"{st.session_state.current_box['name']} / {st.session_state.current_box['type']}")
            desc = st.text_area("指摘内容")
            photo = st.file_uploader("写真を撮影")
            if photo: st.image(photo)
            if st.button("この内容で保存"):
                db_post("inspection_records", {"record_id": str(uuid.uuid4()), "inspection_id": st.session_state.current_box['id'], "property_id": st.session_state.current_box['prop_id'], "issue_detail": desc, "issue_photo_url": process_photo(photo), "progress_status": "是正待ち", "floor_level": "101", "area": "LDK", "work_type": "FM"})
                st.success("保存しました")
            if st.button("終了する"): st.session_state.current_box = None; st.rerun()

    # 3. 是正実施 / 4. 是正確認 (省略せずロジック維持)
    elif st.session_state.active_menu in ["是正実施（協力業者）", "是正確認（管理者）"]:
        status = "是正待ち" if "実施" in st.session_state.active_menu else "是正確認中"
        st.header(st.session_state.active_menu)
        recs = db_get("inspection_records", f"progress_status=eq.{status}")
        for r in recs:
            with st.expander(f"指摘事項: {r['issue_detail'][:15]}..."):
                if r['issue_photo_url']: st.image(r['issue_photo_url'])
                if status == "<td>是正待ち</td>":
                    up = st.file_uploader("是正写真を撮影", key=f"up_{r['record_id']}")
                    if st.button("報告", key=f"s_{r['record_id']}"):
                        db_patch("inspection_records", r['record_id'], {"progress_status": "是正確認中", "fix_photo_url": process_photo(up)}); st.rerun()
                else:
                    st.image(r['fix_photo_url'], caption="是正後")
                    if st.button("承認", key=f"ok_{r['record_id']}"): db_patch("inspection_records", r['record_id'], {"progress_status": "完了"}); st.rerun()

    # 5. 完了分一覧 (統合ロジック突破版)
    elif st.session_state.active_menu == "完了分一覧（共通）":
        if st.session_state.drill_report_key is None:
            st.header("完了分一覧")
            # 完了しているレコードを全取得
            all_done = db_get("inspection_records", "progress_status=eq.完了")
            # 物件名・検査種類を取得するために全検査情報を取得
            all_ins = db_get("inspections", "select=*")
            ins_map = {i['inspection_id']: i for i in all_ins}

            # 【重要】物件名 -> 検査種類の順にグループ化
            report_tree = {}
            for r in all_done:
                ins = ins_map.get(r['inspection_id'])
                if ins:
                    p_name = ins['property_name']
                    i_type = ins['inspection_type']
                    if p_name not in report_tree: report_tree[p_name] = set()
                    report_tree[p_name].add(i_type)
            
            if not report_tree:
                st.info("完了した報告書はありません。")
            else:
                for p_name, types in report_tree.items():
                    with st.expander(p_name): # 物件名の枠（アイコンなし）
                        for t_name in sorted(list(types)):
                            # 物件名と検査種類の組み合わせをキーにする
                            if st.button(t_name, key=f"btn_{p_name}_{t_name}"):
                                st.session_state.drill_report_key = {"prop": p_name, "type": t_name}
                                st.rerun()
        else:
            # 報告書詳細表示
            if st.button("＜ 戻る"): st.session_state.drill_report_key = None; st.rerun()
            
            sel = st.session_state.drill_report_key
            # その物件名と検査種類に該当する全ての完了レコードをかき集める (統合)
            # 1. 該当する全inspection_idを特定
            target_ins_ids = [i['inspection_id'] for i in db_get("inspections", f"property_name=eq.{sel['prop']}&inspection_type=eq.{sel['type']}")]
            # 2. それらのIDに紐づく完了レコードを取得
            id_query = f"({','.join(target_ins_ids)})"
            all_recs = db_get("inspection_records", f"inspection_id=in.{id_query}&progress_status=eq.完了")

            html = f"""
            <div id="print-report-wrapper" style="background-color: white; padding: 20px; border-radius: 8px;">
                <h2 style="text-align: center;">{sel['prop']}</h2>
                <h3 style="text-align: center;">{sel['type']}報告書</h3>
                <table style="width:100%; border-collapse: collapse; border: 2px solid black; font-size:12px; text-align:center;">
                    <tr style="background:#eee;">
                        <th style="border:1px solid black; padding:8px;">No.</th>
                        <th style="border:1px solid black; padding:8px;">指摘内容</th>
                        <th style="border:1px solid black; padding:8px;">Before</th>
                        <th style="border:1px solid black; padding:8px;">After</th>
                    </tr>"""
            for idx, r in enumerate(all_recs):
                img_b = f'<img src="{r.get("issue_photo_url")}" style="width:140px;">' if r.get("issue_photo_url") else "なし"
                img_a = f'<img src="{r.get("fix_photo_url")}" style="width:140px;">' if r.get("fix_photo_url") else "なし"
                html += f"""
                    <tr>
                        <td style="border:1px solid black; padding:8px;">{idx+1}</td>
                        <td style="border:1px solid black; padding:8px; text-align:left;">{r.get('issue_detail','')}</td>
                        <td style="border:1px solid black; padding:8px;">{img_b}</td>
                        <td style="border:1px solid black; padding:8px;">{img_a}</td>
                    </tr>"""
            html += "</table></div>"
            st.markdown(html, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
