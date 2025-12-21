import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta

# --- 1. 定数とヘッダー定義 ---
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
NUM_COLS = 236 

ROW1 = [None] * NUM_COLS
ROW1[0], ROW1[4], ROW1[9], ROW1[17], ROW1[197], ROW1[207] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報', 'Timetable-schedule情報', 'Timetable期間/特異日情報'
ROW3 = [None] * NUM_COLS
ROW3[0:3], ROW3[4:8] = ['[zone]', '[id]', '[fade]'], ['[group]', '[id]', '[type]', '[zone]']
ROW3[9:17] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[fresh-key]', '[zone]', '[group]']
ROW3[17:22] = ['[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]']
for i in range(22, 196, 2): ROW3[i], ROW3[i+1] = '[time]', '[scene]'
CSV_HEADER = [ROW1, [None] * NUM_COLS, ROW3]

# --- 2. アプリ設定とデータ初期化 ---
st.set_page_config(page_title="設定データ作成アプリ", layout="wide")
st.title("設定データ作成アプリ ⚙️")

for key in ['z_list', 'g_list', 's_list', 'tt_list']:
    if key not in st.session_state: st.session_state[key] = []

# --- 3. UIセクション ---
st.header("1. 店舗名入力")
shop_name = st.text_input("店舗名", value="店舗A")
st.divider()

# --- 2. ゾーン登録 ---
st.header("2. ゾーン登録")
with st.form("z_form", clear_on_submit=True):
    col_z1, col_z2 = st.columns(2)
    z_name = col_z1.text_input("ゾーン名")
    z_fade = col_z2.number_input("フェード秒", 0, 60, 0)
    if st.form_submit_button("ゾーンを追加"):
        if z_name:
            st.session_state.z_list.append({"ゾーン名": z_name, "フェード秒": z_fade})
            st.rerun()

if st.session_state.z_list:
    z_df_disp = pd.DataFrame(st.session_state.z_list)
    z_df_disp.index += 1
    st.table(z_df_disp)
    del_z_idx = st.number_input("削除する番号", 0, len(st.session_state.z_list), step=1, key="del_z")
    if st.button("選択したゾーンを削除") and del_z_idx > 0:
        st.session_state.z_list.pop(del_z_idx - 1); st.rerun()

# --- 3. グループ登録 ---
st.header("3. グループ登録")
v_zones = [""] + [z["ゾーン名"] for z in st.session_state.z_list]
with st.form("g_form", clear_on_submit=True):
    col_g1, col_g2, col_g3 = st.columns(3)
    g_name = col_g1.text_input("グループ名")
    g_type = col_g2.selectbox("タイプ", list(GROUP_TYPE_MAP.keys()))
    g_zone = col_g3.selectbox("紐づけるゾーン", options=v_zones)
    if st.form_submit_button("グループを追加"):
        if g_name and g_zone:
            st.session_state.g_list.append({"グループ名": g_name, "グループタイプ": g_type, "紐づけるゾーン名": g_zone})
            st.rerun()

if st.session_state.g_list:
    g_df_disp = pd.DataFrame(st.session_state.g_list)
    g_df_disp.index += 1
    st.table(g_df_disp)
    del_g_idx = st.number_input("削除する番号", 0, len(st.session_state.g_list), step=1, key="del_g")
    if st.button("選択したグループを削除") and del_g_idx > 0:
        st.session_state.g_list.pop(del_g_idx - 1); st.rerun()

st.divider()

# --- 4. シーン登録 ---
st.header("4. シーン登録・編集")
v_groups = [""] + [g["グループ名"] for g in st.session_state.g_list]
g_dict = {g["グループ名"]: g for g in st.session_state.g_list}

if st.session_state.s_list:
    s_df_disp = pd.DataFrame(st.session_state.s_list)
    s_df_disp.index += 1
    st.table(s_df_disp)
    selected_s_idx = st.number_input("編集・削除する行番号 (0は新規)", 0, len(st.session_state.s_list), step=1)
else:
    selected_s_idx = 0

init_s = st.session_state.s_list[selected_s_idx-1] if selected_s_idx > 0 else {"シーン名": "", "紐づけるグループ名": "", "調光": 100, "ケルビン": "", "Syncaカラー": "", "FreshKey": ""}

with st.form("s_form_v25"):
    c1, c2, c3 = st.columns([2, 2, 1])
    s_name = c1.text_input("シーン名", value=init_s["シーン名"])
    target_g = c2.selectbox("対象グループ", options=v_groups, index=v_groups.index(init_s["紐づけるグループ名"]) if init_s["紐づけるグループ名"] in v_groups else 0)
    dim = c3.number_input("調光(%)", 0, 100, int(init_s["調光"]))
    cc1, cc2, cc3, cc4 = st.columns([2, 1, 1, 2])
    k_val = cc1.text_input("ケルビン", value=init_s["ケルビン"])
    row_val = cc2.selectbox("Synca 行(1-11)", ["-"] + list(range(1, 12)))
    col_val = cc3.selectbox("Synca 列(1-11)", ["-"] + list(range(1, 12)))
    f_key = cc4.text_input("Fresh Key", value=init_s.get("FreshKey", ""))
    
    if st.form_submit_button("保存"):
        if s_name and target_g:
            synca_code = f"'{row_val}-{col_val}" if str(row_val) != "-" and str(col_val) != "-" else ""
            new_data = {"シーン名": s_name, "紐づけるグループ名": target_g, "紐づけるゾーン名": g_dict[target_g]["紐づけるゾーン名"], "調光": dim, "ケルビン": k_val if not synca_code else "", "Syncaカラー": synca_code, "FreshKey": f_key}
            if selected_s_idx == 0: st.session_state.s_list.append(new_data)
            else: st.session_state.s_list[selected_s_idx-1] = new_data
            st.rerun()

