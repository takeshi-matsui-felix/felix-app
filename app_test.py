import streamlit as st
import streamlit.components.v1 as components
import base64

st.set_page_config(page_title="スマホ内・瞬間圧縮テスト", layout="centered")

# ==========================================
# 📱 スマホ内で圧縮を完結させる専用HTML/JSコンポーネント
# ==========================================
CLIENT_COMPRESS_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        body { margin: 0; padding: 10px; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; background-color: transparent;}
        
        /* 現場で押しやすい大きなボタンのデザイン */
        .upload-btn {
            display: inline-block;
            width: 100%;
            max-width: 400px;
            padding: 18px 20px;
            background-color: #FF4B4B; /* Streamlitの赤色 */
            color: white;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            text-align: center;
            cursor: pointer;
            box-sizing: border-box;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .upload-btn:active { background-color: #FF3333; transform: translateY(2px); }
        
        /* 本当の入力フォームは綺麗に隠す（透明化ではなく標準的な手法） */
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
        // Streamlitの枠（iframe）の高さを自動調整する関数
        function setHeight(h) {
            window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: h}, "*");
        }
        window.onload = () => setHeight(120);

        const input = document.getElementById('file-input');
        const status = document.getElementById('status');
        const preview = document.getElementById('preview');

        input.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) return;

            // 撮影・選択された瞬間に処理開始（まだネットには送っていません）
            status.innerHTML = '⏳ スマホ内で高速圧縮中...';
            setHeight(120);

            const reader = new FileReader();
            reader.onload = function(event) {
                const img = new Image();
                img.onload = function() {
                    
                    // 【圧縮設定】最大サイズと画質をコントロール
                    const MAX_SIZE = 800; // 縦横最大800px（十分な画質を担保）
                    let width = img.width;
                    let height = img.height;

                    if (width > height) {
                        if (width > MAX_SIZE) { height *= MAX_SIZE / width; width = MAX_SIZE; }
                    } else {
                        if (height > MAX_SIZE) { width *= MAX_SIZE / height; height = MAX_SIZE; }
                    }

                    // Canvas（お絵かきボード）を使って画像を縮小描画
                    const canvas = document.createElement('canvas');
                    canvas.width = width;
                    canvas.height = height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);

                    // 【最重要】JPEG形式で品質を40%に落とし、約50KB〜70KBを狙う
                    const compressedDataUrl = canvas.toDataURL('image/jpeg', 0.4);

                    // プレビュー表示
                    preview.src = compressedDataUrl;
                    preview.style.display = "block";
                    status.innerHTML = '✅ 圧縮完了！Streamlitに送信しました';
                    setHeight(400); // 画像を表示するので枠を広げる

                    // 圧縮された軽いデータだけをStreamlit（Python側）へ送る
                    window.parent.postMessage({
                        isStreamlitMessage: true,
                        type: "streamlit:setComponentValue",
                        value: compressedDataUrl
                    }, "*");
                };
                img.src = event.target.result;
            };
            reader.readAsDataURL(file);
        });
    </script>
</body>
</html>
"""

# StreamlitにHTMLコンポーネントを認識させる
def client_compress_component():
    return components.html(CLIENT_COMPRESS_HTML, height=120)

# ==========================================
# 画面表示
# ==========================================
st.title("⚡ スマホ内・瞬間圧縮テスト")
st.write("5MBの写真がスマホの中で圧縮され、サーバーには軽いデータだけが送られるため、13秒の待機時間がなくなるかのテストです。")
st.markdown("---")

st.markdown("### 1. ここで撮影してください")
# コンポーネントの呼び出し
compressed_b64 = client_compress_component()

st.markdown("### 2. 受信結果（サーバー側）")
if compressed_b64:
    st.success("🎉 サクッと受信完了しました！")
    
    # Python側で受け取ったBase64データの実際のサイズ（KB）を計算
    base64_str = compressed_b64.split(",")[1] if "," in compressed_b64 else compressed_b64
    size_in_bytes = (len(base64_str) * 3) / 4
    size_in_kb = size_in_bytes / 1024
    
    st.info(f"💾 **サーバーに届いたデータサイズ: 約 {size_in_kb:.1f} KB**\n\n(※目標の50〜70KB前後に収まっていれば大成功です！)")
    
    # 画質の確認
    st.markdown("#### 🔍 画質確認")
    st.write("この画質で報告書に載ります。現場の指摘箇所が確認できるかチェックしてください。")
    st.image(compressed_b64, use_container_width=True)
else:
    st.warning("待機中... 上のボタンから撮影してください。")
