import streamlit as st
import streamlit.components.v1 as components
import os
import tempfile

st.set_page_config(page_title="スマホ内・瞬間圧縮テスト V6", layout="centered")

# ==========================================
# 📱 スマホ内で圧縮を完結させる専用HTML/JS
# ==========================================
CLIENT_COMPRESS_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        body { margin: 0; padding: 10px; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; background-color: transparent;}
        .upload-btn {
            display: block; width: 100%; max-width: 400px; padding: 18px 20px;
            background-color: #FF4B4B; color: white; border-radius: 8px;
            font-size: 16px; font-weight: bold; text-align: center;
            cursor: pointer; box-sizing: border-box; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .upload-btn:active { background-color: #FF3333; transform: translateY(2px); }
        input[type="file"] { display: none; }
        #status { margin-top: 15px; font-size: 14px; color: #333; font-weight: bold; text-align: center; }
        #preview { margin-top: 15px; max-width: 100%; border-radius: 8px; display: none; border: 2px solid #ddd; }
    </style>
</head>
<body>
    <label class="upload-btn">
        📸 現場で撮影 ／ アルバムから選択
        <input type="file" accept="image/*" id="file-input">
    </label>
    <div id="status">待機中...上のボタンをタップしてください</div>
    <img id="preview" />

    <script>
        // ★【最重要修正】Streamlitへの「準備完了」の挨拶シグナル
        function sendReady() {
            window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:componentReady", apiVersion: 1}, "*");
        }
        function setHeight(h) {
            window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: h}, "*");
        }
        function sendToStreamlit(val) {
            window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setComponentValue", value: val}, "*");
        }

        // 画面が読み込まれたら、絶対に最初に挨拶を送る！
        window.onload = function() {
            sendReady();
            setHeight(120);
        };

        const input = document.getElementById('file-input');
        const status = document.getElementById('status');
        const preview = document.getElementById('preview');

        input.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) return;

            status.innerHTML = '⏳ スマホ内で高速圧縮中...';
            setHeight(120);

            const reader = new FileReader();
            reader.onload = function(event) {
                const img = new Image();
                img.onload = function() {
                    // サイズを約50〜70KBに落とすための調整
                    const MAX_SIZE = 800; 
                    let width = img.width;
                    let height = img.height;

                    if (width > height) {
                        if (width > MAX_SIZE) { height *= MAX_SIZE / width; width = MAX_SIZE; }
                    } else {
                        if (height > MAX_SIZE) { width *= MAX_SIZE / height; height = MAX_SIZE; }
                    }

                    const canvas = document.createElement('canvas');
                    canvas.width = width;
                    canvas.height = height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);

                    // JPEG形式、品質40%で圧縮
                    const compressedDataUrl = canvas.toDataURL('image/jpeg', 0.4);

                    preview.src = compressedDataUrl;
                    preview.style.display = "block";
                    status.innerHTML = '✅ 圧縮完了！サーバーに送信しました';
                    setHeight(400); 

                    // 圧縮済みの軽いデータをStreamlitに渡す
                    sendToStreamlit(compressedDataUrl);
                };
                img.src = event.target.result;
            };
            reader.readAsDataURL(file);
        });
    </script>
</body>
</html>
"""

# 🛠️ GitHubのフォルダ問題を回避！サーバーの一時領域を借りて確実に行う
temp_dir = os.path.join(tempfile.gettempdir(), "fast_camera_comp_v6")
os.makedirs(temp_dir, exist_ok=True)

with open(os.path.join(temp_dir, "index.html"), "w", encoding="utf-8") as f:
    f.write(CLIENT_COMPRESS_HTML)

def client_compress_component():
    component_func = components.declare_component("fast_camera_v6", path=temp_dir)
    return component_func(key="fast_camera_test_v6")

# ==========================================
# 画面表示
# ==========================================
st.title("⚡ スマホ内・瞬間圧縮テスト V6")
st.write("5MBの写真がスマホの中で圧縮され、サーバーには軽いデータだけが送られるため、13秒の待機時間がなくなるかのテストです。")
st.markdown("---")

st.markdown("### 1. ここで撮影してください")
compressed_b64 = client_compress_component()

st.markdown("### 2. 受信結果（サーバー側）")
if compressed_b64 and isinstance(compressed_b64, str) and "base64," in compressed_b64:
    st.success("🎉 サクッと受信完了しました！")
    
    base64_str = compressed_b64.split("base64,")[1]
    size_in_bytes = (len(base64_str) * 3) / 4
    size_in_kb = size_in_bytes / 1024
    
    st.info(f"💾 **サーバーに届いたデータサイズ: 約 {size_in_kb:.1f} KB**\n\n(※目標の50〜70KB前後に収まっていれば大成功です！)")
    
    st.markdown("#### 🔍 画質確認")
    st.image(compressed_b64, use_container_width=True)
elif compressed_b64 is not None:
    st.warning("待機中... 上の赤いボタンから撮影してください。")
