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

# セッション管理
states = {
    'z_list': [], 'g_list': [], 's_list': [], 'tt_list': [],
    'tt_slots_count': 1, 'auto_scene_count': 2
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

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
    st.table(pd.DataFrame(st.session_state.z_list).assign(No=range(1, len(st.session_state.z_list)+1)).set_index('No'))
    col_z_del1, col_z_del2 = st.columns([1, 4])
    del_z_idx = col_z_del1.number_input("削除するNo", 1, len(st.session_state.z_list), key="del_z_idx")
    if col_z_del2.button("選択したゾーンを削除（決定）"):
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
    st.table(pd.DataFrame(st.session_state.g_list).assign(No=range(1, len(st.session_state.g_list)+1)).set_index('No'))
    col_g_del1, col_g_del2 = st.columns([1, 4])
    del_g_idx = col_g_del1.number_input("削除するNo", 1, len(st.session_state.g_list), key="del_g_idx")
    if col_g_del2.button("選択したグループを削除（決定）"):
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
    selected_s_idx = st.number_input("編集・削除No (0は新規)", 0, len(st.session_state.s_list), 0)
else:
    selected_s_idx = 0

init_s = st.session_state.s_list[selected_s_idx-1] if selected_s_idx > 0 else {"シーン名": "", "紐づけるグループ名": "", "調光": 100, "ケルビン": "", "Syncaカラー": "", "FreshKey": ""}

with st.form("s_form_v28"):
    c1, c2, c3 = st.columns([2, 2, 1])
    s_name = c1.text_input("シーン名", value=init_s["シーン名"])
    target_g = c2.selectbox("対象グループ", options=v_groups, index=v_groups.index(init_s["紐づけるグループ名"]) if init_s["紐づけるグループ名"] in v_groups else 0)
    dim = c3.number_input("調光(%)", 0, 100, int(init_s["調光"]))
    cc1, cc2, cc3, cc4 = st.columns([2, 1, 1, 2])
    k_val = cc1.text_input("ケルビン", value=init_s["ケルビン"])
    row_val = cc2.selectbox("Synca 行(1-11)", ["-"] + list(range(1, 12)))
    col_val = cc3.selectbox("Synca 列(1-11)", ["-"] + list(range(1, 12)))
    f_key = cc4.text_input("Fresh Key", value=init_s.get("FreshKey", ""))
    
    col_s_btn1, col_s_btn2 = st.columns([1, 4])
    if col_s_btn1.form_submit_button("保存"):
        if s_name and target_g:
            synca_code = f"'{row_val}-{col_val}" if str(row_val) != "-" and str(col_val) != "-" else ""
            new_data = {"シーン名": s_name, "紐づけるグループ名": target_g, "紐づけるゾーン名": g_dict[target_g]["紐づけるゾーン名"], "調光": dim, "ケルビン": k_val if not synca_code else "", "Syncaカラー": synca_code, "FreshKey": f_key}
            if selected_s_idx == 0: st.session_state.s_list.append(new_data)
            else: st.session_state.s_list[selected_s_idx-1] = new_data
            st.rerun()
    if selected_s_idx > 0:
        if col_s_btn2.form_submit_button("選択したシーンを削除（決定）"):
            st.session_state.s_list.pop(selected_s_idx - 1); st.rerun()

st.divider()

# --- 5. タイムテーブル登録 ---
st.header("5. タイムテーブル登録")
v_scenes = [""] + sorted(list(set([s["シーン名"] for s in st.session_state.s_list])))

# 繰り返し自動生成
with st.expander("✨ スケジュール自動作成 (複数シーンの繰り返し対応)"):
    with st.form("auto_tt"):
        col_a1, col_a2, col_a3, col_a4 = st.columns(4)
        auto_z = col_a1.selectbox("対象ゾーン", options=v_zones)
        start_t = col_a2.text_input("開始時間", "10:00")
        end_t = col_a3.text_input("終了時間", "21:00")
        interval = col_a4.number_input("間隔(分)", 1, 120, 8)
        
        st.write("▼ 繰り返すシーンの順番を設定")
        auto_scenes = []
        scene_cols = st.columns(4)
        for i in range(st.session_state.auto_scene_count):
            with scene_cols[i % 4]:
                as_val = st.selectbox(f"シーン {i+1}", options=v_scenes, key=f"auto_s_{i}")
                if as_val: auto_scenes.append(as_val)
        
        col_auto_btn1, col_auto_btn2 = st.columns([2, 8])
        if col_auto_btn1.form_submit_button("スケジュールを計算してセット"):
            if auto_scenes:
                try:
                    curr = datetime.strptime(start_t, "%H:%M")
                    limit = datetime.strptime(end_t, "%H:%M")
                    auto_slots = []; idx = 0
                    while curr <= limit:
                        auto_slots.append({"time": curr.strftime("%H:%M"), "scene": auto_scenes[idx % len(auto_scenes)]})
                        curr += timedelta(minutes=interval); idx += 1
                    st.session_state.temp_slots = auto_slots
                    st.session_state.temp_tt_zone = auto_z
                    st.session_state.tt_slots_count = len(auto_slots)
                    st.rerun()
                except: st.error("形式エラー(HH:MM)")
        
    if st.button("➕ 繰り返しシーンを追加"):
        st.session_state.auto_scene_count += 1; st.rerun()
    if st.session_state.auto_scene_count > 1:
        if st.button("➖ シーン枠を減らす"):
            st.session_state.auto_scene_count -= 1; st.rerun()

# タイムテーブル本体フォーム
with st.form("tt_main_form"):
    ct1, ct2 = st.columns(2)
    tt_name = ct1.text_input("タイムテーブル名 (例: 春)")
    tt_zone = ct2.selectbox("対象ゾーン", options=v_zones, index=v_zones.index(st.session_state.get("temp_tt_zone", "")) if st.session_state.get("temp_tt_zone", "") in v_zones else 0)
    
    st.write("▼ スケジュール詳細")
    base_data = st.session_state.get("temp_slots", [])
    final_slots = []
    
    for i in range(st.session_state.tt_slots_count):
        c_time, c_scene = st.columns([1, 2])
        def_t = base_data[i]["time"] if i < len(base_data) else ""
        def_s = base_data[i]["scene"] if i < len(base_data) else ""
        t_val = c_time.text_input(f"時間 {i+1}", value=def_t, key=f"tt_t_{i}")
        s_val = c_scene.selectbox(f"シーン {i+1}", options=v_scenes, index=v_scenes.index(def_s) if def_s in v_scenes else 0, key=f"tt_s_{i}")
        if t_val and s_val: final_slots.append({"time": t_val, "scene": s_val})
            
    if st.form_submit_button("タイムテーブルをリストに保存"):
        if tt_name and tt_zone and final_slots:
            st.session_state.tt_list.append({"tt_name": tt_name, "zone": tt_zone, "slots": final_slots})
            st.session_state.tt_slots_count = 1
            st.session_state.temp_tt_zone = ""
            if "temp_slots" in st.session_state: del st.session_state.temp_slots
            st.rerun()

if st.button("➕ 手動スロットを追加"):
    st.session_state.tt_slots_count += 1; st.rerun()

if st.session_state.tt_list:
    st.subheader("現在のタイムテーブル一覧")
    tt_disp = pd.DataFrame([{"名": tt["tt_name"], "ゾーン": tt["zone"], "数": len(tt['slots'])} for tt in st.session_state.tt_list])
    tt_disp.index += 1
    st.table(tt_disp)
    col_tt_del1, col_tt_del2 = st.columns([1, 4])
    del_tt_idx = col_tt_del1.number_input("削除するNo", 1, len(st.session_state.tt_list), key="del_tt_idx")
    if col_tt_del2.button("選択したタイムテーブルを削除（決定）"):
        st.session_state.tt_list.pop(del_tt_idx - 1); st.rerun()

st.divider()

# --- 4. 出力処理 ---
if st.button("プレビューを確認してCSV作成", type="primary"):
    zf_f = pd.DataFrame(st.session_state.z_list)
    gf_f = pd.DataFrame(st.session_state.g_list)
    sf_f = pd.DataFrame(st.session_state.s_list)
    tt_f = st.session_state.tt_list
    mat = pd.DataFrame(index=range(max(len(zf_f), len(gf_f), len(sf_f
