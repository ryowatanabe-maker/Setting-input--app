import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime, timedelta

# --- 1. 定数とヘッダー定義 ---
# システムが認識できる名称に統一 (Synca Brightも 3ch)
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}
NUM_COLS = 236 

# CSVの1行目（セクションタイトル）
ROW1 = [None] * NUM_COLS
ROW1[0], ROW1[4], ROW1[9], ROW1[17], ROW1[197], ROW1[207] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報', 'Timetable-schedule情報', 'Timetable期間/特異日情報'

# CSVの3行目（項目ヘッダー）
ROW3 = [None] * NUM_COLS
ROW3[0:3], ROW3[4:8] = ['[zone]', '[id]', '[fade]'], ['[group]', '[id]', '[type]', '[zone]']
ROW3[9:16] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]']
ROW3[17:22] = ['[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]']
for i in range(22, 196, 2): ROW3[i], ROW3[i+1] = '[time]', '[scene]'
ROW3[197:206] = ['[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]']
ROW3[207:212] = ['[zone-period]', '[start]', '[end]', '[timetable]', '[zone]']

CSV_HEADER = [ROW1, [None] * NUM_COLS, ROW3]

# --- 2. アプリ設定とデータ初期化 ---
st.set_page_config(page_title="FitPlus設定データ作成", layout="wide")
st.title("FitPlus 設定データ作成アプリ ⚙️")

# セッション管理（画面を更新してもデータを保持する）
for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
    if key not in st.session_state: st.session_state[key] = []
if 'tt_slots_count' not in st.session_state: st.session_state.tt_slots_count = 1
if 'auto_scene_count' not in st.session_state: st.session_state.auto_scene_count = 2
if 'scene_edit_buf' not in st.session_state: st.session_state.scene_edit_buf = {}

# --- 3. UIセクション ---
st.header("1. 店舗名入力 ")
shop_name = st.text_input("店舗名", value="店舗A")
st.divider()

# 2. ゾーン登録
st.header("2. ゾーン登録 ")
with st.form("z_form", clear_on_submit=True):
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
st.header("3. グループ登録 ")
v_zones = [""] + [z["ゾーン名"] for z in st.session_state.z_list]
with st.form("g_form", clear_on_submit=True):
    col_g1, col_g2, col_g3 = st.columns(3)
    g_n, g_t, g_z = col_g1.text_input("グループ名"), col_g2.selectbox("タイプ", list(GROUP_TYPE_MAP.keys())), col_g3.selectbox("紐づけるゾーン", options=v_zones)
    if st.form_submit_button("グループを追加 ➕"):
        if g_n and g_z:
            st.session_state.g_list.append({"グループ名": g_n, "グループタイプ": g_t, "紐づけるゾーン名": g_z})
            st.rerun()

if st.session_state.g_list:
    st.table(pd.DataFrame(st.session_state.g_list).assign(No=range(1, len(st.session_state.g_list)+1)).set_index('No'))

st.divider()

# 4. シーン登録（整合性エラー対策）
st.header("4. シーン登録・編集 ")
if st.session_state.s_list:
    s_df_hist = pd.DataFrame(st.session_state.s_list)
    disp_df = s_df_hist.groupby(["シーン名", "紐づけるゾーン名"]).size().reset_index().rename(columns={0:"グループ数"})
    disp_df.index += 1
    st.write("▼ 現在の登録状況（行をクリックで編集）")
    ev_s = st.dataframe(disp_df, use_container_width=True, on_select="rerun", selection_mode="single-row", key="s_v_final")
    
    if len(ev_s.selection.rows) > 0:
        row = disp_df.iloc[ev_s.selection.rows[0]]
        st.session_state.scene_edit_buf = {"name": row["シーン名"], "zone": row["紐づけるゾーン名"]}
        if st.button("選択したシーンを削除 🗑️"):
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["シーン名"] == row["シーン名"] and s["紐づけるゾーン名"] == row["紐づけるゾーン名"])]
            st.session_state.scene_edit_buf = {}
            st.rerun()

