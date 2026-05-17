import streamlit as st
import requests
import urllib.parse

# === LINE API設定 ===
LINE_CLIENT_ID = "2010108828"
LINE_CLIENT_SECRET = "2c73ce25e71858bcb09c89c79fa6bbe0"
REDIRECT_URI = "https://felix-app-prbmr4ghbjai7n7hzfyahj.streamlit.app/"

def main():
    st.set_page_config(page_title="LINE ID 取得テスト", layout="centered")
    st.title("LINE ID 表示テスト (リロード禁止版)")

    # URLパラメータを直接取得（記憶に頼らない）
    qp = st.query_params
    code = qp.get("code")

    # ==========================================================
    # 1. LINEからコードを持って帰ってきた瞬間の処理（リロードなし）
    # ==========================================================
    if code:
        st.info("✅ URLから暗号コードを受信しました！通信を開始します...")
        
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
                line_user_id = profile_res.json().get("userId")
                line_display_name = profile_res.json().get("displayName")
                
                # 取得した瞬間にそのまま画面に出力（再読込させない）
                st.success("🎉 LINE IDの取得に完全成功しました！")
                st.markdown(f"### 取得したLINE ID:\n**`{line_user_id}`**")
                st.markdown(f"### LINE登録名:\n**{line_display_name}**")
            else:
                st.error(f"❌ Profile取得エラー: {profile_res.text}")
        else:
            st.error(f"❌ Token取得エラー({res.status_code}): {res.text}")
            
        st.warning("※画面はこのまま動かさないでください（ページを更新すると消えます）")
        
        if st.button("テストを終了して最初に戻る"):
            st.query_params.clear()
            st.rerun()

    # ==========================================================
    # 2. 初回アクセス時の画面
    # ==========================================================
    else:
        st.info("下のURLをコピーしてブラウザで開き、LINE認証へ進んでください。")
        encoded_uri = urllib.parse.quote(REDIRECT_URI, safe='')
        login_url = f"https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id={LINE_CLIENT_ID}&redirect_uri={encoded_uri}&state=test_mode&scope=profile%20openid"
        
        st.link_button("👉 LINEログインしてIDを取得する", login_url, type="primary", use_container_width=True)
        st.markdown("---")
        st.code(login_url)

if __name__ == "__main__":
    main()
