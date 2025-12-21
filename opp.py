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
ROW3[207:212] = ['[zone-period]', '[start]', '[end]', '[timetable]', '[zone]']

CSV_HEADER = [ROW1, [None] * NUM_COLS, ROW3]

# --- 2. アプリ設定とデータ初期化 ---
st.set_page_config(page_title="設定データ作成アプリ", layout="wide")
st.title("設定データ作成アプリ ⚙️")

# セッション管理
for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
    if key not in st.session_state: st.session_state[key] = []
if 'tt_slots_count' not in st.session_state: st.session_state.tt_slots_count = 1
if 'auto_scene_count' not in st.session_state: st.session_state.auto_scene_count = 2

# --- 3. 各登録セクション ---
st.header("1. 店舗名入力 🏢")
shop_name = st.text_input("店舗名", value="")
st.divider()

# 2. ゾーン登録
st.header("2. ゾーン登録 🌐")
with st.form("z_form_v43", clear_on_submit=True):
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
    if st.button("ゾーン削除 🗑️") and del_z_idx > 0: st.session_state.z_list.pop(del_z_idx - 1); st.rerun()

# 3. グループ登録
st.header("3. グループ登録 💡")
v_zones = [""] + [z["ゾーン名"] for z in st.session_state.z_list]
with st.form("g_form_v43", clear_on_submit=True):
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

# 4. シーン登録
st.header("4. シーン登録・編集 🎬")
v_groups = [""] + [g["グループ名"] for g in st.session_state.g_list]
g_dict = {g["グループ名"]: g for g in st.session_state.g_list}
if st.session_state.s_list:
    s_df_disp = pd.DataFrame(st.session_state.s_list).assign(No=range(1, len(st.session_state.s_list)+1)).set_index('No')
    st.table(s_df_disp)
    sel_s_idx = st.number_input("編集・削除No", 0, len(st.session_state.s_list), 0)
else: sel_s_idx = 0

with st.form("s_form_v43"):
    init_s = st.session_state.s_list[sel_s_idx-1] if sel_s_idx > 0 else {"シーン名": "", "紐づけるグループ名": "", "調光": 100, "ケルビン": "", "Syncaカラー": ""}
    c1, c2, c3 = st.columns([2, 2, 1])
    s_n, t_g, dim = c1.text_input("シーン名", value=init_s["シーン名"]), c2.selectbox("対象グループ", v_groups, index=v_groups.index(init_s["紐づけるグループ名"]) if init_s["紐づけるグループ名"] in v_groups else 0), c3.number_input("調光(%)", 0, 100, int(init_s["調光"]))
    cc1, cc2, cc3 = st.columns([2, 1, 1])
    k_i, r_v, c_v = cc1.text_input("ケルビン", value=init_s["ケルビン"]), cc2.selectbox("Synca 行", ["-"] + list(range(1, 12))), cc3.selectbox("Synca 列", ["-"] + list(range(1, 12)))
    if st.form_submit_button("シーン保存 ✅"):
        if s_n and t_g:
            g_tp = g_dict[t_g]["グループタイプ"]
            sc = f"'{r_v}-{c_v}" if str(r_v) != "-" and str(col_v) != "-" else ""
            new_s = {"シーン名": s_n, "紐づけるグループ名": t_g, "紐づけるゾーン名": g_dict[t_g]["紐づけるゾーン名"], "調光": dim, "ケルビン": "" if g_tp == "調光" else (k_i if not sc else ""), "Syncaカラー": sc if g_tp in ["Synca", "Synca Bright"] else ""}
            if sel_s_idx == 0: st.session_state.s_list.append(new_s)
            else: st.session_state.s_list[sel_s_idx-1] = new_s
            st.rerun()

st.divider()

# 5. タイムテーブル作成
st.header("5. タイムテーブル作成 ⏳")
v_scenes = [""] + sorted(list(set([s["シーン名"] for s in st.session_state.s_list])))
with st.expander("スケジュール自動作成"):
    with st.form("at_v43"):
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
            except: st.error("時刻形式エラー")
    if st.button("枠追加 ➕"): st.session_state.auto_scene_count += 1; st.rerun()

with st.form("tt_v43"):
    ct1, ct2 = st.columns(2)
    tt_n, tt_z = ct1.text_input("タイムテーブル名", value="通常"), ct2.selectbox("対象ゾーン ", v_zones, index=v_zones.index(st.session_state.get("temp_tt_zone", "")) if st.session_state.get("temp_tt_zone", "") in v_zones else 0)
    cs1, cs2 = st.columns(2)
    ss, se = cs1.selectbox("日出シーン", v_scenes), cs2.selectbox("日没シーン", v_scenes)
    f_slots, b_slots = [], st.session_state.get("temp_slots", [])
    for i in range(st.session_state.tt_slots_count):
        c_t, c_s = st.columns([1, 2])
        dt, ds = (b_slots[i]["time"], b_slots[i]["scene"]) if i < len(b_slots) else ("", "")
        tv, sv = c_t.text_input(f"時間{i+1}", value=dt, key=f"t_{i}"), c_s.selectbox(f"シーン{i+1}", v_scenes, index=v_scenes.index(ds) if ds in v_scenes else 0, key=f"s_{i}")
        if tv and sv: f_slots.append({"time": tv, "scene": sv})
    if st.form_submit_button("タイムテーブル保存 ✅"):
        st.session_state.tt_list.append({"tt_name": tt_n, "zone": tt_z, "sun_start": ss, "sun_end": se, "slots": f_slots})
        st.session_state.tt_slots_count = 1; st.rerun()

