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
import urllib.parse

# ==========================================
# 1. Supabase & LINE 接続設定
# ==========================================
SUPABASE_URL = "https://vzuzeymvyftmfuaxrvtb.supabase.co"
SUPABASE_KEY = "sb_publishable_2y-rvfayu8BYs0oo-UOzGA_EQTBYLxm"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# 🔑 LINE APIの設定（個別送信用）
LINE_ACCESS_TOKEN = "XwqNwZuN4ruE09xplLcq21zyruMyZDwi1r41J0HyXtD34XRb2D+RL6wskoCdRh2qgQ2R6IbbxQJDYKoUSiH+i2a+pgKaTJjwawe6u0XdRDxD0VOOGeMMBKdRq6E6OMTkg3yvurB+BOUB5k98bcaBgwdB04t89/1O/w1cDnyilFU="

# 🔑 LINE ログイン（業者登録連携用）
LINE_CLIENT_ID = "2010108828"
LINE_CLIENT_SECRET = "2c73ce25e71858bcb09c89c79fa6bbe0"

# 💡 ローカルテスト用に変更済み
REDIRECT_URI = "http://localhost:8501/"

ADMIN_PASSWORD = "2011"
DELETE_PASSWORD = "5963"

def db_get(table, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    try:
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list): return [d for d in data if isinstance(d, dict)]
            elif isinstance(data, dict): return [data]
        return []
    except Exception: return []

def db_post(table, data): requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=data)

# 💡 バグ修正：テーブルによって検索キー（ID列）を自動で切り替える
def db_patch(table, record_id, data): 
    pk_col = "partner_id" if table == "partners" else "record_id"
    requests.patch(f"{SUPABASE_URL}/rest/v1/{table}?{pk_col}=eq.{record_id}", headers=HEADERS, json=data)

def db_delete_record(record_id): requests.delete(f"{SUPABASE_URL}/rest/v1/inspection_records?record_id=eq.{record_id}", headers=HEADERS)
def db_delete_property(prop_id):
    requests.delete(f"{SUPABASE_URL}/rest/v1/inspection_records?property_id=eq.{prop_id}", headers=HEADERS)
    requests.delete(f"{SUPABASE_URL}/rest/v1/inspections?property_id=eq.{prop_id}", headers=HEADERS)
    requests.delete(f"{SUPABASE_URL}/rest/v1/properties?property_id=eq.{prop_id}", headers=HEADERS)

def upload_to_storage(base64_str):
    if not base64_str or not isinstance(base64_str, str): return None
    if base64_str.startswith("http://") or base64_str.startswith("https://"): return base64_str
    try:
        encoded = base64_str.split(",", 1)[1] if "," in base64_str else base64_str
        file_data = base64.b64decode(encoded)
        filename = f"{uuid.uuid4()}.jpg"
        url = f"{SUPABASE_URL}/storage/v1/object/photos/{filename}"
        res = requests.post(url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "image/jpeg"}, data=file_data)
        if res.status_code in [200, 201]: return f"{SUPABASE_URL}/storage/v1/object/public/photos/{filename}"
        else: return base64_str
    except Exception: return base64_str

def bg_save_inspection(photo_b64, record_data):
    saved_url = upload_to_storage(photo_b64)
    if saved_url: record_data["issue_photo_url"] = saved_url
    db_post("inspection_records", record_data)

def bg_save_correction(rec_id, fix_photo_b64, partner_id=None, company_name=None):
    fix_url = upload_to_storage(fix_photo_b64)
    up_data = {"progress_status": "是正確認中", "fix_photo_url": fix_url}
    if partner_id and company_name:
        up_data["partner_id"] = partner_id
        up_data["company_name"] = company_name
    db_patch("inspection_records", rec_id, up_data)

def bg_patch_record(rec_id, photo_b64, up_data):
    if photo_b64:
        url = upload_to_storage(photo_b64)
        if url: up_data["issue_photo_url"] = url
    db_patch("inspection_records", rec_id, up_data)

# 🚀 LINE通知送信機能
def send_line_push_message(to_user_id, text_message):
    if not to_user_id: return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    data = {
        "to": to_user_id,
        "messages": [{"type": "text", "text": text_message}]
    }
    try:
        requests.post(url, headers=headers, json=data)
    except Exception as e:
        print(f"LINE送信エラー: {e}")

# 🚀 LINEログイン連携用の関数（エラー解析強化版）
def get_line_login_url(partner_id):
    encoded_uri = urllib.parse.quote(REDIRECT_URI, safe='')
    return f"https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id={LINE_CLIENT_ID}&redirect_uri={encoded_uri}&state={partner_id}&scope=profile%20openid"

def get_line_profile(code):
    token_url = "https://api.line.me/oauth2/v2.1/token"
    payload = {
        "grant_type": "authorization_code", 
        "code": code, 
        "redirect_uri": REDIRECT_URI,
        "client_id": LINE_CLIENT_ID, 
        "client_secret": LINE_CLIENT_SECRET
    }
    res = requests.post(token_url, data=payload)
    if res.status_code != 200:
        return None, f"Token取得エラー ({res.status_code}): {res.text}"
        
    access_token = res.json().get("access_token")
    profile_res = requests.get("https://api.line.me/v2/profile", headers={"Authorization": f"Bearer {access_token}"})
    if profile_res.status_code != 200:
        return None, f"Profile取得エラー ({profile_res.status_code}): {profile_res.text}"
        
    return profile_res.json().get("userId"), "成功"

