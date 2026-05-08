import streamlit as st
from PIL import Image, ImageOps
import io
import base64

st.set_page_config(page_title="70KB 圧縮テスト", layout="centered")

st.title("📸 70KB 自動圧縮テスト")
st.write("現場の「いつものカメラ」で撮った数MBの写真を、送信直前に自動で約70KB（数十KB）に圧縮するテストです。")
st.markdown("---")

# 現場でいつも使う「ファイルアップローダー（背面カメラが起動するもの）」
photo = st.file_uploader("ここをタップして撮影（またはアルバムから選択）", type=['jpg', 'png', 'jpeg'])

if photo is not None:
    # 1. 元のファイルサイズを計算
    original_size_kb = len(photo.getvalue()) / 1024
    
    try:
        # 2. 画像を開いて、スマホの縦横の向き（EXIF）を正しく補正
        img = Image.open(photo)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        
        # 3. リサイズ（長辺を最大800pxに縮小）
        img.thumbnail((800, 800))
        
        # 4. 圧縮処理（品質を40%に落として、70KB前後を狙う）
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=40)
        compressed_bytes = buf.getvalue()
        
        # 5. 圧縮後の実データサイズを計算
        compressed_size_kb = len(compressed_bytes) / 1024
        
        # 6. Supabase送信用（Base64化）の最終通信サイズを計算
        b64_str = base64.b64encode(compressed_bytes).decode('utf-8')
        b64_size_kb = len(b64_str) / 1024
        
        # 画面に結果を表示
        st.success("✅ 圧縮＆処理完了！")
        
        st.info(f"""
        📊 **サイズ測定結果**
        * 📉 **元のサイズ**: 約 {original_size_kb:,.1f} KB
        * 🎯 **圧縮後の実サイズ**: 約 **{compressed_size_kb:,.1f} KB** （←この軽さになります！）
        * 📤 **通信時のサイズ (Base64)**: 約 {b64_size_kb:,.1f} KB （無料枠を消費する実際のサイズ）
        """)
        
        # 画質の確認
        st.markdown("### 🔍 【画質の確認】")
        st.write("以下の写真が、実際にサーバーに送られて報告書に載る画質です。拡大して文字や細部が見えるか確認してください。")
        st.image(compressed_bytes, use_container_width=True)

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
