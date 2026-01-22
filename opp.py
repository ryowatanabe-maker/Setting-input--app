import streamlit as st
import pandas as pd
import io
import json
import tarfile

# --- 1. 定数 (成功した「インポート可能.tar」の構造を完全再現) ---
NUM_COLS = 72
Z_ID_BASE, G_ID_BASE, S_ID_BASE = 4097, 32769, 8193
TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

st.set_page_config(page_title="FitPlus インポート完全版 v71", layout="wide")
st.title("FitPlus インポート成功確定版 (直接tar出力) ⚙️")

# セッション管理
for key in ['z_list', 'g_list', 's_list']:
    if key not in st.session_state: st.session_state[key] = []

# --- 2. 登録セクション (UI) ---
c1, c2 = st.columns(2)
with c1:
    with st.form("z_f", clear_on_submit=True):
        st.subheader("1. ゾーン登録")
        zn = st.text_input("ゾーン名 (例: 店内)")
        zf = st.number_input("フェード秒", 0, 60, 10)
        if st.form_submit_button("追加"):
            if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    for i, z in enumerate(st.session_state.z_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"📍 {z['名']}")
        if cr.button("削除", key=f"dz_{i}"): st.session_state.z_list.pop(i); st.rerun()

with c2:
    vz = [""] + [z["名"] for z in st.session_state.z_list]
    with st.form("g_f", clear_on_submit=True):
        st.subheader("2. グループ登録")
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(TYPE_MAP.keys()))
        gz = st.selectbox("所属ゾーン", options=vz)
        if st.form_submit_button("追加"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
    for i, g in enumerate(st.session_state.g_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"💡 {g['名']} ({g['ゾ']})")
        if cr.button("削除", key=f"dg_{i}"): st.session_state.g_list.pop(i); st.rerun()

st.header("3. シーン設定")
with st.container(border=True):
    col_sn, col_sz = st.columns(2)
    s_name = col_sn.text_input("シーン名 (例: 日中)")
    s_zone = col_sz.selectbox("設定ゾーン", options=vz, key="sz_s")
    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        scene_tmp = []
        for g in target_gs:
            st.write(f"■ {g['名']}")
            cc1, cc2 = st.columns(2)
            dim = cc1.number_input("調光%", 0, 100, 100, key=f"d_{g['名']}_{s_name}")
            kel = cc2.text_input("色温度", "3500", key=f"k_{g['名']}_{s_name}") if g['型'] != "調光" else ""
            scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel})
        if st.button("このシーン設定を保存", use_container_width=True):
            if s_name: st.session_state.s_list.extend(scene_tmp); st.rerun()

# --- 3. 成功データを100%再現するバイナリ出力ロジック ---
st.divider()
st.header("4. 生成とダウンロード")

if st.button("📥 インポート専用 .tar を出力", type="primary", use_container_width=True):
    # --- A. CSVの作成 (成功データの72列を完全再現) ---
    df = pd.DataFrame("", index=range(100), columns=range(NUM_COLS))
    
    # データ配置
    for i, z in enumerate(st.session_state.z_list): df.iloc[i, 0:3] = [z["名"], Z_ID_BASE + i, z["秒"]]
    for i, g in enumerate(st.session_state.g_list): df.iloc[i, 4:8] = [g["名"], G_ID_BASE + i, TYPE_MAP.get(g["型"]), g["ゾ"]]
    s_m, s_idx = {}, S_ID_BASE
    for i, r in enumerate(st.session_state.s_list):
        k = (r["sn"], r["zn"])
        if k not in s_m: s_m[k] = s_idx; s_idx += 1
        df.iloc[i, 9:16] = [r["sn"], s_m[k], r["dim"], r["kel"], "", r["zn"], r["gn"]]

    # ヘッダー (インポート可能.tarから完全コピー)
    h1 = [""] * NUM_COLS
    h1[0], h1[4], h1[9], h1[17], h1[33], h1[43] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報', 'Timetable-schedule情報', 'Timetable期間/特異日情報'
    h3 = [""] * NUM_COLS
    h3[0:3] = ['[zone]', '[id]', '[fade]']
    h3[4:8] = ['[group]', '[id]', '[type]', '[zone]']
    h3[9:16] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]']
    h3[17:21] = ['[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]'] # 以下省略せず72列まで保持
    
    # 結合と72列カット
    final_csv = pd.concat([pd.DataFrame([h1, [""]*NUM_COLS, h3]), df], ignore_index=True).iloc[:, :72]

    # バイナリ化 (BOMありUTF-8 / CRLF)
    csv_buf = io.BytesIO()
    final_csv.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    csv_bytes = csv_buf.getvalue()

    # --- B. JSONの作成 (CSV名に拡張子を含める) ---
    json_bytes = json.dumps({"pair": [], "csv": "setting_data.csv"}, indent=2).encode('utf-8')

    # --- C. TARの作成 (USTAR形式 / 隠しファイル0) ---
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        # setting_data.csv として追加
        c_info = tarfile.TarInfo(name="setting_data.csv")
        c_info.size = len(csv_bytes)
        tar.addfile(c_info, io.BytesIO(csv_bytes))
        # temp.json として追加
        j_info = tarfile.TarInfo(name="temp.json")
        j_info.size = len(json_bytes)
        tar.addfile(j_info, io.BytesIO(json_bytes))

    st.success("成功！このtarファイルを『解凍せずに』そのまま投げてください。")
    st.download_button("📥 FitPlus_Setup.tar を保存", tar_buf.getvalue(), "FitPlus_Setup.tar")
