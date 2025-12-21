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
ROW3[9:16] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]']
ROW3[17:22] = ['[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]']
for i in range(22, 196, 2): ROW3[i], ROW3[i+1] = '[time]', '[scene]'
# Timetable-schedule情報 (197-205列目付近)
ROW3[197:206] = ['[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]']

CSV_HEADER = [ROW1, [None] * NUM_COLS, ROW3]

# --- 2. アプリ設定とデータ初期化 ---
st.set_page_config(page_title="設定データ作成アプリ", layout="wide")
st.title("設定データ作成アプリ ⚙️")

states = {
    'z_list': [], 'g_list': [], 's_list': [], 'tt_list': [], 'ts_list': [],
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
    del_z_idx = col_z_del1.number_input("削除No", 1, len(st.session_state.z_list), key="del_z_idx")
    if col_z_del2.button("ゾーン削除確定"):
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

init_s = st.session_state.s_list[selected_s_idx-1] if selected_s_idx > 0 else {"シーン名": "", "紐づけるグループ名": "", "調光": 100, "ケルビン": "", "Syncaカラー": ""}

with st.form("s_form_v31"):
    c1, c2, c3 = st.columns([2, 2, 1])
    s_name = c1.text_input("シーン名", value=init_s["シーン名"])
    target_g = c2.selectbox("対象グループ", options=v_groups, index=v_groups.index(init_s["紐づけるグループ名"]) if init_s["紐づけるグループ名"] in v_groups else 0)
    dim = c3.number_input("調光(%)", 0, 100, int(init_s["調光"]))
    cc1, cc2, cc3 = st.columns([2, 1, 1])
    k_val = cc1.text_input("ケルビン", value=init_s["ケルビン"])
    row_val = cc2.selectbox("Synca 行(1-11)", ["-"] + list(range(1, 12)))
    col_val = cc3.selectbox("Synca 列(1-11)", ["-"] + list(range(1, 12)))
    
    col_s_btn1, col_s_btn2 = st.columns([1, 4])
    if col_s_btn1.form_submit_button("保存"):
        if s_name and target_g:
            synca_code = f"'{row_val}-{col_val}" if str(row_val) != "-" and str(col_val) != "-" else ""
            new_data = {"シーン名": s_name, "紐づけるグループ名": target_g, "紐づけるゾーン名": g_dict[target_g]["紐づけるゾーン名"], "調光": dim, "ケルビン": k_val if not synca_code else "", "Syncaカラー": synca_code}
            if selected_s_idx == 0: st.session_state.s_list.append(new_data)
            else: st.session_state.s_list[selected_s_idx-1] = new_data
            st.rerun()
    if selected_s_idx > 0:
        if col_s_btn2.form_submit_button("シーン削除確定"):
            st.session_state.s_list.pop(selected_s_idx - 1); st.rerun()

st.divider()

# --- 5. タイムテーブル案の作成 ---
st.header("5. タイムテーブル案（パターン）の作成")
v_scenes = [""] + sorted(list(set([s["シーン名"] for s in st.session_state.s_list])))

# 繰り返し自動生成
with st.expander("✨ 繰り返しパターンを自動作成"):
    with st.form("auto_tt_v31"):
        col_a1, col_a2, col_a3, col_a4 = st.columns(4)
        auto_z = col_a1.selectbox("対象ゾーン", options=v_zones)
        start_t = col_a2.text_input("開始時間", "10:00")
        end_t = col_a3.text_input("終了時間", "21:00")
        interval = col_a4.number_input("間隔(分)", 1, 120, 8)
        auto_scenes = []
        scene_cols = st.columns(4)
        for i in range(st.session_state.auto_scene_count):
            with scene_cols[i % 4]:
                as_val = st.selectbox(f"シーン {i+1}", options=v_scenes, key=f"auto_s_{i}")
                if as_val: auto_scenes.append(as_val)
        if st.form_submit_button("パターン計算"):
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
                except: st.error("形式エラー")
    if st.button("➕ 繰り返し用シーン追加"): st.session_state.auto_scene_count += 1; st.rerun()

with st.form("tt_main_v31"):
    ct1, ct2 = st.columns(2)
    tt_name = ct1.text_input("タイムテーブル案の名前 (例: 通常, 正月)", value="通常")
    tt_zone = ct2.selectbox("対象ゾーン", options=v_zones, index=v_zones.index(st.session_state.get("temp_tt_zone", "")) if st.session_state.get("temp_tt_zone", "") in v_zones else 0)
    csun1, csun2 = st.columns(2)
    sun_start = csun1.selectbox("日出シーン", options=v_scenes)
    sun_end = csun2.selectbox("日没シーン", options=v_scenes)
    
    final_slots = []
    for i in range(st.session_state.tt_slots_count):
        c_time, c_scene = st.columns([1, 2])
        def_t = st.session_state.get("temp_slots", [])[i]["time"] if i < len(st.session_state.get("temp_slots", [])) else ""
        def_s = st.session_state.get("temp_slots", [])[i]["scene"] if i < len(st.session_state.get("temp_slots", [])) else ""
        t_val = c_time.text_input(f"時間 {i+1}", value=def_t, key=f"tt_t_{i}")
        s_val = c_scene.selectbox(f"シーン {i+1}", options=v_scenes, index=v_scenes.index(def_s) if def_s in v_scenes else 0, key=f"tt_s_{i}")
        if t_val and s_val: final_slots.append({"time": t_val, "scene": s_val})
    if st.form_submit_button("タイムテーブル案を保存"):
        st.session_state.tt_list.append({"tt_name": tt_name, "zone": tt_zone, "sun_start": sun_start, "sun_end": sun_end, "slots": final_slots})
        st.rerun()

if st.button("➕ 手動スロット追加"): st.session_state.tt_slots_count += 1; st.rerun()

st.divider()

# --- 6. タイムスケジュール期間設定 (daily設定) ---
st.header("6. タイムスケジュール期間設定 (適用曜日)")
v_tt_names = [""] + [tt["tt_name"] for tt in st.session_state.tt_list]

with st.form("ts_form"):
    st.write("どのゾーンに、どのタイムテーブルを、いつ適用するか設定します。")
    col_ts1, col_ts2 = st.columns(2)
    target_z_ts = col_ts1.selectbox("対象ゾーン ", options=v_zones)
    apply_mode = col_ts2.radio("適用方法", ["毎日(daily)", "曜日ごとに指定"])
    
    if apply_mode == "毎日(daily)":
        daily_tt = st.selectbox("適用するタイムテーブル案", options=v_tt_names)
        days_config = {"daily": daily_tt, "mon": "", "tue": "", "wed": "", "thu": "", "fri": "", "sat": "", "sun": ""}
    else:
        st.write("各曜日に適用する案を選択してください")
        cday1, cday2, cday3, cday4 = st.columns(4)
        mon = cday1.selectbox("月", options=v_tt_names); tue = cday2.selectbox("火", options=v_tt_names)
        wed = cday3.selectbox("水", options=v_tt_names); thu = cday4.selectbox("木", options=v_tt_names)
        fri, sat, sun_v = st.columns(3)
        fri_v = fri.selectbox("金", options=v_tt_names); sat_v = sat.selectbox("土", options=v_tt_names); sun_v_v = sun_v.selectbox("日", options=v_tt_names)
        days_config = {"daily": "", "mon": mon, "tue": tue, "wed": wed, "thu": thu, "fri": fri_v, "sat": sat_v, "sun": sun_v_v}

    if st.form_submit_button("スケジュール設定を保存"):
        if target_z_ts:
            st.session_state.ts_list.append({"zone": target_z_ts, "config": days_config})
            st.rerun()

if st.session_state.ts_list:
    st.table(pd.DataFrame([{"ゾーン": x["zone"], "毎日": x["config"]["daily"]} for x in st.session_state.ts_list]))

st.divider()

# --- 7. 出力処理 ---
if st.button("プレビューを確認してCSV作成", type="primary"):
    zf_f = pd.DataFrame(st.session_state.z_list)
    gf_f = pd.DataFrame(st.session_state.g_list)
    sf_f = pd.DataFrame(st.session_state.s_list)
    tt_f = st.session_state.tt_list
    ts_f = st.session_state.ts_list
    
    mat = pd.DataFrame(index=range(max(len(zf_f), len(gf_f), len(sf_f), len(tt_f), len(ts_f), 1)), columns=range(NUM_COLS))
    for i, r in zf_f.iterrows(): mat.iloc[i, 0:3] = [r["ゾーン名"], 4097+i, r["フェード秒"]]
    for i, r in gf_f.iterrows(): mat.iloc[i, 4:8] = [r["グループ名"], 32770+i, GROUP_TYPE_MAP.get(r["グループタイプ"], "1ch"), r["紐づけるゾーン名"]]
    
    scene_id_db = {}; sid_cnt = 8193
    for i, r in sf_f.iterrows():
        sn = r["シーン名"]
        if sn not in scene_id_db: scene_id_db[sn] = sid_cnt; sid_cnt += 1
        mat.iloc[i, 9:16] = [sn, scene_id_db[sn], r["調光"], r["ケルビン"], r["Syncaカラー"], r["紐づけるゾーン名"], r["紐づけるグループ名"]]
    
    for i, tt in enumerate(tt_f):
        mat.iloc[i, 17:22] = [tt["tt_name"], 12289+i, tt["zone"], tt["sun_start"], tt["sun_end"]]
        c_idx = 22
        for slot in tt["slots"]:
            if c_idx < 196: mat.iloc[i, c_idx], mat.iloc[i, c_idx+1] = slot["time"], slot["scene"]; c_idx += 2

    # Timetable-schedule情報 (197列目〜) の書き込み
    for i, ts in enumerate(ts_f):
        cfg = ts["config"]
        # [zone-ts], [daily], [mon], [tue], [wed], [thu], [fri], [sat], [sun]
        mat.iloc[i, 197:206] = [ts["zone"], cfg["daily"], cfg["mon"], cfg["tue"], cfg["wed"], cfg["thu"], cfg["fri"], cfg["sat"], cfg["sun"]]

    final_df = pd.concat([pd.DataFrame(CSV_HEADER), mat], ignore_index=True)
    st.dataframe(final_df.iloc[3:].dropna(how='all', axis=0), use_container_width=True)
    buf = io.BytesIO()
    final_df.to_csv(buf, index=False, header=False, encoding="utf-8-sig")
    st.download_button("📥 CSVダウンロード", buf.getvalue(), f"{shop_name}_setting.csv", "text/csv")
