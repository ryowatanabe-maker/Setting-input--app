import streamlit as st
import pandas as pd
import io
import json
import tarfile

# --- 1. 定数 (マニュアル ver1.2 準拠) ---
NUM_COLS = 236
Z_ID_BASE = 4097
G_ID_BASE = 32769
S_ID_BASE = 8193

# マニュアル記載のグループタイプ 
TYPE_MAP = {
    "調光": "1ch", 
    "調光調色": "2ch", 
    "Synca": "3ch"
}

st.set_page_config(page_title="FitPlus マニュアル準拠版 v74", layout="wide")
st.title("FitPlus ⚙️ 名称32文字制限・ID紐付け版")

# セッション状態の維持
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []

# --- 2. 登録セクション (マニュアルの文字数制限を適用) ---
c1, c2 = st.columns(2)
with c1:
    with st.form("z_f", clear_on_submit=True):
        st.subheader("1. ゾーン登録")
        # マニュアル：ゾーン名称(1～32文字) [cite: 241]
        zn = st.text_input("ゾーン名 (最大32文字)", max_chars=32)
        # マニュアル：フェード 0分0秒～60分0秒 [cite: 242]
        zf_m = st.number_input("フェード時間(分)", 0, 60, 0)
        zf_s = st.number_input("フェード時間(秒)", 0, 59, 0)
        if st.form_submit_button("追加"):
            if zn and len(st.session_state.z_list) < 35: # 最大35個 [cite: 245]
                st.session_state.z_list.append({"名": zn, "秒": zf_m * 60 + zf_s})
                st.rerun()
            elif len(st.session_state.z_list) >= 35:
                st.error("ゾーンは最大35個までです。")

with c2:
    vz = [z["名"] for z in st.session_state.z_list]
    with st.form("g_f", clear_on_submit=True):
        st.subheader("2. グループ登録")
        # マニュアル：グループ名称(1～32文字) [cite: 250]
        gn = st.text_input("グループ名 (最大32文字)", max_chars=32)
        gt = st.selectbox("タイプ", list(TYPE_MAP.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.form_submit_button("追加"):
            if gn and gz and len(st.session_state.g_list) < 140: # 最大140個 [cite: 259]
                st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz})
                st.rerun()
            elif len(st.session_state.g_list) >= 140:
                st.error("グループは最大140個までです。")

st.header("3. シーン設定")
# マニュアル：シーン行数合計 720行以内 [cite: 31, 381]
total_rows = len(st.session_state.s_list)
st.caption(f"現在のシーン登録行数: {total_rows} / 720行")

with st.container(border=True):
    col_sn, col_sz = st.columns(2)
    # マニュアル：シーン名称(1～32文字) [cite: 264]
    s_name = col_sn.text_input("シーン名 (最大32文字)", max_chars=32)
    s_zone_name = col_sz.selectbox("設定ゾーン", options=[""] + vz, key="sz_s")
    
    if s_zone_name:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone_name]
        scene_tmp = []
        for g in target_gs:
            st.write(f"■ {g['名']}")
            cc1, cc2 = st.columns(2)
            # 調光率 0～100% (空白は100%として処理) [cite: 372]
            dim = cc1.number_input("調光%", 0, 100, 100, key=f"d_{g['名']}_{s_name}")
            # 色温度 (空白は4000Kとして処理) [cite: 373]
            kel = cc2.text_input("色温度(K)", "4000", key=f"k_{g['名']}_{s_name}") if g['型'] != "調光" else ""
            scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone_name, "dim": dim, "kel": kel})
        
        if st.button("このシーン設定を保存"):
            if s_name:
                # 既存の同一シーンを削除して上書き
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone_name)]
                st.session_state.s_list.extend(scene_tmp)
                st.rerun()

# --- 3. CSV出力ロジック (マニュアル完全準拠) ---
st.divider()
if st.button("📥 インポート専用 .tar を出力", type="primary", use_container_width=True):
    # マニュアルの236列構成を再現 
    df = pd.DataFrame("", index=range(730), columns=range(NUM_COLS))
    
    z_map = {z["名"]: Z_ID_BASE + i for i, z in enumerate(st.session_state.z_list)}
    g_map = {g["名"]: G_ID_BASE + i for i, g in enumerate(st.session_state.g_list)}

    # Zone (0:名, 1:ID, 2:フェード秒) [cite: 14, 596]
    for i, z in enumerate(st.session_state.z_list):
        df.iloc[i, 0:3] = [z["名"], z_map[z["名"]], z["秒"]]
    
    # Group (4:名, 5:ID, 6:タイプ[1ch等], 7:ゾーンID) [cite: 14, 596]
    for i, g in enumerate(st.session_state.g_list):
        df.iloc[i, 4:8] = [g["名"], g_map[g["名"]], TYPE_MAP.get(g["型"]), z_map.get(g["ゾ"])]
    
    # Scene (9:名, 10:ID, 11:調光, 12:色温度, 13:演出, 14:ゾーンID, 15:グループID) [cite: 14, 596]
    s_unique_m, s_idx = {}, S_ID_BASE
    for i, r in enumerate(st.session_state.s_list):
        k = (r["sn"], r["zn"])
        if k not in s_unique_m:
            s_unique_m[k] = s_idx
            s_idx += 1
        # ID(数字)を使用して紐付けを行う
        df.iloc[i, 9:16] = [r["sn"], s_unique_m[k], r["dim"], r["kel"], "static", z_map.get(r["zn"]), g_map.get(r["gn"])]

    # ヘッダー (マニュアルのタイトル行とブラケット行) [cite: 14, 596]
    h0 = [""] * NUM_COLS
    h0[0], h0[4], h0[9] = 'Zone情報','Group情報','Scene情報'
    h2 = [""] * NUM_COLS
    h2[0:3] = ['[zone]','[id]','[fade]']
    h2[4:8] = ['[group]','[id]','[type]','[zone]']
    h2[9:16] = ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]']

    final_csv = pd.concat([pd.DataFrame([h0, [""]*NUM_COLS, h2]), df], ignore_index=True)

    # バイナリ化 (BOMありUTF-8) [cite: 621]
    csv_buf = io.BytesIO()
    final_csv.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        c_bytes = csv_buf.getvalue()
        c_info = tarfile.TarInfo(name="setting_data.csv"); c_info.size = len(c_bytes)
        tar.addfile(c_info, io.BytesIO(c_bytes))
        j_bytes = json.dumps({"pair": [], "csv": "setting_data.csv"}, indent=2).encode('utf-8')
        j_info = tarfile.TarInfo(name="temp.json"); j_info.size = len(j_bytes)
        tar.addfile(j_info, io.BytesIO(j_bytes))

    st.success("マニュアル準拠の32文字制限・ID紐付け版で作成しました。")
    st.download_button("📥 ゲートウェイ用tarを保存", tar_buf.getvalue(), "FitPlus_Manual_v74.tar")
