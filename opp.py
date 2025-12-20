import streamlit as st
import pandas as pd
import io
import numpy as np

# --- 1. Constant Definitions ---
GROUP_TYPE_MAP = {
    "調光": "1ch",
    "調光調色": "2ch",
    "Synca": "3ch",
    "Synca Bright": "fresh 3ch"
}

NUM_COLS = 74

# Define CSV Headers
ROW1 = ['Zone情報', None, None, None, 'Group情報', None, None, None, None, 'Scene情報', None, None, None, None, None, None, None, 'Timetable情報', None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, 'Timetable-schedule情報', None, None, None, None, None, None, None, None, None, 'Timetable期間/特異日情報', None, None, None, None, None, 'センサーパターン情報', None, None, None, None, 'センサータイムテーブル情報', None, None, 'センサータイムテーブル/スケジュール情報', None, None, None, None, None, None, None, None, None, 'センサータイムテーブル期間/特異日情報', None, None, None, None]
ROW2 = [None] * NUM_COLS
ROW3 = ['[zone]', '[id]', '[fade]', None, '[group]', '[id]', '[type]', '[zone]', None, '[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]', None, '[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', None, '[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]', None, '[zone-period]', '[start]', '[end]', '[timetable]', '[zone]', None, '[pattern]', '[id]', '[type]', '[mode]', None, '[sensor-timetable]', '[id]', None, '[sensor-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]', None, '[sensor-period]', '[start]', '[end]', '[timetable]', '[group]']

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

# --- 2. Streamlit Config ---
st.set_page_config(page_title="Lighting Configurator", layout="wide")
st.title("Lighting Setting Data App ⚙️")

# Session State Initialization
if 'zone_df' not in st.session_state:
    st.session_state.zone_df = pd.DataFrame([{"Zone Name": "", "Fade(sec)": 0}])
if 'group_df' not in st.session_state:
    st.session_state.group_df = pd.DataFrame([{"Group Name": "", "Type": "調光", "Link Zone": ""}])
if 'scene_df' not in st.session_state:
    # Order: Scene -> Zone -> Group -> Dimming -> Color
    st.session_state.scene_df = pd.DataFrame([{"Scene Name": "", "Link Zone": "", "Link Group": "", "Dimming": 100, "Color(K)": ""}])

# --- 3. Input UI ---
st.header("1. Store Info")
shop_name = st.text_input("Store Name", value="StoreA")
output_filename = f"{shop_name}_setting_data.csv"

st.divider()

st.header("2. Zone Settings")
zone_edit = st.data_editor(st.session_state.zone_df, num_rows="dynamic", use_container_width=True, key="z_edit_v5")
st.session_state.zone_df = zone_edit
valid_zones = [str(z).strip() for z in zone_edit["Zone Name"].tolist() if str(z).strip()]

st.header("3. Group Settings")
group_edit = st.data_editor(
    st.session_state.group_df,
    num_rows="dynamic",
    column_config={
        "Type": st.column_config.SelectboxColumn(options=list(GROUP_TYPE_MAP.keys())),
        "Link Zone": st.column_config.SelectboxColumn(options=[""] + valid_zones)
    },
    use_container_width=True,
    key="g_edit_v5"
)
st.session_state.group_df = group_edit
valid_groups = [str(g).strip() for g in group_edit["Group Name"].tolist() if str(g).strip()]
group_to_type = dict(zip(group_edit["Group Name"], group_edit["Type"]))

st.header("4. Scene Settings")
st.caption("Color Check: 調光調色(2700-6500K), Synca(1800-12000K)")
scene_edit = st.data_editor(
    st.session_state.scene_df,
    num_rows="dynamic",
    column_config={
        "Link Zone": st.column_config.SelectboxColumn(options=[""] + valid_zones),
        "Link Group": st.column_config.SelectboxColumn(options=[""] + valid_groups),
        "Dimming": st.column_config.NumberColumn(min_value=0, max_value=100, format="%d%%")
    },
    use_container_width=True,
    key="s_edit_v5"
)
st.session_state.scene_df = scene_edit

st.divider()

# --- 4. Validation & CSV Output ---
if st.button("Preview and Verify", type="primary"):
    z_f = zone_edit[zone_edit["Zone Name"].str.strip() != ""].reset_index(drop=True)
    g_f = group_edit[group_edit["Group Name"].str.strip() != ""].reset_index(drop=True)
    s_f = scene_edit[scene_edit["Scene Name"].str.strip() != ""].reset_index(drop=True)
    
    # Validation for Kelvin
    errs = []
    for i, row in s_f.iterrows():
        g_n = row["Link Group"]
        k_str = str(row["Color(K)"]).upper().replace("K", "").strip()
        if g_n in group_to_type and k_str.isdigit():
            k = int(k_str)
            tp = group_to_type[g_n]
            if tp == "調光調色" and not (2700 <= k <= 6500):
                errs.append(f"Row {i+1}: {g_n}(調光調色) must be 2700-6500K. Input: {k}K")
            elif tp in ["Synca", "Synca Bright"] and not (1800 <= k <= 12000):
                errs.append(f"Row {i+1}: {g_n}({tp}) must be 1800-12000K. Input: {k}K")
    
    if errs:
        for e in errs: st.error(e)
    else:
        # Build Data Matrix
        max_r = max(len(z_f), len(g_f), len(s_f))
        mat = pd.DataFrame(index=range(max_r), columns=range(NUM_COLS))
        for i, r in z_f.iterrows():
            mat.iloc[i, 0], mat.iloc[i, 1], mat.iloc[i, 2] = r["Zone Name"], 4097+i, r["Fade(sec)"]
        for i, r in g_f.iterrows():
            mat.iloc[i, 4], mat.iloc[i, 5], mat.iloc[i, 6], mat.iloc[i, 7] = r["Group Name"], 32769+i, GROUP_TYPE_MAP.get(r["Type"], ""), r["Link Zone"]
        for i, r in s_f.iterrows():
            mat.iloc[i, 9], mat.iloc[i, 10], mat.iloc[i, 11], mat.iloc[i, 12], mat.iloc[i, 14], mat.iloc[i, 15] = r["Scene Name"], 8193+i, r["Dimming"], r["Color(K)"], r["Link Zone"], r["Link Group"]

        st.session_state.out_df = pd.concat([pd.DataFrame([ROW1, ROW2, ROW3]), mat], ignore_index=True)
        st.subheader("5. Final Preview")
        p_df = st.session_state.out_df.copy()
        p_df.columns = make_unique_cols(ROW3)
        st.dataframe(p_df.iloc[3:], hide_index=True, use_container_width=True)

if 'out_df' in st.session_state:
    buf = io.BytesIO()
    st.session_state.out_df.to_csv(buf, index=False, header=False, encoding="utf-8-sig")
    st.download_button("📥 Download CSV", buf.getvalue(), output_filename, "text

