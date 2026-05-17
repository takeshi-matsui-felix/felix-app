import streamlit as st
import requests
import urllib.parse

# === LINE API設定 ===
LINE_CLIENT_ID = "2010108828"
LINE_CLIENT_SECRET = "2c73ce25e71858bcb09c89c79fa6bbe0"
REDIRECT_URI = "https://felix-app-prbmr4ghbjai7n7hzfyahj.streamlit.app/"

def main():
    st.title("LINE ID 表示アプリ")

    # URLパラメータから認証コードを取得
    qp = st.query_params
    code = qp.get("code")

    # LINEから戻ってきた処理
    if code:
        # 1. アクセストークンの取得
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
            
            # 2. プロフィール情報の取得
            profile_res = requests.get(
                "https://api.line.me/v2/profile", 
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if profile_res.status_code == 200:
                line_user_id = profile_res.json().get("userId")
                line_name = profile_res.json().get("displayName")
                
                # 3. 取得したIDを画面に表示
                st.success("🎉 LINE IDの取得に成功しました")
                st.markdown(f"### 取得したLINE ID:\n`{line_user_id}`")
                st.markdown(f"### LINE登録名: {line_name}")
            else:
                st.error(f"プロフィール取得失敗: {profile_res.text}")
        else:
            st.error(f"トークン取得失敗: {res.text}")
            
        if st.button("最初に戻る"):
            st.query_params.clear()
            st.rerun()

    # 最初の画面処理
    else:
        st.write("以下のリンクからLINEログインを行ってください。")
        encoded_uri = urllib.parse.quote(REDIRECT_URI, safe='')
        # URLの不具合を防ぐためstateのスペースを排除
        login_url = f"https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id={LINE_CLIENT_ID}&redirect_uri={encoded_uri}&state=felix_test&scope=profile%20openid"
        
        st.markdown(f"## [👉 LINEログインしてIDを表示する]({login_url})")

if __name__ == "__main__":
    main()
