import streamlit as st
import requests
import uuid
import datetime
import base64
import io
import json

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

# 🛡 【絶対防御】データベース通信時のエラー回避
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

def db_delete_property(prop_id):
    requests.delete(f"{SUPABASE_URL}/rest/v1/inspection_records?property_id=eq.{prop_id}", headers=HEADERS)
    requests.delete(f"{SUPABASE_URL}/rest/v1/inspections?property_id=eq.{prop_id}", headers=HEADERS)
    requests.delete(f"{SUPABASE_URL}/rest/v1/properties?property_id=eq.{prop_id}", headers=HEADERS)

def process_photo(upload_file):
    if upload_file is None: return None
    try:
        from PIL import Image
        img = Image.open(upload_file)
        img.thumbnail((600, 600))
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
    except:
        return f"data:image/jpeg;base64,{base64.b64encode(upload_file.getvalue()).decode('utf-8')}"

# ==========================================
# 2. UI設定 (スマホ画面にピタッと収まるレスポンシブ仕様)
# ==========================================
st.set_page_config(page_title="Felix検査App", layout="wide")

st.markdown("""
<style>
    div.stButton > button {
        border-radius: 6px; height: 50px; font-weight: bold; width: 100%; margin-bottom: 5px;
    }
    footer {visibility: hidden;}
    
    /* 読み込み中インジケータを画面中央に白く綺麗に表示 */
    [data-testid="stStatusWidget"] {
        position: fixed !important;
        top: 50% !important;
        left: 50% !important;
        transform: translate(-50%, -50%) !important;
        background-color: rgba(255, 255, 255, 0.95) !important;
        border: 1px solid #E0E0E0 !important;
        border-radius: 12px !important;
        padding: 15px 25px !important;
        z-index: 99999 !important;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.1) !important;
    }
    [data-testid="stStatusWidget"] label, [data-testid="stStatusWidget"] p {
        color: #121212 !important;
        font-size: 16px !important;
        font-weight: bold !important;
    }
    [data-testid="stStatusWidget"] svg {
        color: #121212 !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 定型文データ (全スキャン完全版)
# ==========================================
ISSUE_TEMPLATES = json.loads('{"配筋検査":{"定着関連":["定着不良","定着不足"],"人通口関連":["人通口の補強筋（コの字）不良","人通口なし","人通口不要"],"重ね継手":["重ね継手不良"],"スラブ筋":["第１スラブ筋が無い"],"その他":["埋設配管が鉄筋に接触 スリーブ補強不良","スリーブ補強筋がない","土除去 防湿フィルム破れ"],"新規追加内容":["FG4コンクリート打ちが図面と不整合のため是正","鉄筋のあきが取れていない 粗骨材の最大寸法の1.25倍以上かつ25㎜以上確認","人通口の端末筋の定着がスラブに伸びているため、梁定着にする"]},"躯体検査":{"内部金物":["ホールダウン金物取付不良","大引き金物の取付不良","金物（〇〇）の釘打ち不良","MDC-５Sが無い","MDC-5の固定不良","MDS-10Nが無い","MDS-10Nの固定不良","あおり止め金物が無い","ＭＤＳ金物のビス打ち不良","ころび止め金物が無い","BHK-185金物の固定ビス打ち込み不良"],"外部金物":["外部　帯金物S-45が無い","外部　帯金物S-45×2が無い","外部　帯金物S－90が無い","外部　帯金物S－90×２が無い"],"合板・壁":["合板等の釘打ち固定不良","合板の釘抜け（下地に未固定）不要な釘を抜き取り再度釘固定","耐力壁　釘打ち固定不良"],"その他箇所":["縦枠等の釘打ち不足・不良","根太と頭つなぎの釘固定が無い","サッシ下端の合板が張られていない","カーテンボックス側にクギが飛び出している。逆側からクギを打ち換えるか、飛び出している釘を切断する","防振根太にクギ打ちがされているため防振根太と根太が接触(釘外す)","床根太の穴あけが基準を超えている。構造検討の上対応すること","電気落とし込み穴、1/2（44.5㎜）ラインを超えでいる。電気施工マニュアルを参照のこと","防振根太と根太に隙間５㎜の隙間が無い","鋼製建具の下端合板に隙間あり。隙間無く合板を張ること","屋根合板の釘打ち不良"],"基礎・土間":["基礎　立上り断熱材　隙間の処理が現場発泡ウレタンで塞いでいない","土間コンクリートの端部・溝鉛直部のモルタル補修必要（完了時確認するため写真不要）"],"その他":["屋根の水上・水下の合板受け材（パッキン）：ｔ9×38×50＠150が無い","床根太の穴あけが基準を超えている。構造検討の上対応すること","竪穴区画内　日東化成株式会社（プラシール　NF-12HM）未済","竪穴区画内　熱膨張耐火材：古河テクノマテリアル　イチジカンパット　PS060WL-0695　が無い","防水の立ち上がり寸法がH=250ない","鋼製建具下（平場）の防水範囲不足","頭つなぎの貫通NG。構造検討","鋼製束がない（図面位置と相違）"],"新規追加内容":["下地材がない","頭つなぎに貫通穴をあけている。補強すること","下地取付位置間違い"]},"中間検査":{"PB関連":["PB張り不足","PB張り上げ不足。母屋たる木まで張り上げ。","PBボード開口が大き過ぎる。石膏ボード張り増しすること","ＰＢ留め付け不良※全室、全箇所確認のこと","開口部周りＰＢ留め付け不良※全室、全箇所確認のこと","竪穴区画範囲の壁PBは合板下端まで張り上げること　施工マニュアル（ＳＴ－０２－０１）確認のこと","竪穴区画範囲の壁PBは隙間なく張り付けること","壁PB施工がされていない（矩計図参照）","外壁壁はPBをモヤ下まで張りあげる","PS内の床に石膏ボード12.5張りがされていない","界壁ＰＢの床根太、床合板取合い耐火材（スキマナイト等）未処理　※全室、全箇所確認のこと"],"ビス・ビスピッチ":["ビスピッチ不良　壁：外周部＠100中間部＠200になっていない＊全住戸確認すること","150φダクト貫通部の開口補強下地に全周ビス固定＠100がされていない　※全室、全箇所確認のこと","ビスピッチ不良　天井：外周＠150中間＠200になっていない","ビスピッチ不良　壁：外周部＠100中間部＠200になっていない","ビスピッチ不良　一般壁・界壁：外周部＠100中間部＠200、天井：外周部＠150.中間部200","天井ケイカルのビスピッチ不良　外周＠150　中間＠200","開口部端部の上部ビス留めが無い　＠100㎜　施工マニュアルＦＲ－０３－０１参照"],"カーテンボックス":["カーテンボックス内、上部と側面に強化石膏ボード張りがされていない","カーテンボックス上部に断熱材がない"],"貫通部・穴あき":["梁貫通不可。構造検討の上、補強。","床根太の穴あけが基準を超えている。構造検討の上、補強。","給水管・排水管の貫通部隙間の不燃材埋め（注意喚起）","電気配線等の貫通部隙間の不燃材埋め（注意喚起）","竪穴区画内　日東化成株式会社（プラシール　NF-12HM）未済","電気配線界壁貫通","150Φダクト壁貫通位置不良。開口補強追加施工、もしくは開口補強位置是正","電気配線の縦貫通が1/2を超えている。PGで補強","壁内のダクト被覆が無い"],"防振関連":["防振根太に固定金物を使用している。防振根太から根太に固定金物位置を移動する","防振根太に固定金物使用。防振根太から根太に固定金物位置を移動","防振吊り木受け材の床根太とのクリアーなし","防振吊り木受け材のころびとのクリアーなし"],"水道関連":["施工範囲内に音ナイン等が施工されていない","縦管の音ナイン等に隙間処置をすること","基礎　立上り断熱材　隙間の処理が現場発泡ウレタンで塞いでいない"],"その他":["ニッチのサイズ不良","ニッチの設置高さ不良","界壁は野地合板まで施工","界壁の遮音シートは合板下端まで張り上げてからPB張りすること","屋根下部のサイディング施工がされていない（施工マニュアルST-02-01）","天井断熱材の防湿フィルム隙間に、テープ貼りがされていない","遮音マットが隙間無く施工されていない","断熱材上部にテープ貼りがされていない","天井断熱材の防湿フィルム継ぎ目に、テープ貼りがされていない"],"ハットジョイナー":["片ハットジョイナーが無い","片ハットジョイナー・入隅板金（入隅50）が未施工"],"ファイヤーストップ":["ファイヤーストップが無い（施工マニュアルSI-03-01参照）","最上層のファイヤーストップ未施工（施工マニュアルSI-03-01参照）","バルコニー、踊り場開口部のファイヤーストップ未施工（施工マニュアルSI-03-01参照）"],"入隅板金":["入隅板金（入隅50）、補強テープ未施工※すべての入隅確認、是正","補強テープ、入隅板金、片ハットジョイナーが無い　すべて取り付けること","入隅板金未施工（入隅50）","土台水切りが防鼠タイプを使用していない（施工マニュアルSI-02-01）","竪穴区画範囲の天井裏サイディングが一部未済（合板下端まで）。施工マニュアル（ＳＴ－０２－０１）確認のこと","手摺：透湿防水シートの施工不良（施工マニュアルSI-01-03参照）","透湿防水シート破れ","屋根下部のサイディング施工がされていない。隙間なくサイディングを張ること（施工マニュアルST-02-01参照）","一側足場部の親綱なし","樋の通り湾曲","サイディング小口未処理"],"新規追加内容":["電気配線の床貫通部未処理","ガス管の床貫通部未処理","天井PB貼り不足","壁PBジョイントあて木なし（留め付けなし）","カーテンボックス端部納まり不良","透湿防水シート貼り方不良。下から上に重ねる。","断熱材切断部にテープ貼りがされていない","スパンドレル範囲の壁PBは合板下端まで張り上げること"]},"社内検査(設計)":{"玄関":{"玄関見切り":["玄関見切りトメ仕上り不良","玄関見切り浮き","玄関見切り固定不良","玄関見切り位置是正","玄関見切り隙間","見切りとフロアタイル取り合い隙間処理","見切りとクロス取り合い 隙間リペア"],"シューズボックス":["シューズボックスのラッチ調整不十分","シューズボックス扉調整。バタンとうるさい","シューズボックス扉調整。扉傾き","シューズボックス扉調整。壁に擦る","シューズボックス扉調整。ボックスに対して斜めっている","シューズボックス扉バタンとうるさい。涙目設置","シューズボックスとクロス取り合い隙間をコーキング処理","シューズボックスリペア","シューズボックス取付位置是正","シューズボックス丁番外れ","シューズボックス建具受け用涙目設置","シューズボックスの開き勝手が逆","シューズクローク下端のコーキング未済","シューズボックス閉時隙間広い。 プッシュ金具の調整"],"玄関ドア外":["玄関戸の戸当たりなし","英文字の位置を玄関戸ライン側に是正","玄関戸固定ビスとコーキング未施工","玄関戸固定ビス頭コーキング未施工","玄関戸下のはみだし材除去","玄関戸固定シールはみ出し。サッシ固定ビスなし。","玄関戸アングルピース下隙間及び横隙間のシーリング、及び固定ビス頭コーキング未施工"],"玄関ドア扉":["玄関扉調整（異音あり）","玄関ドアクローザー調整 (異音あり)","玄関ドアレバーハンドル調整。","玄関扉英字カッティングシート剥がれ","玄関扉英字カッティングシート未施工"],"玄関ドア内":["沓摺とフロアタイル取合いコーキング処理（コーキング黒）","玄関枠下とフロアタイルに隙間あり（コーキング　白）","玄関枠ビス未施工・ビス打ち不良","玄関戸枠凹み","ビス浮き","玄関ドアと沓摺の間隙間","沓摺浮き・異音"],"巾木":["巾木下の隙間をコーキング処理（コーキング　白）","巾木下の隙間をコーキング処理（ボンドコーク　白）","巾木小口処理","巾木隙間","巾木とクロスの取合いボンドコーク処理","巾木反り"],"フロアタイル":["フロアタイルと巾木との取合い隙間あり(フロアタイル同色)","フロアタイルと玄関枠の取合い隙間あり（シーリング　床同色）","フロアタイルと沓づりの取合い隙間あり（シーリング床同色）","フロアタイル浮き","フロアタイル段差","フロアタイル隙間"],"建具関係":["建付け調整(トイレドア)","建付け調整(LDKドア)","トイレドアレバーハンドル調整","LDKドアレバーハンドル調整","LDK入口建具の上部隙間"],"戸当たり関係":["戸当たり不要。取り外し後、リペア","トイレ建具の戸当たり未施工","トイレ建具の戸当たり調整","トイレ建具の戸当たり位置是正（図面確認）"],"その他":["涙目設置(トイレドア用)","ドアスコープ傾き"]},"トイレ":{"建具関係":["レバーハンドル調整","建具固定できない","鍵がかからない","建具調整","レバーハンドルが建具枠に当たらないよう戸当たり位置調整。","戸当たりゴムパッキンカット","建具枠下隙間コーキング処理（コーキング　白）"],"タオル掛け・ペーパーホルダー":["タオル掛けがたつき","タオル掛け傾き","ペーパーホルダーがたつき","ペーパーホルダー傾き","タオル掛け、ペーパーホルダー未施工","タオル掛け、ペーパーホルダーがたつき","タオル掛け、ペーパーホルダー傾き"],"見切り":["見切り浮き","見切り建具枠隙間リペア"],"巾木関係":["巾木浮き、歪み是正","巾木小口処理","巾木下の隙間をコーキング処理（コーキング　白）","巾木下の隙間をコーキング処理（ボンドコーク　白）","巾木反り","巾木隙間","巾木留め付けフィニッシュ飛び出し"],"フロアタイル":["フロアタイルと巾木との取合い隙間あり(フロアタイル同色)","フロアタイルと枠との取合い隙間あり(フロアタイル同色)","フロアタイル段差","フロアタイル隙間","フロアタイルと見切りの間に隙間","フロアタイル浮き","フロアタイル目違い"],"便器関係":["便器と床の隙間コーキング処理","便器設置位置是正"],"サッシ関係":["サッシの鍵がかからない。建付け調整。","サッシ開閉固い。建付け調整","サッシ固定ビス傾き。是正後、ビス頭コーキング処理。","サッシ固定ビスコーキング処理なし","サッシ固定ビスなし、コーキング処理なし","サッシ固定シールはみ出し","サッシ固定シールはみ出し。サッシ固定ビスなし。","網戸の建付け調整","網戸の動きが重い","クレセント受けのビスキャップが無い","網戸なし"],"サッシ枠関係":["サッシ枠とクロスの取合いボンドコーク処理","サッシ枠の木目シート剥がれ（キズ）","サッシ枠のキズ、へこみ"],"その他":["ドアストッパー取付位置は図面確認","照明つかない","換気扇とクロス隙間あり","トイレアース線未接続","トイレ、タオル掛け、ペーパーホルダー未設置"]},"キッチン":{"ダクト関係":["ダクトのPB貫通部未処理","ダクトのPB貫通部処理不十分","ダクト未施工","ダクト被覆不十分","ダクトのPB貫通部未処理、ダクト被覆不十分"],"配管関係":["配管のPB貫通部未処理","配管のPB貫通部処理不十分","配管カバー浮き。テープ未施工","配管隙間カバー取付け","配管隙間カバー取付け、及び排水管をまっすぐにする","排水管をまっすぐにする","配管カバー未設置"],"キッチン壁・パネル":["キッチン壁がバチっているので是正","キッチン壁際の隙間調整。","キッチンパネル見切りがたつき","キッチン際のコーキング仕上り不良（凹み過ぎ）","キッチン際のコーキング仕上り不良","キッチンパネルと床の取り合い隙間コーキング処理"],"ＰＢ関係":["壁PB留め付けピッチ不良","天井PB貼り不足","PB貼り不足","ＰＢ貼り隙間あり、耐火材充填","電線のＰＢ貫通部未処理"],"床下点検口":["床下点検口のフロア材のがたつきあり（調整）","点検口枠とフロア材隙間にコーキング処理（またはリペア）","床下点検口枠固定不良","床下点検口収納ボックス固定不良","床下点検口の蓋のがたつき","床下点検口の蓋と枠との間に隙間あり（フロア材の張り伸ばし）"],"キッチンパネル関係":["キッチンパネルにキズ","キッチンパネルにへこみ","キッチンパネルとキッチンの取り合い隙間コーキング処理"],"サッシ周り関係":["サッシ固定ビスコーキング処理なし","サッシ固定ビスなし コーキング処理なし","サッシ固定シールはみ出し","サッシ固定シールはみ出し。サッシ固定ビスなし。","サッシ固定ビス傾き。是正後、ビス頭コーキング処理。","サッシの開閉が重い","サッシの鍵がかからない。建付け調整。","サッシレール歪みあり","サッシ枠とクロスの取合いボンドコーク処理","網戸の動きが重い"],"レンジフード":["レンジフード幕板リペア","レンジフード幕板調整。前面を合わせる","レンジフード幕板キズ","レンジフード幕板凹み"],"吊戸":["吊戸棚固定金具ぐらつき","吊戸扉調整","吊戸扉調整（上下隙間を合わせる）","吊戸扉調整（間が広い）","吊戸棚とクロス隙間コーキング","吊戸段差","吊戸扉調整（面を合わせる）"],"シンク":["シンク台扉調整","シンク下、排水管はまっすぐに是正"],"キャビネット":["背板未施工","キャビネット扉段差"],"その他":["左右留め具ずれ","配線廻り隙間未処理","雑巾ずり未施工"]},"LDK":{"建具関係":["レバーハンドル調整","建具上隙間コーキング","建具の戸当たり未施工","LDK建具の戸当たり調整","建具が９０度開く位置に戸当たり位置是正。","建具枠際クロス浮き","引違い戸は左が後ろ","LDK建具開閉時床に擦る","建具枠下隙間コーキング"],"巾木":["巾木浮き","掃き出しサッシ際の巾木小口未処理※両側","巾木小口処理","巾木下隙間"],"サッシ・サッシ周り関係":["サッシ固定ビスコーキング処理なし","サッシ固定ビスなし コーキング処理なし","サッシ固定シールはみ出し","サッシ固定シールはみ出し。サッシ固定ビスなし。","サッシ固定ビス傾き。是正後、ビス頭コーキング処理。","サッシレール歪みあり","サッシビス浮き","サッシビスなし","サッシビスの頭のつぶれているビスは取替え","サッシクレセント調整","サッシゴム破れ","サッシ枠際クロスコーキング処理","開閉時異音あり","開閉時重たい","開閉時ポコポコする","クレセント高さ調整","サッシ開閉固い。建付け調整。","サッシの鍵がかからない。建付け調整。","網戸の動きが重い","シャッター開閉固い","シャッター閉めた際、光が漏れる","シャッターの固定ビスコーキング処理なし","サッシ枠とクロスの取合いボンドコーク処理","サッシ枠の木目シート剥がれ（キズ）","サッシ枠のキズ、へこみ","網戸なし"],"網戸関係":["網戸調整","網戸調整。サッシ枠取合い隙間あり","網戸調整（開閉時異音あり）","網戸調整（がたつき）","網戸ヒゲカット","網戸と障子が干渉"],"ニッチ内設備リモコン":["インターホンの高さを給湯リモコンに合わせる","インターホン傾き","インターホンの位置をセンターに是正。是正後、給湯器高さ合わせる。","インターホン・スイッチの取付位置不良（施工マニュアルを確認すること）","給湯リモコンの高さをインターホンに合わせる"],"ニッチ関係":["ニッチコーク処理不良","ニッチ上端通り、仕上り不良","ニッチ枠周り、仕上り不良","ニッチサイズ是正"],"ライト・スイッチ・コンセント関係":["照明電球種類間違い（洗面室以外は電球色）","ダウンライト浮き","ダウンライト周りクロス破れ","スイッチ位置是正"],"室内物干し":["室内物干しの取り付け位置が図面と相違","室内物干し傾き"],"カーテンレール":["カーテンレール位置を是正（マニュアル参考）","カーテンレール未施工"],"フロア材関係":["階段上がり口フロア材の浮き","床鳴り","フロア材のキズ、へこみ","フロア材の段差","フロア材の隙間"],"その他":["エアコンダクト隙間あり","感知器が図面の位置と相違","床鳴り","エアコン未設置","インターホン、リモコン鋼製ＢＯＸ未使用","手摺ブラケット固定不良","笠木キズ","笠木とクロスの取合いボンドコーク処理","カーテンレール下地位置図面確認（補強の有無）"]},"バルコニー":{"軒天":["軒天サイディング留め付け材不適。釘留めとする。","軒天サイディング釘打ち間違い処理不良。きれいに処理できなければ張替え。","軒天サインディング欠け","軒天サイディング釘頭浮き","軒天サイディング釘頭処理不良"],"サイディング":["サイディング欠け・割れ","サイディング段差あり","サイディング釘頭処理不足","サイディング釘施工不足","サッシ上コーキング黒","ビスタッチアップ同色","サイディングが割れ　取替","サイディングと通気見切りに隙間あり","ビスミス跡処理不足"],"エアコンドレン":["エアコンドレン排水は溝まで延長","エアコンドレンが長過ぎる"],"排水関係":["排水溝仕上り不良","排水目皿なし","排水桝なし","排水溝勾配不良","排水溝勾配未施工","水たまりあり","オーバーフロー管周りコーキング","バルコニーのFRP防水仕上り不良","排水口ドレン周りコーキング処理不良","排水溝水たまり"],"長尺・モルタル":["長尺取合い未処理","長尺取合い仕上り不良","長尺浮き","長尺はみだし接着剤除去","長尺端部のとおりが悪い","長尺シート取合いモルタル処理"],"給湯器":["給湯器の給水管の外壁サイディング貫通部処理不十分","給湯器のガス管、追い炊き配管の外壁サイディング貫通部処理不十分","給湯器高さ1900合わせ"],"物干し・避難はしご":["物干し金物がたつき","避難はしご設置位置不適","避難はしご使用法看板設置位置不適"],"笠木":["笠木ビス傾き","笠木浮き","笠木コーキング仕上り不良"],"サッシ関係":["サッシ枠キズ","サッシガラスキズ","網戸外れ、破れ","サッシ周囲のコーキング不良"],"笠木・手摺関係":["笠木キズ","笠木ジョイント部コーキング不良","手摺固定不良","笠木下端シーリング不良"],"その他":["土台水切り納まり不良","スパンドレル内、防火ダンパー付きに変更","コーキングだれ","クレセント高さ調整","室外機未設置","笠木未施工","サッシビス飛び出し","ビス頭シールなし","排気延長配管支持金物不足","物干し金物取付不良","外壁の汚れ"]},"洋室":{"引き戸":["引き戸建具調整","左が奥に是正","引き戸の建付け調整。閉めたときに隙間あり。","引き戸建具開閉時に引っ掛かりあり","引き戸建具枠小口処理","引き戸 戸当たりクッションカット","引き戸の引手浮き調整","引き戸建具枠下とフローリングの隙間コーキング"],"クローゼット":["CL建具調整（ストッパーに位置を5㎝に是正）","CL建具開閉時に引っ掛かりあり","CL建具枠上の隙間コーキング","CL建具枠小口処理","CL建具枠のビスキャップが無い","扉と扉の接触","CL建具枠下とフローリングの隙間コーキング"],"枕棚・ハンガーパイプ":["枕棚のクロス取合い隙間","枕棚の固定不十分","枕棚の前框がたつき","枕棚上の雑巾ずり浮き。隙間コーキング処理。","枕棚上雑巾づり小口処理（両側）","枕棚上雑巾づりは前框までに是正","枕棚の取扱い注意表示・耐荷シールなし","枕棚の取扱い注意表示はがれ","枕棚天板の前框取合いの小口仕上り不良","雑巾づりと天板の隙間コーキング","ハンガーパイプ取付け不良","ハンガーパイプ固定不良","ハンガーパイプキズ"],"巾木":["巾木出隅キャップなし","巾木未施工","巾木下隙間コーキング","巾木浮き、歪み是正","巾木小口処理","巾木下の隙間をコーキング処理（ボンドコーク　白）","巾木反り","巾木とクロスの取合いボンドコーク処理","巾木下の隙間をコーキング処理（コーキング　白）"],"洋室窓周り":["雑巾摺り・前框のコーク不十分","雑巾づり上のコーク切れ"],"床・床下関係":["床鳴り","床下掃除（奥まで）","床下水替え、乾燥、清掃。設備管片付け。","床下点検口調整"],"電気関係":["照明つかない","スイッチ位置が図面と不整合","給気口傾き","給気口浮き"],"サッシ関係":["サッシの鍵がかからない。建付け調整。","サッシ開閉固い。建付け調整。","網戸の動きが重い","サッシ固定ビス傾き。是正後、ビス頭コーキング処理。","サッシ固定ビスなし コーキング処理なし","サッシ固定シールはみ出し","サッシ枠とクロスの取合いボンドコーク処理"],"フロア材関係":["床鳴り","フロア材のキズ、へこみ","フロア材の隙間"],"その他":["戸当たり未施工","戸当たり不要。取り外し後、リペア","ピクチャーレール固定不良","ピクチャーレールキズ"]},"洗面室":{"建具関係":["建具調整","片引き戸の建付け調整。閉めたときに隙間あり。","片引き戸の開閉時異音あり。","ソフトクローズ調整","ソフトクローズ取付け"],"見切り":["見切り取合い隙間リペア","見切り浮き","見切りキズリペア"],"巾木":["巾木下隙間あり","巾木未施工","巾木と枠取合い隙間コーキング処理","巾木下隙間あり（コーキング　白）","巾木下隙間あり（ボンドコーク　白）","巾木小口処理","壁クロスと巾木との取合い隙間ボンドコーク処理"],"建具枠":["枠下隙間あり（コーキング　白）","枠の下端（フロアタイル取合い）仕上り不良"],"フロアタイル":["フロアタイルと巾木との取合い隙間あり(フロアタイル同色)","フロアタイルと枠との取合い隙間あり(フロアタイル同色)","フロアタイル浮き","フロアタイル段差","フロアタイルと見切りの取合い隙間あり(フロアタイル同色)","フロアタイル目違い","フロアタイル隙間","床鳴り（フロアタイル下地合板）","床下収納庫のフロアタイル段差"],"洗面台関係":["洗面台の寄り不適","洗面化粧台扉調整（天端合わせる、上下隙間を合わせる、左右の出を合わせる）","洗面化粧台横のコーキング未施工","水道配管工事未施工","洗面台際コーキング仕上り不良","洗面化粧台底部隙間是正","洗面台 鏡の上下スキマ不揃い","洗面台の背板ビス固定が未施工"],"配管カバー":["配管カバーなし","配管カバー浮き、貼り付け","配管カバー色違い（白にする）"],"洗濯パン":["洗濯パン下部隙間 つけなおし","洗濯パン留め付けビス穴のカバーなし","洗濯パン固定不良","洗濯パン位置是正(図面に合わせる)","巾木と洗濯パン隙間処理"],"床下関係":["床下掃除（奥まで）","床下点検口調整","床下スタイロと基礎の隙間発泡ウレタン吹付け","断熱固定不良。断熱ジョイント部に隙間あり"],"UB入口枠":["UB入口下枠湾曲","UB入口下枠ビス浮き","UB入口縦枠ビス浮き","UB入口枠ビス忘れ","UB入口枠ビスの頭のつぶれているビスは取替え","UB入口下枠、枠、巾木下隙間あり（コーキング　白）","UB入口下枠下隙間あり（コーキング　白）"],"サッシ関係":["サッシの鍵がかからない。建付け調整。","サッシ開閉固い。建付け調整","サッシ固定ビスなし コーキング処理なし","サッシ固定シールはみ出し","サッシ枠とクロスの取合いボンドコーク処理","サッシ枠キズ"],"洗面台・洗濯パン":["洗面化粧台と壁の隙間コーキング不良","洗濯機パンと壁の隙間コーキング不良","洗面化粧台の扉調整","洗面台鏡のキズ"],"その他":["水漏れ原因究明の上、是正","照明電球種類間違い（洗面室は、昼白色）","給湯リモコンをスイッチの通りに合わせる","涙目位置是正 (扉が当たってしまっている)","洗面台扉段差","分電盤のカバー取付不良","換気扇の作動不良、異音","タオル掛けがたつき"]},"UB":{"UB折れ戸":["UB折れ戸調整（開閉時かたい）","UB折れ戸下枠ビス浮き","UB折れ戸縦枠ビス浮き","折れ戸とフロアタイルの間隙間処理","UB折れ戸枠ビス交換","UB折れ戸固定ビス未施工","UB折れ戸下パッキンゴム外れ"],"PB壁・天井関連":["壁PB留め付けピッチ不良","天井PB留め付けピッチ不良","壁ＰＢ貼り不足","ＰＢ貼り隙間あり、耐火材充填","ＰＢ穴あり、耐火材充填","PBビスなし","壁PBジョイントあて木なし（留め付けなし）","天井PBジョイントあて木なし（留め付けなし）"],"ダクト関連":["ダクトジョイント処理不良","ダクト支持固定不十分","ダクト余長を減らす","ダクト蛇行是正","ダクト未施工","ダクトのＰＢ貫通部未処理","ダクト被覆不十分","ダクトのＰＢ貫通部未処理、ダクト被覆不十分","ダクト材種間違い（アルミ⇒スチールに是正）"],"UB周り断熱":["UB周り断熱材未施工","UB周り断熱材貫通部未処理"],"電気配線関連":["電気配線のＰＢ貫通部未処理","電気配線のＰＢ貫通部処理不十分"],"給排水管":["音ナイン施工範囲不適","給水・給湯管のＰＢ貫通部未処理","給水・給湯管のＰＢ貫通部処理不十分"],"ガス管関連":["ガス管、追い炊き配管のＰＢ貫通部未処理","ガス管、追い炊き配管のＰＢ貫通部処理材不適。耐火材にて処理。"],"浴室暖房乾燥機":["浴室暖房乾燥機ダクト接続不良","浴室暖房乾燥機ダクト接続未施工"],"リモコン線":["リモコン線のＰＢ貫通部未処理","リモコン配線貫通部未処理"],"UB点検口":["UB点検口ふた調整。ロックがかからない","UB点検口ふたキズ"],"UB設備関連":["カウンターの傾き、固定不良","浴槽エプロンのガタつき","シャワーフックの固定不良","鏡のキズ、汚れ、固定不良","排水口の部品欠品、水はけ不良"],"その他":["断熱材フィルムカット","壁パネルのキズ、汚れ","浴槽のキズ、汚れ","コーキングの打ち忘れ、仕上がり不良","点検口の蓋のがたつき、閉まり不良","換気乾燥暖房機の作動不良、異音"]},"廊下・階段・ENT":{"排水カバー":["排水カバーはタイルまで落とす","排水カバーは土間まで落とす"],"土台水切り":["土台水切り納まり不良","土台水切り施工範囲不良","土台水切りゆがみ","土台水切りが寸足らず","土台水切りエンドキャップ取付け","土台水切りの矩が出ていない"],"サイディング":["サイディング小口未処理","サイディング小口未処理（１階廊下）","サイディング小口未処理（２階廊下）","サイディング小口未処理（３階廊下）","サイディングシール押さえ不良","サイディング納まり不良","サイディングキズ","エントランス戸上、サイディング隙間処理","エントランス戸上、サイディング納まり不良","エントランス戸枠との取り合いのサイディングは床まで張り伸ばす","１階階段下、サイディング未施工","入隅板金未施工","片ハットジョイナーが無い","釘頭のタッチアップが不十分"],"階段":["階段手すりゆがみ","階段手すり傾き。天端合わせる","階段手すり端部通り合わせる"],"長尺シート":["長尺シート納まり不良","長尺シートマス周りカット不良","長尺取合い未処理","長尺はみだし接着剤除去","３階廊下 長尺シート仕上げ不良","2階廊下 長尺シート仕上げ不良","1～2階階段 長尺シート仕上げ不良","長尺シート取合い処理不十分","長尺シート取合い未処理"],"ポーチタイル":["ポーチタイル仕上り不良","ポーチタイル浮き"],"笠木":["笠木コーキング仕上り不良","笠木のカドが鋭利","笠木ビス施工不良"],"排水関連":["排水マスなし ※長尺仕上げも是正あり","排水溝勾配未施工","排水目皿なし"],"エントランス":["エントランス戸の戸当たり未施工","トイの繋ぎが未済"],"外壁関係":["通気見切り施工不良","コーキング施工不十分","通気見切り縁エンドキャップ取付け"],"廊下内":["水たまりあり","巾木仕上り不良","消火器ＢＯＸのサイディング取合い隙間あり","サイディングと土間取り合い部のモルタル埋め未施工","巾木未施工"],"階段・手摺":["階段踏み板キズ","階段蹴込み板隙間","階段側板隙間","階段床鳴り","手摺ブラケット固定不良","手摺ジョイント部段差"],"巾木・フロア材":["巾木浮き","巾木小口処理","巾木下隙間","フロア材のキズ、へこみ"],"その他":["ストレーナーなし","１階の階段昇り口のFRP防水のマットが露出","軒天割れ","軒天釘頭処理","掲示板の取付不良、傾き","集合ポストの扉開閉不良","天井材の汚れ"]},"外部":{"杭関連":["境界杭復旧（敷地〇〇）","分筆杭復旧（敷地〇〇）","道路後退杭復旧（敷地〇〇）"],"側溝":["破損が大きい側溝蓋補修、もしくは交換","側溝掃除"],"土間コン関連・砂利・砂・砕石":["土間コンクリートひび割れ","土間コンクリートレベル是正","所定の伸縮目地なし","溝の砕石量不適。（土間とフラットにする）","溝の砕石入れ不十分","土留めブロック隣地との隙間の清掃、砂入れ","土留めブロック隣地との隙間の砂追加","土間コンクリート舗装未施工","ブロック際砕石は、単粒黒砕石20-30に是正","浸透マス砕石施工不十分","水たまりあり"],"メーター・マス":["メーター設置位置不良","メーター設置精度不良","メーター蓋清掃","メーター位置不適（図面と相違、駐車の邪魔）","最終枡に泥、ゴミあり","メーター位置不適（図面通りの位置に是正）","メーター蓋不揃い","マス天端を天端を土間レベルに合わせる","マスの蓋割れ"],"駐車場・駐輪場":["駐車場ライン剥がれ","駐車場輪留め・ライン未施工","サイクルストッパー未施工"],"排水カバー":["排水カバー未施工","排水カバーは土間まで落とす"],"散水栓":["散水栓ＢＯＸ通り不適","散水栓ボックスは建物の反対側にてメーターボックスと通りを揃える"],"受水槽":["受水槽未設置","受水槽の給水管の保温がされていない","受水槽に南京錠がついているか"],"電気設備関連":["電気配管はまっすぐに是正","スパンドレル内、防火ダンパー付きに変更","防犯カメラ未施工"],"土台水切り":["土台水切りの歪み","土台水切りのへこみ","土台水切りの角がない"],"サイディング":["エントランスの袖壁サイディングが床面までない","外壁欠けあり","目地位置図面と相違","サイデイング小口処置がされていない"],"その他":["オーバーハングゆがみ","ベントキャップキズ、へこみ","巾木仕上り不良","ゴミボックス未施工","オーバーフロー管カバー未設置","タテトイ未施工","パニックオープン未施工","笠木の角が鋭利"]}}}')

# 🛡 【絶対防御】キャッシュメモリの強制クリーンアップ
for key in ["role", "active_menu", "pre_selected_prop", "delete_target"]:
    if key not in st.session_state:
        st.session_state[key] = None

if "issue_saved" not in st.session_state:
    st.session_state.issue_saved = False

if "drill_target" not in st.session_state or not isinstance(st.session_state.drill_target, dict):
    st.session_state.drill_target = None

if "current_box" not in st.session_state or not isinstance(st.session_state.current_box, dict):
    st.session_state.current_box = None

is_partner_url = False
try:
    if hasattr(st, "query_params") and "mode" in st.query_params:
        if "partner" in str(st.query_params.get("mode", "")): is_partner_url = True
except Exception: pass

if is_partner_url:
    st.session_state.role = "partner"
    st.session_state.active_menu = "是正実施（協力業者）"

def jump_to_menu(menu_name, prop_id=None):
    st.session_state.active_menu = menu_name
    st.session_state.pre_selected_prop = prop_id
    st.session_state.drill_target = None
    st.session_state.current_box = None
    st.session_state.delete_target = None
    st.rerun()

# --- 選択肢の定義 ---
FLOOR_OPTS = ["-- 選択 --", "101","102","103","201","202","203","301","302","303","共用部","外部"]

AREA_OPTS_STANDARD = ["-- 選択 --", "玄関", "廊下・階段・ENT", "LDK", "キッチン", "洋室", "洗面室", "UB", "トイレ", "バルコニー", "外部", "その他"]
AREA_OPTS_SHANAI = ["-- 選択 --", "玄関", "トイレ", "キッチン", "LDK", "バルコニー", "洋室", "洗面室", "UB", "廊下・階段・ENT", "外部", "その他"]

WORK_OPTS_STANDARD = ["-- 選択 --", "基礎工事（鉄筋）", "基礎工事（型枠）", "フレーミング", "FM", "造作", "内装", "電気", "設備", "ガス", "清掃", "サッシ", "外壁", "外構", "コーキング", "リペア", "その他"]

WORK_OPTS_HAIKIN = ["-- 選択 --", "基礎工事(鉄筋)", "水道", "ガス", "その他"]
WORK_OPTS_KUTAI = ["-- 選択 --", "フレーミング", "電気", "水道", "防水", "その他"]
WORK_OPTS_CHUKAN = ["-- 選択 --", "造作", "電気", "水道", "外壁", "ガス", "足場", "その他"]
WORK_OPTS_SHANAI = ["-- 選択 --", "A.リペア", "B.清掃", "C.クロス", "D.造作", "E.水道", "F.電気", "G.キッチン", "H.サッシ", "I.外壁", "J.外構", "K.コーキング", "L.ガス", "板金", "Z.その他"]

INSP_OPTS = ["-- 選択 --", "配筋検査","躯体検査","断熱検査","中間検査","社内検査(設計)","社内検査(建設)","社内検査(マーケ)","社内検査(不動産)"]
SHANAI_KENSA_TYPES = ["社内検査(設計)", "社内検査(建設)", "社内検査(マーケ)", "社内検査(不動産)"]

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
        st.rerun()

    menu_opts = ["物件登録（管理者）", "検査実施（管理者）", "是正実施（協力業者）", "是正確認（管理者）", "完了分一覧（共通）"] if st.session_state.role == "admin" else ["是正実施（協力業者）", "完了分一覧（共通）"]
    if st.session_state.active_menu not in menu_opts: st.session_state.active_menu = menu_opts[0]
    selected_menu = st.sidebar.radio("MENU", menu_opts, index=menu_opts.index(st.session_state.active_menu))
    
    if selected_menu != st.session_state.active_menu:
        st.session_state.active_menu = selected_menu
        st.session_state.pre_selected_prop = None
        st.session_state.drill_target = None
        st.session_state.current_box = None
        st.session_state.delete_target = None
        st.rerun()

    # 1. 物件登録
    if st.session_state.active_menu == "物件登録（管理者）":
        st.header("物件登録")
        name = st.text_input("新規物件名")
        if st.button("登録"):
            if name: db_post("properties", {"property_id": str(uuid.uuid4()), "property_name": name}); st.success("登録完了")
        props = db_get("properties", "select=*")
        for p in props:
            prop_id = p.get('property_id')
            prop_name = p.get('property_name', '不明')
            c1, c2 = st.columns([7, 3])
            if c1.button(f"{prop_name} 検査へ", key=f"p_{prop_id}"): jump_to_menu("検査実施（管理者）", prop_id)
            
            if c2.button("削除", key=f"d_{prop_id}"):
                st.session_state.delete_target = prop_id
                st.rerun()
                
            if st.session_state.delete_target == prop_id:
                st.warning(f"⚠️ 本当に「{prop_name}」を削除しますか？紐づくすべてのデータが消えます。")
                del_pw = st.text_input("削除用パスワードを入力", type="password", key=f"pw_{prop_id}", placeholder="2011")
                col_y, col_n = st.columns(2)
                if col_y.button("Yes (削除実行)", key=f"yes_{prop_id}"):
                    if del_pw == "2011":
                        db_delete_property(prop_id)
                        st.session_state.delete_target = None
                        st.rerun()
                    else:
                        st.error("パスワードが違います")
                if col_n.button("No (キャンセル)", key=f"no_{prop_id}"):
                    st.session_state.delete_target = None
                    st.rerun()
                st.markdown("---")

    # 2. 検査実施
    elif st.session_state.active_menu == "検査実施（管理者）":
        if not st.session_state.current_box:
            st.header("検査開始")
            props = db_get("properties", "select=*")
            opts = [{"property_id": None, "property_name": "-- 選択 --"}] + props
            idx = 0
            if st.session_state.pre_selected_prop:
                for i, p in enumerate(opts):
                    if p.get('property_id') == st.session_state.pre_selected_prop: idx = i; break
            
            target = st.selectbox("物件を選択", opts, index=idx, format_func=lambda x: x.get('property_name', '不明'))
            ins_type = st.selectbox("検査種類を選択", INSP_OPTS)
            
            c1, c2 = st.columns(2)
            ins_date = c1.date_input("検査日時", datetime.date.today())
            inspector = c2.text_input("検査員", "管理者")
            
            if st.button("検査スタート"):
                prop_name = target.get('property_name')
                prop_id = target.get('property_id')
                if prop_name != "-- 選択 --" and ins_type != "-- 選択 --":
                    nid = str(uuid.uuid4())
                    db_post("inspections", {"inspection_id": nid, "property_id": prop_id, "property_name": prop_name, "inspection_type": ins_type, "inspection_date": str(ins_date), "inspector": inspector})
                    st.session_state.current_box = {"id": nid, "prop_id": prop_id, "name": prop_name, "type": ins_type}
                    st.session_state.pre_selected_prop = None; st.rerun()
                else: st.error("物件と検査種類を選んでください")
        else:
            c_name = st.session_state.current_box.get('name', '')
            c_type = st.session_state.current_box.get('type', '')
            c_id = st.session_state.current_box.get('id', '')
            c_prop_id = st.session_state.current_box.get('prop_id', '')
            
            st.subheader(f"{c_name} / {c_type}")
            if not st.session_state.issue_saved:
                ins_type = c_type
                f, a = "一式", "全体"
                
                if ins_type in SHANAI_KENSA_TYPES:
                    area_opts = AREA_OPTS_SHANAI
                    work_opts = WORK_OPTS_SHANAI
                elif ins_type == "躯体検査":
                    area_opts = AREA_OPTS_STANDARD
                    work_opts = WORK_OPTS_KUTAI
                elif ins_type == "配筋検査":
                    area_opts = AREA_OPTS_STANDARD
                    work_opts = WORK_OPTS_HAIKIN
                elif ins_type == "中間検査":
                    area_opts = AREA_OPTS_STANDARD
                    work_opts = WORK_OPTS_CHUKAN
                else:
                    area_opts = AREA_OPTS_STANDARD
                    work_opts = WORK_OPTS_STANDARD
                
                if ins_type not in ["配筋検査", "躯体検査", "中間検査"]:
                    c1, c2 = st.columns(2)
                    f = c1.selectbox("階層", FLOOR_OPTS)
                    a = c2.selectbox("部位", area_opts)
                
                cat_dict = {}
                if ins_type in ["配筋検査", "躯体検査", "中間検査"]:
                    cat_dict = ISSUE_TEMPLATES.get(ins_type, {})
                elif ins_type in SHANAI_KENSA_TYPES:
                    cat_dict = ISSUE_TEMPLATES.get("社内検査(設計)", {}).get(a, {})
                
                if not isinstance(cat_dict, dict):
                    cat_dict = {}
                
                cat_opts = ["-- 分類を選択 --"] + list(cat_dict.keys())
                sel_cat = st.selectbox("分類を選択（A列）", cat_opts)
                
                temp_list = ["-- 定型文から選ぶ --"]
                if sel_cat != "-- 分類を選択 --":
                    temp_list.extend(cat_dict.get(sel_cat, []))
                
                sel_temp = st.selectbox("よくある指摘事項（D列）", temp_list)
                desc = st.text_area("詳細・場所の追記（または定型文以外の自由入力）")
                
                # 📍【UI修正】工種のプルダウンを、詳細追記の後、写真の前に移動
                w = st.selectbox("工種を選択", work_opts)
                
                photo = st.file_uploader("撮影", type=['jpg','png','jpeg'])
                if photo: st.image(photo)
                
                if st.button("この内容で保存"):
                    final_desc = ""
                    if sel_temp != "-- 定型文から選ぶ --":
                        final_desc = sel_temp
                        if desc.strip() != "":
                            final_desc += "：" + desc.strip()
                    else:
                        final_desc = desc.strip()

                    if w != "-- 選択 --" and final_desc != "" and photo is not None:
                        db_post("inspection_records", {
                            "record_id": str(uuid.uuid4()), 
                            "inspection_id": c_id, 
                            "property_id": c_prop_id, 
                            "floor_level": f, 
                            "area": a, 
                            "work_type": w, 
                            "issue_detail": final_desc,  
                            "issue_photo_url": process_photo(photo), 
                            "progress_status": "是正待ち"
                        })
                        st.session_state.issue_saved = True
                        st.rerun()
                    else: 
                        st.error("工種・内容(定型文または自由入力)・写真はすべて必須です")
                
                if st.button("終了"): st.session_state.current_box = None; st.rerun()
            else:
                st.success("保存完了"); 
                if st.button("続けて次を登録"): st.session_state.issue_saved = False; st.rerun()
                if st.button("検査全体を終了"): st.session_state.current_box = None; st.session_state.issue_saved = False; st.rerun()

    # 3. 是正実施
    elif st.session_state.active_menu == "是正実施（協力業者）":
        st.header("是正実施")
        all_recs = db_get("inspection_records", "progress_status=eq.是正待ち")
        all_ins = db_get("inspections", "select=*")
        
        ins_map = {}
        for i in all_ins:
            if isinstance(i, dict) and i.get('inspection_id'):
                ins_map[i.get('inspection_id')] = i
                
        tree = {}
        for r in all_recs:
            if not isinstance(r, dict): continue
            ins = ins_map.get(r.get('inspection_id'))
            if ins:
                p = ins.get('property_name', '不明')
                t = ins.get('inspection_type', '不明')
                if p not in tree: tree[p] = {}
                tree[p][t] = tree[p].get(t, 0) + 1
                
        for p_name, types in tree.items():
            with st.expander(p_name):
                for t_name, count in types.items():
                    if st.button(f"{t_name} ({count}件)", key=f"f_{p_name}_{t_name}"):
                        st.session_state.drill_target = {"prop": p_name, "type": t_name}; st.rerun()
        
        sel = st.session_state.drill_target or {}
        prop_val = sel.get('prop', '')
        type_val = sel.get('type', '')
        
        if prop_val and type_val:
            if st.button("＜ 物件選択に戻る"): st.session_state.drill_target = None; st.rerun()
            
            t_ids = [str(i.get('inspection_id')) for i in all_ins if isinstance(i, dict) and i.get('property_name') == prop_val and i.get('inspection_type') == type_val and i.get('inspection_id')]
            
            if t_ids:
                recs = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.是正待ち")
                w_groups = {}
                for r in recs:
                    if not isinstance(r, dict): continue
                    w = r.get('work_type') or 'その他'
                    if w not in w_groups: w_groups[w] = []
                    w_groups[w].append(r)
                
                for w_name, w_recs in w_groups.items():
                    st.subheader(f"■ 工種: {w_name}")
                    for r in w_recs:
                        floor = r.get('floor_level', '')
                        area = r.get('area', '')
                        head_text = f"{floor} {area}".strip()
                        if floor == "一式": head_text = ""
                        
                        detail = r.get('issue_detail', '')
                        title = f"{head_text} - {detail[:15]}..." if head_text else f"{detail[:15]}..."
                        rec_id = r.get('record_id')
                        
                        with st.expander(title):
                            if r.get('reject_reason'): st.error(f"否認理由: {r.get('reject_reason')}")
                            st.write("【指摘内容】", detail)
                            if r.get('issue_photo_url'): st.image(r.get('issue_photo_url'))
                            
                            up = st.file_uploader("是正写真をアップロード", key=f"up_{rec_id}", type=['jpg','png','jpeg'])
                            if up: st.image(up, caption="アップロード画像プレビュー")
                            
                            if st.button("完了報告", key=f"s_{rec_id}"):
                                if up: 
                                    db_patch("inspection_records", rec_id, {"progress_status": "是正確認中", "fix_photo_url": process_photo(up)})
                                    st.rerun()
                                else: 
                                    st.error("写真が必要です")
            else:
                st.info("対象の項目がありません。")

    # 4. 是正確認 / 5. 完了分一覧
    elif st.session_state.active_menu in ["是正確認（管理者）", "完了分一覧（共通）"]:
        st.header(st.session_state.active_menu)
        status = "是正確認中" if "確認" in st.session_state.active_menu else "完了"
        all_recs = db_get("inspection_records", f"progress_status=eq.{status}")
        all_ins = db_get("inspections", "select=*")
        
        ins_map = {}
        for i in all_ins:
            if isinstance(i, dict) and i.get('inspection_id'):
                ins_map[i.get('inspection_id')] = i
                
        tree = {}
        for r in all_recs:
            if not isinstance(r, dict): continue
            ins = ins_map.get(r.get('inspection_id'))
            if ins:
                p = ins.get('property_name', '不明')
                t = ins.get('inspection_type', '不明')
                if p not in tree: tree[p] = set()
                tree[p].add(t)
        
        if not tree: st.info("対象の項目はありません。")
        for p_name, types in tree.items():
            with st.expander(p_name):
                for t_name in sorted(list(types)):
                    if st.button(t_name, key=f"c_{p_name}_{t_name}"):
                        st.session_state.drill_target = {"prop": p_name, "type": t_name}; st.rerun()
        
        sel = st.session_state.drill_target or {}
        prop_val = sel.get('prop', '')
        type_val = sel.get('type', '')
        
        if prop_val and type_val:
            if st.button("＜ 戻る"): st.session_state.drill_target = None; st.rerun()
            
            target_ins = None
            t_ids = []
            for i in all_ins:
                if isinstance(i, dict) and i.get('property_name') == prop_val and i.get('inspection_type') == type_val:
                    t_ids.append(str(i.get('inspection_id')))
                    if target_ins is None:
                        target_ins = i
                        
            ins_date_str = target_ins.get('inspection_date', '-') if target_ins else '-'
            inspector_str = target_ins.get('inspector', '-') if target_ins else '-'
            
            if t_ids:
                recs = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.{status}")
                
                if status == "完了":
                    html = f"""<div id="print-report-wrapper" style="background:white; padding:20px; border-radius:8px; font-family:sans-serif;">
                        <h2 style="text-align:center; margin-bottom:5px;">{prop_val}</h2><h3 style="text-align:center; margin-top:0;">{type_val}報告書</h3>
                        <div style="text-align:right; font-size:12px; color:#555; margin-bottom:10px; border-bottom:1px solid #ccc; padding-bottom:5px;">
                            <strong>検査日:</strong> {ins_date_str} &nbsp;&nbsp; <strong>検査員:</strong> {inspector_str}
                        </div>"""
                    
                    w_groups = {}
                    for r in recs:
                        if not isinstance(r, dict): continue
                        w = r.get('work_type') or 'その他'
                        if w not in w_groups: w_groups[w] = []
                        w_groups[w].append(r)
                        
                    for w_name, w_recs in w_groups.items():
                        html += f"<h4 style='margin-top:20px; border-bottom:1px solid #000;'>工種: {w_name}</h4>"
                        html += """<table style="width:100%; border-collapse:collapse; border:2px solid black; font-size:12px; text-align:center; margin-bottom:20px;">
                            <tr style="background:#eee;"><th style="border:1px solid black; padding:8px; width:5%;">No</th><th style="border:1px solid black; padding:8px; width:15%;">場所</th><th style="border:1px solid black; padding:8px; width:25%;">Before</th><th style="border:1px solid black; padding:8px; width:30%;">詳細</th><th style="border:1px solid black; padding:8px; width:25%;">After</th></tr>"""
                        for idx, r in enumerate(w_recs):
                            i_photo = r.get("issue_photo_url")
                            f_photo = r.get("fix_photo_url")
                            img_b = f'<img src="{i_photo}" style="width:100%; max-width:150px;">' if i_photo else ""
                            img_a = f'<img src="{f_photo}" style="width:100%; max-width:150px;">' if f_photo else ""
                            
                            floor = r.get('floor_level', '')
                            area = r.get('area', '')
                            loc_text = f"{floor}<br>{area}" if floor != "一式" else "-"
                            detail = r.get('issue_detail', '')
                            
                            html += f"""<tr><td style="border:1px solid black; padding:8px;">{idx+1}</td><td style="border:1px solid black; padding:8px;">{loc_text}</td><td style="border:1px solid black; padding:8px;">{img_b}</td><td style="border:1px solid black; padding:8px; text-align:left;">{detail}</td><td style="border:1px solid black; padding:8px;">{img_a}</td></tr>"""
                        html += "</table>"
                    html += "</div>"
                    st.markdown(html, unsafe_allow_html=True)
                else:
                    w_groups = {}
                    for r in recs:
                        if not isinstance(r, dict): continue
                        w = r.get('work_type') or 'その他'
                        if w not in w_groups: w_groups[w] = []
                        w_groups[w].append(r)
                    
                    for w_name, w_recs in w_groups.items():
                        st.subheader(f"■ 工種: {w_name}")
                        for r in w_recs:
                            floor = r.get('floor_level', '')
                            area = r.get('area', '')
                            detail = r.get('issue_detail', '')
                            rec_id = r.get('record_id')
                            
                            head_text = f"【{floor} {area}】".strip()
                            if floor == "一式": head_text = ""
                            title = f"{head_text} {detail}" if head_text else f"【指摘内容】 {detail}"
                            
                            st.markdown(f"**{title}**")
                            
                            c1, c2 = st.columns(2)
                            i_photo = r.get('issue_photo_url')
                            f_photo = r.get('fix_photo_url')
                            if i_photo: c1.image(i_photo, caption="Before")
                            if f_photo: c2.image(f_photo, caption="After")
                            
                            ca, cb = st.columns(2)
                            if ca.button("✅ 承認（完了へ）", key=f"ok_{rec_id}"): 
                                db_patch("inspection_records", rec_id, {"progress_status": "完了"})
                                st.rerun()
                            
                            reason = cb.text_input("否認理由を入力", key=f"re_{rec_id}", label_visibility="collapsed", placeholder="否認理由があれば入力")
                            if cb.button("❌ 否認（差し戻し）", key=f"ng_{rec_id}"): 
                                db_patch("inspection_records", rec_id, {"progress_status": "是正待ち", "reject_reason": reason})
                                st.rerun()
                            
                            st.markdown("---") 

if __name__ == "__main__":
    main()
