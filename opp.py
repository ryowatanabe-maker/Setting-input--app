import streamlit as st
import pandas as pd
import io
import json
import tarfile
import csv

# --- 1. 定数 (「インポート可能.tar」をバイナリレベルで完コピ) ---
NUM_COLS = 72
Z_ID_BASE, G_ID_BASE, S_ID_BASE = 4097, 32769, 8193
TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

st.set_page_config(page_title="FitPlus メインGW完全対応版", layout="wide")
st.title("FitPlus 設定作成 (反映エラー解消版) ⚙️")

# セッション状態
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []

# --- 2. 登録 UI (ここは変更なし) ---
c1, c2 = st.columns(2)
with c1:
    with st.form("z_form", clear_on_submit=True):
        st.subheader("1. ゾーン登録")
        zn = st.text_input("ゾーン名")
        zf = st.number_input("フェード", 0, 60, 10)
        if st.form_submit_button("追加"):
            if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    for i, z in enumerate(st.session_state.z_list):
        cl, cr = st.columns([4, 1]); cl.write(f"📍 {z['名']} (ID: {Z_ID_BASE+i})")
        if cr.button("削除", key=f"dz_{i}"): st.session_state.z_list.pop(i); st.rerun()

with c2:
    vz = [""] + [z["名"] for z in st.session_state.z_list]
    with st.form("g_form", clear_on_submit=True):
        st.subheader("2. グループ登録")
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(TYPE_MAP.keys()))
        gz = st.selectbox("所属ゾーン", options=vz)
        if st.form_submit_button("追加"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
    for i, g in enumerate(st.session_state.g_list):
        cl, cr = st.columns([4, 1]); cl.write(f"💡 {g['名']} ({g['ゾ']})")
        if cr.button("削除", key=f"dg_{i}"): st.session_state.g_list.pop(i); st.rerun()

st.header("3. シーン設定")
with st.container(border=True):
    col_sn, col_sz = st.columns(2)
    s_name = col_sn.text_input("シーン名")
    s_zone = col_sz.selectbox("設定ゾーン", options=vz, key="sz_s")
    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        scene_tmp = []
        for g in target_gs:
            st.write(f"■ {g['名']}")
            cc1, cc2 = st.columns(2)
            dim = cc1.number_input("調光", 0, 100, 100, key=f"d_{g['名']}_{s_name}")
            kel = cc2.text_input("色温度", "3500", key=f"k_{g['名']}_{s_name}") if g['型'] != "調光" else ""
            scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel})
        if st.button("このシーンを保存", use_container_width=True):
            if s_name: st.session_state.s_list.extend(scene_tmp); st.rerun()

# --- 3. CSV手動生成ロジック (Pandasを使わず純粋なカンマ区切りを生成) ---
st.divider()
if st.button("📥 メインGW専用 .tar を出力 (反映成功版)", type="primary", use_container_width=True):
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_NONE, escapechar=' ', lineterminator='\r\n')
    
    # ヘッダー行作成
    h1 = [""] * NUM_COLS
    h1[0], h1[4], h1[9], h1[17] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報'
    h3 = [""] * NUM_COLS
    h3[0:3] = ['[zone]', '[id]', '[fade]']
    h3[4:8] = ['[group]', '[id]', '[type]', '[zone]']
    h3[9:16] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]']
    h3[17:22] = ['[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]']
    
    writer.writerow(h1)
    writer.writerow([""] * NUM_COLS)
    writer.writerow(h3)

    # データ行作成 (最大数に合わせてループ)
    max_rows = max(len(st.session_state.z_list), len(st.session_state.g_list), len(st.session_state.s_list), 1)
    s_map, s_idx = {}, S_ID_BASE
    
    for i in range(max_rows):
        row = [""] * NUM_COLS
        # ゾーン
        if i < len(st.session_state.z_list):
            z = st.session_state.z_list[i]
            row[0], row[1], row[2] = z["名"], Z_ID_BASE + i, z["秒"]
        # グループ
        if i < len(st.session_state.g_list):
            g = st.session_state.g_list[i]
            row[4], row[5], row[6], row[7] = g["名"], G_ID_BASE + i, TYPE_MAP.get(g["型"]), g["ゾ"]
        # シーン
        if i < len(st.session_state.s_list):
            s = st.session_state.s_list[i]
            key = (s["sn"], s["zn"])
            if key not in s_map: s_map[key] = s_idx; s_idx += 1
            row[9], row[10], row[11], row[12], row[14], row[15] = s["sn"], s_map[key], s["dim"], s["kel"], s["zn"], s["gn"]
        
        writer.writerow(row)

    # バイナリ化 (BOMあり UTF-8)
    csv_bytes = output.getvalue().encode('utf-8-sig')
    json_bytes = json.dumps({"pair": [], "csv": "setting_data.csv"}, indent=2).encode('utf-8')

    # TAR作成 (ustar形式)
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        c_info = tarfile.TarInfo(name="setting_data.csv"); c_info.size = len(csv_bytes)
        tar.addfile(c_info, io.BytesIO(csv_bytes))
        j_info = tarfile.TarInfo(name="temp.json"); j_info.size = len(json_bytes)
        tar.addfile(j_info, io.BytesIO(json_bytes))

    st.success("作成しました！解凍せずそのままゲートウェイへ。")
    st.download_button("📥 Final_Setup.tar", tar_buf.getvalue(), "Final_Setup.tar")
