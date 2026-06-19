import streamlit as st
import app  # 既存の黄金コード(app.py)を読み込む

# 起動した瞬間、強制的に「東海エリアの業者」として記憶させる
if "role" not in st.session_state or st.session_state.role is None:
    st.session_state.role = "partner"
    st.session_state.target_area = "東海エリア"
    st.session_state.active_menu = "ホーム"

# 黄金コードのメイン画面を起動
app.main()
