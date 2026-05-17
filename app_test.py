import streamlit as st
import requests
import urllib.parse

# === LINE API設定 ===
LINE_CLIENT_ID = "2010108828"
LINE_CLIENT_SECRET = "2c73ce25e71858bcb09c89c79fa6bbe0"

# ⚠️ 注意: LINE Developersに登録しているURLと完全一致
REDIRECT_URI = "https://felix-app-prbmr4ghbjai7n7hzfyahj.streamlit.app/"

def main():
    st.set_page_config(page_title="LINE ID 取得テスト", layout="centered")
    st.title("LINE ID 表示テスト (Android対応版)")

    # --- セッション管理 ---
    if "line_user_id" not in st.session_state:
        st.session_state.line_user_id = None
    if "line_display_name" not in st.session_state:
        st.session_state.line_display_name = None
    if "processed_code" not in st.session_state:
        st.session_state.processed_code = None
    if "error_message" not in st.session_state:
        st.session_state.error_message = None

    qp = st.query_params
    code = qp.get("code")

    # ==========================================================
    # 1. 認証コード(code)を受け取り、まだ処理していない場合のみ実行
    # ==========================================================
    if code and st.session_state.processed_code != code:
        st.session_state.processed_code = code
        
        with st.spinner("LINEサーバーと通信中..."):
            token_url = "https://api.line.me/oauth2/v2.1/token"
            payload = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": LINE_CLIENT_ID,
                "client_secret": LINE_CLIENT_SECRET
            }
            res = requests.post(token_url, data=payload)
            
            if res.status_code == 200:
                access_token = res.json().get("access_token")
                
                profile_res = requests.get(
                    "https://api.line.me/v2/profile", 
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if profile_res.status_code == 200:
                    st.session_state.line_user_id = profile_res.json().get("userId")
                    st.session_state.line_display_name = profile_res.json().get("displayName")
                    st.session_state.error_message = None
                else:
                    st.session_state.error_message = f"Profile取得エラー: {profile_res.text}"
            else:
                st.session_state.error_message = f"Token取得エラー({res.status_code}): {res.text}"
        
        st.query_params.clear()
        st.rerun()

    # ==========================================================
    # 2. 取得成功時の画面表示
    # ==========================================================
    if st.session_state.line_user_id:
        st.success("🎉 LINE IDの取得に成功しました！")
        st.markdown(f"### 取得したLINE ID:\n**`{st.session_state.line_user_id}`**")
        st.markdown(f"### LINE登録名:\n**{st.session_state.line_display_name}**")
        
        if st.button("もう一度最初からテストする"):
            st.session_state.line_user_id = None
            st.session_state.line_display_name = None
            st.session_state.processed_code = None
            st.session_state.error_message = None
            st.rerun()

    # ==========================================================
    # 3. エラー発生時の画面表示
    # ==========================================================
    elif st.session_state.error_message:
        st.error("❌ エラーが発生しました。LINE側から以下の理由で拒否されています。")
        st.code(st.session_state.error_message)
        
        if st.button("最初に戻る"):
            st.session_state.error_message = None
            st.session_state.processed_code = None
            st.rerun()

    # ==========================================================
    # 4. 初回アクセス時の画面（タップ専用ボタン化）
    # ==========================================================
    else:
        st.info("下のボタンをタップして、LINE認証へ進んでください。")
        encoded_uri = urllib.parse.quote(REDIRECT_URI, safe='')
        login_url = f"https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id={LINE_CLIENT_ID}&redirect_uri={encoded_uri}&state=test_mode&scope=profile%20openid"
        
        # 🟢 修正：スマホで確実に押せる巨大なネイティブボタンに変更
        st.link_button("👉 LINEログインしてIDを取得する", login_url, type="primary", use_container_width=True)
        
        st.markdown("---")
        st.markdown("**※万が一上のボタンが反応しない場合は、以下のURLをコピーしてChromeブラウザで開いてください。**")
        st.code(login_url)

if __name__ == "__main__":
    main()
