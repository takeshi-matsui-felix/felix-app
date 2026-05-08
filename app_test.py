import streamlit as st

st.title("📸 純正カメラのスピードテスト")
st.write("Streamlit標準のカメラ機能がサクサク動くかテストします。")

# カメラ機能のみを呼び出す
photo = st.camera_input("ここをタップして撮影")

# 撮影されたら下に表示する
if photo is not None:
    st.success("撮影完了！スピードはどうでしたか？")
    st.image(photo, caption="撮影された写真", use_container_width=True)
