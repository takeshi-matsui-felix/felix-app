import streamlit as st
import streamlit.components.v1 as components
import datetime
import tempfile
import os

st.set_page_config(page_title="黒板カメラテスト", layout="centered")

st.title("🚧 V2 電子黒板カメラ プロトタイプ")
st.write("入力した情報が、写真の右下に**一枚の画像として焼き付け（合成）**されます。")

# 1. 黒板に印字するテスト用データを入力
st.markdown("### 📝 黒板の内容を入力")
c1, c2 = st.columns(2)
prop_name = c1.text_input("物件名", "サンプルレジデンス")
ins_date = c2.date_input("検査日", datetime.date.today())
work_type = c1.text_input("工種", "内装工事")
area_name = c2.text_input("部位", "LDK")
issue_desc = st.text_input("指摘事項", "クロスの傷、要補修")

st.markdown("---")
st.markdown("### 📷 写真を撮影（または選択）")

# 2. スマホ内部で黒板を合成する特殊コンポーネント (HTML/JS)
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
        // Python(Streamlit)から送られてきたデータを受け取る器
        let boardData = { prop_name: "", ins_date: "", work_type: "", area_name: "", issue_desc: "" };

        // データの受け取り監視
        window.addEventListener("message", function(event) {
            if (event.data.type === "streamlit:render") {
                if (event.data.args) {
                    boardData.prop_name = event.data.args.prop_name || "";
                    boardData.ins_date = event.data.args.ins_date || "";
                    boardData.work_type = event.data.args.work_type || "";
                    boardData.area_name = event.data.args.area_name || "";
                    boardData.issue_desc = event.data.args.issue_desc || "";
                }
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
                    const MAX_SIZE = 800; // 黒板の文字を見やすくするため、画質を少し向上
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

                    // 2. 黒板（背景）の描画
                    const boardWidth = width * 0.50; // 画像幅の約半分
                    const boardHeight = height * 0.35; // 画像高さの約3分の1
                    const startX = width - boardWidth - 10; // 右下に配置
                    const startY = height - boardHeight - 10;
                    
                    ctx.fillStyle = "rgba(0, 50, 0, 0.85)"; // 深緑色の黒板
                    ctx.fillRect(startX, startY, boardWidth, boardHeight);
                    
                    // 3. 黒板の白い枠線
                    ctx.strokeStyle = "white";
                    ctx.lineWidth = 2;
                    ctx.strokeRect(startX + 5, startY + 5, boardWidth - 10, boardHeight - 10);

                    // 4. 文字の描画設定
                    ctx.fillStyle = "white";
                    const fontSize = Math.floor(width * 0.035); // 画像サイズに比例したフォント
                    ctx.font = fontSize + "px sans-serif";
                    
                    const textStartX = startX + 15;
                    let textY = startY + fontSize + 15;
                    const lineSpacing = fontSize * 1.5;

                    ctx.fillText("物件: " + boardData.prop_name, textStartX, textY);
                    textY += lineSpacing;
                    ctx.fillText("日付: " + boardData.ins_date, textStartX, textY);
                    textY += lineSpacing;
                    ctx.fillText("工種: " + boardData.work_type + " ／ 部位: " + boardData.area_name, textStartX, textY);
                    textY += lineSpacing;
                    
                    // 指摘事項は少し赤色で目立たせる
                    ctx.fillStyle = "#ffdddd";
                    ctx.fillText("指摘: " + boardData.issue_desc, textStartX, textY);

                    // 5. 結合した画像をデータURL化して送信
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

# HTMLを一時ファイルに出力
temp_dir = os.path.join(tempfile.gettempdir(), "board_camera_test_v2")
os.makedirs(temp_dir, exist_ok=True)
with open(os.path.join(temp_dir, "index.html"), "w", encoding="utf-8") as f:
    f.write(CLIENT_COMPRESS_HTML)

# コンポーネントの呼び出しと、Python側の変数をJavaScriptへ動的に渡す
board_cam_func = components.declare_component("board_camera", path=temp_dir)
photo = board_cam_func(
    prop_name=prop_name, 
    ins_date=str(ins_date), 
    work_type=work_type, 
    area_name=area_name, 
    issue_desc=issue_desc,
    key="test_cam"
)

# 3. 合成結果のプレビュー表示
if photo:
    st.image(photo, caption="完成した証拠写真（※長押しで保存できます）", use_container_width=True)
    st.success("✅ 電子黒板の焼き付けに成功しました！この画像がSupabaseに保存されます。")
    st.info("※画像を長押し（または右クリック）して「画像を保存」し、黒板がちゃんと画像の一部になっていることを確認してみてください。")
