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
ROW3[197:206] = ['[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]']
ROW3[207:212] = ['[zone-period]', '[id]', '[start]', '[end]', '[timetable]', '[zone]']

CSV_HEADER = [ROW1, [None] * NUM_COLS, ROW3]

# --- 2. アプリ設定とデータ初期化 ---
st.set_page_config(page_title="設定データ作成アプリ", layout="wide")
st.title("設定データ作成アプリ ⚙️")

# セッション管理
for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
    if key not in st.session_state: st.session_state[key] = []
if 'tt_slots_count' not in st.session_state: st.session_state.tt_slots_count = 1
if 'auto_scene_count' not in st.session_state: st.session_state.auto_scene_count = 2

# --- 3. UIセクション ---
st.header("1. 店舗名入力 ")
shop_name = st.text_input("店舗名", value="")
st.divider()

# --- 2. ゾーン登録 ---
st.header("2. ゾーン登録 ")
with st.form("z_form_v37", clear_on_submit=True):
    col_z1, col_z2 = st.columns(2)
    z_name = col_z1.text_input("ゾーン名")
    z_fade = col_z2.number_input("フェード秒", 0, 60, 0)
    if st.form_submit_button("ゾーンを追加 ➕"):
        if z_name:
            st.session_state.z_list.append({"ゾーン名": z_name, "フェード秒": z_fade})
            st.rerun()
if st.session_state.z_list:
    st.table(pd.DataFrame(st.session_state.z_list).assign(No=range(1, len(st.session_state.z_list)+1)).set_index('No'))
    del_z_idx = st.number_input("ゾーン削除No", 0, len(st.session_state.z_list), 0, key="dz")
    if st.button("ゾーン削除実行 🗑️") and del_z_idx > 0: st.session_state.z_list.pop(del_z_idx - 1); st.rerun()

# --- 3. グループ登録 ---
st.header("3. グループ登録 ")
v_zones = [""] + [z["ゾーン名"] for z in st.session_state.z_list]
with st.form("g_form_v37", clear_on_submit=True):
    col_g1, col_g2, col_g3 = st.columns(3)
    g_name = col_g1.text_input("グループ名")
    g_type = col_g2.selectbox("タイプ", list(GROUP_TYPE_MAP.keys()))
    g_zone = col_g3.selectbox("紐づけるゾーン", options=v_zones)
    if st.form_submit_button("グループを追加 ➕"):
        if g_name and g_zone:
            st.session_state.g_list.append({"グループ名": g_name, "グループタイプ": g_type, "紐づけるゾーン名": g_zone})
            st.rerun()
if st.session_state.g_list:
    st.table(pd.DataFrame(st.session_state.g_list).assign(No=range(1, len(st.session_state.g_list)+1)).set_index('No'))
    del_g_idx = st.number_input("グループ削除No", 0, len(st.session_state.g_list), 0, key="dg")
    if st.button("グループ削除実行 🗑️") and del_g_idx > 0: st.session_state.g_list.pop(del_g_idx - 1); st.rerun()

# --- 4. シーン登録 ---
st.header("4. シーン登録・編集 ")
v_groups = [""] + [g["グループ名"] for g in st.session_state.g_list]
g_dict = {g["グループ名"]: g for g in st.session_state.g_list}
if st.session_state.s_list:
    s_df_disp = pd.DataFrame(st.session_state.s_list)
    s_df_disp.index += 1
    st.table(s_df_disp)
    sel_s_idx = st.number_input("編集・削除No", 0, len(st.session_state.s_list), 0)
else: sel_s_idx = 0

with st.form("s_form_v37"):
    init_s = st.session_state.s_list[sel_s_idx-1] if sel_s_idx > 0 else {"シーン名": "", "紐づけるグループ名": "", "調光": 100, "ケルビン": "", "Syncaカラー": ""}
    c1, c2, c3 = st.columns([2, 2, 1])
    s_name = c1.text_input("シーン名", value=init_s["シーン名"])
    target_g = c2.selectbox("対象グループ", options=v_groups, index=v_groups.index(init_s["紐づけるグループ名"]) if init_s["紐づけるグループ名"] in v_groups else 0)
    dim = c3.number_input("調光(%)", 0, 100, int(init_s["調光"]))
    cc1, cc2, cc3 = st.columns([2, 1, 1])
    k_in = cc1.text_input("ケルビン", value=init_s["ケルビン"])
    row_v = cc2.selectbox("Synca 行", ["-"] + list(range(1, 12)))
    col_v = cc3.selectbox("Synca 列", ["-"] + list(range(1, 12)))
    if st.form_submit_button("シーン保存 ✅"):
        if s_name and target_g:
            g_tp = g_dict[target_g]["グループタイプ"]
            sc = f"'{row_v}-{col_v}" if str(row_v) != "-" and str(col_v) != "-" else ""
            new_s = {"シーン名": s_name, "紐づけるグループ名": target_g, "紐づけるゾーン名": g_dict[target_g]["紐づけるゾーン名"], "調光": dim, "ケルビン": "" if g_tp == "調光" else (k_in if not sc else ""), "Syncaカラー": sc if g_tp in ["Synca", "Synca Bright"] else ""}
            if sel_s_idx == 0: st.session_state.s_list.append(new_s)
            else: st.session_state.s_list[sel_s_idx-1] = new_s
            st.rerun()

