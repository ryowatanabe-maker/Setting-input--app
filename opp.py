import streamlit as st
import pandas as pd
import io
import json
import tarfile

# --- 1. 定数 (メインゲートウェイ・72列・ID 1〜 形式) ---
NUM_COLS = 72
TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

st.set_page_config(page_title="FitPlus メインGW用反映版", layout="wide")
st.title("FitPlus 設定作成 (メインGW用・中身反映重視) ⚙️")

# セッション管理
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []

# --- 2. 登録セクション ---
c1, c2 = st.columns(2)
with c1:
    with st.form("z_form", clear_on_submit=True):
        st.subheader("1. ゾーン登録")
        zn = st.text_input("ゾーン名")
        zf = st.number_input("フェード", 0, 60, 10)
        if st.form_submit_button("追加"):
            if zn:
                # IDを 1 から連番で振る
                st.session_state.z_list.append({"名": zn, "秒": zf, "id": len(st.session_state.z_list) + 1})
                st.rerun()
    for i, z in enumerate(st.session_state.z_list):
        cl, cr = st.columns([4, 1]); cl.write(f"📍 {z['名']} (ID: {z['id']})")
        if cr.button("削除", key=f"dz_{i}"): st.session_state.z_list.pop(i); st.rerun()

with c2:
    vz = [""] + [z["名"] for z in st.session_state.z_list]
    with st.form("g_form", clear_on_submit=True):
        st.subheader("2. グループ登録")
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(TYPE_MAP.keys()))
        gz = st.selectbox("所属ゾーン", options=vz)
        if st.form_submit_button("追加"):
            if gn and gz:
                # IDを 1 から連番で振る
                st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz, "id": len(st.session_state.g_list) + 1})
                st.rerun()
    for i, g in enumerate(st.session_state.g_list):
        cl, cr = st.columns([4, 1]); cl.write(f"💡 {g['名']} ({g['ゾ']})")
        if cr.button("削除", key=f"dg_{i}"): st.session_state.g_list.pop(i); st.rerun()

st.header("3. シーン設定")
with st.container(border=True):
    sn = st.text_input("シーン名")
    sz = st.selectbox("対象ゾーン", options=vz, key="sz_s")
    if sz:
        t_gs = [g for g in st.session_state.g_list if g["ゾ"] == sz]
        s_tmp = []
        for g in t_gs:
            st.write(f"■ {g['名']}")
            cc1, cc2 = st.columns(2)
            d = cc1.number_input("調光", 0, 100, 100, key=f"d_{g['名']}_{sn}")
            k = cc2.text_input("色温度", "3500", key=f"k_{g['名']}_{sn}") if g['型'] != "調光" else ""
            s_tmp.append({"sn": sn, "gn": g['名'], "zn": sz, "dim": d, "kel": k})
        if st.button("保存", use_container_width=True):
            if sn:
                # シーンIDも連番管理
                st.session_state.s_list.extend(s_tmp); st.rerun()

# --- 3. メインGW用出力ロジック (72列・ID 1〜) ---
st.divider()
if st.button("📥 メインGW用 .tar をダウンロード", type="primary", use_container_width=True):
    # 72列の白紙
    mat = pd.DataFrame("", index=range(200), columns=range(NUM_COLS))
    
    # データ配置
    for i, z in enumerate(st.session_state.z_list):
        mat.iloc[i, 0:3] = [z["名"], z["id"], z["秒"]]
    for i, g in enumerate(st.session_state.g_list):
        mat.iloc[i, 4:8] = [g["名"], g["id"], TYPE_MAP.get(g["型"]), g["ゾ"]]
    
    # シーンIDの連番生成
    s_map, s_idx = {}, 1
    for i, r in enumerate(st.session_state.s_list):
        key = (r["sn"], r["zn"])
        if key not in s_map: s_map[key] = s_idx; s_idx += 1
        mat.iloc[i, 9:16] = [r["sn"], s_map[key], r["dim"], r["kel"], "", r["zn"], r["gn"]]

    # ヘッダー (72列用)
    h1 = [""] * NUM_COLS
    h1[0], h1[4], h1[9], h1[17] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報'
    h3 = [""] * NUM_COLS
    h3[0:3], h3[4:8] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]']
    h3[9:16] = ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]']
    
    # 結合 (2行目は空行)
    final_csv = pd.concat([pd.DataFrame([h1, [""]*NUM_COLS, h3]), mat], ignore_index=True).iloc[:, :72]

    # バイナリ化 (BOMあり UTF-8)
    csv_buf = io.BytesIO()
    final_csv.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    
    # TAR作成 (ustar)
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        c_bytes = csv_buf.getvalue()
        c_info = tarfile.TarInfo(name="setting_data.csv"); c_info.size = len(c_bytes)
        tar.addfile(c_info, io.BytesIO(c_bytes))
        j_bytes = json.dumps({"pair": [], "csv": "setting_data.csv"}, indent=2).encode('utf-8')
        j_info = tarfile.TarInfo(name="temp.json"); j_info.size = len(j_bytes)
        tar.addfile(j_info, io.BytesIO(j_bytes))

    st.success("メインGW用(72列・ID 1〜)で作成しました。解凍せずアップロードしてください。")
    st.download_button("📥 Main_GW_Import.tar", tar_buf.getvalue(), "Main_GW_Import.tar")
