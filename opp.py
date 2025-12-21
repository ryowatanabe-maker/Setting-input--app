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

# --- 2. アプリ設定 ---
st.set_page_config(page_title="設定データ作成アプリ", layout="wide")
st.title("設定データ作成アプリ ⚙️")

# セッションステートの初期化
if 'z_df' not in st.session_state:
    st.session_state.z_df = pd.DataFrame([{"ゾーン名": "", "フェード秒": 0}])
if 'g_df' not in st.session_state:
    st.session_state.g_df = pd.DataFrame([{"グループ名": "", "グループタイプ": "調光", "紐づけるゾーン名": ""}])
if 's_df' not in st.session_state:
    # 順番: シーン名 -> 紐づけるグループ名 -> 紐づけるゾーン名
    st.session_state.s_df = pd.DataFrame([{"シーン名": "", "紐づけるグループ名": "", "紐づけるゾーン名": "", "調光": 100, "調色": ""}])
if 'scene_master' not in st.session_state:
    st.session_state.scene_master = [""]

# --- 3. UI セクション ---

st.header("1. 店舗名入力")
shop_name = st.text_input("店舗名", value="店舗A")
out_filename = f"{shop_name}_setting_data.csv"

st.divider()

# 2. ゾーン情報
st.header("2. ゾーン情報")
z_edit = st.data_editor(st.session_state.z_df, num_rows="dynamic", use_container_width=True, key="z_edit_v11")
st.session_state.z_df = z_edit
v_zones = [""] + [str(z).strip() for z in z_edit["ゾーン名"].tolist() if str(z).strip()]

# 3. グループ情報
st.header("3. グループ情報")
g_edit = st.data_editor(
    st.session_state.g_df,
    num_rows="dynamic",
    column_config={
        "グループタイプ": st.column_config.SelectboxColumn(options=list(GROUP_TYPE_MAP.keys())),
        "紐づけるゾーン名": st.column_config.SelectboxColumn(options=v_zones)
    },
    use_container_width=True,
    key="g_edit_v11"
)
st.session_state.g_df = g_edit
v_groups = [""] + [str(g).strip() for g in g_edit["グループ名"].tolist() if str(g).strip()]
g_to_zone_dict = dict(zip(g_edit["グループ名"], g_edit["紐づけるゾーン名"]))
g_to_tp_dict = dict(zip(g_edit["グループ名"], g_edit["グループタイプ"]))

st.divider()

# 4. シーン情報
st.header("4. シーン情報")

# シーン名マスター登録エリア
with st.expander("シーン名を追加・管理"):
    new_s = st.text_input("登録するシーン名")
    if st.button("登録"):
        if new_s and new_s not in st.session_state.scene_master:
            st.session_state.scene_master.append(new_s)
            st.rerun()

st.caption(f"登録済みシーン名: {', '.join(st.session_state.scene_master)}")

# シーン情報の表示と編集
s_edit = st.data_editor
