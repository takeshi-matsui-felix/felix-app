import streamlit as st
import streamlit.components.v1 as components
import os

st.set_page_config(page_title="爆速カメラ テストV2", layout="centered")

# ==========================================
# 📸 爆速カメラ・コンポーネント (ネイティブカメラ呼び出し版)
# ==========================================
FAST_CAMERA_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        body { margin: 0; display: flex; flex-direction: column; align-items: center; font-family: sans-serif; background: #1e1e1e; padding: 10px; }
        /* 更新されたことがひと目で分かるように青いボタンにしました */
        .btn { width: 100%; max-width: 400px; padding: 20px; background: #4a90e2; color: #fff; border: none; border-radius: 12px; font-size: 18px; font-weight: bold; cursor: pointer; text-align: center; box-sizing: border-box; box-shadow: 0 4px 6px rgba(0,0,0,0.3); display: block; }
        .btn:active { background: #357abd; transform: translateY(2px); }
        #cameraInput { display: none; }
        #preview { width: 100%; max-width: 400px; margin-top: 15px; border-radius: 10px; display: none; border: 2px solid #4a90e2; }
    </style>
</head>
<body>
    <label for="cameraInput" class="btn" id="btnLabel"><i class="fa-solid fa-camera"></i> 【V2】撮影して圧縮送信</label>
    <input type="file" accept="image/*" capture="environment" id="cameraInput">
    <img id="preview" />

    <script>
        function sendToStreamlit(val) {
            window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setComponentValue", value: val}, "*");
        }
        function setHeight(h) {
            window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: h}, "*");
        }
        window.onload = () => setHeight(100);

        const input = document.getElementById('cameraInput');
        const preview = document.getElementById('preview');
        const btnLabel = document.getElementById('btnLabel');

        input.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) return;

            btnLabel.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 圧縮中...';
            
            const img = new Image();
            img.onload = function() {
                let w = img.width;
                let h = img.height;
                const MAX_SIZE = 800;

                if (w > h) {
                    if (w > MAX_SIZE) { h *= MAX_SIZE / w; w = MAX_SIZE; }
                } else {
                    if (h > MAX_SIZE) { w *= MAX_SIZE / h; h = MAX_SIZE; }
                }

                const canvas = document.createElement('canvas');
                canvas.width = w;
                canvas.height = h;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, w, h);

                const compressedDataUrl = canvas.toDataURL('image/jpeg', 0.7);
                preview.src = compressedDataUrl;
                preview.style.display = "block";
                setHeight(400); 
                
                btnLabel.innerHTML = '<i class="fa-solid fa-check"></i> 送信完了！(再撮影可)';
                sendToStreamlit(compressedDataUrl);
            };
            img.src = URL.createObjectURL(file);
        });
    </script>
</body>
</html>
"""

# 🛠️ フォルダ名を「V2」に変えて、Streamlitの記憶を強制リセットします
COMPONENT_DIR = "fast_camera_comp_v2"
if not os.path.exists(COMPONENT_DIR):
    os.makedirs(COMPONENT_DIR)

with open(os.path.join(COMPONENT_DIR, "index.html"), "w", encoding="utf-8") as f:
    f.write(FAST_CAMERA_HTML)

def fast_camera_component():
    # コンポーネントの登録名もV2に変更
    component_func = components.declare_component("fast_camera_v2", path=COMPONENT_DIR)
    return component_func(key="fast_camera_test_v2")

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
    st.info(f"💾 **スマホ内で圧縮されたデータサイズ: 約 {size_in_kb:.1f} KB**\n\n(※通常1枚 5,000〜10,000 KBなので、約1/50の軽さになっています)")
    
    st.image(compressed_image_b64, caption="受信した圧縮済み画像")
else:
    st.warning("待機中... カメラで撮影ボタンを押してください。")
