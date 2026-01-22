import streamlit as st
import pandas as pd
import io
import json
import tarfile

# --- 0. アプリ設定と定数 ---
st.set_page_config(page_title="FitPlus 最終解決版 v68", layout="wide")

# BBR4HG / 大利根店 / 自己圧縮成功形式を完全コピー
NUM_COLS = 72
Z_ID_BASE, G_ID_BASE, S_ID_BASE = 4097, 32769, 8193
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

st.title("FitPlus 設定作成 (直接tar出力・BBR4HG対応) ⚙️")

# セッション状態の初期化
for key in ['z_list', 'g_list', 's_list']:
    if key not in st.session_state:
        st.session_state[key] = []

# --- 1. ゾーン・グループ登録セクション ---
st.header("1. ゾーン・グループ登録")
cz, cg = st.columns(2)

with cz:
    with st.form("z_form", clear_on_submit=True):
        st.subheader("ゾーン追加")
        zn = st.text_input("ゾーン名")
        zf = st.number_input("フェード秒", 0, 60, 0)
        if st.form_submit_button("追加"):
            if zn:
                st.session_state.z_list.append({"名": zn, "秒": zf})
                st.rerun()
    # 履歴表示と削除
    for i, z in enumerate(st.session_state.z_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"📍 {z['名']} (ID:{Z_ID_BASE+i})")
        if cr.button("削除", key=f"dz_{i}_{z['名']}"):
            st.session_state.z_list.pop(i)
            st.rerun()

with cg:
    vz = [""] + [z["名"] for z in st.session_state.z_list]
    with st.form("g_form", clear_on_submit=True):
        st.subheader("グループ追加")
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(GROUP_TYPE_MAP.keys()))
        gz = st.selectbox("所属ゾーン", options=vz)
        if st.form_submit_button("追加"):
            if gn and gz:
                st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz})
                st.rerun()
    # 履歴表示と削除
    for i, g in enumerate(st.session_state.g_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"💡 {g['名']} ({g['ゾ']})")
        if cr.button("削除", key=f"dg_{i}_{g['名']}"):
            st.session_state.g_list.pop(i)
            st.rerun()

st.divider()

# --- 2. シーン登録セクション ---
st.header("2. シーン設定")
with st.container(border=True):
    col_sn, col_sz = st.columns(2)
    s_name = col_sn.text_input("シーン名 (例: 日中)")
    s_zone = col_sz.selectbox("対象ゾーン", options=vz, key="sz_select")
    
    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        scene_tmp = []
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
            scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "syn": syn})
        
        if st.button("このシーン設定を保存 ✅", use_container_width=True, key="save_scene_btn"):
            if s_name:
                # 同一のシーン名+ゾーン名があれば上書き
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
                st.session_state.s_list.extend(scene_tmp)
                st.rerun()

# 登録済みシーンのサマリー
if st.session_state.s_list:
    st.write("▼ 現在登録されているシーン")
    s_df = pd.DataFrame(st.session_state.s_list)
    summ = s_df.groupby(["sn", "zn"]).size().reset_index()
    for i, row in summ.iterrows():
        cl, cr = st.columns([5, 1])
        cl.write(f"🎬 {row['sn']} (ゾーン: {row['zn']})")
        if cr.button("削除", key=f"ds_{i}_{row['sn']}"):
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == row["sn"] and s["zn"] == row["zn"])]
            st.rerun()

st.divider()

# --- 3. TAR直接出力ロジック ---
st.header("3. ゲートウェイ用インポートファイルの作成 💾")
st.info("ボタンを押すと、直接アップロード可能な .tar ファイルを生成します。")

if st.button("📥 インポート用 .tar を生成して保存", type="primary", use_container_width=True, key="export_tar_btn"):
    # --- 1. CSVデータの組み立て ---
    mat = pd.DataFrame(index=range(200), columns=range(NUM_COLS)).fillna('')
    for i, z in enumerate(st.session_state.z_list):
        mat.iloc[i, 0:3] = [z["名"], Z_ID_BASE + i, z["秒"]]
    for i, g in enumerate(st.session_state.g_list):
        mat.iloc[i, 4:8] = [g["名"], G_ID_BASE + i, GROUP_TYPE_MAP.get(g["型"]), g["ゾ"]]
    s_db, s_cnt = {}, S_ID_BASE
    for i, r in enumerate(st.session_state.s_list):
        key = (r["sn"], r["zn"])
        if key not in s_db: s_db[key] = s_cnt; s_cnt += 1
        mat.iloc[i, 9:16] = [r["sn"], s_db[key], r["dim"], r["kel"], r["syn"], r["zn"], r["gn"]]

    R1 = [''] * NUM_COLS
    R1[0], R1[4], R1[9], R1[17] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報'
    R3 = [''] * NUM_COLS
    R3[0:3], R3[4:8] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]']
    R3[9:16] = ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]']
    
    # 大利根店・自己圧縮成功版と同じ72列、BOMなし、CRLF改行
    final_df = pd.concat([pd.DataFrame([R1, ['']*NUM_COLS, R3]), mat], ignore_index=True).iloc[:, :72]
    csv_buf = io.BytesIO()
    final_df.to_csv(csv_buf, index=False, header=False, encoding="utf-8", quoting=3, escapechar=' ', lineterminator='\r\n')
    csv_data = csv_buf.getvalue()

    # --- 2. JSONデータの組み立て ---
    json_data = json.dumps({"pair": [], "csv": "setting_data"}, indent=2).encode('utf-8')

    # --- 3. メモリ上で TAR を作成 (USTAR形式・ゴミ混入なし) ---
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        # CSVファイルを追加
        csv_info = tarfile.TarInfo(name="setting_data.csv")
        csv_info.size = len(csv_data)
        tar.addfile(tarinfo=csv_info, fileobj=io.BytesIO(csv_data))
        # JSONファイルを追加
        json_info = tarfile.TarInfo(name="temp.json")
        json_info.size = len(json_data)
        tar.addfile(tarinfo=json_info, fileobj=io.BytesIO(json_data))

    st.success("tarファイルの生成に成功しました！このファイルを『展開せずに』そのままアップロードしてください。")
    st.download_button("📥 ゲートウェイ用tarをダウンロード", tar_buf.getvalue(), "FitPlus_Import.tar", "application/x-tar")
