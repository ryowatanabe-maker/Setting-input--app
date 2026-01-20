import streamlit as st
import pandas as pd
import io
import os
import json
from datetime import datetime, timedelta

# --- 1. アプリ設定と定数 ---
st.set_page_config(page_title="FitPlus 自己圧縮対応版", layout="wide")
st.title("FitPlus 設定データ作成 (自己圧縮・インポート完全対応) ⚙️")

# BBR4HG/大利根店形式(72列)をベースに固定
NUM_COLS = 72
Z_ID_BASE = 4097
G_ID_BASE = 32769
S_ID_BASE = 8193
TT_ID_BASE = 12289
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

# セッション管理
for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
    if key not in st.session_state: st.session_state[key] = []

# --- 2. 登録セクション ---
st.header("1. ゾーン・グループ登録")
c1, c2 = st.columns(2)
with c1:
    with st.form("z_f"):
        zn = st.text_input("ゾーン名 (例: 店内)")
        zf = st.number_input("フェード秒", 0, 60, 0)
        if st.form_submit_button("ゾーン追加"):
            if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    # 削除機能
    for i, z in enumerate(st.session_state.z_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"📍 {z['名']}")
        if cr.button("削除", key=f"dz_{i}"): st.session_state.z_list.pop(i); st.rerun()

with c2:
    vz = [""] + [z["名"] for z in st.session_state.z_list]
    with st.form("g_f"):
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(GROUP_TYPE_MAP.keys()))
        gz = st.selectbox("所属ゾーン", options=vz)
        if st.form_submit_button("グループ追加"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
    # 削除機能
    for i, g in enumerate(st.session_state.g_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"💡 {g['名']} ({g['型']})")
        if cr.button("削除", key=f"dg_{i}"): st.session_state.g_list.pop(i); st.rerun()

st.divider()

st.header("2. シーン登録")
with st.container(border=True):
    csn, csz = st.columns(2)
    s_name = csn.text_input("シーン名 (例: 日中)")
    s_zone = csz.selectbox("設定対象ゾーン", options=vz, key="sz_sel")
    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        scene_data = []
        for g in target_gs:
            st.write(f"■ {g['名']}")
            c1, c2, c3 = st.columns([1, 1, 2])
            dim = c1.number_input("調光%", 0, 100, 100, key=f"d_{g['名']}_{s_name}")
            kel = c2.text_input("色温度", "3500", key=f"k_{g['名']}_{s_name}") if g['型'] != "調光" else ""
            syn = ""
            if "Synca" in g['型']:
                with c3:
                    cs1, cs2 = st.columns(2)
                    r = cs1.selectbox("行", ["-"] + list(range(1, 12)), key=f"r_{g['名']}_{s_name}")
                    c = cs2.selectbox("列", ["-"] + list(range(1, 12)), key=f"c_{g['名']}_{s_name}")
                    if r != "-" and c != "-": syn = f"{r}-{c}"
            scene_data.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "syn": syn})
        if st.button("シーン保存", use_container_width=True):
            st.session_state.s_list.extend(scene_data); st.rerun()

st.divider()

# --- 3. CSV & JSON出力ロジック ---
st.header("3. 自己圧縮用データの出力 💾")
st.info("※ここで出力されるCSV名は 'setting_data.csv' に固定されます。")

if st.button("インポート用ファイルを生成", type="primary", use_container_width=True):
    # ヘッダー構築
    ROW1 = [None] * NUM_COLS
    ROW1[0], ROW1[4], ROW1[9], ROW1[17], ROW1[33], ROW1[43] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報', 'Timetable-schedule情報', 'Timetable期間/特異日情報'
    ROW3 = [None] * NUM_COLS
    ROW3[0:3] = ['[zone]', '[id]', '[fade]']
    ROW3[4:8] = ['[group]', '[id]', '[type]', '[zone]']
    ROW3[9:16] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]']
    ROW3[17:22] = ['[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]']
    for i in range(22, 32, 2): ROW3[i], ROW3[i+1] = '[time]', '[scene]'
    ROW3[33:42] = ['[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]']
    ROW3[43:48] = ['[zone-period]', '[start]', '[end]', '[timetable]', '[zone]']

    mat = pd.DataFrame(index=range(200), columns=range(NUM_COLS))
    
    # ゾーン
    for i, r in enumerate(st.session_state.z_list):
        mat.iloc[i, 0:3] = [r["名"], Z_ID_BASE+i, r["秒"]]
    
    # グループ
    for i, r in enumerate(st.session_state.g_list):
        mat.iloc[i, 4:8] = [r["名"], G_ID_BASE+i, GROUP_TYPE_MAP.get(r["型"]), r["ゾ"]]
    
    # シーン (整合性維持のため列14[zone]を必ず埋める)
    s_db, s_cnt = {}, S_ID_BASE
    for i, r in enumerate(st.session_state.s_list):
        key = (r["sn"], r["zn"])
        if key not in s_db: s_db[key] = s_cnt; s_cnt += 1
        mat.iloc[i, 9:16] = [r["sn"], s_db[key], r["dim"], r["kel"], r["syn"], r["zn"], r["gn"]]

    # CSVの作成
    buf_csv = io.BytesIO()
    final_csv = pd.concat([pd.DataFrame([ROW1, [None]*NUM_COLS, ROW3]), mat.dropna(how='all')], ignore_index=True)
    final_csv.to_csv(buf_csv, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    
    # JSONの作成 (CSV名に合わせる)
    json_data = {"pair": [], "csv": "setting_data"}
    buf_json = io.BytesIO(json.dumps(json_data, indent=2).encode('utf-8'))

    st.success("準備完了！以下の2つのファイルをダウンロードして、直接tarにまとめてください。")
    c_dl1, c_dl2 = st.columns(2)
    c_dl1.download_button("1. CSVを保存 (setting_data.csv)", buf_csv.getvalue(), "setting_data.csv", "text/csv")
    c_dl2.download_button("2. JSONを保存 (temp.json)", buf_json.getvalue(), "temp.json", "application/json")

st.warning("⚠️ 自己圧縮のコツ: フォルダごとではなく、上記2つのファイルだけを直接選択してtarにまとめてください。")
