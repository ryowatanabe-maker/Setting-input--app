import streamlit as st
import pandas as pd
import io
import json

# --- 1. 定数定義（BBR4HG / 大利根店形式に完全準拠） ---
NUM_COLS = 72
Z_ID, G_ID, S_ID, T_ID = 4097, 32769, 8193, 12289
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

st.set_page_config(page_title="FitPlus設定作成 完全版", layout="wide")
st.title("FitPlus 設定作成 (BBR4HG / 自己圧縮対応) ⚙️")

# セッション初期化（履歴を保持する箱）
for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
    if key not in st.session_state:
        st.session_state[key] = []

# --- 2. 登録セクション（UI） ---
st.header("1. ゾーン・グループ登録")
c1, c2 = st.columns(2)
with c1:
    with st.form("z_form"):
        zn = st.text_input("ゾーン名 (例: 店内)")
        zf = st.number_input("フェード秒", 0, 60, 0)
        if st.form_submit_button("ゾーン追加"):
            if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    # 履歴表示と削除
    for i, z in enumerate(st.session_state.z_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"📍 {z['名']}")
        if cr.button("削除", key=f"dz_{i}"): st.session_state.z_list.pop(i); st.rerun()

with c2:
    vz = [""] + [z["名"] for z in st.session_state.z_list]
    with st.form("g_form"):
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(GROUP_TYPE_MAP.keys()))
        gz = st.selectbox("所属ゾーン", options=vz)
        if st.form_submit_button("グループ追加"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
    # 履歴表示と削除
    for i, g in enumerate(st.session_state.g_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"💡 {g['名']} ({g['型']})")
        if cr.button("削除", key=f"dg_{i}"): st.session_state.g_list.pop(i); st.rerun()

st.divider()

st.header("2. シーン登録")
with st.container(border=True):
    csn, csz = st.columns(2)
    s_name = csn.text_input("シーン名 (例: 日中)")
    s_zone = csz.selectbox("設定対象ゾーン", options=vz, key="sz_sel")
    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        scene_data = []
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
            scene_data.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "syn": syn})
        if st.button("このシーンを保存 ✅", use_container_width=True):
            st.session_state.s_list.extend(scene_data); st.rerun()

st.divider()

# --- 3. 出力ロジック (BOMなし・72列固定) ---
st.header("3. 出力 💾")
if st.button("setting_data.csv と temp.json を生成", type="primary", use_container_width=True):
    mat = pd.DataFrame(index=range(200), columns=range(NUM_COLS))
    
    # ゾーン (0-2)
    for i, z in enumerate(st.session_state.z_list):
        mat.iloc[i, 0:3] = [z["名"], Z_ID + i, z["秒"]]
    
    # グループ (4-7) 【最重要: 7列目にゾーン名を入れる】
    for i, g in enumerate(st.session_state.g_list):
        mat.iloc[i, 4:8] = [g["名"], G_ID + i, GROUP_TYPE_MAP.get(g["型"]), g["ゾ"]]
    
    # シーン (9-15) 【最重要: 14列目にゾーン名、15列目にグループ名を入れる】
    s_db, s_cnt = {}, S_ID
    for i, r in enumerate(st.session_state.s_list):
        key = (r["sn"], r["zn"])
        if key not in s_db: s_db[key] = s_cnt; s_cnt += 1
        mat.iloc[i, 9:16] = [r["sn"], s_db[key], r["dim"], r["kel"], "", r["zn"], r["gn"]]

    # ヘッダー (大利根店形式)
    ROW1 = [None] * NUM_COLS
    ROW1[0], ROW1[4], ROW1[9], ROW1[17] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報'
    ROW3 = [None] * NUM_COLS
    ROW3[0:3], ROW3[4:8] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]']
    ROW3[9:16] = ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]']
    
    final_df = pd.concat([pd.DataFrame([ROW1, [None]*NUM_COLS, ROW3]), mat.dropna(how='all')], ignore_index=True)

    # --- CSV出力 (BOMなし・UTF-8) ---
    buf_csv = io.BytesIO()
    # encoding="utf-8" にして BOM(sig) を抜く
    final_df.to_csv(buf_csv, index=False, header=False, encoding="utf-8", lineterminator='\r\n')
    
    # --- JSON作成 ---
    json_str = json.dumps({"pair": [], "csv": "setting_data"}, indent=2)
    buf_json = io.BytesIO(json_str.encode('utf-8'))

    st.success("BOMなし/72列形式で作成しました。")
    st.download_button("1. setting_data.csv を保存", buf_csv.getvalue(), "setting_data.csv")
    st.download_button("2. temp.json を保存", buf_json.getvalue(), "temp.json")
