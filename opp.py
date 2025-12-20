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

# --- アプリ設定 ---
st.set_page_config(page_title="スケジュール設定アプリ", layout="wide")
st.title("店舗設定データ作成アプリ ⚙️")

if 'zone_df' not in st.session_state:
    st.session_state.zone_df = pd.DataFrame([{"ゾーン名": "", "フェード秒": 0}])
if 'group_df' not in st.session_state:
    st.session_state.group_df = pd.DataFrame([{"グループ名": "", "グループタイプ": "調光", "紐づけるゾーン名": ""}])
if 'scene_df' not in st.session_state:
    st.session_state.scene_df = pd.DataFrame([{"シーン名": "", "調光": 100, "調色": "", "紐づけるゾーン名": "", "紐づけるグループ名": ""}])

# ① 店舗名入力
st.header("① 店舗名を入力")
shop_name = st.text_input("店舗名", value="店舗A")
output_filename = f"{shop_name}_setting_data.csv"

st.divider()

# ② ゾーン情報
st.header("② ゾーン情報を入力")
zone_edit = st.data_editor(st.session_state.zone_df, num_rows="dynamic", use_container_width=True, key="z_edit")
st.session_state.zone_df = zone_edit
valid_zones = [z for z in zone_edit["ゾーン名"].tolist() if z]

# ③ グループ情報
st.header("③ グループ情報を入力")
group_edit = st.data_editor(
    st.session_state.group_df,
    num_rows="dynamic",
    column_config={
        "グループタイプ": st.column_config.SelectboxColumn(options=list(GROUP_TYPE_MAP.keys())),
        "紐づけるゾーン名": st.column_config.SelectboxColumn(options=[""] + valid_zones)
    },
    use_container_width=True,
    key="g_edit"
)
st.session_state.group_df = group_edit
valid_groups = [g for g in group_edit["グループ名"].tolist() if g]

# ④ シーン情報
st.header("④ シーン情報を入力")
scene_edit = st.data_editor(
    st.session_state.scene_df,
    num_rows="dynamic",
    column_config={
        "調光": st.column_config.NumberColumn(min_value=0, max_value=100, format="%d%%"),
        "紐づけるゾーン名": st.column_config.SelectboxColumn(options=[""] + valid_zones),
        "紐づけるグループ名": st.column_config.SelectboxColumn(options=[""] + valid_groups)
    },
    use_container_width=True,
    key="s_edit"
)
st.session_state.scene_df = scene_edit

st.divider()

# --- データ作成 ---
if st.button("プレビューを確認する", type="primary"):
    z_final = zone_edit[zone_edit["ゾーン名"] != ""].reset_index(drop=True)
    g_final = group_edit[group_edit["グループ名"] != ""].reset_index(drop=True)
    s_final = scene_edit[scene_edit["シーン名"] != ""].reset_index(drop=True)
    
    max_rows = max(len(z_final), len(g_final), len(s_final))
    data_matrix = pd.DataFrame(index=range(max_rows), columns=range(NUM_COLS))
    
    for i, row in z_final.iterrows():
        data_matrix.iloc[i, 0], data_matrix.iloc[i, 1], data_matrix.iloc[i, 2] = row["ゾーン名"], 4097 + i, row["フェード秒"]
    for i, row in g_final.iterrows():
        data_matrix.iloc[i, 4], data_matrix.iloc[i, 5], data_matrix.iloc[i, 6], data_matrix.iloc[i, 7] = row["グループ名"], 32769 + i, GROUP_TYPE_MAP.get(row["グループタイプ"], ""), row["紐づけるゾーン名"]
    for i, row in s_final.iterrows():
        data_matrix.iloc[i, 9], data_matrix.iloc[i, 10], data_matrix.iloc[i, 11], data_matrix.iloc[i, 12], data_matrix.iloc[i, 14], data_matrix.iloc[i, 15] = row["シーン名"], 8193 + i, row["調光"], row["調色"], row["紐づけるゾーン名"], row["紐づけるグループ名"]

    final_output_df = pd.concat([pd.DataFrame(CSV_HEADER), data_matrix], ignore_index=True)
    st.session_state.final_csv = final_output_df

    st.subheader("⑤ 最終確認")
    preview_df = final_output_df.copy()
    preview_df.columns = make_unique_cols(ROW3)
    st.dataframe(preview_df.iloc[3:], hide_index=True, use_container_width=True)

if 'final_csv' in st.session_state:
    # --- 文字化け対策の修正ポイント ---
    # BytesIOを使用してバイナリとして書き出すことで、BOM (utf-8-sig) を確実に保持します
    csv_buf = io.BytesIO()
    st.session_state.final_csv.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig")
    
    st.download_button(
        label="📥 CSVをダウンロードして出力 (文字化け修正版)",
        data=csv_buf.getvalue(),
        file_name=output_filename,
        mime="text/csv"
    )