if st.session_state.tt_list:
    tt_df = pd.DataFrame([{"タイムテーブル名": x["tt_name"], "ゾーン": x["zone"], "登録数": len(x["slots"])} for x in st.session_state.tt_list])
    ev = st.dataframe(tt_df, use_container_width=True, on_select="rerun", selection_mode="single-row")
    if len(ev.selection.rows) > 0:
        sel = st.session_state.tt_list[ev.selection.rows[0]]
        with st.expander(f"【詳細】{sel['tt_name']} 内容", expanded=True):
            st.info(f"日出: {sel['sun_start']} / 日没: {sel['sun_end']}")
            st.table(pd.DataFrame(sel['slots']))
            if st.button("削除 🗑️"): st.session_state.tt_list.pop(ev.selection.rows[0]); st.rerun()

st.divider()

# 6. スケジュール適用・特異日設定
st.header("6. スケジュール適用・特異日設定 🗓️")
tt_to_zone = {tt["tt_name"]: tt["zone"] for tt in st.session_state.tt_list}
v_tt_names = [""] + list(tt_to_zone.keys())

col_a1, col_a2 = st.columns(2)
with col_a1:
    st.subheader("通常スケジュール設定 📅")
    with st.form("ts_form_v43"):
        mode = st.radio("設定方法", ["毎日一括(daily)", "曜日を指定して登録"])
        target_tt = st.selectbox("適用するタイムテーブル", v_tt_names)
        checked_days = []
        if mode == "曜日を指定して登録":
            st.write("適用曜日：")
            dcols = st.columns(7); dnames = ["月", "火", "水", "木", "金", "土", "日"]
            for i, d in enumerate(dnames):
                if dcols[i].checkbox(d): checked_days.append(d)
        if st.form_submit_button("適用保存 ✅"):
            if target_tt:
                tz = tt_to_zone[target_tt]
                idx = next((i for i, x in enumerate(st.session_state.ts_list) if x["zone"] == tz), None)
                if idx is None:
                    st.session_state.ts_list.append({"zone": tz, "config": {"daily":"", "mon":"", "tue":"", "wed":"", "thu":"", "fri":"", "sat":"", "sun":""}})
                    idx = len(st.session_state.ts_list) - 1
                if mode == "毎日一括(daily)": st.session_state.ts_list[idx]["config"]["daily"] = target_tt
                else:
                    dmap = {"月":"mon", "火":"tue", "水":"wed", "木":"thu", "金":"fri", "土":"sat", "日":"sun"}
                    for d in checked_days: st.session_state.ts_list[idx]["config"][dmap[d]] = target_tt
                st.rerun()

with col_a2:
    st.subheader("特異日・期間設定 🎌")
    with st.form("period_form_v43"):
        p_name = st.text_input("特異日名（例：正月、GW）", value="")
        pt = st.selectbox("適用するタイムテーブル ", v_tt_names)
        ps, pe = st.text_input("開始(MM/DD)", "01/01"), st.text_input("終了(MM/DD)", "01/03")
        if st.form_submit_button("期間保存 ✅"):
            if pt and ps and pe and p_name:
                if ps > pe: st.error("警告：年またぎ（12/31〜01/01）の設定はできません。")
                else:
                    pz = tt_to_zone[pt]
                    st.session_state.period_list.append({"name": p_name, "zone": pz, "tt": pt, "start": ps, "end": pe})
                    st.rerun()

if st.session_state.ts_list or st.session_state.period_list:
    st.subheader("現在の適用状況 📋")
    if st.session_state.ts_list:
        st.write("**通常設定**")
        st.table(pd.DataFrame([{"ゾーン": x["zone"], "毎日": x["config"]["daily"], "曜日別": ", ".join([f"{jp}:{x['config'][en]}" for en, jp in {"mon":"月", "tue":"火", "wed":"水", "thu":"木", "fri":"金", "sat":"土", "sun":"日"}.items() if x['config'][en]])} for x in st.session_state.ts_list]))
    if st.session_state.period_list:
        st.write("**特異日設定**")
        st.table(pd.DataFrame(st.session_state.period_list).rename(columns={"name":"特異日名", "zone":"ゾーン", "tt":"タイムテーブル", "start":"開始日", "end":"終了日"}))
    
    # ボタン名の変更と注釈の追加
    st.caption("※下のボタンは、上記スケジュール（適用・特異日）の登録のみをリセットします。ゾーンやグループ設定は消えません。")
    if st.button("スケジュールの割り当てをリセット 🔄", use_container_width=True): 
        st.session_state.ts_list = []
        st.session_state.period_list = []
        st.rerun()

st.divider()

# --- 7. CSV出力 ---
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
        mat.iloc[i, 207:212] = [p["name"], p["start"], p["end"], p["tt"], p["zone"]]

    st.dataframe(mat.iloc[:max(len(zf), len(gf), len(sf), len(ttf), 10)].dropna(how='all', axis=1))
    buf = io.BytesIO()
    pd.concat([pd.DataFrame(CSV_HEADER), mat], ignore_index=True).to_csv(buf, index=False, header=False, encoding="utf-8-sig")
    st.download_button("CSVダウンロード 📥", buf.getvalue(), f"{shop_name}_setting.csv", "text/csv")
