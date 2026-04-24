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
# 2. UI設定 (白背景に完全リセット・文字化けなし)
# ==========================================
st.set_page_config(page_title="Felix検査App", layout="wide")

st.markdown("""
<style>
    div.stButton > button {
        border-radius: 6px; height: 50px; font-weight: bold; width: 100%; margin-bottom: 5px;
    }
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 定型文データ (2重プルダウン・全608項目 完全版)
# ==========================================
ISSUE_TEMPLATES = json.loads('{"配筋検査":{"定着関連":["定着不良","定着不足"],"人通口関連":["人通口の補強筋（コの字）不良","人通口なし","人通口不要"],"重ね継手":["重ね継手不良"],"スラブ筋":["第１スラブ筋が無い"],"その他":["埋設配管が鉄筋に接触 スリーブ補強不良","スリーブ補強筋がない","土除去 防湿フィルム破れ"],"新規追加内容":["FG4コンクリート打ちが図面と不整合のため是正","鉄筋のあきが取れていない 粗骨材の最大寸法の1.25倍以上かつ25㎜以上確認","人通口の端末筋の定着がスラブに伸びているため、梁定着にする"]},"躯体検査":{"内部金物":["ホールダウン金物取付不良","大引き金物の取付不良","金物（〇〇）の釘打ち不良","MDC-５Sが無い","MDC-5の固定不良","MDS-10Nが無い","MDS-10Nの固定不良","あおり止め金物が無い","ＭＤＳ金物のビス打ち不良","ころび止め金物が無い","BHK-185金物の固定ビス打ち込み不良"],"外部金物":["外部　帯金物S-45が無い","外部　帯金物S-45×2が無い","VPの固定不良","S-65の固定不良","TS金物の固定不良","コーナー金物の固定不良"],"釘打ち関連":["大引きの釘打ち不良","根太の釘打ち不良","合板の釘打ち不良。＠150","合板の釘めり込み","合板が柱・スタッドに掛かっていない","合板目地が空いていない","壁合板の釘打ち不良。＠100","壁合板の釘打ち不良。＠150","合板がスタッドに掛かっていない","合板の目地が空いていない","開口補強の釘打ち不良","屋根合板の釘打ち不良。＠150","合板がたる木に掛かっていない"],"防腐・防蟻処理":["防腐防蟻処理の塗布忘れ、もしくは処理不足","防腐防蟻処理の塗布忘れ、もしくは処理不足（玄関）","防腐防蟻処理の塗布忘れ、もしくは処理不足（ＵＢ）"],"継手・欠き込み関連":["頭つなぎの継手位置不良。スタッド上で継ぐ","上枠の継手位置不良。スタッド上で継ぐ","204の欠き込みが大きすぎるため補強が必要","スタッドの切り詰めが不適（スタッドの補強が必要）","マグサの施工不良"],"屋根関連":["ころび止め未施工","あおり止め金物未施工","あおり止め金物釘打ち不良","たる木ひねり金物（TS）の施工忘れ、もしくは施工不良"],"その他金物":["各種金物の施工忘れ、もしくは施工不良","各種金物の釘打ち不良"]},"中間検査":{"PB関連":["PB張り不足","PB張り上げ不足。母屋たる木まで張り上げ。","PBボード開口が大き過ぎる。石膏ボード張り増しすること","ＰＢ留め付け不良※全室、全箇所確認のこと","開口部周りＰＢ留め付け不良※全室、全箇所確認のこと","竪穴区画範囲の壁PBは合板下端まで張り上げること　施工マニュアル（ＳＴ－０２－０１）確認のこと","竪穴区画範囲の壁PBは隙間なく張り付けること","壁PB施工がされていない（矩計図参照）","外壁壁はPBをモヤ下まで張りあげる","PS内の床に石膏ボード12.5張りがされていない","界壁ＰＢの床根太、床合板取合い耐火材（スキマナイト等）未処理　※全室、全箇所確認のこと","壁PBジョイントあて木なし（留め付けなし）"],"ビス・ビスピッチ":["ビスピッチ不良　壁：外周部＠100中間部＠200になっていない＊全住戸確認すること","150φダクト貫通部の開口補強下地に全周ビス固定＠100がされていない　※全室、全箇所確認のこと　","ボードビスなし　※全室、全箇所確認のこと"],"界壁関連":["界壁の遮音シートは、野地合板まで施工すること","界壁は野地合板まで施工"],"貫通部・隙間処理":["縦管の音ナイン等に隙間処置をすること","施工範囲内に音ナイン等が施工されていない","電気配線界壁貫通","竪穴区画内　日東化成株式会社（プラシール　NF-12HM）未済","電気配線等の貫通部隙間の不燃材埋め（注意喚起）","各種配管等の貫通部隙間の不燃材埋め","150Φダクトの貫通部隙間不燃材（ロックウール等）埋め","基礎と土台の隙間処理（現場発泡ウレタン）が施工されていない　※外周部と玄関土間周り"],"ダクト・配線関連":["壁内のダクト被覆が無い","電気配線の縦貫通が1/2を超えている。PGで補強","150Φダクト壁貫通位置不良。開口補強追加施工、もしくは開口補強位置是正","鋼製ダクト（スパイラル管）未施工"],"防振関連":["防振根太に固定金物を使用している。防振根太から根太に固定金物位置を移動する","防振根太に固定金物使用。防振根太から根太に固定金物位置を移動","防振吊り木受け材の床根太とのクリアーなし","防振吊り木受け材のころびとのクリアーなし"],"水道関連":["基礎　立上り断熱材　隙間の処理が現場発泡ウレタンで塞いでいない"],"その他":["ニッチのサイズ不良","ニッチの設置高さ不良","壁の断熱材が隙間なく充填されていない","壁の断熱材が防湿フィルムで覆われていない（耳を柱に見付けタッカー留め）","コンセントボックス、スイッチボックス周りの防湿処理が不十分","床の断熱材が隙間なく充填されていない（大引きとの取合い・配管周り等の隙間など）","床の断熱材が専用ピンで大引き等に密着するよう留め付けられていない","天井の断熱材が隙間なく充填されていない（各種配線、配管等の貫通部の隙間など）","天井の断熱材が防湿フィルムで覆われていない（耳を野縁に見付けタッカー留め）","ダウンライト等の天井開口部周りの断熱処理不十分","点検口等の開口部周りの断熱処理不十分","バルコニー等の直下部における天井断熱材が隙間なく充填されていない","外断熱材のジョイント部における気密テープ処理不十分","外断熱材の開口部周りにおける気密テープ処理不十分","サッシ周りの断熱処理不十分（現場発泡ウレタン等）","玄関ドア周りの断熱処理不十分（現場発泡ウレタン等）","浴室周りの断熱処理（基礎断熱、壁断熱、天井断熱）が不十分","ユニットバス下部の基礎断熱処理不十分","通気層が確保されていない（外壁、屋根など）","通気層の入り口（土台水切り部など）が塞がれている","通気層の出口（軒天、棟部など）が塞がれている","防湿フィルムの破れ、剥がれがある場合は補修テープで処理すること","防湿フィルムのジョイント部における重なり幅が不足している","防湿フィルムのジョイント部におけるテープ処理不十分","外壁透湿防水シートの破れ、剥がれがある場合は補修テープで処理すること","外壁透湿防水シートのジョイント部における重なり幅が不足している","外壁透湿防水シートのジョイント部におけるテープ処理不十分","サッシ周りの防水テープ処理不十分","配管等の貫通部周りの防水テープ処理不十分","バルコニー防水層（FRP等）の施工不良（ひび割れ、浮き、ピンホールなど）","バルコニー防水層の立ち上がり高さ不足","バルコニー防水層とサッシ等の取合い部における防水処理不十分","屋根葺き材の施工不良（割れ、浮き、ズレなど）","屋根ルーフィングの破れ、剥がれがある場合は補修テープで処理すること","屋根ルーフィングのジョイント部における重なり幅が不足している","屋根ルーフィングの谷部、ケラバ部等における増張り処理不十分"]},"社内検査(設計)":{"玄関":{"玄関見切り":["玄関見切りトメ仕上り不良","玄関見切り浮き","玄関見切り固定不良","玄関見切り位置是正","玄関見切り隙間","見切りとフロアタイル取り合い隙間処理","見切りとクロス取り合い 隙間リペア"],"シュIズボックス":["シューズボックスのラッチ調整不十分","シューズボックス扉調整。バタンとうるさい","シューズボックス扉調整。扉傾き","シューズボックス扉調整。壁に擦る","シューズボックス扉調整。ボックスに対して斜めっている","シューズボックス扉バタンとうるさい。涙目設置","シューズボックスとクロス取り合い隙間をコーキング処理","シューズボックスリペア","シューズボックス取付位置是正","シューズボックス丁番外れ","シューズボックス建具受け用涙目設置","シューズボックスの開き勝手が逆","シューズクローク下端のコーキング未済","シューズボックス閉時隙間広い。 プッシュ金具の調整"],"玄関ドア外":["玄関戸の戸当たりなし","英文字の位置を玄関戸ライン側に是正","玄関戸固定ビスとコーキング未施工","玄関戸固定ビス頭コーキング未施工","玄関戸下のはみだし材除去","玄関戸固定シールはみ出し。サッシ固定ビスなし。","玄関戸アングルピース下隙間及び横隙間のシーリング、及び固定ビス頭コーキング未施工","玄関戸下のはみ出しシール材カット"],"玄関ドア扉":["玄関戸キズあり。リペア","玄関戸丁番のビスキャップが無い","玄関戸の開閉かたい","玄関戸凹み","玄関戸へこみキズあり"],"土間・タイル":["玄関戸外の土間のモルタル仕上り不良","玄関戸内の土間のモルタル仕上り不良","玄関戸外の土間のモルタル汚れ、白華","玄関戸内の土間のモルタル汚れ、白華","玄関タイルの目地不良","玄関タイルの割れ、欠け","玄関タイルの浮き"],"ポIチ・階段":["玄関ポーチの階段蹴上げ高さ不均一","玄関ポーチの階段踏面勾配不良（水たまり）"],"手摺":["玄関手摺の固定不良（がたつき）","玄関手摺の高さ、位置不良"],"電気設備":["照明器具の点灯不良","スイッチ、コンセントのプレート曲がり、隙間","分電盤のカバー取付不良","分電盤内の結線不良、表示間違い","火災報知器の設置位置不良","インターホンの作動不良"],"外部設備":["ポストの取付不良、傾き","表札の取付不良、傾き","宅配ボックスの作動不良","外水栓の漏水、固定不良","雨水桝の高さ不良（土間とフラットでない）","汚水桝の高さ不良（土間とフラットでない）"],"基礎まわり":["基礎巾木のモルタル仕上り不良","基礎巾木のモルタル汚れ、白華"],"外壁・軒天":["外壁サイディングの汚れ、キズ","外壁サイディングのシーリング不良","軒天の汚れ、キズ","軒天の塗装不良"]},"トイレ":{"建具関係":["レバーハンドル調整","建具固定できない","鍵がかからない","建具調整","レバーハンドルが建具枠に当たらないよう戸当たり位置調整。","戸当たりゴムパッキンカット","建具枠下隙間コーキング処理（コーキング　白）"],"タオル掛け・ペlパlホルダl":["タオル掛けがたつき","タオル掛け傾き","ペーパーホルダーがたつき","ペーパーホルダー傾き","タオル掛け、ペーパーホルダー未施工","タオル掛け、ペーパーホルダーがたつき","タオル掛け、ペーパーホルダー傾き"],"見切り":["見切り浮き","見切り建具枠隙間リペア"],"巾木関係":["巾木浮き、歪み是正","巾木小口処理","巾木下の隙間をコーキング処理（コーキング　白）","巾木下の隙間をコーキング処理（ボンドコーク　白）","巾木反り","巾木留め付けビス頭処理（同色ボンドコーク）"],"便器関係":["便器の固定不良（がたつき）","便器からの漏水","ウォシュレットの作動不良"],"手洗い器":["手洗い器の固定不良（がたつき）","手洗い器からの漏水"],"換気・電気設備":["換気扇の作動不良、異音","照明器具の点灯不良","スイッチ、コンセントのプレート曲がり、隙間"],"サッシ・窓枠":["窓サッシの開閉不良","窓サッシの鍵（クレセント）作動不良","窓枠のキズ、汚れ"],"クロス":["壁クロスの剥がれ、浮き、汚れ"]},"キッチン":{"ダクト関係":["ダクトのPB貫通部未処理","ダクトのPB貫通部処理不十分","ダクト未施工","ダクト被覆不十分","ダクトのPB貫通部未処理、ダクト被覆不十分"],"配管関係":["配管のPB貫通部未処理","配管のPB貫通部処理不十分","配管カバー浮き。テープ未施工","配管隙間カバー取付け","配管隙間カバー取付け、及び排水管をまっすぐにする","排水管をまっすぐにする","配管カバー未設置"],"キッチン壁・パネル":["キッチン壁がバチっているので是正","キッチン壁際の隙間調整。","キッチンパネル見切りがたつき","キッチン際のコーキング仕上り不良（凹み過ぎ）","キッチン際のコーキング仕上り不良","キッチンパネルと床の取り合い隙間コーキング処理"],"ＰＢ関係":["壁PB留め付けピッチ不良","天井PB貼り不足","PB貼り不足"],"キッチンパネル関係":["キッチンパネルのキズ、汚れ","キッチンパネルのジョイント部処理不良"],"各種設備関係":["システムキッチンの扉調整（傾き、段差）","システムキッチンの引き出し調整（がたつき、干渉）","システムキッチンの取手固定不良","シンクのキズ、汚れ","水栓金具の固定不良（がたつき）","水栓金具からの漏水","浄水器の作動不良","食洗機の作動不良、水漏れ","IHクッキングヒーター／ガスコンロの作動不良","レンジフードの作動不良、異音","吊戸棚の固定不良","床下収納庫の枠のがたつき、段差","床下収納庫の蓋の開閉不良","照明器具の点灯不良","スイッチ、コンセントのプレート曲がり、隙間","給気口の作動不良"],"床フローリング":["床フローリングのキズ、汚れ、床鳴り"]},"LDK":{"建具関係":["レバーハンドル調整","建具上隙間コーキング","建具の戸当たり未施工","LDK建具の戸当たり調整","建具が９０度開く位置に戸当たり位置是正。","建具枠際クロス浮き","引違い戸は左が後ろ","LDK建具開閉時床に擦る","建具枠下隙間コーキング"],"巾木":["巾木浮き","掃き出しサッシ際の巾木小口未処理※両側","巾木小口処理","巾木下隙間"],"サッシ・サッシ周り関係":["サッシ固定ビスコーキング処理なし","サッシ固定ビスなし コーキング処理なし","サッシ固定シールはみ出し","サッシ固定シールはみ出し。サッシ固定ビスなし。","サッシ固定ビス傾き。是正後、ビス頭コーキング処理。","サッシレール歪みあり","サッシの開閉が重い","サッシの鍵（クレセント）がかかりにくい","網戸の動きが悪い、外れやすい","網戸の破れ、たるみ","サッシ枠のキズ、へこみ","窓枠（膳板）のキズ、汚れ"],"クロス関係":["壁クロスの剥がれ、浮き、汚れ、隙間","天井クロスの剥がれ、浮き、汚れ、隙間"],"床フローリング":["床フローリングのキズ、へこみ、汚れ","床鳴り（歩行時の異音）","床の不陸（傾き、段差）"],"階段関連":["階段の踏み鳴り、きしみ","階段手摺の固定不良（がたつき）","階段の蹴込み板、側板の隙間"],"電気設備関連":["照明器具の点灯不良","スイッチ、コンセントのプレート曲がり、隙間","TV端子、LAN端子の導通不良","エアコンスリーブのキャップ未設置","24時間換気口の作動不良","火災報知器の設置位置不良"]},"バルコニー":{"軒天":["軒天サイディング留め付け材不適。釘留めとする。","軒天サイディング釘打ち間違い処理不良。きれいに処理できなければ張替え。","軒天サインディング欠け","軒天サイディング釘頭浮き","軒天サイディング釘頭処理不良"],"サイディング":["サイディング欠け・割れ","サイディング段差あり","サイディング釘頭処理不足","サイディング釘施工不足","サッシ上コーキング黒","ビスタッチアップ同色","サイディングが割れ　取替","サイディングと通気見切りに隙間あり","ビスミス跡処理不足"],"エアコンドレン":["エアコンドレン排水は溝まで延長","エアコンドレンが長過ぎる"],"排水関係":["排水溝仕上り不良","排水目皿なし","排水桝なし"],"その他":["バルコニー手摺の固定不良（がたつき）","バルコニー手摺のキズ、汚れ","物干し金物の固定不良、高さ・位置不良","FRP防水層のひび割れ、浮き","FRP防水層のトップコート色ムラ、剥がれ","バルコニーサッシ下端の防水処理不良","バルコニーの勾配不良（水たまり）","外壁サイディングのジョイント部シーリング不良","笠木のジョイント部シーリング不良","笠木の固定不良、キズ"]},"洋室":{"引き戸":["引き戸建具調整","左が奥に是正","引き戸の建付け調整。閉めたときに隙間あり。","引き戸建具開閉時に引っ掛かりあり","引き戸建具枠小口処理","引き戸 戸当たりクッションカット","引き戸の引手浮き調整","引き戸建具枠下とフローリングの隙間コーキング"],"クロlゼット":["CL建具調整（ストッパーに位置を5㎝に是正）","CL建具開閉時に引っ掛かりあり","CL建具枠上の隙間コーキング","CL建具枠小口処理","CL建具枠のビスキャップが無い","扉と扉の接触","CL建具枠下とフローリングの隙間コーキング"],"枕棚・ハンガlパイプ":["枕棚のクロス取合い隙間","枕棚の固定不十分","枕棚の前框がたつき","枕棚上の雑巾ずり浮き","ハンガーパイプの固定不良（がたつき）","ハンガーパイプのキズ"],"クロス関係":["壁クロスの剥がれ、浮き、汚れ、隙間","天井クロスの剥がれ、浮き、汚れ、隙間"],"床フローリング":["床フローリングのキズ、へこみ、汚れ","床鳴り（歩行時の異音）"],"巾木":["巾木浮き、隙間","巾木小口処理"],"サッシ関係":["サッシの開閉が重い","サッシの鍵（クレセント）がかかりにくい","網戸の動きが悪い、外れやすい","網戸の破れ、たるみ","窓枠（膳板）のキズ、汚れ"],"電気設備関連":["照明器具（シーリングローゼット）の取付不良","スイッチ、コンセントのプレート曲がり、隙間","TV端子、LAN端子の導通不良","エアコンスリーブのキャップ未設置","24時間換気口の作動不良","火災報知器の設置位置不良"]},"洗面室":{"建具関係":["建具調整","片引き戸の建付け調整。閉めたときに隙間あり。","片引き戸の開閉時異音あり。","ソフトクローズ調整","ソフトクローズ取付け"],"見切り":["見切り取合い隙間リペア","見切り浮き","見切りキズリペア"],"巾木":["巾木下隙間あり","巾木未施工","巾木と枠取合い隙間コーキング処理","巾木下隙間あり（コーキング　白）","巾木下隙間あり（ボンドコーク　白）","巾木小口処理","壁クロスと巾木との取合い隙間ボンドコーク処理"],"建具枠":["枠下隙間あり（コーキング　白）","枠の下端（フロアタイル取合い）仕上り不良"],"フロアタイル":["フロアタイルと巾木との取合い隙間あり(フロアタイルカットし過ぎ)","フロアタイルの浮き、剥がれ","フロアタイルのキズ、汚れ"],"洗面化粧台":["洗面化粧台の扉調整（傾き、段差）","洗面化粧台の引き出し調整（がたつき）","洗面ボウルのキズ、汚れ","水栓金具からの漏水","排水管からの漏水","洗面化粧台と壁の隙間コーキング不良"],"洗濯機関係":["洗濯機パンの固定不良","洗濯機パンの排水トラップ未設置、緩み","洗濯機用水栓の固定不良、漏水"],"クロス関係":["壁クロスの剥がれ、浮き、汚れ","天井クロスの剥がれ、浮き、汚れ"],"換気・電気設備":["換気扇の作動不良、異音","照明器具の点灯不良","スイッチ、コンセントのプレート曲がり、隙間"],"床下点検口":["床下点検口の枠のがたつき、段差"],"分電盤":["分電盤のカバー取付不良"]},"UB":{"UB折れ戸":["UB折れ戸調整（開閉時かたい）","UB折れ戸下枠ビス浮き","UB折れ戸縦枠ビス浮き","折れ戸とフロアタイルの間隙間処理","UB折れ戸枠ビス交換","UB折れ戸固定ビス未施工","UB折れ戸下パッキンゴム外れ"],"PB壁・天井関連":["壁PB留め付けピッチ不良","天井PB留め付けピッチ不良","壁ＰＢ貼り不足","ＰＢ貼り隙間あり、耐火材充填","ＰＢ穴あり、耐火材充填","PBビスなし","壁PBジョイントあて木なし（留め付けなし）","天井PBジョイントあて木なし（留め付けなし）"],"ダクト関連":["ダクトジョイント処理不良","ダクト支持固定不十分","ダクト余長を減らす","ダクト蛇行是正","ダクト未施工"],"浴槽・洗い場関係":["浴槽のキズ、汚れ","洗い場床のキズ、汚れ、水はけ不良","壁パネルのキズ、汚れ","天井パネルのキズ、汚れ"],"水栓金具・シャワl関係":["水栓金具の固定不良、漏水","シャワーフックの固定不良"],"鏡・カウンタl・棚関係":["鏡のキズ、汚れ、固定不良","カウンターの傾き、固定不良","タオル掛け、収納棚の固定不良"],"電気設備関係":["照明器具の点灯不良","換気乾燥暖房機の作動不良、異音"],"その他":["排水口の部品欠品、水はけ不良","コーキングの打ち忘れ、仕上がり不良","点検口の蓋のがたつき、閉まり不良","給湯器リモコンの作動不良","窓サッシの開閉不良、鍵作動不良","ブラインドの作動不良","浴槽エプロンのガタつき"]},"廊下・階段・ENT":{"排水カバl":["排水カバーはタイルまで落とす","排水カバーは土間まで落とす"],"土台水切り":["土台水切り納まり不良","土台水切り施工範囲不良","土台水切りゆがみ","土台水切りが寸足らず","土台水切りエンドキャップ取付け","土台水切りの矩が出ていない"],"サイディング":["サイディング小口未処理","サイディング小口未処理（１階廊下）","サイディング小口未処理（２階廊下）","サイディング小口未処理（３階廊下）","サイディングシール押さえ不良","サイディング納まり不良","サイディングキズ","エントランス戸上、サイディング隙間処理"],"共用部廊下":["共用部廊下の長尺シート浮き、剥がれ","共用部廊下の長尺シート端部シール不良"],"共用部階段":["共用部階段のノンスリップ金物固定不良","共用部階段の長尺シート浮き、剥がれ"],"手摺関係":["手摺の固定不良（がたつき）、キズ"],"雨樋関係":["雨樋（竪樋）の固定不良、傾き","雨樋（這樋）の固定不良"],"電気設備関連":["照明器具の点灯不良","スイッチ、コンセントのプレート曲がり、隙間"],"消火・避難器具":["消火器の設置不良","避難器具（ハッチ等）の作動不良"],"掲示板関係":["掲示板の取付不良、傾き"],"集合ポスト":["集合ポストの扉開閉不良"],"オlトロック":["オートロック盤の作動不良"],"天井・壁関係":["天井材（ジプトーン等）の割れ、汚れ","壁材（塗装等）のムラ、汚れ"],"巾木関係":["巾木の浮き、剥がれ"],"メlタlボックス":["メーターボックスの扉開閉不良","メーターボックス内の配管保温材不良"]},"外部":{"杭関連":["境界杭復旧（敷地〇〇）","分筆杭復旧（敷地〇〇）","道路後退杭復旧（敷地〇〇）"],"側溝":["破損が大きい側溝蓋補修、もしくは交換","側溝掃除"],"土間コン関連・砂利・砂・砕石":["土間コンクリートひび割れ","土間コンクリートレベル是正","所定の伸縮目地なし","溝の砕石量不適。（土間とフラットにする）","溝の砕石入れ不十分","土留めブロック隣地との隙間の清掃、砂入れ","土留めブロック隣地との隙間の砂追加","土間コンクリート舗装未施工","ブロック際砕石は、単粒黒砕石20-30に是正","浸透マス砕石施工不十分","水たまりあり"],"メlタl・マス":["メーター設置位置不良","メーター設置精度不良","メーター蓋清掃","メーター位置不適（図面と相違、駐車の邪魔）","最終枡に泥、ゴミあり"],"駐車場\n駐輪場":["駐車場ライン剥がれ","駐車場輪留め・ライン未施工","サイクルストッパー未施工"],"排水カバl":["排水カバー未施工","排水カバーは土間まで落とす"],"散水栓":["散水栓ＢＯＸ通り不適","散水栓ボックスは建物の反対側にてメーターボックスと通りを揃える"],"受水槽":["受水槽未設置","受水槽の給水管の保温がされていない","受水槽に南京錠がついているか"],"電気設備関連":["電気配管はまっすぐに是正","スパンドレル内、防火ダンパー付きに変更","防犯カメラ未施工"],"土台水切り":["土台水切りの歪み","土台水切りのへこみ","土台水切りの角がない"],"サイディング":["エントランスの袖壁サイディングが床面までない","外壁欠けあり","目地位置図面と相違","サイデイング小口処置がされていない"],"その他":["オーバーハングゆがみ","ベントキャップキズ、へこみ","巾木仕上り不良","ゴミボックス未施工","オーバーフロー管カバー未設置","タテトイ未施工","パニックオープン未施工","笠木の角が鋭利"]}}')

# --- セッションステート管理 ---
if "role" not in st.session_state: st.session_state.role = None
if "active_menu" not in st.session_state: st.session_state.active_menu = None
if "current_box" not in st.session_state: st.session_state.current_box = None
if "issue_saved" not in st.session_state: st.session_state.issue_saved = False
if "pre_selected_prop" not in st.session_state: st.session_state.pre_selected_prop = None

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
    st.rerun()

FLOOR_OPTS = ["-- 選択 --", "101","102","103","201","202","203","301","302","303","共用部","外部"]
AREA_OPTS = ["-- 選択 --", "玄関", "廊下・階段・ENT", "LDK", "キッチン", "洋室", "洗面室", "UB", "トイレ", "バルコニー", "外部", "その他"]
WORK_OPTS = ["-- 選択 --", "基礎工事（鉄筋）", "基礎工事（型枠）", "フレーミング", "FM", "造作", "内装", "電気", "設備", "ガス", "清掃", "サッシ", "外壁", "外構", "コーキング", "リペア", "その他"]
INSP_OPTS = ["-- 選択 --", "配筋検査","躯体検査","断熱検査","中間検査","社内検査(設計)","社内検査(建設)","社内検査(マーケ)","社内検査(不動産)"]

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
        st.session_state.active_menu = selected_menu; st.session_state.pre_selected_prop = None; st.rerun()

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
            idx = 0
            if st.session_state.pre_selected_prop:
                for i, p in enumerate(opts):
                    if p['property_id'] == st.session_state.pre_selected_prop: idx = i; break
            target = st.selectbox("物件を選択", opts, index=idx, format_func=lambda x: x['property_name'])
            ins_type = st.selectbox("検査種類を選択", INSP_OPTS)
            if st.button("検査スタート"):
                if target['property_name'] != "-- 選択 --" and ins_type != "-- 選択 --":
                    nid = str(uuid.uuid4())
                    db_post("inspections", {"inspection_id": nid, "property_id": target['property_id'], "property_name": target['property_name'], "inspection_type": ins_type, "inspection_date": str(datetime.date.today()), "inspector": "管理者"})
                    st.session_state.current_box = {"id": nid, "prop_id": target['property_id'], "name": target['property_name'], "type": ins_type}
                    st.session_state.pre_selected_prop = None; st.rerun()
                else: st.error("物件と検査種類を選んでください")
        else:
            st.subheader(f"{st.session_state.current_box['name']} / {st.session_state.current_box['type']}")
            if not st.session_state.issue_saved:
                ins_type = st.session_state.current_box['type']
                f, a = "一式", "全体"
                
                if ins_type not in ["配筋検査", "躯体検査", "中間検査"]:
                    c1, c2 = st.columns(2)
                    f = c1.selectbox("階層", FLOOR_OPTS)
                    a = c2.selectbox("部位", AREA_OPTS)
                
                w = st.selectbox("工種を選択", WORK_OPTS)
                
                # --- 2重プルダウンロジック ---
                cat_dict = {}
                if ins_type in ["配筋検査", "躯体検査", "中間検査"]:
                    cat_dict = ISSUE_TEMPLATES.get(ins_type, {})
                elif ins_type == "社内検査(設計)":
                    cat_dict = ISSUE_TEMPLATES.get("社内検査(設計)", {}).get(a, {})
                
                # 1. 分類(A列)のプルダウン
                cat_opts = ["-- 分類を選択 --"] + list(cat_dict.keys())
                sel_cat = st.selectbox("分類を選択（A列）", cat_opts)
                
                # 2. 定型文(D列)のプルダウン
                temp_list = ["-- 定型文から選ぶ --"]
                if sel_cat != "-- 分類を選択 --":
                    temp_list.extend(cat_dict.get(sel_cat, []))
                
                sel_temp = st.selectbox("よくある指摘事項（D列）", temp_list)
                # ------------------------------
                
                desc = st.text_area("詳細・場所の追記（または定型文以外の自由入力）")
                
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
                            "inspection_id": st.session_state.current_box['id'], 
                            "property_id": st.session_state.current_box['prop_id'], 
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
        ins_map = {i['inspection_id']: i for i in all_ins}
        tree = {}
        for r in all_recs:
            ins = ins_map.get(r['inspection_id'])
            if ins:
                p, t = ins['property_name'], ins['inspection_type']
                if p not in tree: tree[p] = {}
                tree[p][t] = tree[p].get(t, 0) + 1
        for p_name, types in tree.items():
            with st.expander(p_name):
                for t_name, count in types.items():
                    if st.button(f"{t_name} ({count}件)", key=f"f_{p_name}_{t_name}"):
                        st.session_state.drill_target = {"prop": p_name, "type": t_name}; st.rerun()
        if st.session_state.drill_target:
            if st.button("＜ 物件選択に戻る"): st.session_state.drill_target = None; st.rerun()
            sel = st.session_state.drill_target
            t_ids = [i['inspection_id'] for i in db_get("inspections", f"property_name=eq.{sel['prop']}&inspection_type=eq.{sel['type']}")]
            recs = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.是正待ち")
            for r in recs:
                with st.expander(f"{r.get('floor_level')} {r.get('area')} - {r.get('work_type')}"):
                    if r.get('reject_reason'): st.error(f"否認理由: {r['reject_reason']}")
                    st.write(r.get('issue_detail',''))
                    if r.get('issue_photo_url'): st.image(r['issue_photo_url'])
                    up = st.file_uploader("是正写真をアップロード", key=f"up_{r['record_id']}", type=['jpg','png','jpeg'])
                    if st.button("完了報告", key=f"s_{r['record_id']}"):
                        if up: db_patch("inspection_records", r['record_id'], {"progress_status": "是正確認中", "fix_photo_url": process_photo(up)}); st.rerun()
                        else: st.error("写真が必要です")

    # 4. 是正確認 / 5. 完了分一覧
    elif st.session_state.active_menu in ["是正確認（管理者）", "完了分一覧（共通）"]:
        st.header(st.session_state.active_menu)
        status = "是正確認中" if "確認" in st.session_state.active_menu else "完了"
        all_recs = db_get("inspection_records", f"progress_status=eq.{status}")
        all_ins = db_get("inspections", "select=*")
        ins_map = {i['inspection_id']: i for i in all_ins}
        tree = {}
        for r in all_recs:
            ins = ins_map.get(r['inspection_id'])
            if ins:
                p, t = ins['property_name'], ins['inspection_type']
                if p not in tree: tree[p] = set()
                tree[p].add(t)
        for p_name, types in tree.items():
            with st.expander(p_name):
                for t_name in types:
                    if st.button(t_name, key=f"c_{p_name}_{t_name}"):
                        t_ids = [i['inspection_id'] for i in db_get("inspections", f"property_name=eq.{p_name}&inspection_type=eq.{t_name}")]
                        recs = db_get("inspection_records", f"inspection_id=in.({','.join(t_ids)})&progress_status=eq.{status}")
                        for r in recs:
                            with st.expander(f"{r.get('floor_level')} {r.get('area')}"):
                                c1, c2 = st.columns(2)
                                c1.image(r['issue_photo_url'], caption="Before")
                                if r.get('fix_photo_url'): c2.image(r['fix_photo_url'], caption="After")
                                if status == "是正確認中":
                                    if st.button("承認", key=f"ok_{r['record_id']}"): db_patch("inspection_records", r['record_id'], {"progress_status": "完了"}); st.rerun()
                                    reason = st.text_input("否認理由", key=f"re_{r['record_id']}")
                                    if st.button("否認", key=f"ng_{r['record_id']}"): db_patch("inspection_records", r['record_id'], {"progress_status": "是正待ち", "reject_reason": reason}); st.rerun()

if __name__ == "__main__":
    main()
