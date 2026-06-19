import streamlit as st

# ① 強制的に「業者」かつ「関東エリア」として記憶させる
st.session_state.role = "partner"
st.session_state.target_area = "関東エリア"
st.session_state.active_menu = "ホーム"

# ② 黄金コード(app.py)を読み込んでメイン画面を起動する
import app
app.main()
