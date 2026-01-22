import streamlit as st
import pandas as pd
import io
import json

# --- 1. 定数定義 (大利根店・自己圧縮成功ファイルに完全準拠) ---
NUM_COLS = 72
Z_ID, G_ID, S_ID, T_ID = 4097, 32769, 8193, 12289
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

st.set_page_config(page_title="FitPlus 設定作成 v61", layout="wide")
st.title("FitPlus 設定データ作成 (自己圧縮・BOMなし対応) ⚙️")

# セッション状態の初期化
for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
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
            st.rerun()

if st.session_state.z_list:
    for i, z in enumerate(st.session_state.z_list):
        cl, cr = st.columns([5, 1])
        cl.write(f"📍 {z['名']} (ID: {Z_ID + i})")
        if cr.button("削除", key=f"dz_{i}"):
            st.session_state.z_list.pop(i)
            st.rerun()

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
            st.rerun()

if st.session_state.g_list:
    for i, g in enumerate(st.session_state.g_list):
        cl, cr = st.columns([5, 1])
        cl.write(f"💡 {g['名']} ({g['型']}) -> {g['ゾ']}")
        if cr.button("削除", key=f"dg_{i}"):
            st.session_state.g_list.pop(i)
            st.rerun()

# シーン登録
st.header("3. シーン設定")
with st.container(border=True):
    csn, csz = st.columns(2)
    s_name = csn.text_input("シーン名 (例: 日中)", key="s_name_in")
    s_zone = csz.selectbox("設定対象ゾーン", options=v_zones, key="s_zone_in")
    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        scene_data = []
        for g in target_gs:
            st.write(f"--- {g['名']} ---")
            c1, c2, c3 = st.columns([1, 1, 2])
            dim = c1.number_input("調光%", 0, 100, 100, key=f"d_{g['名']}_{s_name}")
            kel = c2.text_input("ケルビン", "3500", key=f"k_{g['名']}_{s_name}") if g['型'] != "調光" else ""
            syn = ""
            if "Synca" in g['型']:
                with c3:
                    cs1, cs2 = st.columns(2)
                    rv = cs1.selectbox("行", ["-"] + list(range(1, 12)), key=f"r_{g['名']}_{s_name}")
                    cv = cs2.selectbox("列", ["-"] + list(range(1, 12)), key=f"c_{g['名']}_{s_name}")
                    if rv != "-" and cv != "-": syn = f"{rv}-{cv}"
            scene_data.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "syn": syn})
        
        if st.button("このシーンを保存 ✅", use_container_width=True, key="save_s"):
            if s_name:
                st.session_state.s_list.extend(scene_data)
                st.rerun()

if st.session_state.s_list:
    s_df = pd.DataFrame(st.session_state.s_list)
    summ = s_df.groupby(["sn", "zn"]).size().reset_index()
    for i, row in summ.iterrows():
        cl, cr = st.columns([5, 1])
        cl.write(f"🎬 {row['sn']} (ゾーン: {row['zn']})")
        if cr.button("削除", key=f"ds_{i}"):
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == row["sn"] and s["zn"] == row["zn"])]
            st.rerun()

st.divider()

# --- 3. 書き出しロジック (BOMなし・72列・ID 4097) ---
st.header("4. インポート用ファイルの生成 💾")

if st.button("setting_data.csv & temp.json を出力", type="primary", use_container_width=True, key="export_all"):
    # 72列の白紙シート
    mat = pd.DataFrame(index=range(200), columns=range(NUM_COLS))
    
    # 1. ゾーン (0-2列目)
    for i, z in enumerate(st.session_state.z_list):
        mat.iloc[i, 0:3] = [z["名"], Z_ID + i, z["秒"]]
    
    # 2. グループ (4-7列目) 【7列目のゾーン名を固定】
    for i, g in enumerate(st.session_state.g_list):
        mat.iloc[i, 4:8] = [g["名"], G_ID + i, GROUP_TYPE_MAP.get(g["型"]), g["ゾ"]]
    
    # 3. シーン (9-15列目) 【14列目のゾーン名、15列目のグループ名を固定】
    s_db, s_cnt = {}, S_ID
    for i, r in enumerate(st.session_state.s_list):
        key = (r["sn"], r["zn"])
        if key not in s_db:
            s_db[key] = s_cnt
            s_cnt += 1
        mat.iloc[i, 9:16] = [r["sn"], s_db[key], r["dim"], r["kel"], r["syn"], r["zn"], r["gn"]]

    # ヘッダー構築 (大利根店形式)
    ROW1 = [None] * NUM_COLS
    ROW1[0], ROW1[4], ROW1[9], ROW1[17] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報'
    ROW3 = [None] * NUM_COLS
    ROW3[0:3], ROW3[4:8] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]']
    ROW3[9:16] = ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]']
    
    final_df = pd.concat([pd.DataFrame([ROW1, [None]*NUM_COLS, ROW3]), mat.dropna(how='all')], ignore_index=True)

    # --- CSV出力 (BOMなし UTF-8) ---
    buf_csv = io.BytesIO()
    # encoding="utf-8" (sigなし) にすることで、インポート時のゾーン名化けを防ぐ
    final_df.to_csv(buf_csv, index=False, header=False, encoding="utf-8", lineterminator='\r\n')
    
    # --- JSON作成 ---
    json_str = json.dumps({"pair": [], "csv": "setting_data"}, indent=2)
    buf_json = io.BytesIO(json_str.encode('utf-8'))

    st.success("BOMなし・4097形式で生成しました。")
    st.download_button("1. setting_data.csv を保存", buf_csv.getvalue(), "setting_data.csv", key="dl_csv")
    st.download_button("2. temp.json を保存", buf_json.getvalue(), "temp.json", key="dl_json")

st.info("💡 使い方: 保存した2つのファイルを直接選び、tar形式で圧縮してゲートウェイへ。")
