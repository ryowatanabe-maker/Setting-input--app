import streamlit as st
import pandas as pd
import io
import json
import tarfile

# --- 1. 定数 (マニュアル・見本CSVを完全トレース) ---
NUM_COLS = 236
Z_ID_BASE, G_ID_BASE, S_ID_BASE = 4097, 32769, 8193
TYPE_MAP = {"調光": "dim", "調光調色": "color", "Synca": "color"}

st.set_page_config(page_title="FitPlus マニュアル準拠版", layout="wide")
st.title("FitPlus ⚙️ 事前設定マニュアル(ver1.2)完全再現")

# セッション状態
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []

# --- 2. 登録セクション ---
c1, c2 = st.columns(2)
with c1:
    with st.form("z_f", clear_on_submit=True):
        st.subheader("1. ゾーン登録")
        zn = st.text_input("ゾーン名 (1-32文字)")
        zf_m = st.number_input("フェード時間(分)", 0, 60, 0)
        zf_s = st.number_input("フェード時間(秒)", 0, 59, 0)
        if st.form_submit_button("追加"):
            if zn: st.session_state.z_list.append({"名": zn, "分": zf_m, "秒": zf_s}); st.rerun()

with c2:
    vz = [z["名"] for z in st.session_state.z_list]
    with st.form("g_f", clear_on_submit=True):
        st.subheader("2. グループ登録")
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(TYPE_MAP.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.form_submit_button("追加"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()

st.header("3. シーン設定")
with st.container(border=True):
    col_sn, col_sz = st.columns(2)
    s_name = col_sn.text_input("シーン名")
    s_zone = col_sz.selectbox("設定ゾーン", options=[""] + vz, key="sz_s")
    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        scene_tmp = []
        for g in target_gs:
            st.write(f"■ {g['名']}")
            cc1, cc2 = st.columns(2)
            dim = cc1.number_input("調光率%", 0, 100, 100, key=f"d_{g['名']}_{s_name}")
            kel = cc2.text_input("色温度(K)", "4000", key=f"k_{g['名']}_{s_name}") if g['型'] != "調光" else ""
            scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel})
        if st.button("このシーン設定を保存"):
            if s_name:
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
                st.session_state.s_list.extend(scene_tmp); st.rerun()

# --- 3. マニュアル仕様に基づくCSV生成 ---
st.divider()
# 行数チェック
total_scene_rows = len(st.session_state.s_list)
st.write(f"現在の総シーン行数: {total_scene_rows} / 720行")

if st.button("📥 インポート専用 .tar を出力", type="primary", use_container_width=True):
    if total_scene_rows > 720:
        st.error("シーンの合計行数が720行を超えています。インポートできません。")
    else:
        df = pd.DataFrame("", index=range(725), columns=range(NUM_COLS))
        z_map = {z["名"]: Z_ID_BASE + i for i, z in enumerate(st.session_state.z_list)}
        g_map = {g["名"]: G_ID_BASE + i for i, g in enumerate(st.session_state.g_list)}

        # Zone (0:名, 1:ID, 2:秒換算) 
        # ※マニュアル画像に基づき配置
        for i, z in enumerate(st.session_state.z_list):
            total_sec = z["分"] * 60 + z["秒"]
            df.iloc[i, 0:3] = [z["名"], z_map[z["名"]], total_sec]

        # Group (4:名, 5:ID, 6:型, 7:所属ゾーンID)
        for i, g in enumerate(st.session_state.g_list):
            df.iloc[i, 4:8] = [g["名"], g_map[g["名"]], TYPE_MAP.get(g["型"]), z_map.get(g["ゾ"])]

        # Scene (9:名, 10:ID, 11:調光, 12:色温度, 13:演出, 14:ゾーンID, 15:グループID)
        s_unique_m, s_idx = {}, S_ID_BASE
        for i, r in enumerate(st.session_state.s_list):
            k = (r["sn"], r["zn"])
            if k not in s_unique_m:
                s_unique_m[k] = s_idx
                s_idx += 1
            df.iloc[i, 9:16] = [r["sn"], s_unique_m[k], r["dim"], r["kel"], "static", z_map.get(r["zn"]), g_map.get(r["gn"])]

        # ヘッダー定義
        h0 = [""] * NUM_COLS
        h0[0], h0[4], h0[9] = 'Zone情報','Group情報','Scene情報'
        h2 = [""] * NUM_COLS
        h2[0:3], h2[4:8], h2[9:16] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]'], ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]']

        final_csv = pd.concat([pd.DataFrame([h0, [""]*NUM_COLS, h2]), df], ignore_index=True)

        # 出力
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

        st.success("マニュアル準拠のCSV構成で作成しました。")
        st.download_button("📥 ゲートウェイ用tarを保存", tar_buf.getvalue(), "FitPlus_Manual_v1.2.tar")