with st.container(border=True):
    col_sn1, col_sn2 = st.columns(2)
    def_s_name = st.session_state.scene_edit_buf.get("name", "")
    def_s_zone = st.session_state.scene_edit_buf.get("zone", "")
    new_scene_name = col_sn1.text_input("作成シーン名", value=def_s_name)
    sel_zone_for_scene = col_sn2.selectbox("対象ゾーン選択", options=v_zones, index=v_zones.index(def_s_zone) if def_s_zone in v_zones else 0)

    if sel_zone_for_scene:
        # そのゾーンに属するグループのみを抽出
        target_groups = [g for g in st.session_state.g_list if g["紐づけるゾーン名"] == sel_zone_for_scene]
        scene_results = []
        for g in target_groups:
            gn, gt, gz = g["グループ名"], g["グループタイプ"], g["紐づけるゾーン名"]
            st.write(f"**{gn}**")
            
            existing_s = next((s for s in st.session_state.s_list if s["シーン名"] == def_s_name and s["紐づけるグループ名"] == gn), None)
            
            c_dim, c_color, c_synca = st.columns([1, 2, 3])
            dim_val = c_dim.number_input(f"調光(%)", 0, 100, int(existing_s["調光"]) if existing_s else 100, key=f"n_dim_{gn}")
            k_val = c_color.text_input("ケルビン", value=existing_s["ケルビン"] if existing_s else "3500", key=f"k_{gn}") if gt != "調光" else ""
            
            synca_val = ""
            if "Synca" in gt:
                with c_synca:
                    with st.expander("🎨 パレット確認"):
                        if os.path.exists("synca_palette.png"): st.image("synca_palette.png")
                        else: st.info("画像なし")
                    c_s1, c_s2 = st.columns(2)
                    rv = c_s1.selectbox("行", ["-"] + list(range(1, 12)), key=f"sr_{gn}")
                    cv = c_s2.selectbox("列", ["-"] + list(range(1, 12)), key=f"sc_{gn}")
                    if rv != "-" and cv != "-": synca_val = f"'{rv}-{cv}"

            scene_results.append({
                "シーン名": new_scene_name, "紐づけるグループ名": gn, "紐づけるゾーン名": gz,
                "調光": dim_val, "ケルビン": k_val, "Syncaカラー": synca_val
            })

        if st.button("このゾーンのシーンを保存 ✅", use_container_width=True):
            if new_scene_name:
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["シーン名"] == new_scene_name and s["紐づけるゾーン名"] == sel_zone_for_scene)]
                st.session_state.s_list.extend(scene_results)
                st.session_state.scene_edit_buf = {}
                st.rerun()

st.divider()

# 5. タイムテーブル作成
st.header("5. タイムテーブル作成 ")
v_scenes = [""] + sorted(list(set([s["シーン名"] for s in st.session_state.s_list])))
with st.expander("スケジュール自動作成"):
    if st.button("繰り返すシーン枠を増やす ➕"): 
        st.session_state.auto_scene_count += 1
        st.rerun()
    with st.form("at_form"):
        ca1, ca2, ca3, ca4 = st.columns(4)
        az, stt, edt, inv = ca1.selectbox("対象ゾーン ", v_zones), ca2.text_input("開始", "10:00"), ca3.text_input("終了", "21:00"), ca4.number_input("間隔(分)", 6, 120, 30)
        ascs = []
        acols = st.columns(4)
        for i in range(st.session_state.auto_scene_count):
            with acols[i % 4]:
                v = st.selectbox(f"シーン{i+1}", v_scenes, key=f"as_{i}")
                if v: ascs.append(v)
        if st.form_submit_button("一括セット"):
            try:
                curr, limit = datetime.strptime(stt, "%H:%M"), datetime.strptime(edt, "%H:%M")
                slots, idx = [], 0
                while curr <= limit:
                    slots.append({"time": curr.strftime("%H:%M"), "scene": ascs[idx % len(ascs)]})
                    curr += timedelta(minutes=inv); idx += 1
                st.session_state.temp_slots, st.session_state.temp_tt_zone, st.session_state.tt_slots_count = slots, az, len(slots)
                st.rerun()
            except: st.error("時刻形式エラー")

with st.form("tt_form"):
    ct1, ct2 = st.columns(2)
    tt_n, tt_z = ct1.text_input("タイムテーブル名", value="通常"), ct2.selectbox("対象ゾーン  ", v_zones, index=v_zones.index(st.session_state.get("temp_tt_zone", "")) if st.session_state.get("temp_tt_zone", "") in v_zones else 0)
    ss, se = st.selectbox("日出シーン", v_scenes), st.selectbox("日没シーン", v_scenes)
    f_slots, b_slots = [], st.session_state.get("temp_slots", [])
    for i in range(st.session_state.tt_slots_count):
        c_t, c_s = st.columns([1, 2])
        dt, ds = (b_slots[i]["time"], b_slots[i]["scene"]) if i < len(b_slots) else ("", "")
        tv, sv = c_t.text_input(f"時間{i+1}", value=dt, key=f"t_{i}"), c_s.selectbox(f"シーン{i+1}", v_scenes, index=v_scenes.index(ds) if ds in v_scenes else 0, key=f"s_{i}")
        if tv and sv: f_slots.append({"time": tv, "scene": sv})
    if st.form_submit_button("タイムテーブルを保存 ✅"):
        st.session_state.tt_list.append({"tt_name": tt_n, "zone": tt_z, "sun_start": ss, "sun_end": se, "slots": f_slots})
        st.session_state.tt_slots_count = 1; st.session_state.temp_slots = []; st.rerun()

if st.button("手動入力枠を増やす ➕"): 
    st.session_state.tt_slots_count += 1
    st.rerun()

st.divider()

