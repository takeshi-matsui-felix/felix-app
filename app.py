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
# 2. UI設定 (漆黒テーマ・文字色強制固定)
# ==========================================
st.set_page_config(page_title="Felix検査App", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #121212; color: #FFFFFF !important; font-family: sans-serif; }
    header[data-testid="stHeader"] { background-color: #121212 !important; }
    
    [data-testid="stSidebar"] { background-color: #121212 !important; border-right: 1px solid #333; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    [data-testid="stSidebar"] .stRadio label { color: #FFFFFF !important; font-weight: bold !important; }

    div.stButton > button {
        background-color: #1E1E1E; color: #00E5FF !important; border: 1px solid #00E5FF;
        border-radius: 6px; height: 50px; font-weight: bold; width: 100%; margin-bottom: 5px;
    }
    
    [data-testid="stFileUploadDropzone"] {
        background-color: #262730 !important; border: 2px dashed #555 !important; border-radius: 10px !important;
    }
    [data-testid="stFileUploadDropzone"] p, [data-testid="stFileUploadDropzone"] span {
        color: #FFFFFF !important; font-weight: bold !important;
    }
    
    /* 【絶対修正】プルダウンメニューの白飛びを強制的に黒背景・白文字化 */
    div[role="listbox"] { background-color: #1E1E1E !important; }
    ul[role="listbox"] { background-color: #1E1E1E !important; }
    li[role="option"] { background-color: #1E1E1E !important; color: #FFFFFF !important; }
    li[role="option"]:hover { background-color: #00E5FF !important; color: #121212 !important; }
    li[role="option"] span { color: #FFFFFF !important; }
    li[role="option"]:hover span { color: #121212 !important; }
    
    div[data-testid="stExpander"] { background-color: #1E1E1E !important; border: 1px solid #444 !important; }
    #print-report-wrapper, #print-report-wrapper * { color: #000000 !important; }
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 検査用 定型文データ辞書 (純粋な文字列に復旧)
# ==========================================
ISSUE_TEMPLATES = {
    "配筋検査": [
        "定着不良", "定着不足", "人通口の補強筋（コの字）不良", "人通口なし", "重ね継手不良",
        "第１スラブ筋が無い", "埋設配管が鉄筋に接触・スリーブ補強不良", "スリーブ補強筋がない",
        "土除去・防湿フィルム破れ", "鉄筋のあきが取れていない", "端末筋の定着がスラブに伸びているため梁定着にする"
    ],
    "躯体検査": [
        "ホールダウン金物取付不良", "大引き金物の取付不良", "金物の釘打ち不良",
        "MDC-5Sが無い", "MDC-5の固定不良", "MDS-10Nが無い", "MDS-10Nの固定不良"
    ],
    "中間検査": [
        "PB張り不足", "PBボード開口が大き過ぎる", "竪穴区画範囲の壁PB張り上げ不足",
        "界壁PBの床根太取合い耐火材未処理", "ビスピッチ不良", "150φダクト貫通部補強不足",
        "電気配線等の貫通部隙間の不燃材埋め", "防振吊り木受け材クリアーなし", 
        "防振根太に固定金物使用", "音ナイン等隙間処置", "界壁の遮音シート未処理", "ニッチの設置高さ不良"
    ],
    "社内検査(設計)": {
        "玄関": [
            "玄関見切りトメ仕上り不良", "玄関見切り浮き", "見切りとフロアタイル隙間",
            "シューズボックス扉調整。バタンとうるさい", "シューズボックス扉調整。壁に擦る",
            "シューズボックス丁番外れ", "玄関戸固定ビスとコーキング未施工", "玄関戸固定シールはみ出し"
        ],
        "トイレ": [
            "レバーハンドル調整", "建具固定できない", "鍵がかからない",
            "タオル掛けがたつき", "ペーパーホルダーがたつき", 
            "巾木浮き、歪み是正", "巾木下の隙間コーキング処理"
        ],
        "キッチン": [
            "ダクトのPB貫通部未処理", "ダクト被覆不十分", "配管カバー浮き。テープ未施工",
            "配管隙間カバー取付け", "キッチン壁際の隙間調整", "キッチンパネル見切りがたつき",
            "キッチン際のコーキング仕上り不良", "PB貼り不足"
        ],
        "LDK": [
            "レバーハンドル調整", "建具の戸当たり未施工", "建具枠際クロス浮き",
            "建具枠下隙間コーキング", "巾木浮き", "巾木小口処理",
            "サッシ固定ビスコーキング処理なし", "サッシ固定シールはみ出し", "サッシレール歪みあり"
        ],
        "バルコニー": [
            "軒天サイディング釘頭浮き", "サイディング欠け・割れ", "サイディング段差あり",
            "サッシ上コーキング黒", "ビスミス跡処理不足", 
            "エアコンドレン排水は溝まで延長", "排水溝仕上り不良", "排水目皿なし"
        ],
        "洋室": [
            "引き戸建具調整", "引き戸の建付け調整。閉めたときに隙間あり。", 
            "引き戸建具枠小口処理", "CL建具開閉時に引っ掛かりあり", 
            "CL建具枠上の隙間コーキング", "扉と扉の接触", "枕棚の固定不十分"
        ],
        "洗面室": [
            "建具調整", "片引き戸の開閉時異音あり", "ソフトクローズ調整",
            "見切り取合い隙間リペア", "巾木下隙間あり", "巾木小口処理",
            "枠の下端（フロアタイル取合い）仕上り不良"
        ],
        "UB": [
            "UB折れ戸調整（開閉時かたい）", "UB折れ戸下枠ビス浮き", "UB折れ戸固定ビス未施工",
            "壁PB留め付けピッチ不良", "天井PB留め付けピッチ不良", "ＰＢ貼り隙間あり、耐火材充填",
            "ダクトジョイント処理不良", "ダクト支持固定不十分", "ダクト蛇行是正"
        ],
        "廊下・階段・ENT": [
            "排水カバーは土間まで落とす", "土台水切り納まり不良", "土台水切りが寸足らず",
            "土台水切りゆがみ", "サイディング小口未処理", "サイディングシール押さえ不良",
            "サイディングキズ"
        ],
        "外部": [
            "境界杭復旧", "分筆杭復旧", "破損が大きい側溝蓋補修", "側溝掃除",
            "土間コンクリートひび割れ", "土間コンクリートレベル是正", "所定の伸縮目地なし",
            "浸透マス砕石施工不十分", "水たまりあり", "メーター設置位置不良"
        ]
    }
}

# --- セッションステート管理 ---
if "role" not in st.session_state: st.session_state.role = None
if "active_menu" not in st.session_state: st.session_state.active_menu = None
if "drill_target" not in st.session_state: st.session_state.drill_target = None
if "current_box" not in st.session_state: st.session_state.current_box = None
if "issue_saved" not in st.session_state: st.session_state.issue_saved = False
if "pre_selected_prop" not in st.session_state: st.session_state.pre_selected_prop = None

# 業者用URLへのアクセス強制ロジック
is_partner_url = False
try:
    if hasattr(st, "query_params") and "mode" in st.query_params:
        if "partner" in str(st.query_params.get("mode", "")): is_partner_url = True
    elif hasattr(st, "experimental_get_query_params"):
        params = st.experimental_get_query_params()
        if "mode" in params and "partner" in str(params["mode"][0]): is_partner_url = True
except Exception: pass

if is_partner_url:
    st.session_state.role = "partner"
    if st.session_state.active_menu not in ["是正実施（協力業者）", "完了分一覧（共通）"]:
        st.session_state.active_menu = "是正実施（協力業者）"

def jump_to_menu(menu_name, prop_id=None):
    st.session_state.active_menu = menu_name
    st.session_state.drill_target = None
    st.session_state.issue_saved = False
    if prop_id: 
        st.session_state.pre_selected_prop = prop_id
    st.rerun()

FLOOR_OPTS = ["-- 選択 --", "101","102","103","201","202","203","301","302","303","共用部","外部"]
AREA_OPTS = ["-- 選択 --", "玄関", "廊下・階段・ENT", "LDK", "キッチン", "洋室", "洗面室", "UB", "トイレ", "バルコニー", "外部", "SK", "SCL", "その他"]
# 【絶対修正】手動で選ぶための全工種リストを整備
WORK_OPTS = ["-- 選択 --", "基礎工事（鉄筋）", "基礎工事（型枠）", "フレーミング", "FM", "造作", "内装", "電気", "設備", "ガス", "清掃", "サッシ", "外壁", "外構", "コーキング", "リペア", "その他"]
INSP_OPTS = ["-- 選択 --", "配筋検査","躯体検査","断熱検査","中間検査","社内検査(設計)","社内検査(建設)","社内検査(マーケ)","社内検査(不動産)"]

# ==========================================
# 4. アプリケーション本体
# ==========================================
def main():
    if st.session_state.role is None:
        st.markdown("<h1 style='text-align: center;'>Felix検査App</h1>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["管理者", "協力業者"])
        with t1:
            pwd = st.text_input("Password", type="password")
            if st.button("管理者ログイン"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state.role = "admin"; st.session_state.active_menu = "物件登録（管理者）"; st.rerun()
                else: st.error("パスワードが違います")
        with t2:
            if st.button("協力業者としてログイン"):
                st.session_state.role = "partner"; st.session_state.active_menu = "是正実施（協力業者）"; st.rerun()
        return

    st.sidebar.markdown(f"ユーザー: {st.session_state.role}")
    if st.sidebar.button("ログアウト"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        try:
            if hasattr(st, "query_params"): st.query_params.clear()
            elif hasattr(st, "experimental_set_query_params"): st.experimental_set_query_params()
        except: pass
        st.rerun()

    menu_opts = ["物件登録（管理者）", "検査実施（管理者）", "是正実施（協力業者）", "是正確認（管理者）", "完了分一覧（共通）"] if st.session_state.role == "admin" else ["是正実施（協力業者）", "完了分一覧（共通）"]
    if st.session_state.active_menu not in menu_opts: st.session_state.active_menu = menu_opts[0]
    
    selected_menu = st.sidebar.radio("MENU", menu_opts, index=menu_opts.index(st.session_state.active_menu))
    
    # 【絶対修正】メニューを切り替えたら、記憶している物件IDをリセットする
    if selected_menu != st.session_state.active_menu:
        st.session_state.active_menu = selected_menu
        st.session_state.drill_target = None
        st.session_state.issue_saved = False
        st.session_state.pre_selected_prop = None  # バグの原因だった「物件固定化」をここで破壊
        st.rerun()

    # 1. 物件登録
    if st.session_state.active_menu == "物件登録（管理者）":
        st.header("物件登録")
        name = st.text_input("新規物件名")
        if st.button("登録"):
            if name: db_post("properties", {"property_id": str(uuid.uuid4()), "property_name": name}); st.success("登録完了")
        props = db_get("properties", "select=*")
        for p in props:
            c1, c2 = st.columns([8, 2])
            if c1.button(f"{p['property_name']} 検査へ", key=f"p_{p['property_id']}"): jump_to_menu("検査実施（管理者）", p['property_id'])
            if c2.button("✕", key=f"d_{p['property_id']}"): db_delete_property(p['property_id']); st.rerun()

    # 2. 検査実施
    elif st.session_state.active_menu == "検査実施（管理者）":
        if st.session_state.current_box is None:
            st.header("検査開始")
            props = db_get("properties", "select=*")
            opts = [{"property_id": None, "property_name": "-- 選択 --"}] + props
            
            # 記憶している物件IDがあれば合わせる
            idx = 0
            if st.session_state.pre_selected_prop:
                for i, p in enumerate(opts):
                    if p['property_id'] == st.session_state.pre_selected_prop: idx = i; break
            
            target = st.selectbox("物件", opts, index=idx, format_func=lambda x: x['property_name'])
            ins_type = st.selectbox("検査種類", INSP_OPTS)
            
            if st.button("検査スタート"):
                if target['property_name'] != "-- 選択 --" and ins_type != "-- 選択 --":
                    nid = str(uuid.uuid4())
                    db_post("inspections", {"inspection_id": nid, "property_id": target['property_id'], "property_name": target['property_name'], "inspection_type": ins_type, "inspection_date": str(datetime.date.today()), "inspector": "管理者"})
                    st.session_state.current_box = {"id": nid, "prop_id": target['property_id'], "name": target['property_name'], "type": ins_type}
                    st.session_state.pre_selected_prop = None  # スタートしたらリセットする
                    st.rerun()
                else: st.error("選択してください")
        else:
            st.subheader(f"{st.session_state.current_box['name']} / {st.session_state.current_box['type']}")
            if not st.session_state.issue_saved:
                ins_type = st.session_state.current_box['type']
                template_list = []
                f = "-"
                a = "-"
                
                # 配筋・躯体・中間は「階層」「部位」を削除（非表示）
                if ins_type in ["配筋検査", "躯体検査", "中間検査"]:
                    f = "一式"
                    a = "全体"
                    template_list = ISSUE_TEMPLATES.get(ins_type, [])
                else:
                    col1, col2 = st.columns(2)
                    f = col1.selectbox("階層", FLOOR_OPTS)
                    a = col2.selectbox("部位", AREA_OPTS)
                    if ins_type == "社内検査(設計)" and a in ISSUE_TEMPLATES.get(ins_type, {}):
                        template_list = ISSUE_TEMPLATES[ins_type][a]
                
                template_opts = ["-- 選択 --"] + template_list
                
                # 【絶対修正】エラー落ちしない安全な代入処理
                if "issue_text" not in st.session_state: st.session_state.issue_text = ""
                
                def on_template_change():
                    if st.session_state.template_sel != "-- 選択 --":
                        st.session_state.issue_text = st.session_state.template_sel

                st.selectbox("定型文から選ぶ", template_opts, key="template_sel", on_change=on_template_change)
                
                w = st.selectbox("工種", WORK_OPTS)
                desc = st.text_area("指摘内容", key="issue_text")
                
                photo = st.file_uploader("撮影", type=['jpg','png','jpeg'])
                if photo: st.image(photo)
                if st.button("保存"):
                    if w != "-- 選択 --" and desc.strip() != "":
                        db_post("inspection_records", {"record_id": str(uuid.uuid4()), "inspection_id": st.session_state.current_box['id'], "property_id": st.session_state.current_box['prop_id'], "floor_level": f, "area": a, "work_type": w, "issue_detail": desc, "issue_photo_url": process_photo(photo), "progress_status": "是正待ち"})
                        st.session_state.issue_saved = True
                        st.session_state.template_sel = "-- 選択 --"
                        st.session_state.issue_text = ""
                        st.rerun()
                    else: 
                        if ins_type not in ["配筋検査", "躯体検査", "中間検査"] and (f == "-- 選択 --" or a == "-- 選択 --"):
                            st.error("階層・部位を選択してください")
                        else:
                            st.error("工種を選択し、指摘内容を入力してください")
                if st.button("終了"): 
                    st.session_state.current_box = None
                    st.session_state.issue_text = ""
                    st.rerun()
            else:
                st.success("保存完了"); 
                if st.button("次を登録"): 
                    st.session_state.issue_saved = False; st.rerun()
                if st.button("終了"): 
                    st.session_state.current_box = None; st.session_state.issue_saved = False; st.rerun()

    # 3. 是正実施
    elif st.session_state.active_menu == "是正実施（協力業者）":
        st.header("是正実施")
        if st.session_state.drill_target is None:
            all_recs = db_get("inspection_records", "progress_status=eq.是正待ち")
            all_ins = db_get("inspections", "select=*")
            ins_map = {i['inspection_id']: i for i in all_ins}
            tree = {}
            for r in all_recs:
                ins = ins_map.get(r['inspection_id'])
                if ins:
                    p, t = ins['property_name'], ins['inspection_type']
                    if p not in tree: tree[p] = {}
                    tree[p][t] = tree[p].get(t, 0) + 1
            if not tree: st.info("現在、対応が必要な是正項目はありません。")
            for p_name, types in tree.items():
                with st.expander(p_name):
                    for t_name, count in types.items():
                        if st.button(f"{t_name} ({count}件)", key=f"f_{p_name}_{t_name}"):
                            st.session_state.drill_target = {"prop": p_name, "type": t_name}; st.rerun()
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
                    head_text = f"{r.get('floor_level')} {r.get('area')}" if r.get('floor_level') != "一式" else ""
                    with st.expander(f"{head_text} - {r.get('issue_detail','')[:15]}..."):
                        if r.get('reject_reason'): st.error(f"否認理由: {r['reject_reason']}")
                        st.write("【指摘内容】", r.get('issue_detail',''))
                        if r.get('issue_photo_url'): st.image(r['issue_photo_url'], caption="指摘時")
                        
                        up = st.file_uploader("是正写真をアップロード（必須）", key=f"up_{r['record_id']}", type=['jpg','png','jpeg'])
                        if up: st.image(up, caption="プレビュー")
                        
                        if st.button("報告する", key=f"s_{r['record_id']}"):
                            if up is not None:
                                db_patch("inspection_records", r['record_id'], {"progress_status": "是正確認中", "fix_photo_url": process_photo(up)})
                                st.rerun()
                            else:
                                st.error("エラー：是正写真を撮影または選択してください。写真がないと報告できません。")

    # 4. 是正確認
    elif st.session_state.active_menu == "是正確認（管理者）":
        st.header("是正確認")
        if st.session_state.drill_target is None:
            all_recs = db_get("inspection_records", "progress_status=eq.是正確認中")
            all_ins = db_get("inspections", "select=*")
            ins_map = {i['inspection_id']: i for i in all_ins}
            tree = {}
            for r in all_recs:
                ins = ins_map.get(r['inspection_id'])
                if ins:
                    p, t = ins['property_name'], ins['inspection_type']
                    if p not in tree: tree[p] = {}
                    tree[p][t] = tree[p].get(t, 0) + 1
            if not tree: st.info("確認待ちの項目はありません。")
            for p_name, types in tree.items():
                with st.expander(p_name):
                    for t_name, count in types.items():
                        if st.button(f"{t_name} ({count}件)", key=f"c_{p_name}_{t_name}"):
                            st.session_state.drill_target = {"prop": p_name, "type": t_name}; st.rerun()
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
                    head_text = f"{r.get('floor_level')} {r.get('area')}" if r.get('floor_level') != "一式" else ""
                    with st.expander(f"{head_text} - {r.get('issue_detail','')[:15]}..."):
                        st.write("【指摘内容】", r.get('issue_detail',''))
                        c1, c2 = st.columns(2)
                        if r.get('issue_photo_url'): c1.image(r['issue_photo_url'], caption="Before")
                        if r.get('fix_photo_url'): c2.image(r['fix_photo_url'], caption="After")
                        if st.button("承認（完了へ）", key=f"ok_{r['record_id']}"): 
                            db_patch("inspection_records", r['record_id'], {"progress_status": "完了"}); st.rerun()
                        reason = st.text_input("否認理由", key=f"re_{r['record_id']}")
                        if st.button("否認（差し戻し）", key=f"ng_{r['record_id']}"): 
                            db_patch("inspection_records", r['record_id'], {"progress_status": "是正待ち", "reject_reason": reason}); st.rerun()

    # 5. 完了分一覧
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
                    
                    loc_text = f"{r.get('floor_level','')}<br>{r.get('area','')}"
                    if r.get('floor_level') == "一式": loc_text = "-"
                    
                    html += f"""<tr><td style="border:1px solid black; padding:8px;">{idx+1}</td><td style="border:1px solid black; padding:8px;">{loc_text}</td><td style="border:1px solid black; padding:8px;">{img_b}</td><td style="border:1px solid black; padding:8px; text-align:left;">{r.get('issue_detail','')}</td><td style="border:1px solid black; padding:8px;">{img_a}</td></tr>"""
                html += "</table>"
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
