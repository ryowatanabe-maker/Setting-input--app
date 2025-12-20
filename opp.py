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

if 'z_template' not in st.session_state:
    st.session_state.z_template = pd.DataFrame([{"ゾーン名": "", "フェード秒": 0}])
if 'g_template' not in st.session_state:
    st.session_state.g_template = pd.DataFrame([{"グループ名": "", "グループタイプ": "調光", "紐づけるゾーン名": ""}])
if 's_template' not in st.session_state:
    st.session_state.s_template = pd.DataFrame([{"シーン名": "", "紐づけるゾーン名": "", "紐づけるグループ名": "", "調光": 100, "調色": ""}])

# ① 店舗名入力
st.header("1. 店舗名入力")
shop_name = st.text_input("店舗名", value="店舗A")
out_filename = f"{shop_name}_setting_data.csv"

st.divider()

# ② ゾーン情報
st.header("2. ゾーン情報")
z_edit = st.data_editor(st.session_state.z_template, num_rows="dynamic", use_container_width=True, key="zone_editor_stable")
v_zones = [str(z).strip() for z in z_edit["ゾーン名"].tolist() if str(z).strip()]

# ③ グループ情報
st.header("3. グループ情報")
g_edit = st.data_editor(
    st.session_state.g_template,
    num_rows="dynamic",
    column_config={
        "グループタイプ": st.column_config.SelectboxColumn(options=list(GROUP_TYPE_MAP.keys())),
        "紐づけるゾーン名": st.column_config.SelectboxColumn(options=[""] + v_zones)
    },
    use_container_width=True,
    key="group_editor_stable"
)
v_groups = [str(g).strip() for g in g_edit["グループ名"].tolist() if str(g).strip()]
g_to_tp = dict(zip(g_edit["グループ名"], g_edit["グループタイプ"]))

# ④ シーン情報
st.header("4. シーン情報")
st.caption("【入力規制】 調光調色: 2700-6500K / Synca系: 1800-12000K (範囲外はエラーになります)")

s_edit = st.data_editor(
    st.session_state.s_template,
    num_rows="dynamic",
    column_config={
        "紐づけるゾーン名": st.column_config.SelectboxColumn(options=[""] + v_zones),
        "紐づけるグループ名": st.column_config.SelectboxColumn(options=[""] + v_groups),
        "調光": st.column_config.NumberColumn(min_value=0, max_value=100, format="%d%%"),
        "調色": st.column_config.TextColumn("調色(K単位で数字のみ入力)")
    },
    use_container_width=True,
    key="scene_editor_stable"
)

# --- 5. リアルタイム・バリデーション表示 ---
s_valid = s_edit[s_edit["シーン名"].str.strip() != ""].copy()
validation_errors = []

for idx, row in s_valid.iterrows():
    gn = row["紐づけるグループ名"]
    kv_raw = str(row["調色"]).upper().replace("K", "").strip()
    
    if gn in g_to_tp and kv_raw.isdigit():
        k_val = int(kv_raw)
        tp = g_to_tp[gn]
        if tp == "調光調色" and not (2700 <= k_val <= 6500):
            validation_errors.append(f"❌ {idx+1}行目: {gn}は『調光調色』なので2700〜6500Kで入力してください。")
        elif tp in ["Synca", "Synca Bright"] and not (1800 <= k_val <= 12000):
            validation_errors.append(f"❌ {idx+1}行目: {gn}は『{tp}』なので1800〜12000Kで入力してください。")

if validation_errors:
    for err in validation_errors:
        st.error(err)

st.divider()

# --- 6. 実行処理 ---
#
