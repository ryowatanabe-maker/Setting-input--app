import streamlit as st
import pandas as pd
import io

# --- 1. 定数とヘッダーの定義 ---
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
NUM_COLS = 236 

# ヘッダー作成 (アップロードされたCSVの構造を再現)
ROW1 = [None] * NUM_COLS
ROW1[0], ROW1[4], ROW1[9], ROW1[17], ROW1[197], ROW1[207], ROW1[213], ROW1[218], ROW1[221], ROW1[231] = \
    'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報', 'Timetable-schedule情報', 'Timetable期間/特異日情報', 'センサーパターン情報', 'センサータイムテーブル情報', 'センサータイムテーブル/スケジュール情報', 'センサータイムテーブル期間/特異日情報'

ROW3 = [None] * NUM_COLS
ROW3[0:3] = ['[zone]', '[id]', '[fade]']
ROW3[4:8] = ['[group]', '[id]', '[type]', '[zone]']
ROW3[9:16] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]']
ROW3[17:22] = ['[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]']
for i in range(22, 196, 2):
    ROW3[i] = '[time]'
    ROW3[i+1] = '[scene]'
ROW3[197:206] = ['[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]']
ROW3[207:212] = ['[zone-period]', '[start]', '[end]', '[timetable]', '[zone]']

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
for key in ['z_list', 'g_list', 's_list', 'tt_list']:
    if key not in st.session_state: st.session_state[key] = []

# --- 3. UIセクション ---

st.header("1. 店舗名入力")
shop_name = st.text_input("店舗名", value="店舗A")

st.divider()

# 2. ゾーン情報
st.header("2. ゾーン情報")
z_df = st.data_editor(pd.DataFrame(st.session_state.z_list if st.session_state.z_list else [{"ゾーン名": "", "フェード秒": 0}]), num_rows="dynamic", use_container_width=True, key="z_ed_v17")
v_zones = [""] + [z for z in z_df["ゾーン名"].tolist() if z]

# 3. グループ情報
st.header("3. グループ情報")
g_df = st.data_editor(pd.DataFrame(st.session_state.g_list if st.session_state.g_list else [{"グループ名": "", "グループタイプ": "調光", "紐づけるゾーン名": ""}]), 
                      column_config={"グループタイプ": st.column_config.SelectboxColumn(options=list(GROUP_TYPE_MAP.keys())), "紐づけるゾーン名": st.column_config.SelectboxColumn(options=v_zones)},
                      num_rows="dynamic", use_container_width=True, key="g_ed_v17")
g_to_zone = dict(zip(g_df["グループ名"], g_df["紐づけるゾーン名"]))
g_to_type = dict(zip(g_df["グループ名"], g_df["グループタイプ"]))
v_groups = [""] + [g for g in g_df["グループ名"].tolist() if g]

st.divider()

# 4. シーン情報
st.header("4. シーン情報の追加")
st.write("- **調光調色**: 2700 〜 6500 / **Synca**: 1800 〜 12000")

with st.form("scene_form", clear_on_submit=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1: s_name = st.text_input("シーン名")
    with col2: target_g = st.selectbox("グループ名", options=v_groups)
    with col3: dim = st.number_input("調光(%)", 0, 100, 100)
    with col4: color = st.text_input("調色(K)")
    
    if st.form_submit_button("このシーンにグループを追加"):
        if
