import streamlit as st
import pandas as pd
import io
import numpy as np

# --- 1. 定数とヘッダーの定義 ---
GROUP_TYPE_MAP = {
    "調光": "1ch",
    "調光調色": "2ch",
    "Synca": "3ch",
    "Synca Bright": "fresh 3ch"
}

NUM_COLS = 74

# 元のCSVの3行分を定義
ROW1 = ['Zone情報', None, None, None, 'Group情報', None, None, None, None, 'Scene情報', None, None, None, None, None, None, None, 'Timetable情報', None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, 'Timetable-schedule情報', None, None, None, None, None, None, None, None, None, 'Timetable期間/特異日情報', None, None, None, None, None, 'センサーパターン情報', None, None, None, None, 'センサータイムテーブル情報', None, None, 'センサータイムテーブル/スケジュール情報', None, None, None, None, None, None, None, None, None, 'センサータイムテーブル期間/特異日情報', None, None, None, None]
ROW2 = [None] * NUM_COLS
ROW3 = ['[zone]', '[id]', '[fade]', None, '[group]', '[id]', '[type]', '[zone]', None, '[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]', None, '[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', None, '[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]', None, '[zone-period]', '[start]', '[end]', '[timetable]', '[zone]', None, '[pattern]', '[id]', '[type]', '[mode]', None, '[sensor-timetable]', '[id]', None, '[sensor-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]', None, '[sensor-period]', '[start]', '[end]', '[timetable]', '[group]']

ROW1 = (ROW1 + [None] * NUM_COLS)[:NUM_COLS]
ROW3 = (ROW3 + [None] * NUM_COLS)[:NUM_COLS]
CSV_HEADER = [ROW1, ROW2, ROW3]

def make_unique_cols(header_row):
    seen = {}
    unique_names = []
    for i, name in enumerate(header_row):
        base = str(name) if name and str(name) != 'nan' else "col"
        if base not in seen:
            seen[base] = 0
            unique_names.append(base)
        else:
            seen[base] += 1
            unique_names.append(f"{base}_{seen[base]}")
    return unique_names

# --- 2. アプリ基本設定 ---
st.set_page_config(page_title="Lighting Setting App", layout="wide")
st.title("店舗設定データ作成アプリ ⚙️")

# セッションステート初期化
if 'z_df' not in st.session_state:
    st.session_state.z_df = pd.DataFrame([{"ゾーン名": "", "フェード秒": 0}])
if 'g_df' not in st.session_state:
    st.session_state.g_df = pd.DataFrame([{"グループ名": "", "グループタイプ": "調光", "紐づけるゾーン名": ""}])
if 's_df' not in st.session_state:
    # 順番: シーン名 -> ゾーン名 -> グループ名 -> 調光 -> 調色
    st.session_state.s_df = pd.DataFrame([{"シーン名": "", "紐づけるゾーン名": "", "紐づけるグループ名": "", "調光": 100, "調色": ""}])

# ① 店舗名入力
st.header("1. 基本情報")
store = st.text_input("店舗名", value="店舗A")
fn = f"{store}_setting_data.csv"

st.divider()

# ② ゾーン情報
st.header("2. ゾーン情報の入力")
z_edit = st.data_editor(st.session_state.z_df, num_rows="dynamic", use_container_width=True, key="z_ed_key")
st.session_state.z_df = z_edit
v_zones = [str(z).strip() for z in z_edit["ゾーン名"].tolist() if str(z).strip()]

# ③ グループ情報
st.header("3. グループ情報の入力")
g_edit = st.data_editor(
    st.session_state.g_df,
    num_rows="dynamic",
    column_config={
        "グループタイプ": st.column_config.SelectboxColumn(options=list(GROUP_TYPE_MAP.keys())),
        "紐づけるゾーン名": st.column_config.SelectboxColumn(options=[""] + v_zones)
    },
    use_container_width=True,
    key="g_ed_key"
)
st.session_state.g_df = g_edit
v_groups = [str(g).strip() for g in g_edit["グループ名"].tolist() if str(g).strip()]
g_type_lookup = dict(zip(g_edit["グループ名"], g_edit["グループタイプ"]))

# ④ シーン情報
st.header("4. シーン情報の入力")
st.caption("範囲: 調光調色(2700-6500K), Synca系(1800-12000K)")
s_edit = st.data_editor(
    st.session_state.s_df,
    num_rows="dynamic",
    column_config={
        "紐づけるゾーン名": st.column_config.SelectboxColumn(options=[""] + v_zones),
        "紐づけるグループ名": st.column_config.SelectboxColumn(options=[""] + v_groups),
        "調光": st.column_config.NumberColumn(min_value=0, max_value=100)
    },
    use_container_width=True,
    key="s_ed_key"
)
st.session_state.s_df = s_edit

st.divider()

# --- 5. 出力とバリデーション ---
if st.button("内容を確認してプレビュー", type="primary"):
    zf = z_edit[z_edit["ゾーン名"] != ""].reset_index(drop=True)
    gf = g_edit[g_edit["グループ名"] != ""].reset_index(drop=True)
    sf = s_edit[s_edit["シーン名"] != ""].reset_index(drop=True)
    
    # ケルビンチェック
    e_msgs = []
    for i, row in sf.iterrows():
        gn = row["紐づけるグループ名"]
        kv = str(row["調色"]).upper().replace("K", "").strip()
        if gn in g_type_lookup and kv.isdigit():
            k = int(kv)
            tp = g_type_lookup[gn]
            if tp == "調光調色" and not (2700 <= k <= 6500):
                e_msgs.append(f"行{i+1}: {gn}の範囲は2700-6500Kです({
