import streamlit as st
import pandas as pd
import io
import json

# --- 0. バージョン互換用の再起動関数 ---
def safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

# --- 1. アプリ設定と定数 (BBR4HG/大利根店 成功形式) ---
st.set_page_config(page_title="FitPlus設定作成 最終版", layout="wide")

NUM_COLS = 72
Z_ID_BASE, G_ID_BASE, S_ID_BASE = 4097, 32769, 8193
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

st.title("FitPlus 設定作成 (BBR4HG/自己圧縮対応) ⚙️")

# セッション管理（履歴の保存場所）
for key in ['z_list', 'g_list', 's_list']:
    if key not in st.session_state:
        st.session_state[key] = []

# --- 2. UIセクション ---

st.header("1. ゾーン・グループ登録")
col_z, col_g = st.columns(2)

with col_z:
    with st.form("form_zone", clear_on_submit=True):
        st.subheader("ゾーン追加")
        zn = st.text_input("ゾーン名 (例: 店内)")
        zf = st.number_input("フェード秒", 0, 60, 0)
        if st.form_submit_button("追加"):
            if zn:
                st.session_state.z_list.append({"名": zn, "秒": zf})
                safe_rerun()
    # 登録済みゾーンの表示と削除
    for i, z in enumerate(st.session_state.z_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"📍 {z['名']} (ID:{Z_ID_BASE+i})")
        if cr.button("削除", key=f"btn_dz_{i}"):
            st.session_state.z_list.pop(i)
            safe_rerun()

with col_g:
    vz = [""] + [z["名"] for z in st.session_state.z_list]
    with st.form("form_group", clear_on_submit=True):
        st.subheader("グループ追加")
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(GROUP_TYPE_MAP.keys()))
        gz = st.selectbox("所属ゾーン", options=vz)
        if st.form_submit_button("追加"):
            if gn and gz:
                st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz})
                safe_rerun()
    # 登録済みグループの表示と削除
    for i, g in enumerate(st.session_state.g_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"💡 {g['名']} ({g['ゾ']})")
        if cr.button("削除", key=f"btn_dg_{i}"):
            st.session_state.g_list.pop(i)
            safe_rerun()

st.divider()

st.header("2. シーン登録")
with st.container(border=True):
    col_sn, col_sz = st.columns(2)
    s_name = col_sn.text_input("シーン名 (例: 日中)", key="scene_name_input")
    s_zone = col_sz.selectbox("設定対象ゾーン", options=vz, key="scene_zone_select")
    
    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        if not target_gs:
            st.warning("このゾーンにはグループが登録されていません")
        else:
            scene_data_tmp = []
            for g in target_gs:
                st.write(f"■ {g['名']}")
                c1, c2, c3 = st.columns([1, 1, 2])
                dim = c1.number_input("調光%", 0, 100, 100, key=f"dim_{g['名']}_{s_name}")
                kel = c2.text_input("ケルビン", "3500", key=f"kel_{g['名']}_{s_name}") if g['型'] != "調光" else ""
                syn = ""
                if "Synca" in g['型']:
                    with c3:
                        cs1, cs2 = st.columns(2)
                        rv = cs1.selectbox("行", ["-"] + list(range(1, 12)), key=f"row_{g['名']}_{s_name}")
                        cv = cs2.selectbox("列", ["-"] + list(range(1, 12)), key=f"col_{g['名']}_{s_name}")
                        if rv != "-" and cv != "-": syn = f"{rv}-{cv}"
                scene_data_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "syn": syn})
            
            if st.button("このシーン設定を保存 ✅", use_container_width=True, key="btn_save_scene"):
                if s_name:
                    # 重複を削除して保存
                    st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
                    st.session_state.s_list.extend(scene_data_tmp)
                    safe_rerun()

# シーン履歴
if st.session_state.s_list:
    st.write("▼ 登録済みシーン一覧")
    s_df = pd.DataFrame(st.session_state.s_list)
    summ = s_df.groupby(["sn", "zn"]).size().reset_index()
    for i, row in summ.iterrows():
        cl, cr = st.columns([5, 1])
        cl.write(f"🎬 {row['sn']} (ゾーン: {row['zn']})")
        if cr.button("削除", key=f"btn_ds_{i}"):
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == row["sn"] and s["zn"] == row["zn"])]
            safe_rerun()

st.divider()

# --- 3. 出力ロジック (自己圧縮.tar 成功版の完コピ) ---
st.header("3. 出力 (BBR4HG/自己圧縮対応) 💾")

if st.button("setting_data.csv と temp.json を一括生成", type="primary", use_container_width=True, key="btn_export"):
    # 白紙の72列シート
    mat = pd.DataFrame(index=range(200), columns=range(NUM_COLS))
    
    # 1. ゾーン (0-2列目) ID:4097〜
    for i, z in enumerate(st.session_state.z_list):
        mat.iloc[i, 0:3] = [z["名"], Z_ID_BASE + i, z["秒"]]
    
    # 2. グループ (4-7列目) ID:32769〜 【7列目[zone]を埋める】
    for i, g in enumerate(st.session_state.g_list):
        mat.iloc[i, 4:8] = [g["名"], G_ID_BASE + i, GROUP_TYPE_MAP.get(g["型"], "1ch"), g["ゾ"]]
    
    # 3. シーン (9-15列目) ID:8193〜 【14列目[zone]を埋める】
    s_db, s_cnt = {}, S_ID_BASE
    for i, r in enumerate(st.session_state.s_list):
        key = (r["sn"], r["zn"])
        if key not in s_db:
            s_db[key] = s_cnt
            s_cnt += 1
        mat.iloc[i, 9:16] = [r["sn"], s_db[key], r["dim"], r["kel"], r["syn"], r["zn"], r["gn"]]

    # ヘッダー構築
    R1 = [None] * NUM_COLS
    R1[0], R1[4], R1[9], R1[17] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報'
    R3 = [None] * NUM_COLS
    R3[0:3], R3[4:8] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]']
    R3[9:16] = ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]']
    
    final_df = pd.concat([pd.DataFrame([R1, [None]*NUM_COLS, R3]), mat.dropna(how='all')], ignore_index=True)

    # --- CSV出力 (BOMなし UTF-8) ---
    buf_csv = io.BytesIO()
    # encoding="utf-8" (sigなし) で出力し、BBR4HGでのゾーン名化けを防止
    final_df.to_csv(buf_csv, index=False, header=False, encoding="utf-8", lineterminator='\r\n')
    
    # --- JSON作成 ---
    json_data = {"pair": [], "csv": "setting_data"}
    buf_json = io.BytesIO(json.dumps(json_data, indent=2).encode('utf-8'))

    st.success("「自己圧縮.tar」と全く同じ形式で生成しました！")
    st.download_button("1. setting_data.csv を保存", buf_csv.getvalue(), "setting_data.csv", key="dl_csv")
    st.download_button("2. temp.json を保存", buf_json.getvalue(), "temp.json", key="dl_json")

st.info("💡 ダウンロードした2つのファイルだけを選んでtarに固めてアップロードしてください。")
