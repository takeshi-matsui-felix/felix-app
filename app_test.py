import streamlit as st
import streamlit.components.v1 as components
import requests
import urllib.parse

# === LINE API設定 ===
LINE_CLIENT_ID = "2010108828"
LINE_CLIENT_SECRET = "2c73ce25e71858bcb09c89c79fa6bbe0"

def main():
    st.title("🧪 LINE ID 取得 単体テスト (URL自動認識版)")

    # 自身のURLをJavaScriptで自動取得（部分編集を完全に無くすための処理）
    if "my_url" not in st.session_state:
        st.session_state.my_url = None

    # URL取得用の目に見えないコンポーネント
    url_detector = components.html("""
    <script>
        const currentUrl = window.parent.location.href.split('?')[0];
        window.parent.postMessage({
            isStreamlitMessage: true,
            type: "streamlit:setComponentValue",
            value: currentUrl
        }, "*");
    </script>
    """, height=0)

    if url_detector:
        st.session_state.my_url = url_detector

    # URLが取得できるまで待機
    if not st.session_state.my_url:
        st.info("🔄 アプリのURLを自動解析中。しばらくお待ちください...")
        st.stop()

    # 自動認識したURLを帰り道（REDIRECT_URI）として確定
    REDIRECT_URI = st.session_state.my_url

    # LINE Developers登録用の案内を表示
    st.markdown(f"""
    <div style="background-color:#FFF3CD; padding:15px; border-radius:8px; border-left:5px solid #FFA500; margin-bottom:20px;">
        <strong>⚠️ テスト前の確認事項</strong><br>
        LINE Developersの「コールバックURL」に、以下のURLが正しく登録されているか確認してください。<br>
        <code>{REDIRECT_URI}</code>
    </div>
    """, unsafe_allow_html=True)

    # URLのパラメータを取得
    qp = st.query_params
    code = qp.get("code")

    # 1️⃣ LINEから戻ってきた時（codeがある時）の処理
    if code:
        st.info(f"✅ LINEからコードを受け取りました: {code}")
        
        # Token交換
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
            st.success("✅ アクセストークン取得成功！")
            
            # プロフィール取得
            profile_res = requests.get(
                "https://api.line.me/v2/profile", 
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if profile_res.status_code == 200:
                user_id = profile_res.json().get("userId")
                display_name = profile_res.json().get("displayName")
                
                st.balloons()
                st.markdown("## 🎉 取得大成功！！")
                st.markdown(f"### あなたのLINE ID: **`{user_id}`**")
                st.markdown(f"### LINEの名前: **{display_name}**")
            else:
                st.error(f"❌ プロフィール取得エラー: {profile_res.text}")
        else:
            st.error(f"❌ トークン取得エラー: {res.text}")
            
        if st.button("もう一度最初からテストする"):
            st.query_params.clear()
            st.session_state.my_url = None
            st.rerun()

    # 2️⃣ 最初の画面（リンクを押す前）
    else:
        st.write("下のリンクをクリックして、LINEの認証画面へ飛んでください。")
        encoded_uri = urllib.parse.quote(REDIRECT_URI, safe='')
        login_url = f"https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id={LINE_CLIENT_ID}&redirect_uri={encoded_uri}&state=test_state_123&scope=profile%20openid"
        
        st.markdown(f"### [👉 ここをタップしてLINE連携をテスト]({login_url})")

if __name__ == "__main__":
    main()
