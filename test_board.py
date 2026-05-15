import streamlit as st
import streamlit.components.v1 as components
import datetime
import tempfile
import os

st.set_page_config(page_title="是正トレーステスト", layout="centered")

st.title("🚧 V2 是正写真用：黒板トレース実証版")
st.info("業者が『是正報告』をする際、指摘内容を自動で黒板に引き継ぐシミュレーションです。")

# ==========================================
# 1. 指摘時のデータ（DBから読み込んだと想定）
# ==========================================
st.markdown("### 📥 指摘時の情報（DBに保存されている内容）")
col1, col2 = st.columns(2)

# これらがDBから引っ張ってきた「過去のデータ」という扱いです
db_prop = "サンレジデンス名古屋" # 物件名
db_insp_type = "社内検査(建設)"   # 検査種類
db_floor = "201"                # 階層
db_area = "LDK"                 # 部位
db_cat = "クロス"                # 分類

# 指摘事項だけはテスト用に書き換え可能にします
db_issue = st.text_input("DB内の指摘事項（ここを書き換えてトレースを確認）", value="クロスの剥がれ、要補修")

# 今日の日付（撮影日）
today_str = datetime.date.today().strftime("%Y/%m/%d")

st.warning(f"【自動セットされる内容】\n\n物件：{db_prop} / 種類：{db_insp_type} / 場所：{db_floor} {db_area} {db_cat} \n\n※日付は自動的に今日（{today_str}）になります。")

# ==========================================
# 2. JavaScript 黒板コンポーネント（V8_Finalを継承）
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
            background-color: #007bff; color: white; border-radius: 8px;
            font-size: 16px; font-weight: bold; text-align: center; cursor: pointer; 
            box-sizing: border-box; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        input[type="file"] { display: none; }
    </style>
</head>
<body>
    <label class="upload-btn" id="upload-label">
        <i class="fa-solid fa-camera" id="btn-icon"></i> <span id="btn-text">是正写真を撮影</span>
        <input type="file" accept="image/*" id="file-input">
    </label>
    <script>
        let b = { prop: "", insp: "", date: "", loc: "", desc: "" };
        window.addEventListener("message", function(e) {
            if (e.data.type === "streamlit:render" && e.data.args) {
                b.prop = e.data.args.prop || ""; 
                b.insp = e.data.args.insp || ""; 
                b.date = e.data.args.date || "";
                b.loc = e.data.args.loc || ""; 
                b.desc = e.data.args.desc || "";
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
            document.getElementById('btn-text').innerHTML = '是正中...';

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
                    ctx.fillStyle = "rgba(0, 40, 80, 0.9)"; ctx.fillRect(sx, sy, bw, bh); // 是正用は少し青みがかった黒板
                    ctx.strokeStyle = "white"; ctx.lineWidth = 2; ctx.strokeRect(sx+5, sy+5, bw-10, bh-10);
                    
                    ctx.fillStyle = "white"; const fs = Math.floor(w * 0.022); 
                    ctx.font = fs + "px 'Yu Gothic Medium', sans-serif";
                    
                    let ty = sy + fs + 12; const ls = fs * 1.4;
                    const textX = sx + 10, dw = bw - 20;

                    ty = wrapTextAndReturnY(ctx, b.prop, textX, ty, dw, ls, 2);
                    ty = wrapTextAndReturnY(ctx, b.insp + "  " + b.date, textX, ty, dw, ls, 2);
                    ty = wrapTextAndReturnY(ctx, b.loc, textX, ty, dw, ls, 2);
                    ctx.fillStyle = "#ffdddd";
                    wrapTextAndReturnY(ctx, b.desc, textX, ty, dw, ls, 3);

                    sendToStreamlit(canvas.toDataURL('image/jpeg', 0.6));
                    document.getElementById('upload-label').style.backgroundColor = '#2ecc71';
                    document.getElementById('btn-text').innerHTML = 'セット完了';
                };
                img.src = event.target.result;
            };
            reader.readAsDataURL(file);
        });
        window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:componentReady", apiVersion: 1}, "*");
        window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: 80}, "*");
    </script>
</body>
</html>
"""
temp_dir = os.path.join(tempfile.gettempdir(), "fix_trace_test_v1")
os.makedirs(temp_dir, exist_ok=True)
with open(os.path.join(temp_dir, "index.html"), "w", encoding="utf-8") as file: file.write(CLIENT_COMPRESS_HTML)
_fix_camera = components.declare_component("fix_trace_cam", path=temp_dir)

# ==========================================
# 3. カメラ呼び出し
# ==========================================
st.markdown("---")
st.markdown("### 📷 是正完了の撮影（情報は自動トレース）")

# Python側でトレース情報を合体
loc_combined = f"{db_floor} {db_area} {db_cat}".strip()

p_url = _fix_camera(
    prop=db_prop,
    insp=db_insp_type,
    date=today_str,    # ここだけ今日の日付に差し替え
    loc=loc_combined,  # 指摘時の場所をそのまま渡す
    desc=db_issue,     # 指摘時の内容をそのまま渡す
    key="fix_cam_test"
)

if p_url:
    st.image(p_url, caption="【業者撮影】是正完了写真（内容トレース済）", use_container_width=True)
    st.success("✅ 指摘内容が完全にトレースされ、日付だけが今日に更新されました。")
