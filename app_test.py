import streamlit as st
import requests
import urllib.parse

# === LINE API設定 ===
LINE_CLIENT_ID = "2010108828"
LINE_CLIENT_SECRET = "2c73ce25e71858bcb09c89c79fa6bbe0"

# ⚠️ 注意: LINE Developersに登録しているURLと【1文字の狂いもなく（末尾の / も含め）】一致している必要があります。
REDIRECT_URI = "https://felix-app-prbmr4ghbjai7n7hzfyahj.streamlit.app/"

def main():
    st.set_page_config(page_title="LINE ID 取得テスト", layout="centered")
    st.title("LINE ID 表示テスト (最終版)")

    # --- セッション管理（二重実行バグを完全に防ぐための要） ---
    if "line_user_id" not in st.session_state:
        st.session_state.line_user_id = None
    if "line_display_name" not in st.session_state:
        st.session_state.line_display_name = None
    if "processed_code" not in st.session_state:
        st.session_state.processed_code = None
    if "error_message" not in st.session_state:
        st.session_state.error_message = None

    # URLパラメータの取得
    qp = st.query_params
    code = qp.get("code")

    # ==========================================================
    # 1. 認証コード(code)を受け取り、まだ処理していない場合のみ実行
    # ==========================================================
    if code and st.session_state.processed_code != code:
        # 瞬時に「処理済み」としてロックし、Streamlitの2回目実行を弾く
        st.session_state.processed_code = code
        
        with st.spinner("LINEサーバーと通信中..."):
            # Token交換API
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
                
                # Profile取得API
                profile_res = requests.get(
                    "https://api.line.me/v2/profile", 
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if profile_res.status_code == 200:
                    # 取得成功：データをセッションに保存
                    st.session_state.line_user_id = profile_res.json().get("userId")
                    st.session_state.line_display_name = profile_res.json().get("displayName")
                    st.session_state.error_message = None
                else:
                    # Profileエラー
                    st.session_state.error_message = f"Profile取得エラー: {profile_res.text}"
            else:
                # Tokenエラー
                st.session_state.error_message = f"Token取得エラー({res.status_code}): {res.text}"
        
        # 処理が終わったらURLから「code」を消去し、画面をリフレッシュする
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
    # 4. 初回アクセス時の画面（リンク表示）
    # ==========================================================
    else:
        st.info("下のリンクをタップして、LINE認証へ進んでください。")
        encoded_uri = urllib.parse.quote(REDIRECT_URI, safe='')
        login_url = f"https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id={LINE_CLIENT_ID}&redirect_uri={encoded_uri}&state=test_mode&scope=profile%20openid"
        
        st.markdown(f"## [👉 LINEログインしてIDを取得する]({login_url})")

if __name__ == "__main__":
    main()
