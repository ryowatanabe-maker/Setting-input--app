import streamlit as st
import pandas as pd
import io
import json

# --- 0. 再描画関数を最新版に修正 ---
def safe_rerun():
    # 最新のStreamlitではこれだけで動作します
    st.rerun()

# --- 1. 定数定義 (大利根店・自己圧縮成功ファイルに完全準拠) ---
NUM_COLS = 72
Z_ID, G_ID, S_ID, T_ID = 4097, 32769, 8193, 12289
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

st.set_page_config(page_title="FitPlus 設定作成 v61-Final", layout="wide")
st.title("FitPlus 設定データ作成 (BBR4HG/自己圧縮対応) ⚙️")

# セッション状態の初期化
for key in ['z_list', 'g_list', 's_list']:
    if key not in st.session_state:
        st.session_state[key] = []

# --- 2. 登録セクション ---

# ゾーン登録
st.header("1. ゾーン登録")
with st.container(border=True):
    cz1, cz2, cz3 = st.columns([2, 1, 1])
    z_n = cz1.text_input("ゾーン名 (例: 店内)", key="z_name_in")
    z_f = cz2.number_input("フェード秒", 0, 60, 0, key="z_fade_in")
    if cz3.button("ゾーンを追加 ➕", use_container_width=True, key="add_z"):
        if z_n:
            st.session_state.z_list.append({"名": z_n, "秒": z_f})
            safe_rerun()

if st.session_state.z_list:
    for i, z in enumerate(st.session_state.z_list):
        cl, cr = st.columns([5, 1])
        cl.write(f"📍 {z['名']} (ID: {Z_ID + i})")
        if cr.button("削除", key=f"dz_{i}"):
            st.session_state.z_list.pop(i)
            safe_rerun()

# グループ登録
st.header("2. グループ登録")
v_zones = [""] + [z["名"] for z in st.session_state.z_list]
with st.container(border=True):
    cg1, cg2, cg3, cg4 = st.columns([2, 1, 2, 1])
    gn = cg1.text_input("グループ名", key="g_name_in")
    gt = cg2.selectbox("タイプ", list(GROUP_TYPE_MAP.keys()), key="g_type_in")
    gz = cg3.selectbox("所属ゾーン", options=v_zones, key="g_zone_in")
    if cg4.button("グループ追加 ➕", use_container_width=True, key="add_g"):
        if gn and gz:
            st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz})
            safe_rerun()

if st.session_state.g_list:
    for i, g in enumerate(st.session_state.g_list):
        cl, cr = st.columns([5, 1])
        cl.write(f"💡 {g['名']} ({g['型']}) -> {g['ゾ']}")
        if cr.button("削除", key=f"dg_{i}"):
            st.session_state.g_list.pop(i)
            safe_rerun()

# シーン登録
st.header("3. シーン設定")
with st.container(border=True):
    csn, csz = st.columns(2)
    s_name = csn.text_input("シーン名 (例: 日中)", key="scene_name_input")
    s_zone = csz.selectbox("設定対象ゾーン", options=v_zones, key="scene_zone_select")
    
    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        scene_data = []
        for g in target_gs:
            st.write(f"■ グループ: **{g['名']}**")
            c1, c2, c3 = st.columns([1, 1, 2])
            dim = c1.number_input("調光%", 0, 100, 100, key=f"d_val_{g['名']}_{s_name}")
            kel = c2.text_input("色温度", "3500", key=f"k_val_{g['名']}_{s_name}") if g['型'] != "調光" else ""
            syn = ""
            if "Synca" in g['型']:
                with c3:
                    cs1, cs2 = st.columns(2)
                    r_val = cs1.selectbox("行", ["-"] + list(range(1, 12)), key=f"r_val_{g['名']}_{s_name}")
                    c_val = cs2.selectbox("列", ["-"] + list(range(1, 12)), key=f"c_val_{g['名']}_{s_name}")
                    if r_val != "-" and c_val != "-": syn = f"{r_val}-{c_val}"
            scene_data.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "syn": syn})
        
        if st.button("このシーンを保存 ✅", use_container_width=True, key="btn_save_scene"):
            if s_name:
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
                st.session_state.s_list.extend(scene_data)
                safe_rerun()

if st.session_state.s_list:
    s_df = pd.DataFrame(st.session_state.s_list)
    summ = s_df.groupby(["sn", "zn"]).size().reset_index()
    for i, row in summ.iterrows():
        cl, cr = st.columns([5, 1])
        cl.write(f"🎬 {row['sn']} (ゾーン: {row['zn']})")
        if cr.button("削除", key=f"del_s_list_{i}"):
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == row['sn'] and s["zn"] == row['zn'])]
            safe_rerun()

st.divider()

# --- 3. 書き出しロジック (自己圧縮.tar 成功版の完コピ) ---
st.header("4. インポート用データの書き出し 💾")

if st.button("CSV & JSON を生成", type="primary", use_container_width=True, key="btn_download_final"):
    # ヘッダー構築
    ROW1_CSV = [None] * NUM_COLS
    ROW1_CSV[0], ROW1_CSV[4], ROW1_CSV[9], ROW1_CSV[17] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報'
    
    ROW3_CSV = [None] * NUM_COLS
    ROW3_CSV[0:3] = ['[zone]', '[id]', '[fade]']
    ROW3_CSV[4:8] = ['[group]', '[id]', '[type]', '[zone]']
    ROW3_CSV[9:16] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]']

    mat = pd.DataFrame(index=range(200), columns=range(NUM_COLS))
    # ゾーン
    for i, r in enumerate(st.session_state.z_list): mat.iloc[i, 0:3] = [r["名"], Z_ID+i, r["秒"]]
    # グループ
    for i, r in enumerate(st.session_state.g_list): mat.iloc[i, 4:8] = [r["名"], G_ID+i, GROUP_TYPE_MAP.get(r["型"]), r["ゾ"]]
    # シーン
    s_db, s_cnt = {}, S_ID
    for i, r in enumerate(st.session_state.s_list):
        key = (r["sn"], r["zn"])
        if key not in s_db: s_db[key] = s_cnt; s_cnt += 1
        mat.iloc[i, 9:16] = [r["sn"], s_db[key], r["dim"], r["kel"], r["syn"], r["zn"], r["gn"]]

    # CSV出力 (BOMなしUTF-8)
    buf_csv = io.BytesIO()
    final_output = pd.concat([pd.DataFrame([ROW1_CSV, [None]*NUM_COLS, ROW3_CSV]), mat.dropna(how='all')], ignore_index=True)
    final_output.to_csv(buf_csv, index=False, header=False, encoding="utf-8", lineterminator='\r\n')
    
    # JSON作成
    json_data = {"pair": [], "csv": "setting_data"}
    buf_json = io.BytesIO(json.dumps(json_data, indent=2).encode('utf-8'))

    st.success("BOMなし・4097形式で生成しました。")
    st.download_button("1. setting_data.csv を保存", buf_csv.getvalue(), "setting_data.csv", key="download_csv_final")
    st.download_button("2. temp.json を保存", buf_json.getvalue(), "temp.json", key="download_json_final")
