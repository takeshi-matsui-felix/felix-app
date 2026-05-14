import streamlit as st
import base64

# UI設定
st.set_page_config(page_title="Felix検査App - メンテナンス中", page_icon="icon.png")

# アイコンの読み込み（もしあれば）
try:
    with open("icon.png", "rb") as f:
        img_base64 = base64.b64encode(f.read()).decode()
    st.markdown(f'<link rel="apple-touch-icon" href="data:image/png;base64,{img_base64}"><link rel="icon" href="data:image/png;base64,{img_base64}">', unsafe_allow_html=True)
except FileNotFoundError:
    pass

# メンテナンス画面の表示
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .maintenance-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 70vh;
        text-align: center;
        font-family: 'sans-serif';
        padding: 20px;
    }
    .logo {
        font-size: 80px;
        margin-bottom: 20px;
    }
    .title {
        color: #FF4B4B;
        font-size: 28px;
        font-weight: bold;
        margin-bottom: 15px;
    }
    .message {
        color: #333;
        font-size: 18px;
        line-height: 1.6;
        max-width: 600px;
    }
    .footer {
        margin-top: 50px;
        color: #888;
        font-size: 14px;
    }
</style>

<div class="maintenance-container">
    <div class="logo">🏗️</div>
    <div class="title">システムアップデートのお知らせ</div>
    <div class="message">
        現在、Felix検査Appは<b>「通信量の大幅な最適化」および「セキュリティ強化」</b>を目的とした緊急メンテナンスを行っております。<br><br>
        現場での快適な操作と、安全なデータ管理を実現するためのアップデートです。再開まで今しばらくお待ちください。
    </div>
    <div class="footer">
        © 2026 Felix All Rights Reserved.
    </div>
</div>
""", unsafe_allow_html=True)

# サイドバーを非表示にする
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)
