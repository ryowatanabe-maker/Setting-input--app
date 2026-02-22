import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta
import os
import numpy as np

# --- 1. 定数・マニュアル準拠設定 ---
NUM_COLS = 236  # マニュアルおよび赤池店形式の236列を採用
Z_ID_BASE = 4097
G_ID_BASE = 32769
S_ID_BASE = 8193

# 前回のコードの型表記を採用
GROUP_TYPES = {
    "調光": "1ch",
    "調光調色": "2ch",
    "Synca": "3ch",
    "Synca Bright": "fresh 3ch"
}

st.set_page_config(page_title="FitPlus Pro v100", layout="wide")

# セッション状態の初期化 (履歴保持用)
for key in ['z_list', 'g_list', 's_list', 't_list']:
    if key not in st.session_state: st.session_state[key] = []

# --- 2. プロジェクト管理 (サイドバー) ---
st.sidebar.title("🏢 プロジェクト管理")
shop_name = st.sidebar.text_input("店舗名", "FitPlus_Project")
if st.sidebar.button("データをリセット"):
    for key in ['z_list', 'g_list', 's_list', 't_list']: st.session_state[key] = []
    st.rerun()

st.title(f"FitPlus ⚙️ {shop_name} 統合ツール")

# --- 3. ゾーン & グループ登録 ---
st.header("1. ゾーン & グループ登録")
c1, c2 = st.columns(2)

with c1:
    st.subheader("📍 ゾーン登録")
    with st.form("z_form", clear_on_submit=True):
        zn = st.text_input("ゾーン名 (最大32文字)", max_chars=32)
        zf = st.number_input("フェード時間(秒)", 0, 3600, 0)
        if st.form_submit_button("ゾーン追加"):
            if zn:
                st.session_state.z_list.append({"名": zn, "秒": zf})
                st.rerun()
    
    for i, z in enumerate(st.session_state.z_list):
        cols = st.columns([4, 1])
        cols[0].info(f"ゾーン: {z['名']} (ID: {Z_ID_BASE + i} / {z['秒']}s)")
        if cols[1].button("削除", key=f"dz_{i}"):
            st.session_state.z_list.pop(i); st.rerun()

with c2:
    st.subheader("💡 グループ登録")
    vz = [z["名"] for z in st.session_state.z_list]
    with st.form("g_form", clear_on_submit=True):
        gn = st.text_input("グループ名 (最大32文字)", max_chars=32)
        gt = st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.form_submit_button("グループ追加"):
            if gn and gz:
                st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz})
                st.rerun()
    
    for i, g in enumerate(st.session_state.g_list):
        cols = st.columns([4, 1])
        cols[0].success(f"グループ: {g['名']} (ID: {G_ID_BASE + i} / {g['ゾ']})")
        if cols[1].button("削除", key=f"dg_{i}"):
            st.session_state.g_list.pop(i); st.rerun()

st.divider()

# --- 4. シーン作成 ---
st.header("2. シーン作成")
col_sn, col_sz = st.columns(2)
s_name = col_sn.text_input("シーン名 (例: 朝の全点灯)", max_chars=32)
s_zone = col_sz.selectbox("設定対象ゾーン", options=[""] + vz, key="sz_s")

if s_zone:
    # パレット画像の表示
    if os.path.exists("synca_palette.png"):
        st.image("synca_palette.png", caption="Synca演出パレット (X: 1-11, Y: 1-11)", width=500)
    
    target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
    scene_tmp = []
    
    for g in target_gs:
        with st.expander(f"■ {g['名']} ({g['型']}) の詳細", expanded=True):
            dim = st.slider(f"調光% ({g['名']})", 0, 100, 100)
            ex, ey, kel = "", "", "4000"
            
            if "Synca" in g['型']:
                mode = st.radio(f"設定方式 ({g['名']})", ["パレットを使用(1-11)", "色温度(K)を使用"], horizontal=True)
                if mode == "パレットを使用(1-11)":
                    cx, cy = st.columns(2)
                    ex = cx.slider("演出X", 1, 11, 6, key=f"x_{g['名']}")
                    ey = cy.slider("演出Y", 1, 11, 6, key=f"y_{g['名']}")
                else:
                    kel = st.text_input("色温度(K)", "4000", key=f"ks_{g['名']}")
            elif g['型'] == "調光調色":
                kel = st.text_input("色温度(K)", "4000", key=f"k_{g['名']}")
            
            scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
    
    if st.button("このシーンを履歴に保存", use_container_width=True):
        if s_name:
            # 同名シーンの上書き
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
            st.session_state.s_list.extend(scene_tmp)
            st.success(f"シーン『{s_name}』を保存しました")

