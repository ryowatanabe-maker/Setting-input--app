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

# シーン編集用のバッファ
if 'scene_edit_buf' not in st.session_state: st.session_state.scene_edit_buf = {}

# --- 3. UIセクション ---
st.header("1. 店舗名入力 🏢")
shop_name = st.text_input("店舗名", value="")
st.divider()

# 2. ゾーン登録
st.header("2. ゾーン登録 🌐")
with st.form("z_form_v48", clear_on_submit=True):
    col_z1, col_z2 = st.columns(2)
    z_name = col_z1.text_input("ゾーン名")
    z_fade = col_z2.number_input("フェード秒", 0, 60, 0)
    if st.form_submit_button("ゾーンを追加 ➕"):
        if z_name:
            st.session_state.z_list.append({"ゾーン名": z_name, "フェード秒": z_fade})
            st.rerun()
if st.session_state.z_list:
    st.table(pd.DataFrame(st.session_state.z_list).assign(No=range(1, len(st.session_state.z_list)+1)).set_index('No'))

# 3. グループ登録
st.header("3. グループ登録 💡")
v_zones = [""] + [z["ゾーン名"] for z in st.session_state.z_list]
with st.form("g_form_v48", clear_on_submit=True):
    col_g1, col_g2, col_g3 = st.columns(3)
    g_n, g_t, g_z = col_g1.text_input("グループ名"), col_g2.selectbox("タイプ", list(GROUP_TYPE_MAP.keys())), col_g3.selectbox("紐づけるゾーン", options=v_zones)
    if st.form_submit_button("グループを追加 ➕"):
        if g_n and g_z:
            st.session_state.g_list.append({"グループ名": g_n, "グループタイプ": g_t, "紐づけるゾーン名": g_z})
            st.rerun()
if st.session_state.g_list:
    st.table(pd.DataFrame(st.session_state.g_list).assign(No=range(1, len(st.session_state.g_list)+1)).set_index('No'))

st.divider()

# 4. シーン登録（数値入力のみ・編集機能）
st.header("4. シーン登録・編集 🎬")
if st.session_state.s_list:
    s_df_hist = pd.DataFrame(st.session_state.s_list)
    disp_df = s_df_hist.groupby(["シーン名", "紐づけるゾーン名"]).size().reset_index().rename(columns={0:"グループ数"})
    disp_df.index += 1
    st.subheader("現在のシーン登録状況（行をクリックで編集/削除）")
    ev_s = st.dataframe(disp_df, use_container_width=True, on_select="rerun", selection_mode="single-row", key="s_select_v48")
    
    if len(ev_s.selection.rows) > 0:
        row = disp_df.iloc[ev_s.selection.rows[0]]
        st.session_state.scene_edit_buf = {"name": row["シーン名"], "zone": row["紐づけるゾーン名"]}
        col_btn1, col_btn2 = st.columns(2)
        if col_btn1.button("選択したシーンを削除 🗑️"):
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["シーン名"] == row["シーン名"] and s["紐づけるゾーン名"] == row["紐づけるゾーン名"])]
            st.session_state.scene_edit_buf = {}
            st.rerun()
        st.info(f"「{row['シーン名']}」のデータを読み込みました。下のフォームで数値を直して保存してください。")

st.subheader("シーン設定フォーム")
with st.container(border=True):
    col_sn1, col_sn2 = st.columns(2)
    def_s_name = st.session_state.scene_edit_buf.get("name", "")
    def_s_zone = st.session_state.scene_edit_buf.get("zone", "")
    
    new_scene_name = col_sn1.text_input("シーン名", value=def_s_name, key="scene_name_v48")
    sel_zone_for_scene = col_sn2.selectbox("対象ゾーン", options=v_zones, index=v_zones.index(def_s_zone) if def_s_zone in v_zones else 0)

    if sel_zone_for_scene:
        target_groups = [g for g in st.session_state.g_list if g["紐づけるゾーン名"] == sel_zone_for_scene]
        scene_results = []
        for g in target_groups:
            gn, gt = g["グループ名"], g["グループタイプ"]
            st.write(f"**{gn}** ({gt})")
            
            # 既存の設定値を検索（編集用）
            existing_s = next((s for s in st.session_state.s_list if s["シーン名"] == def_s_name and s["紐づけるグループ名"] == gn), None)
            base_dim = int(existing_s["調光"]) if existing_s else 100
            base_k = existing_s["ケルビン"] if existing_s else "3500"
            
            # --- 数値入力ボックスのみのレイアウト ---
            c_dim, c_color, c_synca = st.columns([1, 2, 2])
            
            dim_num = c_dim.number_input(f"調光 (%)", 0, 100, base_dim, key=f"n_dim_{gn}")
            
            k_val = ""
            if gt != "調光":
                k_val = c_color.text_input("ケルビン (K)", value=base_k, key=f"k_{gn}")
            
            synca_val = ""
            if "Synca" in gt:
                rv = c_synca.selectbox("行", ["-"] + list(range(1, 12)), key=f"sr_{gn}")
                cv = c_synca.selectbox("列", ["-"] + list(range(1, 12)), key=f"sc_{gn}")
                if rv != "-" and cv != "-": synca_val = f"'{rv}-{cv}"

            scene_results.append({
                "シーン名": new_scene_name, "紐づけるグループ名": gn, "紐づけるゾーン名": sel_zone_for_scene,
                "調光": dim_num, "ケルビン": k_val if not synca_val else "", "Syncaカラー": synca_val
            })

        if st.button("履歴に登録・上書き保存 ✅", use_container_width=True):
            if new_scene_name:
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["シーン名"] == new_scene_name and s["紐づけるゾーン名"] == sel_zone_for_scene)]
                st.session_state.s_list.extend(scene_results)
                st.session_state.scene_edit_buf = {}
                st.rerun()

