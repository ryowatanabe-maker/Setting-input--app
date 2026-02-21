import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="スケジュール設定アプリ", layout="wide")

st.title("📅 スケジュール設定アプリ (見本データ読込済)")

# 1. 見本CSVのデータをそのまま変数に格納 (GitHubのファイル内容を再現)
csv_data = """Zone情報,,,,Group情報,,,,,Scene情報,,,,,,,,Timetable情報,,,,,,,,,,,,,,,,,,Timetable-schedule情報,,,,,,,,,,Timetable期間/特異日情報,,,,,,センサーパターン情報,,,,,センサータイムテーブル情報,,,センサータイムテーブル/スケジュール情報,,,,,,,,,,センサータイムテーブル期間/特異日情報,,,,
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
[zone],[id],[fade],,[group],[id],[type],[zone],,[scene],[id],[dimming],[color],[perform],[zone],[group],,[zone-timetable],[id],[zone],[sun-start-scene],[sun-end-scene],[time],[scene],[time],[scene],[time],[scene],[time],[scene],[time],[scene],[time],[scene],,[zone-ts],[daily],[monday],[tuesday],[wednesday],[thursday],[friday],[saturday],[sunday],,[zone-period],[start],[end],[timetable],[zone],,[pattern],[id],[type],[mode],,[sensor-timetable],[id],,[sensor-ts],[daily],[monday],[tuesday],[wednesday],[thursday],[friday],[saturday],[sunday],,[sensor-period],[start],[end],[timetable],[group]
zone_A,1,10,,group_A,101,dim,zone_A,,scene_1,201,80,white,static,zone_A,group_A,,zt_01,301,zone_A,sc_start,sc_end,09:00,sc_day,12:00,sc_noon,18:00,sc_eve,,,,,,,zts_01,1,1,1,1,1,1,0,0,,zp_01,2023-10-01,2023-12-31,zt_01,zone_A,,p_01,401,motion,auto,,st_01,501,,sts_01,1,1,1,1,1,1,0,0,,sp_01,2023-10-01,2023-12-31,st_01,group_A
"""

# 2. データの読み込み処理
@st.cache_data
def load_internal_data():
    # 3行目をヘッダーとして読み込み
    df = pd.read_csv(io.StringIO(csv_data), header=2)
    # カラム名の [] を除去
    df.columns = [c.replace('[', '').replace(']', '') if isinstance(c, str) else c for c in df.columns]
    # 未使用の空カラム（Unnamed）を除去
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    return df

# データの初期化
if 'df' not in st.session_state:
    st.session_state.df = load_internal_data()

# 3. アプリ画面の構築
st.subheader("現在の設定データ")
st.info("見本データを読み込みました。以下のテーブルで直接編集できます。")

# データエディタ（アプリ上で入力・修正ができる機能）
edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

# 保存ボタンなどのアクション
if st.button("設定を確定する"):
    st.session_state.df = edited_df
    st.success("設定を更新しました！")
    st.json(st.session_state.df.to_dict(orient='records')) # 動作確認用に中身を表示

# サイドバーにリセットボタン
if st.sidebar.button("見本データにリセット"):
    st.session_state.df = load_internal_data()
    st.rerun()
