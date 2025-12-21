import streamlit as st
import pandas as pd
import io

# --- 1. 定数とヘッダーの定義 ---
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
NUM_COLS = 74

ROW1 = (['Zone情報', None, None, None, 'Group情報', None, None, None, None, 'Scene情報'] + [None] * 64)[:NUM_COLS]
ROW3 = (['[zone]', '[id]', '[fade]', None, '[group]', '[id]', '[type]', '[zone]', None, '[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]'] + [None] * 58)[:NUM_COLS]
CSV_HEADER = [ROW1, [None] * NUM_COLS, ROW3]

def make_unique_cols(header_row):
    seen = {}
    unique_names = []
    for i, name in enumerate(header_row):
        base = str(name) if name and str(name) != 'nan' else f"col_{i}"
        if base not in seen:
            seen[base] = 0; unique_names.append(base)
        else:
            seen[base] += 1; unique_names.append(f"{base}_{seen[base]}")
    return unique_names

# --- 2. アプリ設定 ---
st.set_page_config(page_title="設定データ作成アプリ", layout="wide")
st.title("設定データ作成アプリ ⚙️")

# セッションステートの初期化
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []

# --- 3. UIセクション ---

st.header("1. 店舗名入力")
shop_name = st.text_input("店舗名", value="店舗A")

st.divider()

# 2. ゾーン情報
st.header("2. ゾーン情報")
z_df = st.data_editor(pd.DataFrame(st.session_state.z_list if st.session_state.z_list else [{"ゾーン名": "", "フェード秒": 0}]), num_rows="dynamic", use_container_width=True, key="z_ed")
v_zones = [""] + [z for z in z_df["ゾーン名"].tolist() if z]

# 3. グループ情報
st.header("3. グループ情報")
g_df = st.data_editor(pd.DataFrame(st.session_state.g_list if st.session_state.g_list else [{"グループ名": "", "グループタイプ": "調光", "紐づけるゾーン名": ""}]), 
                      column_config={"グループタイプ": st.column_config.SelectboxColumn(options=list(GROUP_TYPE_MAP.keys())), "紐づけるゾーン名": st.column_config.SelectboxColumn(options=v_zones)},
                      num_rows="dynamic", use_container_width=True, key="g_ed")
g_to_zone = dict(zip(g_df["グループ名"], g_df["紐づけるゾーン名"]))
g_to_type = dict(zip(g_df["グループ名"], g_df["グループタイプ"]))
v_groups = [""] + [g for g in
