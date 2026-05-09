import streamlit as st
import streamlit.components.v1 as components
import os

st.set_page_config(page_title="スマホ内・瞬間圧縮テスト", layout="centered")

# ==========================================
# 🛠️ GitHubに作ったフォルダを確実に読み込む（手抜きなしの正攻法）
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
COMPONENT_DIR = os.path.join(current_dir, "fast_camera_comp")

# 部品の読み込み設定
def client_compress_component():
    try:
        component_func = components.declare_component("fast_camera", path=COMPONENT_DIR)
        return component_func(key="fast_camera_test")
    except Exception as e:
        st.error(f"部品の読み込みに失敗しました。GitHubに「fast_camera_comp/index.html」が正しく作られているか確認してください。エラー詳細: {e}")
        return None

# ==========================================
# 画面表示
# ==========================================
st.title("⚡ スマホ内・瞬間圧縮テスト")
st.write("5MBの写真がスマホの中で約70KBに圧縮され、1秒で送信されるかのテストです。")
st.markdown("---")

st.markdown("### 1. ここで撮影してください")
compressed_b64 = client_compress_component()

st.markdown("### 2. 受信結果（サーバー側）")
if compressed_b64 and isinstance(compressed_b64, str) and "base64," in compressed_b64:
    st.success("🎉 サクッと受信完了しました！")
    
    base64_str = compressed_b64.split("base64,")[1]
    size_in_bytes = (len(base64_str) * 3) / 4
    size_in_kb = size_in_bytes / 1024
    
    st.info(f"💾 **サーバーに届いたデータサイズ: 約 {size_in_kb:.1f} KB**")
    
    st.markdown("#### 🔍 画質確認")
    st.image(compressed_b64, use_container_width=True)
elif compressed_b64 is not None:
    st.warning("待機中... 上の赤いボタンから撮影してください。")
