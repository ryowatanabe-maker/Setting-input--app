import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime, timedelta

# --- 1. アプリ設定 ---
st.set_page_config(page_title="FitPlus設定データ作成(完全版)", layout="wide")
st.title("FitPlus 設定データ作成アプリ ⚙️")

# セッション管理（履歴を保持する箱）
for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
    if key not in st.session_state: st.session_state[key] = []
if 'tt_slots_count' not in st.session_state: st.session_state.tt_slots_count = 1
if 'auto_scene_count' not in st.session_state: st.session_state.auto_scene_count = 2

# --- 2. 機器・店舗設定 ---
st.header("0. 機器と店舗の設定")
col_opt1, col_opt2 = st.columns(2)
with col_opt1:
    gw_type = st.radio("機器選択", ["BBR4HG (72列形式)", "メインゲートウェイ (65列形式)"], horizontal=True)
shop_name = col_opt2.text_input("店舗名", value="店舗A")
st.divider()

# 定数とID設定
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}
if "BBR4HG" in gw_type:
    NUM_COLS, Z_ID_BASE, G_ID_BASE, S_ID_BASE, TT_ID_BASE = 72, 4097, 32769, 8193, 12289
else:
    NUM_COLS, Z_ID_BASE, G_ID_BASE, S_ID_BASE, TT_ID_BASE = 65, 1, 1, 1, 1

# --- 3. ゾーン登録 ---
st.header("1. ゾーン登録")
with st.container(border=True):
    cz1, cz2, cz3 = st.columns([2, 1, 1])
    z_n = cz1.text_input("ゾーン名 (例: 店内, 店外)", key="zn_in")
    z_f = cz2.number_input("フェード秒", 0, 60, 0, key="zf_in")
    if cz3.button("ゾーンを追加 ➕", use_container_width=True):
        if z_n:
            # データを保存
            st.session_state.z_list.append({"名": z_n, "秒": z_f})
            st.rerun()

# ゾーンの履歴表示と削除
if st.session_state.z_list:
    st.subheader("現在のゾーン")
    for i, z in enumerate(st.session_state.z_list):
        cl, cr = st.columns([5, 1])
        cl.write(f"📍 {z['名']} (フェード: {z['秒']}秒)")
        if cr.button("削除", key=f"del_z_{i}"):
            st.session_state.z_list.pop(i)
            st.rerun()

# --- 4. グループ登録 ---
st.header("2. グループ登録")
v_zones = [""] + [z["名"] for z in st.session_state.z_list]
with st.container(border=True):
    cg1, cg2, cg3, cg4 = st.columns([2, 1, 2, 1])
    gn = cg1.text_input("グループ名")
    gt = cg2.selectbox("タイプ", list(GROUP_TYPE_MAP.keys()))
    gz = cg3.selectbox("所属ゾーン", options=v_zones)
    if cg4.button("グループ追加 ➕", use_container_width=True):
        if gn and gz:
            st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz})
            st.rerun()

# グループの履歴表示と削除
if st.session_state.g_list:
    st.subheader("現在のグループ")
    for i, g in enumerate(st.session_state.g_list):
        cl, cr = st.columns([5, 1])
        cl.write(f"💡 {g['名']} ({g['型']}) - 所属: {g['ゾ']}")
        if cr.button("削除", key=f"del_g_{i}"):
            st.session_state.g_list.pop(i)
            st.rerun()

st.divider()

# --- 5. シーン登録 ---
st.header("3. シーン設定")
with st.container(border=True):
    csn, csz = st.columns(2)
    s_name_in = csn.text_input("シーン名 (例: 日中)")
    s_zone_in = csz.selectbox("設定対象ゾーン", options=v_zones, key="s_zone_sel")
    
    if s_zone_in:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone_in]
        scene_data = []
        for g in target_gs:
            st.write(f"■ グループ: **{g['名']}**")
            c1, c2, c3 = st.columns([1, 1, 2])
            dim = c1.number_input("調光%", 0, 100, 100, key=f"d_{g['名']}")
            kel = c2.text_input("色温度", "3500", key=f"k_{g['名']}") if g['型'] != "調光" else ""
            syn = ""
            if "Synca" in g['型']:
                with c3:
                    cs1, cs2 = st.columns(2)
                    r = cs1.selectbox("行", ["-"] + list(range(1, 12)), key=f"r_{g['名']}")
                    c = cs2.selectbox("列", ["-"] + list(range(1, 12)), key=f"c_{g['名']}")
                    if r != "-" and c != "-": syn = f"{r}-{c}"
            scene_data.append({"sn": s_name_in, "gn": g['名'], "zn": s_zone_in, "dim": dim, "kel": kel, "syn": syn})
        
        if st.button("このシーンを保存 ✅", use_container_width=True):
            if s_name_in:
                # 既存の同一(シーン名+ゾーン名)を削除して上書き
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name_in and s["zn"] == s_zone_in)]
                st.session_state.s_list.extend(scene_data)
                st.rerun()