# 6. スケジュール適用
st.header("6. スケジュール適用・特異日設定 🗓️")
tt_to_zone = {tt["tt_name"]: tt["zone"] for tt in st.session_state.tt_list}
v_tt_names = [""] + list(tt_to_zone.keys())
col_a1, col_a2 = st.columns(2)
with col_a1:
    with st.form("ts_form"):
        mode = st.radio("通常設定", ["毎日(daily)", "曜日別"])
        target_tt = st.selectbox("適用するタイムテーブル", v_tt_names)
        if st.form_submit_button("適用保存"):
            if target_tt:
                tz = tt_to_zone[target_tt]
                idx = next((i for i, x in enumerate(st.session_state.ts_list) if x["zone"] == tz), None)
                if idx is None:
                    st.session_state.ts_list.append({"zone": tz, "config": {"daily":"", "mon":"", "tue":"", "wed":"", "thu":"", "fri":"", "sat":"", "sun":""}})
                    idx = len(st.session_state.ts_list) - 1
                if "毎日" in mode: st.session_state.ts_list[idx]["config"]["daily"] = target_tt
                st.rerun()
with col_a2:
    with st.form("period_form"):
        p_n, pt = st.text_input("特異日名"), st.selectbox("適用案 ", v_tt_names)
        ps, pe = st.text_input("開始(MM/DD)", "01/01"), st.text_input("終了(MM/DD)", "01/03")
        if st.form_submit_button("特異日保存"):
            if pt:
                st.session_state.period_list.append({"name": p_n, "zone": tt_to_zone[pt], "tt": pt, "start": ps, "end": pe})
                st.rerun()

if st.button("割り当てをリセット 🔄"): st.session_state.ts_list = []; st.session_state.period_list = []; st.rerun()

st.divider()

# --- 7. 出力 (バグ全修正・整合性確保版) ---
if st.button("CSV作成・ダウンロード 💾", type="primary"):
    zf = pd.DataFrame(st.session_state.z_list)
    gf = pd.DataFrame(st.session_state.g_list)
    sf = pd.DataFrame(st.session_state.s_list)
    ttf, tsf, pf = st.session_state.tt_list, st.session_state.ts_list, st.session_state.period_list

    # 巨大な表の作成
    mat = pd.DataFrame(index=range(max(len(zf), len(gf), len(sf), 100)), columns=range(NUM_COLS))
    
    # ゾーン
    for i, r in zf.iterrows(): mat.iloc[i, 0:3] = [r["ゾーン名"], 4097+i, r["フェード秒"]]
    # グループ (タイプ名を3chに、ゾーン名を正しく配置)
    for i, r in gf.iterrows(): mat.iloc[i, 4:8] = [r["グループ名"], 32770+i, GROUP_TYPE_MAP.get(r["グループタイプ"], "1ch"), r["紐づけるゾーン名"]]
    
    # シーン (整合性エラー対策の要)
    s_db, s_cnt = {}, 8193
    for i, r in sf.iterrows():
        # ゾーンごとに一意のIDを振る
        key = (r["シーン名"], r["紐づけるゾーン名"])
        if key not in s_db:
            s_db[key] = s_cnt
            s_cnt += 1
        
        # 13列目: Syncaカラー, 14列目: [zone], 15列目: [group]
        synca = str(r["Syncaカラー"]).replace("'", "") if r["Syncaカラー"] else ""
        # 13列目のperformは赤池店に合わせ空にするか固定
        mat.iloc[i, 9:16] = [r["シーン名"], s_db[key], r["調光"], r["ケルビン"], synca, r["紐づけるゾーン名"], r["紐づけるグループ名"]]

    # タイムテーブル
    for i, tt in enumerate(ttf):
        mat.iloc[i, 17:22] = [tt["tt_name"], 12289+i, tt["zone"], tt["sun_start"], tt["sun_end"]]
        c_idx = 22
        for slot in tt["slots"]:
            if c_idx < 196: mat.iloc[i, c_idx], mat.iloc[i, c_idx+1] = slot["time"], slot["scene"]; c_idx += 2
    
    # 適用
    for i, ts in enumerate(tsf):
        c = ts["config"]
        mat.iloc[i, 197:206] = [ts["zone"], c["daily"], c["mon"], c["tue"], c["wed"], c["thu"], c["fri"], c["sat"], c["sun"]]

    # 特異日 (日付形式を 1月1日 に変換)
    for i, p in enumerate(pf):
        sd = p["start"].replace("/", "月") + "日" if "/" in p["start"] else p["start"]
        ed = p["end"].replace("/", "月") + "日" if "/" in p["end"] else p["end"]
        # 先頭の0を削除 (01月 -> 1月)
        if sd.startswith("0"): sd = sd[1:]
        if ed.startswith("0"): ed = ed[1:]
        mat.iloc[i, 207:212] = [p["name"], sd, ed, p["tt"], p["zone"]]

    mat = mat.dropna(how='all')
    buf = io.BytesIO()
    final_output = pd.concat([pd.DataFrame(CSV_HEADER), mat], ignore_index=True)
    # 改行コードをWindows形式、BOM付きUTF-8
    final_output.to_csv(buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    st.download_button("完成版CSVをダウンロード 📥", buf.getvalue(), f"{shop_name}_FitPlus.csv", "text/csv")
