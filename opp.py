import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime, timedelta

# --- 1. アプリ設定とセッション管理 ---
st.set_page_config(page_title="FitPlus設定データ作成(マルチ形式対応)", layout="wide")
st.title("FitPlus 設定データ作成アプリ ⚙️")

# データの保持用
for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
    if key not in st.session_state: st.session_state[key] = []
if 'tt_slots_count' not in st.session_state: st.session_state.tt_slots_count = 1
if 'auto_scene_count' not in st.session_state: st.session_state.auto_scene_count = 2
if 'scene_edit_buf' not in st.session_state: st.session_state.scene_edit_buf = {}

# --- 2. 【最優先】機器選択と店舗名 ---
st.header("0. 機器と店舗の設定 🏗️")
col_opt1, col_opt2 = st.columns(2)

with col_opt1:
    gw_type = st.radio(
        "使用する機器を選択してください",
        ["BBR4HG (バッファロー/72列形式)", "メインゲートウェイ (標準/65列形式)"],
        help="BBR4HGはカインズ等の従来形式(ID 4097〜)、メインゲートウェイは最新のエクスポート形式(ID 1〜)に対応します。"
    )

with col_opt2:
    shop_name = st.text_input("店舗名を入力してください", value="店舗A")

st.divider()

# --- 3. 定数定義の自動切り替え ---
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

if "BBR4HG" in gw_type:
    NUM_COLS = 72
    ZONE_ID_START = 4097
    GROUP_ID_START = 32769
    SCENE_ID_START = 8193
    TT_ID_START = 12289
else:
    NUM_COLS = 65
    ZONE_ID_START = 1
    GROUP_ID_START = 1
    SCENE_ID_START = 1
    TT_ID_START = 1

# ヘッダー行の構築 (機器によって列の位置を微調整)
ROW1 = [None] * NUM_COLS
ROW1[0], ROW1[4], ROW1[9], ROW1[17] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報'

if "BBR4HG" in gw_type:
    ROW1[33], ROW1[43] = 'Timetable-schedule情報', 'Timetable期間/特異日情報'
else:
    ROW1[24], ROW1[34] = 'Timetable-schedule情報', 'Timetable期間/特異日情報'

ROW3 = [None] * NUM_COLS
ROW3[0:3], ROW3[4:8] = ['[zone]', '[id]', '[fade]'], ['[group]', '[id]', '[type]', '[zone]']
ROW3[9:16] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]']
ROW3[17:22] = ['[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]']

if "BBR4HG" in gw_type:
    # 72列版はタイムテーブル枠が22〜31列目
    for i in range(22, 32, 2): ROW3[i], ROW3[i+1] = '[time]', '[scene]'
    ROW3[33:42] = ['[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]']
    ROW3[43:48] = ['[zone-period]', '[start]', '[end]', '[timetable]', '[zone]']
else:
    # 65列版は24列目からスケジュール
    ROW3[24:33] = ['[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]']
    ROW3[34:40] = ['[zone-period]', '[id]', '[start]', '[end]', '[timetable]', '[zone]']

CSV_HEADER = [ROW1, [None] * NUM_COLS, ROW3]

# --- 4. 登録セクション (UI) ---
st.header("1. ゾーン・グループ登録 🌐")
c1, c2 = st.columns(2)

with c1:
    with st.form("z_form"):
        z_n = st.text_input("ゾーン名")
        z_f = st.number_input("フェード秒", 0, 60, 0)
        if st.form_submit_button("ゾーン追加"):
            if z_n: st.session_state.z_list.append({"ゾーン名": z_n, "フェード秒": z_f}); st.rerun()

with c2:
    v_zones = [""] + [z["ゾーン名"] for z in st.session_state.z_list]
    with st.form("g_form"):
        g_n = st.text_input("グループ名")
        g_t = st.selectbox("タイプ", list(GROUP_TYPE_MAP.keys()))
        g_z = st.selectbox("紐づけるゾーン", options=v_zones)
        if st.form_submit_button("グループ追加"):
            if g_n and g_z: st.session_state.g_list.append({"グループ名": g_n, "グループタイプ": g_t, "紐づけるゾーン名": g_z}); st.rerun()

st.divider()

