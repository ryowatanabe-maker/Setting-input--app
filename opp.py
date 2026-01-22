import streamlit as st
import pandas as pd
import io
import json

# --- 0. アプリ設定と互換性関数 ---
st.set_page_config(page_title="FitPlus設定作成 v63", layout="wide")

def safe_rerun():
    try:
        st.rerun()
    except:
        st.experimental_rerun()

# --- 1. 定数定義 (BBR4HG/大利根店形式 準拠) ---
NUM_COLS = 72
Z_ID_BASE, G_ID_BASE, S_ID_BASE, TT_ID_BASE = 4097, 32769, 8193, 12289
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

st.title("FitPlus 設定作成 (BBR4HG対応版) ⚙️")

# セッション管理（これがないとデータが消えます）
for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
    if key not in st.session_state:
        st.session_state[key] = []

# --- 2. 登録セクション ---

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
                safe_rerun()
    # 履歴
    for i, z in enumerate(st.session_state.z_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"📍 {z['名']}")
        if cr.button("削除", key=f"dz_{z['名']}_{i}"):
            st.session_state.z_list.pop(i)
            safe_rerun()

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
                safe_rerun()
    # 履歴
    for i, g in enumerate(st.session_state.g_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"💡 {g['名']} ({g['ゾ']})")
        if cr.button("削除", key=f"dg_{g['名']}_{i}"):
            st.session_state.g_list.pop(i)
            safe_rerun()

st.divider()

st.header("2. シーン登録")
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
        
        if st.button("シーン保存 ✅", use_container_width=True, key="save_scene_btn"):
            if s_name:
                # 重複削除
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
                st.session_state.s_list.extend(scene_tmp)
                safe_rerun()

st.divider()

# --- 3. 出力ロジック (自己圧縮.tar 成功版) ---
st.header("3. 出力 💾")
if st.button("setting_data.csv & temp.json を生成", type="primary", use_container_width=True, key="export_btn"):
    mat = pd.DataFrame(index=range(200), columns=range(NUM_COLS))
    
    # ゾーン
    for i, z in enumerate(st.session_state.z_list):
        mat.iloc[i, 0:3] = [z["名"], Z_ID_BASE + i, z["秒"]]
    
    # グループ
    for i, g in enumerate(st.session_state.g_list):
        mat.iloc[i, 4:8] = [g["名"], G_ID_BASE + i, GROUP_TYPE_MAP.get(g["型"]), g["ゾ"]]
    
    # シーン
    s_db, s_cnt = {}, S_ID_BASE
    for i, r in enumerate(st.session_state.s_list):
        key = (r["sn"], r["zn"])
        if key not in s_db: s_db[key] = s_cnt; s_cnt += 1
        mat.iloc[i, 9:16] = [r["sn"], s_db[key], r["dim"], r["kel"], r["syn"], r["zn"], r["gn"]]

    # ヘッダー
    R1 = [None] * NUM_COLS
    R1[0], R1[4], R1[9], R1[17] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報'
    R3 = [None] * NUM_COLS
    R3[0:3], R3[4:8] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]']
    R3[9:16] = ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]']
    
    final_df = pd.concat([pd.DataFrame([R1, [None]*NUM_COLS, R3]), mat.dropna(how='all')], ignore_index=True)

    # --- CSV出力 (BOMなし UTF-8 / 大利根店形式) ---
    buf_csv = io.BytesIO()
    final_df.to_csv(buf_csv, index=False, header=False, encoding="utf-8", lineterminator='\r\n')
    
    # --- JSON作成 ---
    json_str = json.dumps({"pair": [], "csv": "setting_data"}, indent=2)
    buf_json = io.BytesIO(json_str.encode('utf-8'))

    st.success("成功！以下の2つを保存してtarにしてください")
    st.download_button("1. setting_data.csv", buf_csv.getvalue(), "setting_data.csv", key="dl_csv")
    st.download_button("2. temp.json", buf_json.getvalue(), "temp.json", key="dl_json")
