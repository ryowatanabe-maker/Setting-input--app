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

# セッションステートの初期化 (一番最初だけ実行)
if 'z_df' not in st.session_state:
    st.session_state.z_df = pd.DataFrame([{"ゾーン名": "", "フェード秒": 0}])
if 'g_df' not in st.session_state:
    st.session_state.g_df = pd.DataFrame([{"グループ名": "", "グループタイプ": "調光", "紐づけるゾーン名": ""}])
if 's_df' not in st.session_state:
    st.session_state.s_df = pd.DataFrame([{"シーン名": "", "紐づけるゾーン名": "", "紐づけるグループ名": "", "調光": 100, "調色": ""}])

# --- 3. UIセクション ---
st.header("1. 店舗名入力")
shop_name = st.text_input("店舗名", value="店舗A")
out_filename = f"{shop_name}_setting_data.csv"

st.divider()

# ② ゾーン情報
st.header("2. ゾーン情報")
# 消える対策: 戻り値を直接使わず、session_state を参照し続ける
z_edit = st.data_editor(
    st.session_state.z_df, 
    num_rows="dynamic", 
    use_container_width=True, 
    key="zone_editor_fixed"
)
# 編集のたびにsession_stateを上書き保存
st.session_state.z_df = z_edit
v_zones = [str(z).strip() for z in z_edit["ゾーン名"].tolist() if str(z).strip()]

# ③ グループ情報
st.header("3. グループ情報")
g_edit = st.data_editor(
    st.session_state.g_df,
    num_rows="dynamic",
    column_config={
        "グループタイプ": st.column_config.SelectboxColumn(options=list(GROUP_TYPE_MAP.keys())),
        "紐づけるゾーン名": st.column_config.SelectboxColumn(options=[""] + v_zones)
    },
    use_container_width=True,
    key="group_editor_fixed"
)
st.session_state.g_df = g_edit
v_groups = [str(g).strip() for g in g_edit["グループ名"].tolist() if str(g).strip()]
g_to_tp = dict(zip(g_edit["グループ名"], g_edit["グループタイプ"]))

# ④ シーン情報
st.header("4. シーン情報")
st.caption("調色: 調光調色(2700-6500K), Synca(1800-12000K)")
s_edit = st.data_editor(
    st.session_state.s_df,
    num_rows="dynamic",
    column_config={
        "紐づけるゾーン名": st.column_config.SelectboxColumn(options=[""] + v_zones),
        "紐づけるグループ名": st.column_config.SelectboxColumn(options=[""] + v_groups),
        "調光": st.column_config.NumberColumn(min_value=0, max_value=100, format="%d%%")
    },
    use_container_width=True,
    key="scene_editor_fixed"
)
st.session_state.s_df = s_edit

st.divider()

# --- 4. CSV出力処理 ---
if st.button("プレビューを確認する", type="primary"):
    zf = z_edit[z_edit["ゾーン名"].str.strip() != ""].reset_index(drop=True)
    gf = g_edit[g_edit["グループ名"].str.strip() != ""].reset_index(drop=True)
    sf = s_edit[s_edit["シーン名"].str.strip() != ""].reset_index(drop=True)
    
    # バリデーション
    errs = []
    for i, row in sf.iterrows():
        gn = row["紐づけるグループ名"]
        kv = str(row["調色"]).upper().replace("K", "").strip()
        if gn in g_to_tp and kv.isdigit():
            k = int(kv)
            tp = g_to_tp[gn]
            if tp == "調光調色" and not (2700 <= k <= 6500):
                errs.append(f"行{i+1}: {gn}(調光調色)は2700-6500Kの範囲外です({k}K)")
            elif tp in ["Synca", "Synca Bright"] and not (1800 <= k <= 12000):
                errs.append(f"行{i+1}: {gn}({tp})は1800-12000Kの範囲外です({k}K)")
    
    if errs:
        for e in errs: st.error(e)
    else:
        max_r = max(len(zf), len(gf), len(sf))
        mat = pd.DataFrame(index=range(max_r), columns=range(NUM_COLS))
        for i, r in zf.iterrows():
            mat.iloc[i, 0], mat.iloc[i, 1], mat.iloc[i, 2] = r["ゾーン名"], 4097+i, r["フェード秒"]
        for i, r in gf.iterrows():
            mat.iloc[i, 4], mat.iloc[i, 5], mat.iloc[i, 6], mat.iloc[i, 7] = r["グループ名"], 32769+i