st.divider()

# --- 5. タイムテーブル作成 ---
st.header("5. タイムテーブル作成 ")
v_scenes = [""] + sorted(list(set([s["シーン名"] for s in st.session_state.s_list])))
with st.expander("スケジュール自動作成"):
    with st.form("at_v37"):
        ca1, ca2, ca3, ca4 = st.columns(4)
        az, stt, edt, inv = ca1.selectbox("対象ゾーン", v_zones), ca2.text_input("開始", "10:00"), ca3.text_input("終了", "21:00"), ca4.number_input("間隔(分) ※6分以上", 6, 120, 8)
        ascs = []
        acols = st.columns(4)
        for i in range(st.session_state.auto_scene_count):
            with acols[i % 4]:
                v = st.selectbox(f"シーン{i+1}", v_scenes, key=f"as_{i}")
                if v: ascs.append(v)
        if st.form_submit_button("セット"):
            try:
                curr, limit = datetime.strptime(stt, "%H:%M"), datetime.strptime(edt, "%H:%M")
                slots, idx = [], 0
                while curr <= limit:
                    slots.append({"time": curr.strftime("%H:%M"), "scene": ascs[idx % len(ascs)]})
                    curr += timedelta(minutes=inv); idx += 1
                st.session_state.temp_slots, st.session_state.temp_tt_zone, st.session_state.tt_slots_count = slots, az, len(slots)
                st.rerun()
            except: st.error("時刻形式が不正です(HH:MM)")
    if st.button("繰り返し用シーン枠を追加"): st.session_state.auto_scene_count += 1; st.rerun()

with st.form("tt_v37"):
    ct1, ct2 = st.columns(2)
    tt_n = ct1.text_input("タイムテーブル名", value="通常")
    tt_z = ct2.selectbox("対象ゾーン ", v_zones, index=v_zones.index(st.session_state.get("temp_tt_zone", "")) if st.session_state.get("temp_tt_zone", "") in v_zones else 0)
    cs1, cs2 = st.columns(2)
    ss, se = cs1.selectbox("日出シーン ☀️", v_scenes), cs2.selectbox("日没シーン 🌙", v_scenes)
    f_slots, b_slots = [], st.session_state.get("temp_slots", [])
    for i in range(st.session_state.tt_slots_count):
        c_t, c_s = st.columns([1, 2])
        dt = b_slots[i]["time"] if i < len(b_slots) else ""
        ds = b_slots[i]["scene"] if i < len(b_slots) else ""
        tv, sv = c_t.text_input(f"時間{i+1}", value=dt, key=f"t37_{i}"), c_s.selectbox(f"シーン{i+1}", v_scenes, index=v_scenes.index(ds) if ds in v_scenes else 0, key=f"s37_{i}")
        if tv and sv: f_slots.append({"time": tv, "scene": sv})
    if st.form_submit_button("タイムテーブル保存 ✅"):
        st.session_state.tt_list.append({"tt_name": tt_n, "zone": tt_z, "sun_start": ss, "sun_end": se, "slots": f_slots})
        st.session_state.tt_slots_count = 1; st.rerun()

if st.button("手動スロットを追加 ➕"): st.session_state.tt_slots_count += 1; st.rerun()

st.divider()

# --- 6. 適用 & 特異日設定 ---
st.header("6. スケジュール適用・特異日設定 ")
v_tt_names = [""] + [tt["tt_name"] for tt in st.session_state.tt_list]