st.divider()

# --- 5. タイムテーブル登録（自動生成機能付き） ---
st.header("5. タイムテーブル登録")
v_scenes = [""] + sorted(list(set([s["シーン名"] for s in st.session_state.s_list])))

with st.expander("✨ 繰り返しスケジュールを自動生成する"):
    with st.form("auto_tt"):
        col_a1, col_a2, col_a3 = st.columns(3)
        start_t = col_a1.text_input("開始時間", "10:00")
        end_t = col_a2.text_input("終了時間", "21:00")
        interval = col_a3.number_input("間隔（分）", 1, 60, 8)
        
        col_a4, col_a5 = st.columns(2)
        scene_a = col_a4.selectbox("シーンA (先)", options=v_scenes)
        scene_b = col_a5.selectbox("シーンB (後)", options=v_scenes)
        
        if st.form_submit_button("スケジュールを計算する"):
            try:
                curr = datetime.strptime(start_t, "%H:%M")
                limit = datetime.strptime(end_t, "%H:%M")
                auto_slots = []
                toggle = True
                while curr <= limit:
                    auto_slots.append({"time": curr.strftime("%H:%M"), "scene": scene_a if toggle else scene_b})
                    curr += timedelta(minutes=interval)
                    toggle = not toggle
                st.session_state.temp_slots = auto_slots
                st.success(f"{len(auto_slots)}件のスケジュールを生成しました。下のフォームで内容を確認して保存してください。")
            except:
                st.error("時間の形式が正しくありません(HH:MM)")

with st.form("tt_main_form"):
    ct1, ct2 = st.columns(2)
    tt_name = ct1.text_input("タイムテーブル名 (例: 春)")
    tt_zone = ct2.selectbox("対象ゾーン", options=v_zones)
    
    st.write("▼ スケジュール内容 (自動生成または手動入力)")
    final_slots = []
    # 自動生成されたデータがあれば初期値に使う
    base_data = st.session_state.get("temp_slots", [])
    
    cols = st.columns(4)
    for i in range(40): # 最大40スロットまで拡張
        with cols[i % 4]:
            def_t = base_data[i]["time"] if i < len(base_data) else ""
            def_s = base_data[i]["scene"] if i < len(base_data) else ""
            t_val = st.text_input(f"時間{i+1}", value=def_t, key=f"tt_t_{i}")
            s_val = st.selectbox(f"シーン{i+1}", options=v_scenes, index=v_scenes.index(def_s) if def_s in v_scenes else 0, key=f"tt_s_{i}")
            if t_val and s_val: final_slots.append({"time": t_val, "scene": s_val})
            
    if st.form_submit_button("タイムテーブルを保存"):
        if tt_name and tt_zone and final_slots:
            st.session_state.tt_list.append({"tt_name": tt_name, "zone": tt_zone, "slots": final_slots})
            if "temp_slots" in st.session_state: del st.session_state.temp_slots
            st.rerun()

if st.session_state.tt_list:
    tt_disp = pd.DataFrame([{"名": tt["tt_name"], "ゾーン": tt["zone"], "数": len(tt['slots'])} for tt in st.session_state.tt_list])
    tt_disp.index += 1
    st.table(tt_disp)
    del_tt_idx = st.number_input("削除番号", 0, len(st.session_state.tt_list), step=1)
    if st.button("削除") and del_tt_idx > 0:
        st.session_state.tt_list.pop(del_tt_idx - 1); st.rerun()

st.divider()

# --- 4. 出力処理 ---
if st.button("プレビューを確認してCSV作成", type="primary"):
    zf_f = pd.DataFrame(st.session_state.z_list)
    gf_f = pd.DataFrame(st.session_state.g_list)
    sf_f = pd.DataFrame(st.session_state.s_list)
    tt_f = st.session_state.tt_list
    
    mat = pd.DataFrame(index=range(max(len(zf_f), len(gf_f), len(sf_f), len(tt_f), 1)), columns=range(NUM_COLS))
    for i, r in zf_f.iterrows(): mat.iloc[i, 0:3] = [r["ゾーン名"], 4097+i, r["フェード秒"]]
    for i, r in gf_f.iterrows(): mat.iloc[i, 4:8] = [r["グループ名"], 32770+i, GROUP_TYPE_MAP.get(r["グループタイプ"], "1ch"), r["紐づけるゾーン名"]]
    
    scene_id_db = {}; sid_cnt = 8193
    for i, r in sf_f.iterrows():
        sn = r["シーン名"]
        if sn not in scene_id_db: scene_id_db[sn] = sid_cnt; sid_cnt += 1
        mat.iloc[i, 9:17] = [sn, scene_id_db[sn], r["調光"], r["ケルビン"], r["Syncaカラー"], r.get("FreshKey",""), r["紐づけるゾーン名"], r["紐づけるグループ名"]]
    
    for i, tt in enumerate(tt_f):
        mat.iloc[i, 17:20] = [tt["tt_name"], 12289+i, tt["zone"]]
        c_idx = 22
        for slot in tt["slots"]:
            if c_idx < 196:
                mat.iloc[i, c_idx], mat.iloc[i, c_idx+1] = slot["time"], slot["scene"]
                c_idx += 2

    final_df = pd.concat([pd.DataFrame(CSV_HEADER), mat], ignore_index=True)
    st.write("### 最終プレビュー")
    st.dataframe(final_df.iloc[3:].dropna(how='all', axis=0), use_container_width=True)
    buf = io.BytesIO()
    final_df.to_csv(buf, index=False, header=False, encoding="utf-8-sig")
    st.download_button("📥 CSVダウンロード", buf.getvalue(), f"{shop_name}_setting.csv", "text/csv")