st.divider()

# --- 5. タイムテーブル作成 ---
st.header("5. タイムテーブル作成 ⏳")
v_scenes = [""] + sorted(list(set([s["シーン名"] for s in st.session_state.s_list])))
with st.expander("スケジュール自動作成"):
    with st.form("at_v48"):
        ca1, ca2, ca3, ca4 = st.columns(4)
        az, stt, edt, inv = ca1.selectbox("対象ゾーン ", v_zones), ca2.text_input("開始", "10:00"), ca3.text_input("終了", "21:00"), ca4.number_input("間隔(分)", 6, 120, 8)
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
            except: st.error("形式エラー")

with st.form("tt_v48"):
    ct1, ct2 = st.columns(2)
    tt_n, tt_z = ct1.text_input("タイムテーブル名", value="通常"), ct2.selectbox("対象ゾーン  ", v_zones, index=v_zones.index(st.session_state.get("temp_tt_zone", "")) if st.session_state.get("temp_tt_zone", "") in v_zones else 0)
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
        st.rerun()

if st.session_state.tt_list:
    st.subheader("タイムテーブル履歴（クリックで詳細）")
    tt_sum_df = pd.DataFrame([{"タイムテーブル名": x["tt_name"], "ゾーン": x["zone"], "登録数": len(x["slots"])} for x in st.session_state.tt_list])
    ev = st.dataframe(tt_sum_df, use_container_width=True, on_select="rerun", selection_mode="single-row", key="tt_list_v48")
    if len(ev.selection.rows) > 0:
        sel = st.session_state.tt_list[ev.selection.rows[0]]
        with st.expander(f"{sel['tt_name']} 内容", expanded=True):
            st.table(pd.DataFrame(sel['slots']))
            if st.button("削除 🗑️", key="del_tt_v48"): st.session_state.tt_list.pop(ev.selection.rows[0]); st.rerun()

st.divider()

# 6. スケジュール適用
st.header("6. スケジュール適用・特異日設定 🗓️")
tt_to_zone = {tt["tt_name"]: tt["zone"] for tt in st.session_state.tt_list}
v_tt_names = [""] + list(tt_to_zone.keys())
col_a1, col_a2 = st.columns(2)
with col_a1:
    st.subheader("通常スケジュール設定 📅")
    with st.form("ts_v48"):
        mode = st.radio("設定方法", ["毎日一括(daily)", "曜日を指定して登録"])
        target_tt = st.selectbox("適用するタイムテーブル", v_tt_names)
        checked_days = []
        if mode == "曜日を指定して登録":
            dcols = st.columns(7); dnames = ["月", "火", "水", "木", "金", "土", "日"]
            for i, d in enumerate(dnames):
                if dcols[i].checkbox(d): checked_days.append(d)
        if st.form_submit_button("適用を保存 ✅"):
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
    with st.form("period_v48"):
        p_n = st.text_input("特異日名")
        pt = st.selectbox("タイムテーブル案 ", v_tt_names)
        ps, pe = st.text_input("開始(MM/DD)", "01/01"), st.text_input("終了(MM/DD)", "01/03")
        if st.form_submit_button("期間保存 ✅"):
            if pt and ps and pe:
                if ps > pe: st.error("年またぎ不可")
                else:
                    pz = tt_to_zone[pt]
                    st.session_state.period_list.append({"name": p_n, "zone": pz, "tt": pt, "start": ps, "end": pe}); st.rerun()

if st.session_state.ts_list or st.session_state.period_list:
    st.subheader("現在の適用状況")
    if st.session_state.ts_list:
        ts_summary = []
        for x in st.session_state.ts_list:
            conf = x["config"]
            d_str = ", ".join([f"{jp}:{conf[en]}" for en, jp in {"mon":"月", "tue":"火", "wed":"水", "thu":"木", "fri":"金", "sat":"土", "sun":"日"}.items() if conf[en]])
            ts_summary.append({"ゾーン": x["zone"], "毎日": conf["daily"], "曜日別": d_str if d_str else "-"})
        st.table(pd.DataFrame(ts_summary))
    if st.session_state.period_list: st.table(pd.DataFrame(st.session_state.period_list))
    if st.button("スケジュールの割り当てをリセット 🔄"): st.session_state.ts_list = []; st.session_state.period_list = []; st.rerun()

st.divider()

# --- 7. 出力 ---
if st.button("CSV作成・プレビュー 💾", type="primary"):
    zf, gf, sf, ttf, tsf, pf = pd.DataFrame(st.session_state.z_list), pd.DataFrame(st.session_state.g_list), pd.DataFrame(st.session_state.s_list), st.session_state.tt_list, st.session_state.ts_list, st.session_state.period_list
    mat = pd.DataFrame(index=range(max(len(zf), len(gf), len(sf), len(ttf), 100)), columns=range(NUM_COLS))
    for i, r in zf.iterrows(): mat.iloc[i, 0:3] = [r["ゾーン名"], 4097+i, r["フェ秒"]]
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
    st.download_button("ダウンロード 📥", buf.getvalue(), f"{shop_name}_setting.csv", "text/csv")