# 5. シーン登録
st.header("2. シーン登録・編集 🎬")
with st.container(border=True):
    col_sn1, col_sn2 = st.columns(2)
    new_scene_name = col_sn1.text_input("シーン名 (例: 日中)")
    sel_zone_for_scene = col_sn2.selectbox("対象ゾーン", options=v_zones)

    if sel_zone_for_scene:
        target_groups = [g for g in st.session_state.g_list if g["紐づけるゾーン名"] == sel_zone_for_scene]
        scene_results = []
        for g in target_groups:
            gn, gt, gz = g["グループ名"], g["グループタイプ"], g["紐づけるゾーン名"]
            st.write(f"**{gn}**")
            c_dim, c_color, c_synca = st.columns([1, 1, 2])
            dim_val = c_dim.number_input(f"調光%", 0, 100, 100, key=f"d_{gn}")
            k_val = c_color.text_input("ケルビン", "3500", key=f"k_{gn}") if gt != "調光" else ""
            synca_val = ""
            if "Synca" in gt:
                with c_synca:
                    cs1, cs2 = st.columns(2)
                    rv = cs1.selectbox("行", ["-"] + list(range(1, 12)), key=f"r_{gn}")
                    cv = cs2.selectbox("列", ["-"] + list(range(1, 12)), key=f"c_{gn}")
                    if rv != "-" and cv != "-": synca_val = f"{rv}-{cv}"
            scene_results.append({"シーン名": new_scene_name, "紐づけるグループ名": gn, "紐づけるゾーン名": gz, "調光": dim_val, "ケルビン": k_val, "Syncaカラー": synca_val})
        
        if st.button("このシーンを保存 ✅"):
            st.session_state.s_list.extend(scene_results); st.rerun()

st.divider()

# --- 6. 出力ロジック (選択機器に合わせて完璧に配置) ---
st.header("3. CSV作成 💾")
if st.button("設定CSVを生成してダウンロード", type="primary"):
    zf, gf, sf = pd.DataFrame(st.session_state.z_list), pd.DataFrame(st.session_state.g_list), pd.DataFrame(st.session_state.s_list)
    mat = pd.DataFrame(index=range(max(len(zf), len(gf), len(sf), 50)), columns=range(NUM_COLS))
    
    # ゾーン
    for i, r in zf.iterrows(): mat.iloc[i, 0:3] = [r["ゾーン名"], ZONE_ID_START+i, r["フェード秒"]]
    
    # グループ
    for i, r in gf.iterrows(): mat.iloc[i, 4:8] = [r["グループ名"], GROUP_ID_START+i, GROUP_TYPE_MAP.get(r["グループタイプ"], "1ch"), r["紐づけるゾーン名"]]
    
    # シーン
    s_db, s_cnt = {}, SCENE_ID_START
    for i, r in sf.iterrows():
        key = (r["シーン名"], r["紐づけるゾーン名"])
        if key not in s_db: s_db[key] = s_cnt; s_cnt += 1
        synca = str(r["Syncaカラー"]).replace("'", "")
        # 列配置: 9[scene], 10[id], 11[dim], 12[color], 13[synca], 14[zone], 15[group]
        mat.iloc[i, 9:16] = [r["シーン名"], s_db[key], r["調光"], r["ケルビン"], synca, r["紐づけるゾーン名"], r["紐づけるグループ名"]]

    # タイムテーブル (簡易保存)
    for i, tt in enumerate(st.session_state.tt_list):
        mat.iloc[i, 17:22] = [tt["tt_name"], TT_ID_START+i, tt["zone"], tt["sun_start"], tt["sun_end"]]

    # スケジュール・特異日 (機器によって列番号を切り替え)
    ts_col = 33 if "BBR4HG" in gw_type else 24
    pe_col = 43 if "BBR4HG" in gw_type else 34
    
    for i, ts in enumerate(st.session_state.ts_list):
        c = ts["config"]
        mat.iloc[i, ts_col:ts_col+9] = [ts["zone"], c["daily"], c["mon"], c["tue"], c["wed"], c["thu"], c["fri"], c["sat"], c["sun"]]
    
    for i, p in enumerate(st.session_state.period_list):
        sd = p["start"].replace("/", "月") + "日" if "/" in p["start"] else p["start"]
        ed = p["end"].replace("/", "月") + "日" if "/" in p["end"] else p["end"]
        mat.iloc[i, pe_col:pe_col+5] = [p["name"], sd, ed, p["tt"], p["zone"]]

    buf = io.BytesIO()
    final_output = pd.concat([pd.DataFrame(CSV_HEADER), mat.dropna(how='all')], ignore_index=True)
    final_output.to_csv(buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    st.download_button("CSVを保存 📥", buf.getvalue(), f"{shop_name}_FitPlus.csv", "text/csv")