col_apply1, col_apply2 = st.columns(2)
with col_apply1:
    st.subheader("通常スケジュール (曜日) 📅")
    with st.form("ts_v37"):
        tz = st.selectbox("対象ゾーン", v_zones)
        mode = st.radio("設定方法", ["毎日(daily)", "曜日別"])
        if mode == "毎日(daily)":
            d_tt = st.selectbox("タイムテーブル名", v_tt_names)
            cfg = {"daily": d_tt, "mon": "", "tue": "", "wed": "", "thu": "", "fri": "", "sat": "", "sun": ""}
        else:
            c_d = st.columns(2)
            mon = c_d[0].selectbox("月", v_tt_names); tue = c_d[1].selectbox("火", v_tt_names)
            wed = c_d[0].selectbox("水", v_tt_names); thu = c_d[1].selectbox("木", v_tt_names)
            fri = c_d[0].selectbox("金", v_tt_names); sat = c_d[1].selectbox("土", v_tt_names); sun = c_d[0].selectbox("日", v_tt_names)
            cfg = {"daily": "", "mon": mon, "tue": tue, "wed": wed, "thu": thu, "fri": fri, "sat": sat, "sun": sun}
        if st.form_submit_button("通常設定を保存 ✅"):
            st.session_state.ts_list.append({"zone": tz, "config": cfg}); st.rerun()

with col_apply2:
    st.subheader("特異日・期間設定 (正月など) ")
    with st.form("period_v37"):
        pz = st.selectbox("対象ゾーン ", v_zones)
        p_tt = st.selectbox("適用タイムテーブル ", v_tt_names)
        p_start = st.text_input("開始日 (MM/DD)", placeholder="01/01")
        p_end = st.text_input("終了日 (MM/DD)", placeholder="01/03")
        if st.form_submit_button("期間設定を保存 ✅"):
            if pz and p_tt and p_start:
                st.session_state.period_list.append({"zone": pz, "tt": p_tt, "start": p_start, "end": p_end})
                st.rerun()

if st.session_state.ts_list or st.session_state.period_list:
    st.write("▼ 現在の登録一覧")
    if st.session_state.ts_list: st.table(pd.DataFrame([{"ゾーン": x["zone"], "毎日": x["config"]["daily"]} for x in st.session_state.ts_list]))
    if st.session_state.period_list: st.table(pd.DataFrame(st.session_state.period_list))
    if st.button("全設定をクリア 🔄"): st.session_state.ts_list = []; st.session_state.period_list = []; st.rerun()

st.divider()

# --- 7. 出力 ---
if st.button("プレビューを確認してCSV作成 💾", type="primary"):
    zf, gf, sf, ttf, tsf, pf = pd.DataFrame(st.session_state.z_list), pd.DataFrame(st.session_state.g_list), pd.DataFrame(st.session_state.s_list), st.session_state.tt_list, st.session_state.ts_list, st.session_state.period_list
    mat = pd.DataFrame(index=range(max(len(zf), len(gf), len(sf), len(ttf), 100)), columns=range(NUM_COLS))
    for i, r in zf.iterrows(): mat.iloc[i, 0:3] = [r["ゾーン名"], 4097+i, r["フェード秒"]]
    for i, r in gf.iterrows(): mat.iloc[i, 4:8] = [r["グループ名"], 32770+i, GROUP_TYPE_MAP.get(r["グループタイプ"], "1ch"), r["紐づけるゾーン名"]]
    s_db, s_cnt = {}, 8193
    for i, r in sf.iterrows():
        sn = r["シーン名"]; s_db[sn] = s_db.get(sn, s_cnt); s_cnt = s_cnt+1 if sn not in s_db else s_cnt
        mat.iloc[i, 9:16] = [sn, s_db[sn], r["調光"], r["ケルビン"], r["Syncaカラー"], r["紐づけるゾーン名"], r["紐づけるグループ名"]]
    for i, tt in enumerate(ttf):
        mat.iloc[i, 17:22] = [tt["tt_name"], 12289+i, tt["zone"], tt["sun_start"], tt["sun_end"]]
        c_idx = 22
        for slot in tt["slots"]:
            if c_idx < 196: mat.iloc[i, c_idx], mat.iloc[i, c_idx+1] = slot["time"], slot["scene"]; c_idx += 2
    for i, ts in enumerate(tsf):
        c = ts["config"]
        mat.iloc[i, 197:206] = [ts["zone"], c["daily"], c["mon"], c["tue"], c["wed"], c["thu"], c["fri"], c["sat"], c["sun"]]
    for i, p in enumerate(pf):
        mat.iloc[i, 207:212] = [p["zone"], 16385+i, p["start"], p["end"], p["tt"], p["zone"]]

    final_df = pd.concat([pd.DataFrame(CSV_HEADER), mat], ignore_index=True)
    st.dataframe(final_df.iloc[3:].dropna(how='all', axis=0), use_container_width=True)
    buf = io.BytesIO()
    final_df.to_csv(buf, index=False, header=False, encoding="utf-8-sig")
    st.download_button("CSVダウンロード 📥", buf.getvalue(), f"{shop_name}_setting.csv", "text/csv")