st.divider()

# --- 5. タイムテーブル ---
st.header("3. タイムテーブル (スケジュール)")
t_zone = st.selectbox("スケジュールを設定するゾーン", options=[""] + vz, key="t_sz")

if t_zone:
    scenes = sorted(list(set([s["sn"] for s in st.session_state.s_list if s["zn"] == t_zone])))
    if scenes:
        if st.button("⏰ 09:00から6分間隔で自動生成"):
            base = datetime.strptime("09:00", "%H:%M")
            st.session_state[f"tt_{t_zone}"] = [{"時刻": (base + timedelta(minutes=i*6)).strftime("%H:%M"), "シーン": scenes[0]} for i in range(10)]
        
        if f"tt_{t_zone}" not in st.session_state: st.session_state[f"tt_{t_zone}"] = []
        
        tt_data = st.data_editor(st.session_state[f"tt_{t_zone}"], num_rows="dynamic", use_container_width=True)
        
        if st.button("タイムテーブルを確定"):
            st.session_state.t_list = [t for t in st.session_state.t_list if t["zn"] != t_zone]
            st.session_state.t_list.append({"zn": t_zone, "slots": tt_data})
            st.success("タイムテーブルを保存しました")
    else:
        st.warning("このゾーンに対応するシーンがまだ登録されていません。")

st.divider()

# --- 6. 書き出し ---
st.header("4. データ出力")
if st.button("📦 ゲートウェイ用 .tar を一括生成", type="primary", use_container_width=True):
    # 236列のベースDataFrame
    df_data = pd.DataFrame("", index=range(1000), columns=range(NUM_COLS))
    
    # ゾーン
    for i, z in enumerate(st.session_state.z_list):
        df_data.iloc[i, 0:3] = [z["名"], Z_ID_BASE + i, z["秒"]]
    
    # グループ
    for i, g in enumerate(st.session_state.g_list):
        df_data.iloc[i, 4:8] = [g["名"], G_ID_BASE + i, GROUP_TYPES[g["型"]], g["ゾ"]]
    
    # シーン
    s_id_map, current_s_id = {}, S_ID_BASE
    for i, r in enumerate(st.session_state.s_list):
        k = (r["sn"], r["zn"])
        if k not in s_id_map:
            s_id_map[k] = current_s_id
            current_s_id += 1
        color_val = f"{r['ex']}/{r['ey']}" if r['ex'] != "" else r['kel']
        df_data.iloc[i, 9:16] = [r["sn"], s_id_map[k], r["dim"], color_val, "static", r["zn"], r["gn"]]
        
    # タイムテーブル
    for i, t in enumerate(st.session_state.t_list):
        df_data.iloc[i, 17:20] = [f"{t['zn']}_Schedule", "", t['zn']]
        for j, slot in enumerate(t["slots"][:80]):
            df_data.iloc[i, 22 + j*2] = slot["時刻"]
            df_data.iloc[i, 23 + j*2] = slot["シーン"]

    # ヘッダー (マニュアル 236列完全再現)
    h0 = [""] * NUM_COLS
    h0[0], h0[4], h0[9], h0[17] = 'Zone情報','Group情報','Scene情報','Timetable情報'
    h2 = [""] * NUM_COLS
    h2[0:3], h2[4:8], h2[9:16] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]'], ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]']
    h2[17:22] = ['[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]']
    for j in range(22, 194, 2): h2[j], h2[j+1] = '[time]','[scene]'

    final_df = pd.concat([pd.DataFrame([h0, [""]*NUM_COLS, h2]), df_data], ignore_index=True)
    
    csv_buf = io.BytesIO()
    final_df.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        csv_bytes = csv_buf.getvalue()
        c_info = tarfile.TarInfo(name="setting_data.csv"); c_info.size = len(csv_bytes)
        tar.addfile(c_info, io.BytesIO(csv_bytes))
        
        json_bytes = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8')
        j_info = tarfile.TarInfo(name="temp.json"); j_info.size = len(json_bytes)
        tar.addfile(j_info, io.BytesIO(json_bytes))

    st.download_button(f"📥 {shop_name}_FitPlus_Setup.tar を保存", tar_buf.getvalue(), f"{shop_name}_FitPlus_Setup.tar")