if st.session_state.s_list:
    st.subheader("現在のシーン登録状況")
    s_df = pd.DataFrame(st.session_state.s_list)
    summ = s_df.groupby(["sn", "zn"]).size().reset_index()
    for i, row in summ.iterrows():
        cl, cr = st.columns([5, 1])
        cl.write(f"🎬 {row['sn']} (ゾーン: {row['zn']})")
        if cr.button("削除", key=f"del_s_{i}"):
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == row['sn'] and s["zn"] == row['zn'])]
            st.rerun()

st.divider()

# --- 6. タイムテーブル・スケジュール・特異日 ---
st.header("4. スケジュール・特異日設定")
tab1, tab2, tab3 = st.tabs(["タイムテーブル案作成", "通常スケジュール割当", "特異日(期間)設定"])

with tab1:
    v_s_names = [""] + sorted(list(set([s["sn"] for s in st.session_state.s_list])))
    with st.form("tt_form"):
        tt_name = st.text_input("案の名前 (例: 通常, セール時)", "通常")
        tt_zone = st.selectbox("対象ゾーン", v_zones, key="ttz")
        sun_s = st.selectbox("日出シーン", v_s_names)
        sun_e = st.selectbox("日没シーン", v_s_names)
        slots = []
        for i in range(4):
            c1, c2 = st.columns(2)
            t = c1.text_input(f"時刻{i+1}", "09:00" if i==0 else "", placeholder="HH:MM")
            s = c2.selectbox(f"シーン{i+1}", v_s_names, key=f"tts_{i}")
            if t and s: slots.append({"t": t, "s": s})
        if st.form_submit_button("タイムテーブル案を保存"):
            if tt_name and tt_zone:
                st.session_state.tt_list.append({"name": tt_name, "zone": tt_zone, "ss": sun_s, "se": sun_e, "slots": slots})
                st.rerun()

if st.session_state.tt_list:
    st.write("▼ 登録済みのタイムテーブル案")
    for i, t in enumerate(st.session_state.tt_list):
        cl, cr = st.columns([5, 1])
        cl.write(f"⏳ {t['name']} (ゾーン: {t['zone']}) - 設定数: {len(t['slots'])}")
        if cr.button("削除", key=f"del_tt_{i}"):
            st.session_state.tt_list.pop(i); st.rerun()

with tab2:
    v_tt = [""] + [t["name"] for t in st.session_state.tt_list]
    with st.form("ts_form"):
        target_tt = st.selectbox("適用する案", v_tt)
        if st.form_submit_button("毎日(daily)として適用"):
            if target_tt:
                zone_of_tt = next(t["zone"] for t in st.session_state.tt_list if t["name"] == target_tt)
                st.session_state.ts_list = [x for x in st.session_state.ts_list if x["zone"] != zone_of_tt]
                st.session_state.ts_list.append({"zone": zone_of_tt, "daily": target_tt})
                st.rerun()

if st.session_state.ts_list:
    for i, ts in enumerate(st.session_state.ts_list):
        cl, cr = st.columns([5, 1])
        cl.write(f"📅 ゾーン: {ts['zone']} ➔ 毎日: {ts['daily']}")
        if cr.button("解除", key=f"del_ts_{i}"):
            st.session_state.ts_list.pop(i); st.rerun()

with tab3:
    with st.form("p_form"):
        p_n = st.text_input("特異日名 (例: 正月)")
        p_t = st.selectbox("使用する案", v_tt, key="pt_sel")
        p_s = st.text_input("開始(MM/DD)", "01/01")
        p_e = st.text_input("終了(MM/DD)", "01/03")
        if st.form_submit_button("特異日として保存"):
            if p_t:
                zone_of_p = next(t["zone"] for t in st.session_state.tt_list if t["name"] == p_t)
                st.session_state.period_list.append({"name": p_n, "zone": zone_of_p, "tt": p_t, "start": p_s, "end": p_e})
                st.rerun()

if st.session_state.period_list:
    for i, p in enumerate(st.session_state.period_list):
        cl, cr = st.columns([5, 1])
        cl.write(f"🎌 {p['name']} ({p['start']}〜{p['end']}) ➔ 案: {p['tt']}")
        if cr.button("削除", key=f"del_p_{i}"):
            st.session_state.period_list.pop(i); st.rerun()

st.divider()