# ==========================================
# 📱 2. スマート電子黒板カメラ
# ==========================================
SMART_CAMERA_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
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
        <i class="fa-solid fa-camera" id="btn-icon"></i> <span id="btn-text">黒板付きで撮影 ／ 選択</span>
        <input type="file" accept="image/*" id="file-input">
    </label>
    <script>
        let b = { propName: "", inspType: "", inspDate: "", locationText: "", issueDetail: "", mode: "insp", companyName: "" };
        window.addEventListener("message", function(e) {
            if (e.data.type === "streamlit:render" && e.data.args) {
                b.propName = e.data.args.propName || ""; b.inspType = e.data.args.inspType || ""; 
                b.inspDate = e.data.args.inspDate || ""; b.locationText = e.data.args.locationText || ""; 
                b.issueDetail = e.data.args.issueDetail || ""; b.mode = e.data.args.mode || "insp";
                b.companyName = e.data.args.companyName || "";
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
            document.getElementById('btn-icon').className = 'fa-solid fa-spinner fa-spin';
            document.getElementById('btn-text').innerHTML = '&nbsp;黒板合成中...';

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

                    if (b.mode === 'fix' && b.companyName !== "") {
                        ctx.fillStyle = "#aaddff"; 
                        const mini_fs = Math.floor(w * 0.018);
                        ctx.font = mini_fs + "px 'Yu Gothic Medium', sans-serif";
                        ctx.textAlign = "right";
                        ctx.fillText("施工: " + b.companyName, sx + bw - 15, sy + bh - 15);
                        ctx.textAlign = "left"; 
                    }

                    sendToStreamlit(canvas.toDataURL('image/jpeg', 0.6));
                    document.getElementById('upload-label').style.backgroundColor = '#2ecc71';
                    document.getElementById('btn-icon').className = 'fa-solid fa-check';
                    document.getElementById('btn-text').innerHTML = '&nbsp;セット完了';
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

temp_dir = os.path.join(tempfile.gettempdir(), "smart_cam_final")
os.makedirs(temp_dir, exist_ok=True)
with open(os.path.join(temp_dir, "index.html"), "w", encoding="utf-8") as f:
    f.write(SMART_CAMERA_HTML)

_smart_camera = components.declare_component("smart_cam_final", path=temp_dir)

# ==========================================
# 3. UI設定 & 定型文データ
# ==========================================
st.set_page_config(page_title="Felix検査App", page_icon="icon.png", layout="wide")

st.markdown("""
<style>
    div.stButton > button { border-radius: 6px; height: 50px; font-weight: bold; width: 100%; margin-bottom: 5px; }
    footer {visibility: hidden;}
    [data-testid="stStatusWidget"] { display: none; }
    .record-box { border-bottom: 2px solid #EEEEEE; padding-bottom: 20px; margin-bottom: 20px; }
    .badge-wrap { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; font-weight: bold; margin-left: 5px; }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 4. 定型文データ（フリー項目完備・完全版マスター）
# ==========================================
ISSUE_TEMPLATES = {
    "配筋検査": {
        "定着関連": ["定着不良", "定着不足"],
        "人通口関連": ["人通口の補強筋（コの字）不良", "人通口なし", "人通口不要"],
        "重ね継手": ["重ね継手不良"],
        "スラブ筋": ["第１スラブ筋が無い"],
        "その他": ["埋設配管が鉄筋に接触 スリーブ補強不良", "スリーブ補強筋がない", "土除去 防湿フィルム破れ"],
        "新規追加内容": ["FG4コンクリート打ちが図面と不整合のため是正", "鉄筋のあきが取れていない 粗骨材の最大寸法の1.25倍以上かつ25㎜以上確認", "人通口の端末筋の定着がスラブに伸びているため、梁定着にする"],
        "フリー項目": []
    },
    "躯体検査": {
        "内部金物": ["ホールダウン金物取付不良", "大引き金物の取付不良", "金物（〇〇）の釘打ち不良", "MDC-５Sが無い", "MDC-5の固定不良", "MDS-10Nが無い", "MDS-10Nの固定不良", "あおり止め金物が無い", "ＭＤＳ金物のビス打ち不良", "ころび止め金物が無い", "BHK-185金物の固定ビス打ち込み不良"],
        "外部金物": ["外部　帯金物S-45が無い", "外部　帯金物S-45×2が無い", "外部　帯金物S－90が無い", "外部　帯金物S－90×２が無い"],
        "合板・壁": ["合板等の釘打ち固定不良", "合板の釘抜け（下地に未固定）不要な釘を抜き取り再度釘固定", "耐力壁　釘打ち固定不良"],
        "その他箇所": ["縦枠等の釘打ち不足・不良", "根太と頭つなぎの釘固定が無い", "サッシ下端の合板が張られていない", "カーテンボックス側にクギが飛び出している。逆側からクギを打ち換えるか、飛び出している釘を切断する", "防振根太にクギ打ちがされているため防振根太と根太が接触(釘外す)", "床根太の穴あけが基準を超えている。構造検討の上対応すること", "電気落とし込み穴、1/2（44.5㎜）ラインを超えている。電気施工マニュアルを参照のこと", "防振根太と根太に隙間５㎜の隙間が無い", "鋼製建具の下端合板に隙間あり。隙間無く合板を張ること", "屋根合板の釘打ち不良"],
        "基礎・土間": ["基礎　立上り断熱材　隙間の処理が現場発泡ウレタンで塞いでいない", "土間コンクリートの端部・溝鉛直部のモルタル補修必要（完了時確認するため写真不要）"],
        "その他": ["屋根の水上・水下の合板受け材（パッキン）：ｔ9×38×50＠150が無い", "床根太の穴あけが基準を超えている。構造検討の上対応すること", "竪穴区画内　日東化成株式会社（プラシール　NF-12HM）未済", "竪穴区画内　熱膨張耐火材：古河テクノマテリアル　イチジカンパット　PS060WL-0695　が無い", "防水の立ち上がり寸法がH=250ない", "鋼製建具下（平場）の防水範囲不足", "頭つなぎの貫通NG。構造検討", "鋼製束がない（図面位置と相違）"],
        "新規追加内容": ["下地材がない", "頭つなぎに貫通穴をあけている。補強すること", "下地取付位置間違い"],
        "フリー項目": []
    },
    "中間検査": {
        "PB関連": ["PB張り不足", "PB張り上げ不足。母屋たる木まで張り上げ。", "PBボード開口が大き過ぎる。石膏ボード張り増しすること", "ＰＢ留め付け不良※全室、全箇所確認のこと", "開口部周りＰＢ留め付け不良※全室、全箇所確認のこと", "竪穴区画範囲の壁PBは合板下端まで張り上げること　施工マニュアル（ＳＴ－０２－０１）確認のこと", "竪穴区画範囲の壁PBは隙間なく張り付けること", "壁PB施工がされていない（矩計図参照）", "外壁壁はPBをモヤ下まで張りあげる", "PS内の床に石膏ボード12.5張りがされていない", "界壁ＰＢの床根太、床合板取合い耐火材（スキマナイト等）未処理　※全室、全箇所確認のこと"],
        "ビス・ビスピッチ": ["ビスピッチ不良　壁：外周部＠100中間部＠200になっていない＊全住戸確認すること", "150φダクト貫通部の開口補強下地に全周ビス固定＠100がされていない　※全室、全箇所確認のこと", "ビスピッチ不良　天井：外周＠150中間＠200になっていない", "ビスピッチ不良　壁：外周部＠100中間部＠200になっていない", "ビスピッチ不良　一般壁・界壁：外周部＠100中間部＠200、天井：外周部＠150.中間部200", "天井ケイカルのビスピッチ不良　外周＠150　中間＠200", "開口部端部の上部ビス留めが無い　＠100㎜　施工マニュアルＦＲ－０３－０１参照"],
        "カーテンボックス": ["カーテンボックス内、上部と側面に強化石膏ボード張りがされていない", "カーテンボックス上部に断熱材がない"],
        "貫通部・穴あき": ["梁貫通不可。構造検討の上、補強。", "床根太の穴あけが基準を超えている。構造検討の上、補強。", "給水管・排水管の貫通部隙間の不燃材埋め（注意喚起）", "電気配線等の貫通部隙間の不燃材埋め（注意喚起）", "竪穴区画内　日東化成株式会社（プラシール　NF-12HM）未済", "電気配線界壁貫通", "150Φダクト壁貫通位置不良。開口補強追加施工、もしくは開口補強位置是正", "電気配線の縦貫通が1/2を超えている。PGで補強", "壁内のダクト被覆が無い"],
        "防振関連": ["防振根太に固定金物を使用している。防振根太から根太に固定金物位置を移動する", "防振根太に固定金物使用。防振根太から根太に固定金物位置を移動", "防振吊り木受け材の床根太とのクリアーなし", "防振吊り木受け材のころびとのクリアーなし"],
        "水道関連": ["施工範囲内に音ナイン等が施工されていない", "縦管の音ナイン等に隙間処置をすること", "基礎　立上り断熱材　隙間の処理が現場発泡ウレタンで塞いでいない"],
        "その他": ["ニッチのサイズ不良", "ニッチの設置高さ不良", "界壁は野地合板まで施工", "界壁の遮音シートは合板下端まで張り上げてからPB張りすること", "屋根下部のサイディング施工がされていない（施工マニュアルST-02-01）", "天井断熱材の防湿フィルム隙間に、テープ貼りがされていない", "遮音マットが隙間無く施工されていない", "断熱材上部にテープ貼りがされていない", "天井断熱材の防湿フィルム継ぎ目に、テープ貼りがされていない"],
        "ハットジョイナー": ["片ハットジョイナーが無い", "片ハットジョイナー・入隅板金（入隅50）が未施工"],
        "ファイヤーストップ": ["ファイヤーストップが無い（施工マニュアルSI-03-01参照）", "最上層のファイヤーストップ未施工（施工マニュアルSI-03-01参照）", "バルコニー、踊り場開口部のファイヤーストップ未施工（施工マニュアルSI-03-01参照）"],
        "入隅板金": ["入隅板金（入隅50）、補強テープ未施工※すべての入隅確認、是正", "補強テープ、入隅板金、片ハットジョイナーが無い　すべて取り付けること", "入隅板金未施工（入隅50）", "土台水切りが防鼠タイプを使用していない（施工マニュアルSI-02-01）", "竪穴区画範囲の天井裏サイディングが一部未済（合板下端まで）。施工マニュアル（ＳＴ－０２－０１）確認のこと", "手摺：透湿防水シートの施工不良（施工マニュアルSI-01-03参照）", "透湿防水シート破れ", "屋根下部のサイディング施工がされていない。隙間なくサイディングを張ること（施工マニュアルST-02-01参照）", "一側足場部の親綱なし", "樋の通り湾曲", "サイディング小口未処理"],
        "新規追加内容": ["電気配線の床貫通部未処理", "ガス管の床貫通部未処理", "天井PB貼り不足", "壁PBジョイントあて木なし（留め付けなし）", "カーテンボックス端部納まり不良", "透湿防水シート貼り方不良。下から上に重ねる。", "断熱材切断部にテープ貼りがされていない", "スパンドレル範囲の壁PBは合板下端まで張り上げること"],
        "フリー項目": []
    },
    "社内検査(設計)": {
        "玄関": {
            "玄関見切り": ["玄関見切りトメ仕上り不良", "玄関見切り浮き", "玄関見切り固定不良", "玄関見切り位置是正", "玄関見切り隙間", "見切りとフロアタイル取り合い隙間処理", "見切りとクロス取り合い 隙間リペア"], 
            "シューズボックス": ["シューズボックスのラッチ調整不十分", "シューズボックス扉調整。バタンとうるさい", "シューズボックス扉調整。扉傾き", "シューズボックス扉調整。壁に擦る", "シューズボックス扉調整。ボックスに対して斜めっている", "シューズボックス扉バタンとうるさい。涙目設置", "シューズボックスとクロス取り合い隙間をコーキング処理", "シューズボックスリペア", "シューズボックス取付位置是正", "シューズボックス丁番外れ", "シューズボックス建具受け用涙目設置", "シューズボックスの開き勝手が逆", "シューズクローク下端のコーキング未済", "シューズボックス閉時隙間広い。 プッシュ金具の調整"], 
            "玄関ドア外": ["玄関戸の戸当たりなし", "英文字の位置を玄関戸ライン側に是正", "玄関戸固定ビスとコーキング未施工", "玄関戸固定ビス頭コーキング未施工", "玄関戸下のはみだし材除去", "玄関戸固定シールはみ出し。サッシ固定ビスなし。", "玄関戸アングルピース下隙間及び横隙間のシーリング、及び固定ビス頭コーキング未施工"], 
            "玄関ドア扉": ["玄関扉調整（異音あり）", "玄関ドアクローザー調整 (異音あり)", "玄関ドアレバーハンドル調整。", "玄関扉英字カッティングシート剥がれ", "玄関扉英字カッティングシート未施工"], 
            "玄関ドア内": ["沓摺とフロアタイル取合いコーキング処理（コーキング黒）", "玄関枠下とフロアタイルに隙間あり（コーキング　白）", "玄関枠ビス未施工・ビス打ち不良", "玄関戸枠凹み", "ビス浮き", "玄関ドアと沓摺の間隙間", "沓摺浮き・異音"], 
            "巾木": ["巾木下の隙間をコーキング処理（コーキング　白）", "巾木下の隙間をコーキング処理（ボンドコーク　白）", "巾木小口処理", "巾木隙間", "巾木とクロスの取合いボンドコーク処理", "巾木反り"], 
            "フロアタイル": ["フロアタイルと巾木との取合い隙間あり(フロアタイル同色)", "フロアタイルと玄関枠の取合い隙間あり（シーリング　床同色）", "フロアタイルと沓づりの取合い隙間あり（シーリング床同色）", "フロアタイル浮き", "フロアタイル段差", "フロアタイル隙間"], 
            "建具関係": ["建付け調整(トイレドア)", "建付け調整(LDKドア)", "トイレドアレバーハンドル調整", "LDKドアレバーハンドル調整", "LDK入口建具の上部隙間"], 
            "戸当たり関係": ["戸当たり不要。取り外し後、リペア", "トイレ建具の戸当たり未施工", "トイレ建具の戸当たり調整", "トイレ建具の戸当たり位置は図面確認"], 
            "その他": ["涙目設置(トイレドア用)", "ドアスコープ傾き"],
            "フリー項目": []
        },
        "トイレ": {
            "建具関係": ["レバーハンドル調整", "建具固定できない", "鍵がかからない", "建具調整", "レバーハンドルが建具枠に当たらないよう戸当たり位置調整。", "戸当たりゴムパッキンカット", "建具枠下隙間コーキング処理（コーキング　白）"], 
            "タオル掛け・ペーパーホルダー": ["タオル掛けがたつき", "タオル掛け傾き", "ペーパーホルダーがたつき", "ペーパーホルダー傾き", "タオル掛け、ペーパーホルダー未施工", "タオル掛け、ペーパーホルダーがたつき", "タオル掛け、ペーパーホルダー傾き"], 
            "見切り": ["見切り浮き", "見切り建具枠隙間リペア"], 
            "巾木関係": ["巾木浮き、歪み是正", "巾木小口処理", "巾木下の隙間をコーキング処理（コーキング　白）", "巾木下の隙間をコーキング処理（ボンドコーク　白）", "巾木反り", "巾木隙間", "巾木留め付けフィニッシュ飛び出し"], 
            "フロアタイル": ["フロアタイルと巾木との取合い隙間あり(フロアタイル同色)", "フロアタイルと枠との取合い隙間あり(フロアタイル同色)", "フロアタイル段差", "フロアタイル隙間", "フロアタイルと見切りの間に隙間", "フロアタイル浮き", "フロアタイル目違い"], 
            "便器関係": ["便器と床の隙間コーキング処理", "便器設置位置是正"], 
            "サッシ関係": ["サッシの鍵がかからない。建付け調整。", "サッシ開閉固い。建付け調整", "サッシ固定ビス傾き。是正後、ビス頭コーキング処理。", "サッシ固定ビスコーキング処理なし", "サッシ固定ビスなし、コーキング処理なし", "サッシ固定シールはみ出し", "サッシ固定シールはみ出し。サッシ固定ビスなし。", "網戸の建付け調整", "網戸の動きが重い", "クレセント受けのビスキャップが無い", "網戸なし"], 
            "サッシ枠関係": ["サッシ枠とクロスの取合いボンドコーク処理", "サッシ枠の木目シート剥がれ（キズ）", "サッシ枠のキズ、へこみ"], 
            "その他": ["ドアストッパー取付位置は図面確認", "照明つかない", "換気扇とクロス隙間あり", "トイレアース線未接続", "トイレ、タオル掛け、ペーパーホルダー未設置"],
            "フリー項目": []
        },
        "キッチン": {
            "ダクト関係": ["ダクトのPB貫通部未処理", "ダクトのPB貫通部処理不十分", "ダクト未施工", "ダクト被覆不十分", "ダクトのPB貫通部未処理、ダクト被覆不十分"], 
            "配管関係": ["配管のPB貫通部未処理", "配管のPB貫通部処理不十分", "配管カバー浮き。テープ未施工", "配管隙間カバー取付け", "配管隙間カバー取付け、及び排水管をまっすぐにする", "排水管をまっすぐにする", "配管カバー未設置"], 
            "キッチン壁・パネル": ["キッチン壁がバチっているので是正", "キッチン壁際の隙間調整。", "キッチンパネル見切りがたつき", "キッチン際のコーキング仕上り不良（凹み過ぎ）", "キッチン際のコーキング仕上り不良", "キッチンパネルと床の取り合い隙間コーキング処理"], 
            "ＰＢ関係": ["壁PB留め付けピッチ不良", "天井PB貼り不足", "PB貼り不足", "ＰＢ貼り隙間あり、耐火材充填", "電線のＰＢ貫通部未処理"], 
            "床下点検口": ["床下点検口のフロア材のがたつきあり（調整）", "点検口枠とフロア材隙間にコーキング処理（またはリペア）", "床下点検口枠固定不良", "床下点検口収納ボックス固定不良", "床下点検口の蓋のがたつき", "床下点検口の蓋と枠との間に隙間あり（フロア材の張り伸ばし）"], 
            "キッチンパネル関係": ["キッチンパネルにキズ", "キッチンパネルにへこみ", "キッチンパネルとキッチンの取り合い隙間コーキング処理"], 
            "サッシ周り関係": ["サッシ固定ビスコーキング処理なし", "サッシ固定ビスなし コーキング処理なし", "サッシ固定シールはみ出し", "サッシ固定シールはみ出し。サッシ固定ビスなし。", "サッシ固定ビス傾き。是正後、ビス頭コーキング処理。", "サッシの開閉が重い", "サッシの鍵がかからない。建付け調整。", "サッシレール歪みあり", "サッシ枠とクロスの取合いボンドコーク処理", "網戸の動きが重い"], 
            "レンジフード": ["レンジフード幕板リペア", "レンジフード幕板調整。前面を合わせる", "レンジフード幕板キズ", "レンジフード幕板凹み"], 
            "吊戸": ["吊戸棚固定金具ぐらつき", "吊戸扉調整", "吊戸扉調整（上下隙間を合わせる）", "吊戸扉調整（間が広い）", "吊戸棚とクロス隙間コーキング", "吊戸段差", "吊戸扉調整（面を合わせる）"], 
            "シンク": ["シンク台扉調整", "シンク下、排水管はまっすぐに是正"], 
            "キャビネット": ["背板未施工", "キャビネット扉段差"], 
            "その他": ["左右留め具ずれ", "配線廻り隙間未処理", "雑巾ずり未施工"],
            "フリー項目": []
        },
        "LDK": {
            "建具関係": ["レバーハンドル調整", "建具上隙間コーキング", "建具の戸当たり未施工", "LDK建具の戸当たり調整", "建具が９０度開く位置に戸当たり位置是正。", "建具枠際クロス浮き", "引違い戸は左が後ろ", "LDK建具開閉時床に擦る", "建具枠下隙間コーキング"], 
            "巾木": ["巾木浮き", "掃き出しサッシ際の巾木小口未処理※両側", "巾木小口処理", "巾木下隙間"], 
            "サッシ・サッシ周り関係": ["サッシ固定ビスコーキング処理なし", "サッシ固定ビスなし コーキング処理なし", "サッシ固定シールはみ出し", "サッシ固定シールはみ出し。サッシ固定ビスなし。", "サッシ固定ビス傾き。是正後、ビス頭コーキング処理。", "サッシレール歪みあり", "サッシビス浮き", "サッシビスなし", "サッシビスの頭のつぶれているビスは取替え", "サッシクレセント調整", "サッシゴム破れ", "サッシ枠際クロスコーキング処理", "開閉時異音あり", "開閉時重たい", "開閉時ポコポコする", "クレセント高さ調整", "サッシ開閉固い。建付け調整。", "サッシの鍵がかからない。建付け調整。", "網戸の動きが重い", "シャッター開閉固い", "シャッター閉めた際、光が漏れる", "シャッターの固定ビスコーキング処理なし", "サッシ枠とクロスの取合いボンドコーク処理", "サッシ枠の木目シート剥がれ（キズ）", "サッシ枠のキズ、へこみ", "網戸なし"], 
            "網戸関係": ["網戸調整", "網戸調整。サッシ枠取合い隙間あり", "網戸調整（開閉時異音あり）", "網戸調整（がたつき）", "網戸ヒゲカット", "網戸と障子が干渉"], 
            "ニッチ内設備リモコン": ["インターホンの高さを給湯リモコンに合わせる", "インターホン傾き", "インターホンの位置をセンターに是正。反映。", "インターホン・スイッチの取付位置不良", "給湯リモコンの高さをインターホンに合わせる"], 
            "ニッチ関係": ["ニッチコーク処理不良", "ニッチ上端通り、仕上り不良", "ニッチ枠周り、仕上り不良", "ニッチサイズ是正"], 
            "ライト・スイッチ・コンセント関係": ["照明電球種類間違い（洗面室以外は電球色）", "ダウンライト浮き", "ダウンライト周りクロス破れ", "スイッチ位置是正"], 
            "室内物干し": ["室内物干しの取り付け位置が図面と相違", "室内物干し傾き"], 
            "カーテンレール": ["カーテンレール位置を正に是正（マニュアル参考）", "カーテンレール未施工"], 
            "フロア材関係": ["階段上がり口フロア材の浮き", "床鳴り", "フロア材のキズ、へこみ", "フロア材の段差", "フロア材の隙間"], 
            "その他": ["エアコンダクト隙間あり", "感知器が図面の位置と相違", "床鳴り", "エアコン未設置", "インターホン、リモコン鋼製ＢＯＸ未使用", "手摺ブラケット固定不良", "笠木キズ", "笠木とクロスの取合いボンドコーク処理", "カーテンレール下地位置図面確認（補強の有無）"],
            "フリー項目": []
        },
        "バルコニー": {
            "軒天": ["軒天サイディング留め付け材不適。釘留めとする。", "軒天サイディング釘打ち間違い処理不良。きれいに処理できなければ張替え。", "軒天サインディング欠け", "軒天サイディング釘頭浮き", "軒天サイディング釘頭処理不良"], 
            "サイディング": ["サイディング欠け・割れ", "サイディング段差あり", "サイディング釘頭処理不足", "サイディング釘施工不足", "サッシ上コーキング黒", "ビスタッチアップ同色", "サイディングが割れ　取替", "サイディングと通気見切りに隙間あり", "ビスミス跡処理不足"], 
            "エアコンドレン": ["エアコンドレン排水は溝まで延長", "エアコンドレンが長過ぎる"], 
            "排水関係": ["排水溝仕上り不良", "排水目皿なし", "排水桝なし", "排水溝勾配不良", "排水溝勾配未施工", "水たまりあり", "オーバーフロー管周りコーキング", "バルコニーのFRP防水仕上り不良", "排水口ドレン周りコーキング処理不良", "排水溝水たまり"], 
            "長尺・モルタル": ["長尺取合い未処理", "長尺取合い仕上り不良", "長尺浮き", "長尺はみだし接着剤除去", "長尺端部のとおりが悪い", "長尺シート取合いモルタル処理"], 
            "給湯器": ["給湯器の給水管の外壁サイディング貫通部処理不十分", "給湯器のガス管、追い炊き配管の外壁サイディング貫通部処理不十分", "給湯器高さ1900合わせ"], 
            "物干し・避難はしご": ["物干し金物がたつき", "避難はしご設置位置不適", "避難はしご使用法看板設置位置不適"], 
            "笠木": ["笠木ビス傾き", "笠木浮き", "笠木コーキング仕上り不良"], 
            "サッシ関係": ["サッシ枠キズ", "サッシガラスキズ", "網戸外れ、破れ", "サッシ周囲のコーキング不良"], 
            "笠木・手摺関係": ["笠木キズ", "笠木ジョイント部コーキング不良", "手摺固定不良", "笠木下端シーリング不良"], 
            "その他": ["土台水切り納まり不良", "スパンドレル内、防火ダンパー付きに変更", "コーキングだれ", "室外機未設置", "笠木未施工", "サッシビス飛び出し", "ビス頭シールなし", "物干し金物取付不良", "外壁の汚れ"],
            "フリー項目": []
        },
        "洋室": {
            "引き戸": ["引き戸建具調整", "左が奥に是正", "引き戸の建付け調整。閉めたときに隙間あり。", "引き戸建具開閉時に引っ掛かりあり", "引き戸建具枠小口処理", "引き戸 戸当たりクッションカット", "引き戸の引手浮き調整", "引き戸建具枠下とフローリングの隙間コーキング"], 
            "クローゼット": ["CL建具調整（ストッパーに位置を5㎝に反映）", "CL建具開閉時に引っ掛かりあり", "CL建具枠上の隙間コーキング", "CL建具枠小口処理", "扉と扉の接触", "CL建具枠下とフローリングの隙間コーキング"], 
            "枕棚・ハンガーパイプ": ["枕棚のクロス取合い隙間", "枕棚の固定不十分", "枕棚の前框がたつき", "枕棚上の雑巾ずり浮き。隙間コーキング処理。", "枕棚上雑巾づりは前框までに是正", "枕棚の取扱い注意表示・耐荷シールなし", "枕棚の取扱い注意表示はがれ", "枕棚天板の前框取合いの小口仕上り不良", "雑巾づりと天板の隙間コーキング", "ハンガーパイプ取付け不良", "ハンガーパイプ固定不良", "ハンガーパイプキズ"], 
            "巾木": ["巾木出隅キャップなし", "巾木未施工", "巾木下隙間コーキング", "巾木浮き、歪み是正", "巾木小口処理", "巾木下の隙間をコーキング処理（ボンドコーク　白）", "巾木反り", "巾木とクロスの取合いボンドコーク処理", "巾木下の隙間をコーキング処理（コーキング　白）"], 
            "洋室窓周り": ["雑巾摺り・前框のコーク不十分", "雑巾づり上のコーク切れ"], 
            "床・床下関係": ["床鳴り", "床下掃除（奥まで）", "床下水替え、乾燥、清掃。設備管片付け。", "床下点検口調整"], 
            "電気関係": ["照明つかない", "スイッチ位置が図面と不整合", "給気口傾き", "給気口浮き"], 
            "サッシ関係": ["サッシの鍵がかからない。建付け調整。", "サッシ開閉固い。建付け調整。", "網戸の動きが重い", "サッシ固定ビス傾き。是正後、ビス頭コーキング処理。", "サッシ固定ビスなし コーキング処理なし", "サッシ固定シールはみ出し", "サッシ枠とクロスの取合いボンドコーク処理"], 
            "フロア材関係": ["床鳴り", "フロア材のキズ、へこみ", "フロア材の隙間"], 
            "その他": ["戸当たり未施工", "戸当たり不要。取り外し後、リペア", "ピクチャーレール固定不良", "ピクチャーレールキズ"],
            "フリー項目": []
        },
        "洗面室": {
            "建具関係": ["建具調整", "片引き戸の建付け調整。閉めたときに隙間あり。", "片引き戸の開閉時異音あり。", "ソフトクローズ調整", "ソフトクローズ取付け"], 
            "見切り": ["見切り取合い隙間リペア", "見切り浮き", "見切りキズリペア"], 
            "巾木": ["巾木下隙間あり", "巾木未施工", "巾木と枠取合い隙間コーキング処理", "巾木下隙間あり（コーキング　白）", "巾木下隙間あり（ボンドコーク　白）", "巾木小口処理", "壁クロスと巾木との取合い隙間ボンドコーク処理"], 
            "建具枠": ["枠下隙間あり（コーキング　白）", "枠の下端（フロアタイル取合い）仕上り不良"], 
            "フロアタイル": ["フロアタイルと巾木との取合い隙間あり(フロアタイル同色)", "フロアタイルと枠との取合い隙間あり(フロアタイル同色)", "フロアタイル浮き", "フロアタイル段差", "フロアタイルと見切りの取合い隙間あり(フロアタイル同色)", "フロアタイル目違い", "フロアタイル隙間", "床鳴り（フロアタイル下地合板）", "床下収納庫のフロアタイル段差"], 
            "洗面台関係": ["洗面台の寄り不適", "洗面化粧台扉調整", "洗面化粧台横のコーキング未施工", "水道配管工事未施工", "洗面台際コーキング仕上り不良", "洗面化粧台底部隙間是正", "洗面台 鏡の上下スキマ不揃い", "洗面台の背板ビス固定が未施工"], 
            "配管カバー": ["配管カバーなし", "配管カバー浮き、貼り付け", "配管カバー色違い（白にする）"], 
            "洗濯パン": ["洗濯パン下部隙間 つけなおし", "洗濯パン留め付けビス穴のカバーなし", "洗濯パン固定不良", "洗濯パン位置是正(図面に合わせる)", "巾木と洗濯パン隙間処理"], 
            "床下関係": ["床下掃除（奥まで）", "床下点検口調整", "床下スタイロと基礎の隙間発泡ウレタン吹付け", "断熱固定不良。断熱ジョイント部に隙間あり"], 
            "UB入口枠": ["UB入口下枠湾曲", "UB入口下枠ビス浮き", "UB入口縦枠ビス浮き", "UB入口枠ビス忘れ", "UB入口枠ビスの頭のつぶれているビスは取替え", "UB入口下枠、枠、巾木下隙間あり（コーキング　白）", "UB入口下枠下隙間あり（コーキング　白）"], 
            "サッシ関係": ["サッシの鍵がかからない。建付け調整。", "サッシ開閉固い。建付け調整", "サッシ固定ビスなし コーキング処理なし", "サッシ固定シールはみ出し", "サッシ枠とクロスの取合いボンドコーク処理", "サッシ枠キズ"], 
            "洗面台・洗濯パン": ["洗面化粧台と壁の隙間コーキング不良", "洗濯機パンと壁の隙間コーキング不良", "洗面化粧台の扉調整", "洗面台鏡のキズ"], 
            "その他": ["水漏れ原因究明の上、是正", "照明電球種類間違い（洗面室は、昼白色）", "給湯リモコンをスイッチの通りに合わせる", "涙目位置正 (扉が当たってしまっている)", "洗面台扉段差", "分電盤のカバー取付不良", "換気扇の作動不良、異音", "タオル掛けがたつき"],
            "フリー項目": []
        },
        "UB": {
            "UB折れ戸": ["UB折れ戸調整（開閉時かたい）", "UB折れ戸下枠ビス浮き", "UB折れ戸縦枠ビス浮き", "折れ戸とフロアタイルの間隙間処理", "UB折れ戸枠ビス交換", "UB折れ戸固定ビス未施工", "UB折れ戸下パッキンゴム外れ"], 
            "PB壁・天井関連": ["壁PB留め付けピッチ不良", "天井PB留め付けピッチ不良", "壁ＰＢ貼り不足", "ＰＢ貼り隙間あり、耐火材充填", "ＰＢ穴あり、耐火材充填", "PBビスなし", "壁PBジョイントあて木なし（留め付けなし）", "天井PBジョイントあて木なし（留め付けなし）"], 
            "ダクト関連": ["ダクトジョイント処理不良", "ダクト支持固定不十分", "ダクト余長を減らす", "ダクト蛇行是正", "ダクト未施工", "ダクトのＰＢ貫通部未処理", "ダクト被覆不十分", "ダクトのＰＢ貫通部未処理、ダクト被覆不十分", "ダクト材種間違い（アルミ⇒スチールに是正）"], 
            "UB周り断熱": ["UB周り断熱材未施工", "UB周り断熱材貫通部未処理"], 
            "電気配線関連": ["電気配線のＰＢ貫通部未処理", "電気配線のＰＢ貫通部処理不十分"], 
            "給排水管": ["音ナイン施工範囲不適", "給水・給湯管のＰＢ貫通部未処理", "給水・給湯管のＰＢ貫通部処理不十分"], 
            "ガス管関連": ["ガス管、追い炊き配管のＰＢ貫通部未処理", "ガス管、追い炊き配管のＰＢ貫通部処理材不適。耐火材にて処理。"], 
            "浴室暖房乾燥機": ["浴室暖房乾燥機ダクト接続不良", "浴室暖房乾燥機ダクト接続未施工"], 
            "リモコン線": ["リモコン線のＰＢ貫通部未処理", "リモコン配線貫通部未処理"], 
            "UB点検口": ["UB点検口ふた調整。ロックがかからない", "UB点検口ふたキズ"], 
            "UB設備関連": ["カウンターの傾き、固定不良", "浴槽エプロンのガタつき", "シャワーフックの固定不良", "鏡のキズ、汚れ、固定不良", "排水口の部品欠品、水はけ不良"], 
            "その他": ["断熱材フィルムカット", "壁パネルのキズ、汚れ", "浴槽のキズ、汚れ", "コーキングの打ち忘れ、仕上がり不良", "点検口の蓋のがたつき、閉まり不良", "換気乾燥暖房機の作動不良、異音"],
            "フリー項目": []
        },
        "廊下・階段・ENT": {
            "排水カバー": ["排水カバーはタイルまで落とす", "排水カバーは土間まで落とす"], 
            "土台水切り": ["土台水切り納まり不良", "土台水切り施工範囲不良", "土台水切りゆがみ", "土台水切りエンドキャップ取付け", "土台水切りの矩が出ていない"], 
            "サイディング": ["サイディング小口未処理", "サイディング小口未処理（１階廊下）", "サイディング小口未処理（２階廊下）", "サイディング小口未処理（３階廊下）", "サイディングシール押さえ不良", "サイディング納まり不良", "サイディングキズ", "エントランス戸上、サイディング隙間処理", "エントランス戸枠との取り合いのサイディングは床まで張り伸ばす", "１階階段下、サイディング未施工", "入隅板金未施工", "片ハットジョイナーが無い", "釘頭のタッチアップが不十分"], 
            "階段": ["階段手すりゆがみ", "階段手すり傾き。天端合わせる", "階段手すり端部通り合わせる"], 
            "長尺シート": ["長尺シート納まり不良", "長尺シートマス周りカット不良", "長尺取合い未処理", "長尺はみだし接着剤除去", "３階廊下 長尺シート仕上げ不良", "長尺シート取合い処理不十分", "長尺シート取合い未処理"], 
            "ポーチタイル": ["ポーチタイル仕上り不良", "ポーチタイル浮き"], 
            "笠木": ["笠木コーキング仕上り不良", "笠木のカドが鋭利", "笠木ビス施工不良"], 
            "排水関連": ["排水マスなし ※長尺仕上げも反映", "排水溝勾配未施工", "排水目皿なし"], 
            "エントランス": ["エントランス戸の戸当たり未施工", "トイの繋ぎが未済"], 
            "外壁関係": ["通気見切り施工不良", "コーキング施工不十分", "通気見切り縁エンドキャップ取付け"], 
            "廊下内": ["水たまりあり", "巾木仕上り不良", "消火器ＢＯＸのサイディング取合い隙間あり", "サイディングと土間取り合い部のモルタル埋め未施工", "巾木未施工"], 
            "階段・手摺": ["階段踏み板キズ", "階段蹴込み板隙間", "階段側板隙間", "階段床鳴り", "手摺ブラケット固定不良", "手摺ジョイント部段差"], 
            "巾木・フロア材": ["巾木浮き", "巾木小口処理", "巾木下隙間", "フロア材のキズ、へこみ"], 
            "その他": ["ストレーナーなし", "１階の階段昇り口のFRP防水のマットが露出", "軒天割れ", "軒天釘頭処理", "掲示板の取付不良、傾き", "集合ポストの扉開閉不良", "天井材の汚れ"],
            "フリー項目": []
        },
        "外部": {
            "杭関連": ["境界杭復旧（敷地〇〇）", "分筆杭復旧（敷地〇〇）", "道路後退杭復旧（敷地〇〇）"], 
            "側溝": ["破損が大きい側溝蓋補修、もしくは交換", "側溝掃除"], 
            "土間コン関連・砂利・砂・砕石": ["土間コンクリートひび割れ", "土間コンクリートレベル是正", "所定の伸縮目地なし", "溝の砕石量不適。（土間とフラットにする）", "溝の砕石入れ不十分", "土留めブロック隣地との隙間の清掃、砂入れ", "土留めブロック隣地との隙間の砂追加", "土間コンクリート舗装未施工", "ブロック際砕石は、単粒黒砕石20-30に反映", "浸透マス砕石施工不十分", "水たまりあり"], 
            "メーター・マス": ["メーター設置位置不良", "メーター設置精度不良", "メーター蓋清掃", "メーター位置不適", "最終枡に泥、ゴミあり", "メーター蓋不揃い", "マス天端を土間レベルに合わせる", "マスの蓋割れ"], 
            "駐車場・駐輪場": ["駐車場輪留め・ライン未施工", "サイクルストッパー未施工"], 
            "排水カバー": ["排水カバー未施工", "排水カバーは土間まで落とす"], 
            "散水栓": ["散水栓ＢＯＸ通り不適", "散水栓ボックスは建物の反対側にてメーターボックスと通りを揃える"], 
            "受水槽": ["受水槽未設置", "受水槽の給水管の保温がされていない", "受水槽に南京錠がついているか"], 
            "電気設備関連": ["電気配管はまっすぐに是正", "スパンドレル内、防火ダンパー付きに変更", "防犯カメラ未施工"], 
            "土台水切り": ["土台水切りの歪み", "土台水切りのへこみ", "土台水切りの角がない"], 
            "サイディング": ["エントランスの袖壁サイディングが床面までない", "外壁欠けあり", "目地位置図面と相違", "サイデイング小口処置がされていない"], 
            "その他": ["オーバーハングゆがみ", "ベントキャップキズ、へこみ", "巾木仕上り不良", "ゴミボックス未施工", "オーバーフロー管カバー未設置", "タテトイ未施工", "パニックオープン未施工", "笠木の角が鋭利"],
            "フリー項目": []
        },
        "フリー項目": {
            "フリー項目": []
        }
    }
}


# ==========================================
# 4. セッション管理 & 定数
# ==========================================
for key in ["role", "active_menu", "pre_selected_prop", "delete_target", "skip_render_ids", "show_bulk_confirm", "edit_saved_records", "cached_records", "cached_target_id", "temp_photo", "partner_data", "jump_url", "processed_code"]:
    if key not in st.session_state: st.session_state[key] = None
if st.session_state.skip_render_ids is None: st.session_state.skip_render_ids = []

qp = st.query_params
if qp.get("auth") == ADMIN_PASSWORD:
    st.session_state.role = "admin"
    st.session_state.active_menu = "検査実施（管理者）" if not st.session_state.active_menu else st.session_state.active_menu

def jump_to_menu(menu_name, prop_id=None):
    st.session_state.active_menu = menu_name; st.session_state.pre_selected_prop = prop_id
    st.session_state.drill_target = None; st.session_state.current_box = None; st.session_state.delete_target = None
    st.session_state.issue_saved = False; st.session_state.skip_render_ids = []; st.session_state.show_bulk_confirm = False
    st.session_state.edit_saved_records = False; st.session_state.cached_records = None; st.session_state.cached_target_id = None; st.session_state.temp_photo = None
    st.rerun()

FLOOR_OPTS = ["-- 選択 --", "101","102","103","201","202","203","301","302","303","共用部","外部"]
AREA_OPTS_STANDARD = ["-- 選択 --", "玄関", "廊下・階段・ENT", "LDK", "キッチン", "洋室", "洗面室", "UB", "トイレ", "バルコニー", "外部", "フリー項目"]
AREA_OPTS_SHANAI = ["-- 選択 --", "玄関", "トイレ", "キッチン", "LDK", "バル কুলニー", "洋室", "洗面室", "UB", "廊下・階段・ENT", "外部", "フリー項目"]
WORK_OPTS_STANDARD = ["-- 選択 --", "基礎工事（鉄筋）", "基礎工事（型枠）", "フレーミング", "FM", "造作", "内装", "電気", "設備", "ガス", "清掃", "サッシ", "外壁", "外構", "コーキング", "リペア", "その他"]
WORK_OPTS_HAIKIN = ["-- 選択 --", "基礎工事(鉄筋)", "水道", "ガス", "その他"]
WORK_OPTS_KUTAI = ["-- 選択 --", "フレーミング", "電気", "水道", "防水", "その他"]
WORK_OPTS_CHUKAN = ["-- 選択 --", "造作", "電気", "水道", "外壁", "ガス", "足場", "その他"]
WORK_OPTS_SHANAI = ["-- 選択 --", "A.リペア", "B.清掃", "C.クロス", "D.造作", "E.水道", "F.電気", "G.キッチン", "H.サッシ", "I.外壁", "J.外構", "K.コーキング", "L.ガス", "板金", "Z.その他"]
WORK_OPTS_KIKAN = ["基礎工事", "フレーミング", "防水", "造作", "内装", "電気", "設備", "ガス", "サッシ", "外壁", "足場", "外構", "その他"]
INSP_OPTS = ["-- 選択 --", "配筋検査", "躯体検査", "断熱検査", "中間検査", "社内検査(設計)", "社内検査(建設)", "社内検査(マーケ)", "社内検査(不動産)", "【検査機関】配筋検査", "【検査機関】躯体検査", "【検査機関】断熱検査", "【検査機関】中間検査", "【検査機関】完了検査"]
SHANAI_KENSA_TYPES = ["社内検査(設計)", "社内検査(建設)", "社内検査(マーケ)", "社内検査(不動産)"]
INSPECTOR_OPTS = ["工事監理チーム", "建設部", "不動産事業部", "マーケティング部"]

# ==========================================
# 5. メイン画面・機能
# ==========================================
def main():
    qp = st.query_params
    line_code = qp.get("code")
    state_str = qp.get("state")
    
    # 端末情報を検知して自動ログイン
    if st.session_state.role is None and "saved_partner_id" in st.session_state:
        saved_id = st.session_state["saved_partner_id"]
        res = db_get("partners", f"partner_id=eq.{saved_id}")
        if res:
            st.session_state.role = "partner"
            st.session_state.partner_data = res[0]
            st.session_state.active_menu = "是正実施（協力業者）"

    # 🎯 LINE連携から戻ってきた時の【エラー出力強化版】処理
    if line_code and state_str:
        # ⚠️ Streamlitの二重実行による「使用済みコード」エラーを完全に防ぐ
        if st.session_state.get("processed_code") != line_code:
            st.session_state["processed_code"] = line_code
            with st.spinner("🔄 LINE連携を解析中..."):
                line_user_id, error_msg = get_line_profile(line_code)
                
                if line_user_id:
                    # 成功した場合の処理
                    db_patch("partners", state_str, {"line_user_id": line_user_id})
                    res = db_get("partners", f"partner_id=eq.{state_str}")
                    if res:
                        st.session_state["saved_partner_id"] = state_str
                        st.session_state.role = "partner"
                        st.session_state.partner_data = res[0]
                        st.session_state.active_menu = "是正実施（協力業者）"
                        st.query_params.clear()
                        st.success("🎉 アカウント登録とLINE連携が完了しました！")
                        st.rerun()
                else:
                    # 💥 失敗した場合は、LINEからの生のエラーメッセージを画面に出す
                    st.error("❌ LINE IDの取得に失敗しました。以下のエラーメッセージを確認してください。")
                    st.code(error_msg)
                    st.stop()

    if st.session_state.role is None:
        st.markdown("<h1 style='text-align: center;'>Felix検査App</h1>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["協力業者（登録・ログイン）", "管理者"])
        
        with t1:
            st.markdown("### 👷‍♂️ 協力業者窓口")
            
            if not st.session_state.jump_url:
                st.markdown("""
                <div style="background-color:#F0F8FF; padding:15px; border-radius:8px; border-left:5px solid #0084FF; margin-bottom:15px;">
                    <strong>⚠️ はじめてご利用になる業者様へ</strong><br>
                    以下の必要情報を入力し、「アカウントを作成」を押した後、表示されるリンクからLINE連携を行ってください。
                </div>
                """, unsafe_allow_html=True)
                
                new_c_name = st.text_input("会社名 (例: A工務店)", key="reg_c")
                new_contact = st.text_input("担当者名 (例: 山田太郎)", key="reg_contact")
                new_id = st.text_input("ログインID (半角英数字)", key="reg_id")
                new_pw = st.text_input("パスワード", type="password", key="reg_pw")
                
                if st.button("🟢 アカウントを作成してLINE連携へ進む", type="primary", use_container_width=True):
                    if new_c_name and new_contact and new_id and new_pw:
                        p_id = str(uuid.uuid4())
                        # データベースへ登録
                        db_post("partners", {
                            "partner_id": p_id, 
                            "company_name": new_c_name, 
                            "contact_name": new_contact, 
                            "login_id": new_id, 
                            "login_password": new_pw
                        })
                        
                        st.session_state.jump_url = get_line_login_url(p_id)
                        st.rerun()
                    else:
                        st.error("すべての項目を入力してください。")
            else:
                st.success("✅ アカウントの登録が完了しました！")
                st.markdown("以下のリンクをタップして、LINE連携を完了させてください。")
                
                st.markdown(f"### [👉 ここをタップしてLINE連携を完了する]({st.session_state.jump_url})")
                
                if st.button("やり直す"):
                    st.session_state.jump_url = None
                    st.rerun()
            
            st.markdown("---")
            with st.expander("🔑 すでにアカウントをお持ちの方（ログイン）"):
                p_id = st.text_input("ログインID")
                p_pwd = st.text_input("パスワード", type="password")
                if st.button("ログイン", use_container_width=True):
                    res = db_get("partners", f"login_id=eq.{p_id}&login_password=eq.{p_pwd}")
                    if res and len(res) > 0:
                        st.session_state["saved_partner_id"] = res[0]['partner_id']
                        st.session_state.role = "partner"; st.session_state.partner_data = res[0]
                        st.session_state.active_menu = "是正実施（協力業者）"; st.rerun()
                    else: st.error("ログインIDまたはパスワードが違います")
        
        with t2:
            st.markdown("### 👔 管理者ログイン")
            pwd = st.text_input("Password", type="password", key="admin_pwd")
            if st.button("管理者としてログイン"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state.role = "admin"; st.query_params.auth = ADMIN_PASSWORD
                    st.session_state.active_menu = "物件登録（管理者）"; st.rerun()
                else: st.error("パスワードが違います")
        return

    if st.session_state.role == "partner" and st.session_state.partner_data:
        c_name = st.session_state.partner_data.get("company_name", "不明")
        st.sidebar.markdown(f"**ユーザー: {c_name} 様**")
    else: st.sidebar.markdown(f"ユーザー: {st.session_state.role}")
        
    if st.sidebar.button("ログアウト"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.query_params.clear(); st.rerun()

    confirm_cnt = len(db_get("inspection_records", "select=record_id&progress_status=eq.確認待ち")) if st.session_state.role == "admin" else 0
    def format_menu(m): return f"{m} 🔴未確認{confirm_cnt}件" if m == "検査内容確認（管理者）" and confirm_cnt > 0 else m

    if st.session_state.role == "admin": menu_opts = ["物件登録（管理者）", "検査実施（管理者）", "検査内容確認（管理者）", "是正実施（協力業者）", "是正確認（管理者）", "完了分一覧（共通）", "業者アカウント管理"]
    else: menu_opts = ["是正実施（協力業者）", "完了分一覧（共通）"]
        
    if st.session_state.active_menu not in menu_opts: st.session_state.active_menu = menu_opts[0]
    selected_menu = st.sidebar.radio("MENU", menu_opts, index=menu_opts.index(st.session_state.active_menu), format_func=format_menu)
    if selected_menu != st.session_state.active_menu: jump_to_menu(selected_menu, st.session_state.pre_selected_prop)

    # ----------------------------------------
    # メニュー: 業者アカウント管理
    # ----------------------------------------
    if st.session_state.active_menu == "業者アカウント管理":
        st.header("🏢 協力業者 アカウント管理")
        st.info("協力業者からの「パスワード忘れ」の対応や、アカウント情報の変更を行います。")
        
        partners = db_get("partners", "select=*")
        for p in partners:
            with st.expander(f"👷‍♂️ {p.get('company_name')} (ID: {p.get('login_id')})"):
                u_name = st.text_input("会社名", value=p.get('company_name'), key=f"cn_{p['partner_id']}")
                u_contact = st.text_input("担当者名", value=p.get('contact_name', ''), key=f"contact_{p['partner_id']}")
                u_id = st.text_input("ログインID", value=p.get('login_id'), key=f"id_{p['partner_id']}")
                u_pw = st.text_input("パスワード", value=p.get('login_password'), key=f"pw_{p['partner_id']}")
                u_line = st.text_input("LINE User ID (システム連携用)", value=p.get('line_user_id'), key=f"line_{p['partner_id']}", help="業者がLINE連携するとここに自動でIDが入ります")
                
                c_up, c_del = st.columns(2)
                if c_up.button("💾 更新する", key=f"up_{p['partner_id']}", type="primary"):
                    db_patch("partners", p['partner_id'], {"company_name": u_name, "contact_name": u_contact, "login_id": u_id, "login_password": u_pw, "line_user_id": u_line})
                    st.success("更新しました！"); st.rerun()
                if c_del.button("🗑️ 削除", key=f"del_{p['partner_id']}"):
                    requests.delete(f"{SUPABASE_URL}/rest/v1/partners?partner_id=eq.{p['partner_id']}", headers=HEADERS)
                    st.rerun()

    # ----------------------------------------
    # メニュー: 1. 物件登録 (エリア選択追加)
    # ----------------------------------------
    elif st.session_state.active_menu == "物件登録（管理者）":
        st.header("物件登録")
        name = st.text_input("新規物件名")
        area = st.selectbox("エリアを選択", ["東海エリア", "関東エリア"]) 
        if st.button("登録"):
            if name: db_post("properties", {"property_id": str(uuid.uuid4()), "property_name": name, "area": area}); st.success("登録完了")
        for idx, p in enumerate(db_get("properties", "select=*")):
            prop_id = p.get('property_id')
            if not prop_id: continue
            c1, c2 = st.columns([7, 3])
            if c1.button(f"{p.get('property_name', '不明')} 検査へ", key=f"p_{prop_id}_{idx}"): jump_to_menu("検査実施（管理者）", prop_id)
            if c2.button("削除", key=f"d_{prop_id}_{idx}"): st.session_state.delete_target = prop_id; st.rerun()
            if st.session_state.delete_target == prop_id:
                st.warning("⚠️ 本当に削除しますか？")
                del_pw = st.text_input("パスワード(2011)", type="password", key=f"pw_{prop_id}_{idx}")
                col_y, col_n = st.columns(2)
                if col_y.button("Yes (実行)", key=f"yes_{prop_id}_{idx}"):
                    if del_pw == "2011": db_delete_property(prop_id); st.session_state.delete_target = None; st.rerun()
                    else: st.error("パスワードエラー")
                if col_n.button("キャンセル", key=f"no_{prop_id}_{idx}"): st.session_state.delete_target = None; st.rerun()
                st.markdown("---")

    # ----------------------------------------
    # メニュー: 2. 検査実施
    # ----------------------------------------
    elif st.session_state.active_menu == "検査実施（管理者）":
        if not st.session_state.current_box:
            st.header("検査開始")
            opts = [{"property_id": None, "property_name": "-- 選択 --"}] + [p for p in db_get("properties", "select=*") if p.get('property_id')]
            idx = next((i for i, p in enumerate(opts) if p.get('property_id') == st.session_state.pre_selected_prop), 0)
            target = st.selectbox("物件を選択", opts, index=idx, format_func=lambda x: x.get('property_name', '不明'))
            ins_type = st.selectbox("検査種類", INSP_OPTS)
            c1, c2 = st.columns(2)
            ins_date = c1.date_input("検査日時", datetime.date.today())
            inspector = c2.selectbox("検査員", INSPECTOR_OPTS)
            if st.button("検査スタート"):
                if target.get('property_name') != "-- 選択 --" and ins_type != "-- 選択 --":
                    nid = str(uuid.uuid4())
                    db_post("inspections", {"inspection_id": nid, "property_id": target['property_id'], "property_name": target['property_name'], "inspection_type": ins_type, "inspection_date": str(ins_date), "inspector": inspector})
                    st.session_state.current_box = {"id": nid, "prop_id": target['property_id'], "name": target['property_name'], "type": ins_type, "inspector": inspector}
                    st.session_state.pre_selected_prop = None; st.session_state.issue_saved = False; st.session_state.edit_saved_records = False; st.session_state.temp_photo = None; st.rerun()
                else: st.error("物件と検査種類を選んでください")
        else:
            cb = st.session_state.current_box
            c_name = cb.get('name', ''); c_type = cb.get('type', ''); c_id = cb.get('id', ''); c_prop_id = cb.get('prop_id', ''); c_inspector = cb.get('inspector', '')
            st.subheader(f"{c_name} / {c_type}")
            
            if st.session_state.get("edit_saved_records"):
                st.markdown("#### ✏️ 今回保存したデータの修正")
                if st.button("＜ 検査登録に戻る", use_container_width=True): st.session_state.edit_saved_records = False; st.rerun()
                edit_w_opts = WORK_OPTS_KIKAN if c_type.startswith("【検査機関】") else WORK_OPTS_SHANAI if c_type in SHANAI_KENSA_TYPES else WORK_OPTS_KUTAI if c_type == "躯体検査" else WORK_OPTS_HAIKIN if c_type == "配筋検査" else WORK_OPTS_CHUKAN if c_type == "中間検査" else WORK_OPTS_STANDARD
                for r in db_get("inspection_records", f"inspection_id=eq.{c_id}"):
                    rec_id = r.get('record_id'); floor = r.get('floor_level', ''); area = r.get('area', ''); detail = r.get('issue_detail', '')
                    if not rec_id: continue
                    with st.container():
                        st.markdown('<div class="record-box">', unsafe_allow_html=True)
                        st.markdown(f"**【{floor} {area}】 {detail}**")
                        if r.get('issue_photo_url'): st.image(r.get('issue_photo_url'), width=250)
                        with st.expander("⚙️ 内容を修正"):
                            new_f = floor; new_a = area; sel_temp = None
                            if not c_type.startswith("【検査機関】"):
                                a_opts = AREA_OPTS_SHANAI if c_type in SHANAI_KENSA_TYPES else AREA_OPTS_STANDARD
                                if c_type not in ["配筋検査", "躯体検査", "中間検査"]:
                                    new_f = st.radio("階層", FLOOR_OPTS[1:], index=FLOOR_OPTS[1:].index(floor) if floor in FLOOR_OPTS[1:] else 0, horizontal=True, key=f"ef_{rec_id}")
                                    new_a = st.radio("部位", a_opts[1:], index=a_opts[1:].index(area) if area in a_opts[1:] else 0, horizontal=True, key=f"ea_{rec_id}")
                                cat_dict = ISSUE_TEMPLATES.get(c_type, {}) if c_type in ["配筋検査", "躯体検査", "中間検査"] else ISSUE_TEMPLATES.get("社内検査(設計)", {}).get(new_a, {}) if c_type in SHANAI_KENSA_TYPES else {}
                                if not isinstance(cat_dict, dict): cat_dict = {}
                                cat_keys = list(cat_dict.keys())
                                sel_cat = st.radio("分類", cat_keys, horizontal=True, key=f"ecat_{rec_id}") if cat_keys else None
                                if sel_cat: sel_temp = st.radio("よくある指摘", cat_dict.get(sel_cat, []), key=f"etemp_{rec_id}", horizontal=True)
                            
                            new_detail = st.text_area("詳細", value=detail.split(":", 1)[1] if ":" in detail else detail.split("：", 1)[1] if "：" in detail else detail, key=f"ed_desc_{rec_id}")
                            new_w = st.radio("工種", edit_w_opts, index=edit_w_opts.index(r.get('work_type', '')) if r.get('work_type', '') in edit_w_opts else 0, horizontal=True, key=f"ed_work_{rec_id}")
                            final_desc = (sel_temp + ("：" + new_detail.strip() if new_detail.strip() != "" else "")) if sel_temp else new_detail.strip()
                            if final_desc == "": final_desc = detail 
                            
                            new_photo = _smart_camera(propName=c_name, inspType=c_type, inspDate=datetime.date.today().strftime("%Y/%m/%d"), locationText=f"{new_f} {new_a}", issueDetail=final_desc[:80]+"...", mode="insp", key=f"ed_cam_{rec_id}")
                            c_save, c_del = st.columns(2)
                            if c_save.button("💾 上書き", key=f"ed_save_{rec_id}", type="primary"):
                                up_data = {"floor_level": new_f, "area": new_a, "work_type": new_w, "issue_detail": final_desc}
                                threading.Thread(target=bg_patch_record, args=(rec_id, new_photo, up_data)).start(); st.rerun()
                            if c_del.button("🗑️ 削除", key=f"ed_del_{rec_id}"): db_delete_record(rec_id); st.rerun()
                            if new_photo: st.image(new_photo, width=250)
                        st.markdown('</div>', unsafe_allow_html=True)

            elif not st.session_state.issue_saved:
                if c_type.startswith("【検査機関】"):
                    f = "一式"; a = "全体"; sel_cat = None; sel_temp = None; desc = st.text_area("詳細", label_visibility="collapsed")
                    w = st.radio("工種", WORK_OPTS_KIKAN, horizontal=True, label_visibility="collapsed")
                else:
                    f = "一式"; a = "全体"
                    area_opts = AREA_OPTS_SHANAI if c_type in SHANAI_KENSA_TYPES else AREA_OPTS_STANDARD
                    work_opts = WORK_OPTS_SHANAI if c_type in SHANAI_KENSA_TYPES else WORK_OPTS_KUTAI if c_type == "躯体検査" else WORK_OPTS_HAIKIN if c_type == "配筋検査" else WORK_OPTS_CHUKAN if c_type == "中間検査" else WORK_OPTS_STANDARD
                    if c_type not in ["配筋検査", "躯体検査", "中間検査"]:
                        f = st.radio("階層", FLOOR_OPTS[1:], horizontal=True)
                        a = st.radio("部位", area_opts[1:], horizontal=True)
                    cat_dict = ISSUE_TEMPLATES.get(c_type, {}) if c_type in ["配筋検査", "躯体検査", "中間検査"] else ISSUE_TEMPLATES.get("社内検査(設計)", {}).get(a, {}) if c_type in SHANAI_KENSA_TYPES else {}
                    if not isinstance(cat_dict, dict): cat_dict = {}
                    cat_keys = list(cat_dict.keys())
                    sel_cat = st.radio("分類", cat_keys, horizontal=True) if cat_keys else None
                    sel_temp = st.radio("よくある指摘事項", cat_dict.get(sel_cat, []), horizontal=True) if sel_cat else None
                    desc = st.text_area("詳細", label_visibility="collapsed")
                    w = st.radio("工種", work_opts[1:], horizontal=True)
                
                final_desc = (sel_temp + ("：" + desc.strip() if desc.strip() != "" else "")) if sel_temp else desc.strip()
                loc_str = f"{f} {a} {sel_cat if sel_cat else ''}".strip()
                
                photo_input = _smart_camera(propName=c_name, inspType=c_type, inspDate=datetime.date.today().strftime("%Y/%m/%d"), locationText=loc_str, issueDetail=final_desc[:80]+"...", mode="insp", key="insp_cam")
                if photo_input: st.session_state.temp_photo = photo_input

                if st.button("💾 この内容で保存", type="primary"):
                    if w and final_desc != "" and st.session_state.temp_photo:
                        status = "確認待ち" if c_inspector == "工事監理チーム" else "是正待ち"
                        record_data = {"record_id": str(uuid.uuid4()), "inspection_id": c_id, "property_id": c_prop_id, "floor_level": f, "area": a, "work_type": w, "issue_detail": final_desc, "progress_status": status}
                        threading.Thread(target=bg_save_inspection, args=(st.session_state.temp_photo, record_data)).start()
                        st.session_state.issue_saved = True; st.session_state.temp_photo = None; st.rerun()
                    else: st.error("写真等が必須です")
                if st.button("終了"): st.session_state.current_box = None; st.session_state.temp_photo = None; st.rerun()
                if st.session_state.temp_photo: st.image(st.session_state.temp_photo, width=250)
            else:
                st.success("🎉 保存完了") 
                if st.button("次を登録", use_container_width=True): st.session_state.issue_saved = False; st.rerun()
                if st.button("✏️ 修正", use_container_width=True): st.session_state.edit_saved_records = True; st.rerun()
                if st.button("終了", use_container_width=True): st.session_state.current_box = None; st.session_state.issue_saved = False; st.rerun()

    # ----------------------------------------
    # メニュー: 3. 検査内容確認（管理者専用）
    # ----------------------------------------
    elif st.session_state.active_menu == "検査内容確認（管理者）":
        st.header("検査内容確認 ＆ 最終修正")
        all_recs = db_get("inspection_records", "select=inspection_id,progress_status&progress_status=eq.確認待ち")
        all_ins = db_get("inspections", "select=*")
        ins_map = {i.get('inspection_id'): i for i in all_ins if isinstance(i, dict) and i.get('inspection_id')}
        tree = {}
        for r in all_recs:
            if not isinstance(r, dict): continue
            ins = ins_map.get(r.get('inspection_id'))
            if ins:
                p = ins.get('property_name', '不明'); t = ins.get('inspection_type', '不明')
                if p not in tree: tree[p] = {}
                tree[p][t] = tree[p].get(t, 0) + 1
        
        if not tree: st.info("確認待ちの検査はありません。")
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
            if st.button("＜ 戻る"): st.session_state.drill_target = None; st.session_state.cached_records = None; st.rerun()
            t_ids = [str(i.get('inspection_id')) for i in all_ins if isinstance(i, dict) and i.get('property_name') == prop_val and i.get('inspection_type') == type_val and i.get('inspection_id')]
            if t_ids:
                if st.session_state.cached_records is None or st.session_state.cached_target_id != target_id_str:
                    st.session_state.cached_records = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.確認待ち"); st.session_state.cached_target_id = target_id_str
                recs = st.session_state.cached_records

                if st.button("✅ すべて承認して業者へ送る", type="primary"):
                    for r in recs: db_patch("inspection_records", r['record_id'], {"progress_status": "是正待ち"})
                    st.success("承認しました！"); st.session_state.drill_target = None; st.session_state.cached_records = None; st.rerun()
                st.markdown("---")
                
                edit_w_opts = WORK_OPTS_KIKAN if type_val.startswith("【検査機関】") else WORK_OPTS_SHANAI if type_val in SHANAI_KENSA_TYPES else WORK_OPTS_KUTAI if type_val == "躯体検査" else WORK_OPTS_HAIKIN if type_val == "配筋検査" else WORK_OPTS_CHUKAN if type_val == "中間検査" else WORK_OPTS_STANDARD
                edit_a_opts = AREA_OPTS_SHANAI if type_val in SHANAI_KENSA_TYPES else AREA_OPTS_STANDARD

                w_groups = {}
                for r in recs:
                    w = r.get('work_type') or 'その他'
                    if w not in w_groups: w_groups[w] = []
                    w_groups[w].append(r)
                
                for w_name, w_recs in w_groups.items():
                    st.subheader(f"■ {w_name}")
                    for r in w_recs:
                        rec_id = r.get('record_id'); floor = r.get('floor_level', ''); area = r.get('area', ''); detail = r.get('issue_detail', '')
                        st.markdown('<div class="record-box">', unsafe_allow_html=True)
                        st.markdown(f"**【{floor} {area}】 {detail}**")
                        if r.get('issue_photo_url'): st.image(r.get('issue_photo_url'), width=250)
                        
                        with st.expander("✏️ 修正"):
                            new_f = st.radio("階層", FLOOR_OPTS[1:], index=FLOOR_OPTS[1:].index(floor) if floor in FLOOR_OPTS[1:] else 0, horizontal=True, key=f"vf_{rec_id}")
                            new_a = st.radio("部位", edit_a_opts[1:], index=edit_a_opts[1:].index(area) if area in edit_a_opts[1:] else 0, horizontal=True, key=f"va_{rec_id}")
                            new_d = st.text_area("詳細", value=detail, key=f"vd_{rec_id}")
                            new_w = st.radio("工種", edit_w_opts, index=edit_w_opts.index(r.get('work_type', '')) if r.get('work_type', '') in edit_w_opts else 0, horizontal=True, key=f"vw_{rec_id}")
                            
                            new_p = _smart_camera(propName=prop_val, inspType=type_val, inspDate=datetime.date.today().strftime("%Y/%m/%d"), locationText=f"{new_f} {new_a}", issueDetail=new_d[:80]+"...", mode="insp", key=f"vp_{rec_id}")
                            if st.button("💾 修正保存", key=f"vsave_{rec_id}"):
                                up_data = {"floor_level": new_f, "area": new_a, "issue_detail": new_d.strip(), "work_type": new_w}
                                threading.Thread(target=bg_patch_record, args=(rec_id, new_p, up_data)).start(); st.session_state.cached_records = None; st.rerun()
                            if new_p: st.image(new_p, width=250)

                        c1, c2 = st.columns(2)
                        if c1.button("✅ 承認", key=f"vok_{rec_id}", type="primary"): db_patch("inspection_records", rec_id, {"progress_status": "是正待ち"}); st.session_state.cached_records = None; st.rerun()
                        if c2.button("🗑️ 削除", key=f"vdel_{rec_id}"): db_delete_record(rec_id); st.session_state.cached_records = None; st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

    # ----------------------------------------
    # メニュー: 4. 是正実施
    # ----------------------------------------
    elif st.session_state.active_menu == "是正実施（協力業者）":
        st.header("是正実施")
        all_recs = db_get("inspection_records", "select=inspection_id,progress_status")
        all_ins = db_get("inspections", "select=*")
        ins_map = {i.get('inspection_id'): i for i in all_ins if isinstance(i, dict) and i.get('inspection_id')}
        tree = {}; tree_counts = {}
        
        for r in all_recs:
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
            if st.button("＜ 戻る"): st.session_state.drill_target = None; st.session_state.skip_render_ids = []; st.session_state.cached_records = None; st.rerun()
            t_ids = [str(i.get('inspection_id')) for i in all_ins if isinstance(i, dict) and i.get('property_name') == prop_val and i.get('inspection_type') == type_val and i.get('inspection_id')]
            if t_ids:
                if st.session_state.cached_records is None or st.session_state.cached_target_id != target_id_str:
                    st.session_state.cached_records = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.是正待ち"); st.session_state.cached_target_id = target_id_str
                recs = st.session_state.cached_records
                st.info(f"残り（是正報告待ち）：{len(recs)}件")
                
                w_groups = {}
                for r in recs:
                    if r.get('record_id') in st.session_state.skip_render_ids: continue
                    w = r.get('work_type') or 'その他'
                    if w not in w_groups: w_groups[w] = []
                    w_groups[w].append(r)
                
                edit_w_opts = WORK_OPTS_KIKAN if type_val.startswith("【検査機関】") else WORK_OPTS_SHANAI if type_val in SHANAI_KENSA_TYPES else WORK_OPTS_KUTAI if type_val == "躯体検査" else WORK_OPTS_HAIKIN if type_val == "配筋検査" else WORK_OPTS_CHUKAN if type_val == "中間検査" else WORK_OPTS_STANDARD

                for w_name, w_recs in w_groups.items():
                    st.subheader(f"■ {w_name}")
                    for r in w_recs:
                        rec_id = r.get('record_id')
                        floor = r.get('floor_level', ''); area = r.get('area', ''); detail = r.get('issue_detail', '')
                        with st.container():
                            st.markdown('<div class="record-box">', unsafe_allow_html=True)
                            st.markdown(f"**【{floor} {area}】 {detail}**")
                            if r.get('reject_reason'): st.error(f"否認理由: {r.get('reject_reason')}")
                            
                            if st.session_state.role == "admin":
                                if st.checkbox("⚙️ 編集 (管理者専用)", key=f"edit_chk_{rec_id}"):
                                    new_detail = st.text_area("指摘内容", value=detail, key=f"edit_d_{rec_id}")
                                    new_w = st.radio("工種", edit_w_opts, index=edit_w_opts.index(r.get('work_type', '')) if r.get('work_type', '') in edit_w_opts else 0, horizontal=True, key=f"edit_w_{rec_id}")
                                    new_photo = _smart_camera(propName=prop_val, inspType=type_val, inspDate=datetime.date.today().strftime("%Y/%m/%d"), locationText=f"{floor} {area}", issueDetail=new_detail[:80]+"...", mode="insp", key=f"edit_cam_{rec_id}")
                                    col_u, col_d = st.columns(2)
                                    if col_u.button("💾 更新", key=f"edit_save_{rec_id}"):
                                        threading.Thread(target=bg_patch_record, args=(rec_id, new_photo, {"work_type": new_w, "issue_detail": new_detail})).start(); st.session_state.cached_records = None; st.rerun()
                                    if col_d.button("🗑️ 削除", key=f"edit_del_{rec_id}"): db_delete_record(rec_id); st.session_state.cached_records = None; st.rerun()
                                    if new_photo: st.image(new_photo, width=250)

                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown("**【Before】**")
                                if r.get('issue_photo_url'): st.image(r.get('issue_photo_url'), width=250)
                            with c2:
                                st.markdown("**【After】**")
                                comp_name = st.session_state.partner_data.get("company_name", "") if st.session_state.partner_data else ""
                                up = _smart_camera(propName=prop_val, inspType=type_val, inspDate=datetime.date.today().strftime("%Y/%m/%d"), locationText=f"{floor} {area} {w}".strip(), issueDetail=detail[:80]+"...", mode="fix", companyName=comp_name, key=f"fix_cam_{rec_id}")
                                
                                if st.button("✅ 完了報告", key=f"s_{rec_id}"):
                                    if up: 
                                        p_id = st.session_state.partner_data.get("partner_id") if st.session_state.partner_data else None
                                        threading.Thread(target=bg_save_correction, args=(rec_id, up, p_id, comp_name)).start()
                                        st.session_state.cached_records = [item for item in st.session_state.cached_records if item.get('record_id') != rec_id]
                                        st.session_state.skip_render_ids.append(rec_id); st.rerun()
                                    else: st.error("写真が必要です")
                                if up: st.image(up, width=250)
                            st.markdown('</div>', unsafe_allow_html=True)

    # ----------------------------------------
    # メニュー: 5. 是正確認 / 6. 完了分一覧
    # ----------------------------------------
    elif st.session_state.active_menu in ["是正確認（管理者）", "完了分一覧（共通）"]:
        status = "是正確認中" if "確認" in st.session_state.active_menu else "完了"
        all_recs = db_get("inspection_records", "select=inspection_id,progress_status")
        all_ins = db_get("inspections", "select=*")
        ins_map = {i.get('inspection_id'): i for i in all_ins if isinstance(i, dict) and i.get('inspection_id')}
        tree = {}; tree_counts = {} 
        for r in all_recs:
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
                valid_types = [t for t in types if (status == "是正確認中" and tree_counts[p_name][t].get("wait_conf", 0) > 0) or (status == "完了" and tree_counts[p_name][t].get("done", 0) > 0)]
                if valid_types:
                    has_visible_items = True
                    with st.expander(p_name):
                        for t_idx, t_name in enumerate(sorted(valid_types)):
                            c_data = tree_counts[p_name][t_name]
                            t_cols = st.columns([3, 7])
                            if t_cols[0].button(t_name, key=f"c_{p_idx}_{t_idx}", use_container_width=True):
                                st.session_state.drill_target = {"prop": p_name, "type": t_name}; st.session_state.cached_records = None; st.rerun()
                            t_cols[1].markdown(f"<div class='badge-wrap' style='margin-top:15px;'><span style='color:#555;'>全 {c_data['total']} 件 ･･･ [ ✅ 完了：{c_data['done']} ／ ⚠️ 未完了：{c_data['unres']} ]</span></div>", unsafe_allow_html=True)
            if not has_visible_items: st.info("対象の項目はありません。")

        if prop_val and type_val:
            if st.button("＜ 戻る"): st.session_state.drill_target = None; st.session_state.skip_render_ids = []; st.session_state.cached_records = None; st.rerun()
            t_ids = [str(i.get('inspection_id')) for i in all_ins if isinstance(i, dict) and i.get('property_name') == prop_val and i.get('inspection_type') == type_val and i.get('inspection_id')]
            if t_ids:
                if st.session_state.cached_records is None or st.session_state.cached_target_id != target_id_str:
                    st.session_state.cached_records = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.{status}"); st.session_state.cached_target_id = target_id_str
                recs = st.session_state.cached_records

                if status == "完了":
                    if st.session_state.role == "admin":
                        st.markdown(f"""<div class="admin-delete-box" style="background-color:#FFF0F0; padding:15px; border:2px solid #FF4B4B; border-radius:10px; margin-bottom:20px;">
                            <h3 style="color:#FF4B4B; margin-top:0;">📋 完了物件の削除（管理者専用）</h3>
                        </div>""", unsafe_allow_html=True)
                        del_pass = st.text_input("削除パスワード (5963)", type="password", key=f"del_pass_all")
                        if st.button(f"🚨 この検査のデータを完全に削除する", key=f"del_btn_all"):
                            if del_pass == DELETE_PASSWORD:
                                for iid in t_ids:
                                    requests.delete(f"{SUPABASE_URL}/rest/v1/inspection_records?inspection_id=eq.{iid}", headers=HEADERS)
                                    requests.delete(f"{SUPABASE_URL}/rest/v1/inspections?inspection_id=eq.{iid}", headers=HEADERS)
                                st.success("削除しました！"); st.session_state.drill_target = None; st.session_state.cached_records = None; st.rerun()
                            else: st.error("パスワードエラー")

                    st.markdown(f"<h3 style='text-align:center;'>{prop_val} / {type_val} 報告書</h3>", unsafe_allow_html=True)
                    w_groups = {}
                    for r in recs:
                        w = r.get('work_type') or 'その他'
                        if w not in w_groups: w_groups[w] = []
                        w_groups[w].append(r)
                    for w_name, w_recs in w_groups.items():
                        st.markdown(f"<div style='margin-top:20px; font-weight:bold;'>■ {w_name}</div>", unsafe_allow_html=True)
                        for r in w_recs:
                            st.markdown(f"""<div style="border-bottom: 1px dashed #ccc; padding: 15px 0;">
                                <div><strong>【{r.get('floor_level','')} {r.get('area','')}】</strong> {r.get('issue_detail','')}</div>
                                <table style="width:100%;"><tr>
                                <td style="width:50%; text-align:center;">[ Before ]<br><img src="{r.get('issue_photo_url')}" style="max-height:200px;"></td>
                                <td style="width:50%; text-align:center;">[ After ]<br><img src="{r.get('fix_photo_url')}" style="max-height:200px;"></td>
                                </tr></table></div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"<h3 style='margin-top:0;'>📋 {type_val} (確認待ち {len(recs)}件)</h3>", unsafe_allow_html=True)
                    w_groups = {}
                    for r in recs:
                        if r.get('record_id') in st.session_state.skip_render_ids: continue
                        w = r.get('work_type') or 'その他'
                        if w not in w_groups: w_groups[w] = []
                        w_groups[w].append(r)
                    
                    for w_name, w_recs in w_groups.items():
                        st.subheader(f"■ {w_name}")
                        for r in w_recs:
                            rec_id = r.get('record_id')
                            floor = r.get('floor_level', ''); area = r.get('area', ''); detail = r.get('issue_detail', '')
                            with st.container():
                                st.markdown(f"**【{floor} {area}】 {detail}**")
                                if r.get('company_name'): st.markdown(f"<span style='color:blue; font-size:12px;'>📝 是正報告: {r.get('company_name')}</span>", unsafe_allow_html=True)
                                
                                c1, c2 = st.columns(2)
                                if r.get('issue_photo_url'): c1.image(r.get('issue_photo_url'), width=250)
                                if r.get('fix_photo_url'): c2.image(r.get('fix_photo_url'), width=250)
                                
                                ca, cb = st.columns(2)
                                if ca.button("✅ 承認（完了へ）", key=f"ok_{rec_id}"): 
                                    db_patch("inspection_records", rec_id, {"progress_status": "完了"})
                                    st.session_state.cached_records = [item for item in st.session_state.cached_records if item.get('record_id') != rec_id]; st.session_state.skip_render_ids.append(rec_id); st.rerun()
                                
                                reason = cb.text_input("否認理由", key=f"re_{rec_id}", label_visibility="collapsed")
                                
                                # 🚀 否認（差し戻し）処理 ＋ LINE通知発射！
                                if cb.button("❌ 否認（差し戻し）", key=f"ng_{rec_id}"): 
                                    db_patch("inspection_records", rec_id, {"progress_status": "是正待ち", "reject_reason": reason})
                                    
                                    partner_id = r.get('partner_id')
                                    if partner_id:
                                        p_info = db_get("partners", f"partner_id=eq.{partner_id}")
                                        if p_info and len(p_info) > 0:
                                            line_user_id = p_info[0].get('line_user_id')
                                            if line_user_id:
                                                msg = f"⚠️【Felix建設 協力業者窓口】\n\n{prop_val} の「{type_val}」にて、あなたが提出した是正報告が否認（差し戻し）されました。\n\n▼否認理由\n{reason}\n\nアプリを確認し、再度是正・アップロードをお願いいたします。"
                                                threading.Thread(target=send_line_push_message, args=(line_user_id, msg)).start()
                                                st.toast("✅ 業者へ差し戻しLINEを自動送信しました！")

                                    st.session_state.cached_records = [item for item in st.session_state.cached_records if item.get('record_id') != rec_id]; st.session_state.skip_render_ids.append(rec_id); st.rerun()
                                st.markdown("---") 
                    
                    if recs:
                        if not st.session_state.get("show_bulk_confirm"):
                            if st.button("🚀 表示中を一括承認", type="primary", use_container_width=True): st.session_state.show_bulk_confirm = True; st.rerun()
                        else:
                            st.error("⚠️ 一括で「完了」にしますか？")
                            c_yes, c_no = st.columns(2)
                            if c_yes.button("✅ はい"):
                                for r in recs: db_patch("inspection_records", r['record_id'], {"progress_status": "完了"})
                                st.session_state.show_bulk_confirm = False; st.session_state.skip_render_ids = []; st.session_state.cached_records = []; st.rerun()
                            if c_no.button("キャンセル"): st.session_state.show_bulk_confirm = False; st.rerun()

if __name__ == "__main__":
    try: main()
    except Exception as e: st.error(f"システムエラーが発生しました: {e}"); st.button("復旧")
