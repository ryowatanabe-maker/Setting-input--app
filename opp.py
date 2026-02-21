import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="スケジュール設定アプリ", layout="wide")

st.title("📅 スケジュール設定アプリ (高機能版)")

st.sidebar.header("CSVインポート設定")
uploaded_file = st.sidebar.file_uploader("CSVファイルをアップロードしてください", type=['csv'])

if uploaded_file is not None:
    try:
        # ファイルの読み込み
        content = uploaded_file.getvalue()
        try:
            # 3行目（index=2）をヘッダーとして読み込み
            df = pd.read_csv(io.BytesIO(content), encoding='utf-8', header=2)
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(content), encoding='shift_jis', header=2)

        # カラム名から [] を取り除く（例: [zone] -> zone）
        # これにより、既存のコードが zone という名前でデータを参照できるようになります
        df.columns = [c.replace('[', '').replace(']', '') if isinstance(c, str) else c for c in df.columns]

        # 読み込み成功の表示
        st.success("CSVの読み込みに成功しました（3行目をヘッダーとして認識しました）")

        # データの確認
        if df.empty:
            st.warning("ヘッダーは読み込めましたが、データが1行もありません。")
        
        st.subheader("インポートされたデータのプレビュー")
        st.dataframe(df, use_container_width=True)

        # ここにスケジュール処理のロジックを追加
        # 例: if 'zone' in df.columns: ...

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
        st.info("CSVの3行目に正しい項目名（[zone]など）があるか確認してください。")

else:
    st.info("サイドバーからCSVファイルをアップロードしてください。")