# --- 7. CSV作成ロジック ---
if st.button("CSV作成・ダウンロード 💾", type="primary"):
    # ヘッダー構築
    ROW1_CSV = [None] * NUM_COLS
    ROW1_CSV[0], ROW1_CSV[4], ROW1_CSV[9], ROW1_CSV[17] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報'
    if NUM_COLS == 72:
        ROW1_CSV[33], ROW1_CSV[43] = 'Timetable-schedule情報', 'Timetable期間/特異日情報'
    else:
        ROW1_CSV[24], ROW1_CSV[34] = 'Timetable-schedule情報', 'Timetable期間/特異日情報'
    
    ROW3_CSV = [None] * NUM_COLS
    ROW3_CSV[0:3] = ['[zone]', '[id]', '[fade]']
    ROW3_CSV[4:8] = ['[group]', '[id]', '[type]', '[zone]']
    ROW3_CSV[9:16] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]']
    ROW3_CSV[17:22] = ['[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]']
    if NUM_COLS == 72:
        for i in range(22, 32, 2): ROW3_CSV[i], ROW3_CSV[i+1] = '[time]', '[scene]'
        ROW3_CSV[33:42] = ['[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]']
        ROW3_CSV[43:48] = ['[zone-period]', '[start]', '[end]', '[timetable]', '[zone]']
    else:
        ROW3_CSV[24:33] = ['[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]']
        ROW3_CSV[34:40] = ['[zone-period]', '[id]', '[start]', '[end]', '[timetable]', '[zone]']

    mat = pd.DataFrame(index=range(100), columns=range(NUM_COLS))
    # ゾーン
    for i, r in enumerate(st.session_state.z_list): mat.iloc[i, 0:3] = [r["名"], Z_ID_BASE+i, r["秒"]]
    # グループ
    for i, r in enumerate(st.session_state.g_list): mat.iloc[i, 4:8] = [r["名"], G_ID_BASE+i, GROUP_TYPE_MAP.get(r["型"], "1ch"), r["ゾ"]]
    # シーン
    s_db, s_cnt = {}, S_ID_BASE
    for i, r in enumerate(st.session_state.s_list):
        key = (r["sn"], r["zn"])
        if key not in s_db: s_db[key] = s_cnt; s_cnt += 1
        mat.iloc[i, 9:16] = [r["sn"], s_db[key], r["dim"], r["kel"], r["syn"], r["zn"], r["gn"]]
    # タイムテーブル
    for i, tt in enumerate(st.session_state.tt_list):
        mat.iloc[i, 17:22] = [tt["name"], TT_ID_BASE+i, tt["zone"], tt["ss"], tt["se"]]
        if NUM_COLS == 72:
            c_idx = 22
            for slot in tt["slots"]:
                if c_idx < 32: mat.iloc[i, c_idx], mat.iloc[i, c_idx+1] = slot["t"], slot["s"]; c_idx += 2
    # スケジュールと特異日
    ts_c = 33 if NUM_COLS == 72 else 24
    pe_c = 43 if NUM_COLS == 72 else 34
    for i, ts in enumerate(st.session_state.ts_list): mat.iloc[i, ts_c:ts_c+2] = [ts["zone"], ts["daily"]]
    for i, p in enumerate(st.session_state.period_list):
        sd = p["start"].replace("/", "月") + "日"; ed = p["end"].replace("/", "月") + "日"
        mat.iloc[i, pe_c:pe_c+5] = [p["name"], sd, ed, p["tt"], p["zone"]]

 # --- 7. CSV出力 (特異日エラー対策版) ---
if st.button("CSV作成・ダウンロード 💾", type="primary"):
    # データの準備
    zf, gf, sf = pd.DataFrame(st.session_state.z_list), pd.DataFrame(st.session_state.g_list), pd.DataFrame(st.session_state.s_list)
    ttf, tsf, pf = st.session_state.tt_list, st.session_state.ts_list, st.session_state.period_list

    # 白紙の巨大な表を作成
    mat = pd.DataFrame(index=range(max(len(zf), len(gf), len(sf), 50)), columns=range(NUM_COLS))
    
    # --- (中略：ゾーン、グループ、シーンの流し込み) ---
    # ※ここは前回のコードと同じでOKです

    # --- 特異日セクション (ここがエラーの直接的な原因) ---
    pe_col = 43 if NUM_COLS == 72 else 34
    for i, p in enumerate(pf):
        # 【修正】01/01 や 1/1 を「1月1日」という形式に強制変換する
        start_raw = p["start"].replace("/", "月") + "日" if "/" in p["start"] else p["start"]
        end_raw = p["end"].replace("/", "月") + "日" if "/" in p["end"] else p["end"]
        
        # 先頭の「0」を取る（例：01月01日 → 1月1日）
        def clean_date(d):
            return d.replace("0", "") if d.startswith("0") else d
            
        mat.iloc[i, pe_col:pe_col+5] = [
            p["name"], 
            clean_date(start_raw), 
            clean_date(end_raw), 
            p["tt"], 
            p["zone"]
        ]

    # 【重要】データが入っていない行（カンマだけの行）を完全に消す
    mat = mat.dropna(how='all')

    buf = io.BytesIO()
    final_output = pd.concat([pd.DataFrame(CSV_HEADER), mat], ignore_index=True)
    
    # 改行コードをWindows形式（\r\n）にして保存
    final_output.to_csv(buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    st.download_button("修正済みCSVをダウンロード 📥", buf.getvalue(), f"{shop_name}_FitPlus.csv", "text/csv")
