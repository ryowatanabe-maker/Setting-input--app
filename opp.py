import streamlit as st
import pandas as pd
import io
import json
import tarfile

# --- 1. 定数 (成功データ「インポート可能.tar」をバイナリ解析した結果) ---
NUM_COLS = 72
Z_ID_START = 4097
G_ID_START = 32769
S_ID_START = 8193
TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

st.set_page_config(page_title="FitPlus 最終確定版 v70", layout="wide")
st.title("FitPlus インポート完全成功版 ⚙️")

# セッション状態
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []

# --- 2. 登録セクション ---
c1, c2 = st.columns(2)
with c1:
    with st.form("z"):
        n = st.text_input("ゾーン名")
        f = st.number_input("フェード秒", 0, 60, 10)
        if st.form_submit_button("ゾーン追加"):
            if n: st.session_state.z_list.append({"名": n, "秒": f}); st.rerun()
    for i, x in enumerate(st.session_state.z_list):
        if st.button(f"削除 {x['名']}", key=f"dz{i}"): st.session_state.z_list.pop(i); st.rerun()

with c2:
    vz = [""] + [z["名"] for z in st.session_state.z_list]
    with st.form("g"):
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(TYPE_MAP.keys()))
        gz = st.selectbox("所属ゾーン", options=vz)
        if st.form_submit_button("グループ追加"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
    for i, x in enumerate(st.session_state.g_list):
        if st.button(f"削除 {x['名']}", key=f"dg{i}"): st.session_state.g_list.pop(i); st.rerun()

st.header("シーン設定")
with st.container(border=True):
    sn = st.text_input("シーン名 (例: 日中)")
    sz = st.selectbox("対象ゾーン", options=vz, key="sz_s")
    if sz:
        t_gs = [g for g in st.session_state.g_list if g["ゾ"] == sz]
        s_data = []
        for g in t_gs:
            st.write(f"■ {g['名']}")
            cc1, cc2 = st.columns(2)
            d = cc1.number_input("調光%", 0, 100, 100, key=f"d{g['名']}{sn}")
            k = cc2.text_input("色温度", "3500", key=f"k{g['名']}{sn}") if g['型'] != "調光" else ""
            s_data.append({"sn": sn, "gn": g['名'], "zn": sz, "dim": d, "kel": k})
        if st.button("このシーン設定を保存", use_container_width=True):
            st.session_state.s_list.extend(s_data); st.rerun()

st.divider()

# --- 3. 成功データを「バイナリ完コピ」で出力するロジック ---
st.header("4. 生成・ダウンロード")
if st.button("📥 ゲートウェイ専用 .tar を出力 (直接生成)", type="primary", use_container_width=True):
    # 72列のベース作成
    df = pd.DataFrame("", index=range(100), columns=range(NUM_COLS))
    
    # 1. ゾーン情報
    for i, z in enumerate(st.session_state.z_list):
        df.iloc[i, 0:3] = [z["名"], Z_ID_START + i, z["秒"]]
    
    # 2. グループ情報
    for i, g in enumerate(st.session_state.g_list):
        df.iloc[i, 4:8] = [g["名"], G_ID_START + i, TYPE_MAP.get(g["型"]), g["ゾ"]]
    
    # 3. シーン情報
    s_map = {}
    s_idx = S_ID_START
    for i, s in enumerate(st.session_state.s_list):
        key = (s["sn"], s["zn"])
        if key not in s_map:
            s_map[key] = s_idx
            s_idx += 1
        df.iloc[i, 9:16] = [s["sn"], s_map[key], s["dim"], s["kel"], "", s["zn"], s["gn"]]

    # ヘッダー (「インポート可能.tar」と完全一致)
    h1 = [""] * NUM_COLS
    h1[0], h1[4], h1[9], h1[17] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報'
    h3 = [""] * NUM_COLS
    h3[0:3] = ['[zone]', '[id]', '[fade]']
    h3[4:8] = ['[group]', '[id]', '[type]', '[zone]']
    h3[9:16] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]']
    
    final_csv = pd.concat([pd.DataFrame([h1, [""]*NUM_COLS, h3]), df], ignore_index=True)

    # --- CSVバイナリ作成 (BOMありUTF-8 / CRLF) ---
    csv_buf = io.BytesIO()
    # 成功データがBOMありだったのでutf-8-sigを採用
    final_csv.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    csv_bytes = csv_buf.getvalue()

    # --- JSONバイナリ作成 (CSV名と一致させる) ---
    json_bytes = json.dumps({"pair": [], "csv": "setting_data"}, indent=2).encode('utf-8')

    # --- TAR作成 (ustar形式 / メモリ上で直接生成) ---
    tar_buf = io.BytesIO()
    # format=tarfile.USTAR_FORMAT を明示して古い機器との互換性を最大化
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        # CSVファイル
        c_info = tarfile.TarInfo(name="setting_data.csv")
        c_info.size = len(csv_bytes)
        tar.addfile(c_info, io.BytesIO(csv_bytes))
        # JSONファイル
        j_info = tarfile.TarInfo(name="temp.json")
        j_info.size = len(json_bytes)
        tar.addfile(j_info, io.BytesIO(json_bytes))

    st.success("tarファイルの生成に成功しました！一度も解凍せずに、そのままアップロードしてください。")
    st.download_button("📥 FitPlus_Setup.tar をダウンロード", tar_buf.getvalue(), "FitPlus_Setup.tar")
