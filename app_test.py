import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="HTML Catcher", layout="centered")
st.title("HTMLでURLを捕まえるテスト")

# 松井様のテスト用URLを完全に埋め込み（編集不要）
REDIRECT_URI = "https://felix-app-fu7ewqtabdecfmouhwgxni.streamlit.app/"

html_code = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: sans-serif; text-align: center; padding: 20px;">
    <h2 id="status">URLを解析中...</h2>
    <p id="result" style="font-size: 18px; font-weight: bold; color: blue; word-wrap: break-word;"></p>
    <script>
        window.onload = function() {
            try {
                // 親ウィンドウ（Streamlit）のURLから直接codeを抽出
                const params = new URLSearchParams(window.parent.location.search);
                const code = params.get("code");
                
                if (code) {
                    document.getElementById("status").innerText = "🎉 暗号コード(code)の捕獲に成功！";
                    document.getElementById("result").innerText = "LINEからのコード:\\n" + code;
                    document.getElementById("status").style.color = "green";
                } else {
                    document.getElementById("status").innerText = "❌ URLに code が見つかりません";
                    document.getElementById("status").style.color = "red";
                    document.getElementById("result").innerText = "現在のURL: " + window.parent.location.href;
                }
            } catch (e) {
                document.getElementById("status").innerText = "⚠️ エラー発生";
                document.getElementById("result").innerText = e.message;
            }
        };
    </script>
</body>
</html>
"""
components.html(html_code, height=300)

st.markdown("---")
# LINEログイン用のURL（テスト用URLをエンコード済）
login_url = "https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id=2010108828&redirect_uri=https%3A%2F%2Ffelix-app-fu7ewqtabdecfmouhwgxni.streamlit.app%2F&state=html_test&scope=profile%20openid"

st.markdown("**【テスト手順】以下のURLをコピーして、スマホのChromeブラウザで開いてログインしてください。**")
st.code(login_url)
