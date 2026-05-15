import streamlit as st
import streamlit.components.v1 as components
import datetime
import tempfile
import os

st.set_page_config(page_title="黒板カメラテスト V2", layout="centered")

st.title("🚧 V2 電子黒板カメラ (自動FiX＆小型化テスト)")
st.write("実際のアプリでは、上のラジオボタン等を選ぶだけで、**裏側で自動的に黒板にセット**されます。")

# ==========================================
# 1. 本番アプリを想定した「自動FiX」シミュレーション
# ==========================================
st.markdown("### 🔘 検査項目の選択（本番ではこれを選ぶだけ）")

# 実際は検査スタート時に裏で持っている物件名
hidden_property_name = "サンレジデンス名古屋"
st.info(f"※物件名「{hidden_property_name}」はシステムが裏で記憶しています")

c1, c2 = st.columns(2)
floor = c1.radio("階層", ["101", "102", "103"], horizontal=True)
area = c2.radio("部位", ["玄関", "LDK", "洋室"], horizontal=True)
category = c1.radio("分類", ["建具", "クロス", "床"], horizontal=True)
desc = c2.radio("指摘事項", ["傷・汚れあり", "建付け不良", "未施工"], horizontal=True)

# ==========================================
# 2. スマホ内部で黒板を合成する特殊コンポーネント (HTML/JS)
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
            background-color: #28a745; color: white; border-radius: 8px;
            font-size: 16px; font-weight: bold; text-align: center; cursor: pointer; 
            box-sizing: border-box; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        input[type="file"] { display: none; }
    </style>
</head>
<body>
    <label class="upload-btn" id="upload-label">
        <i class="fa-solid fa-camera" id="btn-icon"></i> <span id="btn-text">黒板付きで撮影 ／ 選択</span>
        <input type="file" accept="image/*" id="file-input">
    </label>
    <script>
        let boardData = { prop_name: "", date: "", loc: "", cat: "", desc: "" };

        window.addEventListener("message", function(event) {
            if (event.data.type === "streamlit:render" && event.data.args) {
                boardData.prop_name = event.data.args.prop_name || "";
                boardData.date = event.data.args.date || "";
                boardData.loc = event.data.args.loc || "";
                boardData.cat = event.data.args.cat || "";
                boardData.desc = event.data.args.desc || "";
            }
        });

        function sendReady() { window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:componentReady", apiVersion: 1}, "*"); }
        function setHeight(h) { window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: h}, "*"); }
        function sendToStreamlit(val) { window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setComponentValue", value: val}, "*"); }
        window.onload = function() { sendReady(); setHeight(80); }; 

        const input = document.getElementById('file-input');
        const uploadLabel = document.getElementById('upload-label');
        const btnIcon = document.getElementById('btn-icon');
        const btnText = document.getElementById('btn-text');

        input.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) return;

            uploadLabel.style.backgroundColor = '#f39c12';
            btnIcon.className = 'fa-solid fa-spinner fa-spin';
            btnText.innerHTML = '&nbsp;黒板合成中...';

            const reader = new FileReader();
            reader.onload = function(event) {
                const img = new Image();
                img.onload = function() {
                    const MAX_SIZE = 800; 
                    let width = img.width; let height = img.height;
                    if (width > height) {
                        if (width > MAX_SIZE) { height *= MAX_SIZE / width; width = MAX_SIZE; }
                    } else {
                        if (height > MAX_SIZE) { width *= MAX_SIZE / height; height = MAX_SIZE; }
                    }
                    const canvas = document.createElement('canvas');
                    canvas.width = width; canvas.height = height;
                    const ctx = canvas.getContext('2d');
                    
                    // 1. 元の写真を描画
                    ctx.drawImage(img, 0, 0, width, height);

                    // 2. 黒板（背景）の描画：★サイズを小さく変更（幅35%、高さ25%）
                    const boardWidth = width * 0.40; 
                    const boardHeight = height * 0.28; 
                    const startX = width - boardWidth - 10; 
                    const startY = height - boardHeight - 10;
                    
                    ctx.fillStyle = "rgba(0, 50, 0, 0.85)"; 
                    ctx.fillRect(startX, startY, boardWidth, boardHeight);
                    
                    ctx.strokeStyle = "white";
                    ctx.lineWidth = 2;
                    ctx.strokeRect(startX + 5, startY + 5, boardWidth - 10, boardHeight - 10);

                    // 4. 文字の描画設定：★文字も少し小さくシャープに
                    ctx.fillStyle = "white";
                    const fontSize = Math.floor(width * 0.030); 
                    ctx.font = fontSize + "px sans-serif";
                    
                    const textStartX = startX + 15;
                    let textY = startY + fontSize + 15;
                    const lineSpacing = fontSize * 1.5;

                    ctx.fillText("物件: " + boardData.prop_name, textStartX, textY);
                    textY += lineSpacing;
                    ctx.fillText("検査: " + boardData.date, textStartX, textY);
                    textY += lineSpacing;
                    ctx.fillText("場所: " + boardData.loc, textStartX, textY);
                    textY += lineSpacing;
                    ctx.fillText("分類: " + boardData.cat, textStartX, textY);
                    textY += lineSpacing;
                    
                    ctx.fillStyle = "#ffdddd";
                    ctx.fillText("指摘: " + boardData.desc, textStartX, textY);

                    // 5. データURL化
                    const dataUrl = canvas.toDataURL('image/jpeg', 0.6);

                    uploadLabel.style.backgroundColor = '#2ecc71';
                    btnIcon.className = 'fa-solid fa-check';
                    btnText.innerHTML = '&nbsp;合成完了';
                    sendToStreamlit(dataUrl);
                };
                img.src = event.target.result;
            };
            reader.readAsDataURL(file);
        });
    </script>
</body>
</html>
"""

temp_dir = os.path.join(tempfile.gettempdir(), "board_camera_test_v3")
os.makedirs(temp_dir, exist_ok=True)
with open(os.path.join(temp_dir, "index.html"), "w", encoding="utf-8") as f:
    f.write(CLIENT_COMPRESS_HTML)

# ==========================================
# 3. 選択された変数を「裏側で」カメラへ渡す
# ==========================================
st.markdown("---")
st.markdown("### 📷 写真を撮影（すべて自動で黒板に入ります）")

today_str = datetime.date.today().strftime("%Y/%m/%d")
loc_str = f"{floor} {area}" # 階層と部位を合体

board_cam_func = components.declare_component("board_camera_auto", path=temp_dir)
photo = board_cam_func(
    prop_name=hidden_property_name, # 裏で持っている物件名
    date=today_str, 
    loc=loc_str,                    # 合体させた場所
    cat=category,                   # 選択した分類
    desc=desc,                      # 選択した指摘事項
    key="auto_cam"
)

if photo:
    st.image(photo, caption="完成した自動連携・小型化黒板", use_container_width=True)
    st.success("✅ 操作一切なしで、選択情報がすべて黒板に焼き付けられました！")
