import streamlit as st
import pandas as pd
import io

# --- 1. 定数とヘッダーの定義 ---
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
NUM_COLS = 236 

# ヘッダー構造
ROW1 = [None] * NUM_COLS
ROW1[0], ROW1[4], ROW1[9], ROW1[17], ROW1[197], ROW1[207], ROW1[213], ROW1[218], ROW1[221], ROW1[231] = \
    'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報', 'Timetable-schedule情報', 'Timetable期間/特異日情報', 'センサーパターン情報', 'センサータイムテーブル情報', 'センサータイムテーブル/スケジュール情報', 'センサータイムテーブル期間/特異日情報'

ROW3 = [None] * NUM_COLS
ROW3[0:3] = ['[zone]', '[id]', '[fade]']
ROW3[4:8] = ['[group]', '[id]', '[type]', '[zone]']
ROW3[9:17] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[fresh-key]', '[zone]', '[group]']
ROW3[17:22] = ['[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]']
for i in range(22, 196, 2):
    ROW3[i] = '[time]'; ROW3[i+1] = '[scene]'
ROW3[197:206] = ['[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]']
ROW3[207:212] = ['[zone-period]', '[start]', '[end]', '[timetable]', '[zone]']

CSV_HEADER = [ROW1, [None] * NUM_COLS, ROW3]

# --- 2. アプリ設定 ---
st.set_page_config(page_title="設定データ作成アプリ", layout="wide")
st.title("設定データ作成アプリ ⚙️")

# セッション管理（初期化時にカラム名を固定してKeyErrorを防止）
if 'z_list' not in st.session_state: 
    st.session_state.z_list = pd.DataFrame(columns=["ゾーン名", "フェード秒"])
if 'g_list' not in st.session_state: 
    st.session_state.g_list = pd.DataFrame(columns=["グループ名", "グループタイプ", "紐づけるゾーン名"])
if 's_list' not in st.session_state: st.session_state.s_list = []
if 'tt_list' not in st.session_state: st.session_state.tt_list = []

# --- 3. UIセクション ---
st.header("1. 店舗名入力")
shop_name = st.text_input("店舗名", value="店舗A")

st.divider()

# 2. ゾーン情報
st.header("2. ゾーン情報")
z_df = st.data_editor(st.session_state.z_list, num_rows="dynamic", use_container_width=True, key="z_editor_v21")
st.session_state.z_list = z_df
# 安全にゾーンリストを取得
v_zones = [""] + [z for z in z_df["ゾーン名"].dropna().tolist() if str(z).strip()]

# 3. グループ情報
st.header("3. グループ情報")
g_df = st.data_editor(st.session_state.g_list, 
                      column_config={
                          "グループタイプ": st.column_config.SelectboxColumn(options=list(GROUP_TYPE_MAP.keys())), 
                          "紐づけるゾーン名": st.column_config.SelectboxColumn(options=v_zones)
                      },
                      num_rows="dynamic", use_container_width=True, key="g_editor_v21")
st.session_state.g_list = g_df
g_to_zone = dict(zip(g_df["グループ名"], g_
