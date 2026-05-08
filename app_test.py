import streamlit as st
import streamlit.components.v1 as components
import os

st.set_page_config(page_title="爆速カメラ テスト", layout="centered")

# ==========================================
# 📸 爆速カメラ・コンポーネント (HTML/JS)
# ==========================================
FAST_CAMERA_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        body { margin: 0; display: flex; flex-direction: column; align-items: center; font-family: sans-serif; background: #1e1e1e; color: white; padding: 10px; }
        .video-container { width: 100%; max-width: 400px; border-radius: 12px; overflow: hidden; border: 2px solid #4a90e2; position: relative; background: #000; }
        video { width: 100%; display: block; }
        .btn { width: 100%; max-width: 400px; padding: 15px; margin-top: 15px; background: #deff9a; color: #000; border: none; border-radius: 10px; font-size: 16px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        .btn:active { background: #c5e685; transform: translateY(2px); box-shadow: 0 1px 3px rgba(0,0,0,0.3); }
        canvas { display: none; }
    </style>
</head>
<body>
    <div class="video-container">
        <video id="video" autoplay playsinline></video>
    </div>
    <button class="btn" id="captureBtn"><i class="fa-solid fa-camera"></i> 撮影して圧縮送信 (ラグなし)</button>
    <canvas id="canvas"></canvas>

    <script>
        function sendToStreamlit(val) {
            window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setComponentValue", value: val}, "*");
        }
        function setHeight(h) {
            window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: h}, "*");
        }
        window.onload = () => setHeight(500);

        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const captureBtn = document.getElementById('captureBtn');

        // カメラ起動
        navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
            .then(stream => { video.srcObject = stream; })
            .catch(err => { alert("カメラの許可が必要です: " + err); });

        // 撮影＆圧縮処理
        captureBtn.onclick = () => {
            captureBtn.innerText = "圧縮＆送信中...";
            captureBtn.style.background = "#ccc";

            let w = video.videoWidth;
            let h = video.videoHeight;
            const MAX_SIZE = 800;
            if (w > h) {
                if (w > MAX_SIZE) { h *= MAX_SIZE / w; w = MAX_SIZE; }
            } else {
                if (h > MAX_SIZE) { w *= MAX_SIZE / h; h = MAX_SIZE; }
            }

            canvas.width = w;
            canvas.height = h;
            ctx.drawImage(video, 0, 0, w, h);

            const compressedDataUrl = canvas.toDataURL('image/jpeg', 0.7);
            sendToStreamlit(compressedDataUrl);
            
            if (navigator.vibrate) navigator.vibrate(50);
            
            setTimeout(() => {
                captureBtn.innerHTML = '<i class="fa-solid fa-camera"></i> もう一度撮影する';
                captureBtn.style.background = "#deff9a";
            }, 1000);
        };
    </script>
</body>
</html>
"""

# 🛠️ 修正ポイント：HTMLを直接渡すのではなく、裏で一時的なフォルダとファイルを作成して読み込ませる
COMPONENT_DIR = "fast_camera_comp"
if not os.path.exists(COMPONENT_DIR):
    os.makedirs(COMPONENT_DIR)

with open(os.path.join(COMPONENT_DIR, "index.html"), "w", encoding="utf-8") as f:
    f.write(FAST_CAMERA_HTML)

def fast_camera_component():
    component_func = components.declare_component("fast_camera", path=COMPONENT_DIR)
    return component_func(key="fast_camera_test")

# ==========================================
# 画面表示
# ==========================================
st.title("🚀 爆速カメラ スピードテスト")
st.write("20秒かかっていた写真アップロードが、何秒になるかテストします。")
st.markdown("---")

st.markdown("### 1. ここで撮影してください")
compressed_image_b64 = fast_camera_component()

st.markdown("### 2. 受信結果")
if compressed_image_b64:
    st.success("✅ 受信完了！劇的に早くなっていませんか？")
    
    # データのサイズ計算（Base64の文字数から推定KBを算出）
    base64_str = compressed_image_b64.split(",")[1] if "," in compressed_image_b64 else compressed_image_b64
    size_in_bytes = (len(base64_str) * 3) / 4
    size_in_kb = size_in_bytes / 1024
    st.info(f"💾 **スマホ内で圧縮されたデータサイズ: 約 {size_in_kb:.1f} KB**\n\n(※通常1枚 5,000〜10,000 KBなので、劇的に軽くなっています)")
    
    st.image(compressed_image_b64, caption="受信した圧縮済み画像")
else:
    st.warning("待機中... カメラで撮影ボタンを押してください。")
