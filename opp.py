import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta
import os

# --- 1. 定数設定 (添付CSV/マニュアル準拠) ---
NUM_COLS = 73 
Z_ID_BASE, G_ID_BASE, S_ID_BASE, T_ID_BASE = 4097, 32769, 8193, 12289
GROUP_TYPES = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}

st.set_page_config(page_title="FitPlus Pro v160", layout="wide")

# セッション状態の初期化
for key in ['z_list', 'g_list', 's_list', 't_list', 'p_list']:
    if key not in st.session_state: st.session_state[key] = []

# --- 2. プロジェクト管理 ---
st.sidebar.title("🏢 プロジェクト管理")
shop_name = st.sidebar.text_input("店舗名", "FitPlus_Project")
if st.sidebar.button("データをリセット"):
    for key in ['z_list', 'g_list', 's_list', 't_list', 'p_list']: st.session_state[key] = []
    st.rerun()

st.title(f"FitPlus ⚙️ {shop_name} 設定ツール")

# --- 3. 構成登録 ---
st.header("1. ゾーン & グループ登録")
c1, c2 = st.columns(2)
with c1:
    st.subheader("📍 ゾーン登録")
    with st.form("z_form", clear_on_submit=True):
        zn = st.text_input("ゾーン名 (最大32文字)", max_chars=32)
        zf = st.number_input("フェード時間(秒)", 0, 3600, 0)
        if st.form_submit_button("追加"):
            if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    for i, z in enumerate(st.session_state.z_list):
        cols = st.columns([4, 1]); cols[0].info(f"ゾーン: {z['名']} ({z['秒']}s)")
        if cols[1].button("削除", key=f"dz_{i}"): st.session_state.z_list.pop(i); st.rerun()

with c2:
    st.subheader("💡 グループ登録")
    vz = [z["名"] for z in st.session_state.z_list]
    with st.form("g_form", clear_on_submit=True):
        gn = st.text_input("グループ名", max_chars=32)
        gt = st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.form_submit_button("追加"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
    for i, g in enumerate(st.session_state.g_list):
        cols = st.columns([4, 1]); cols[0].success(f"グループ: {g['名']} ({g['ゾ']})")
        if cols[1].button("削除", key=f"dg_{i}"): st.session_state.g_list.pop(i); st.rerun()

st.divider()

# --- 4. シーン作成 ---
st.header("2. シーン作成")
col_sn, col_sz = st.columns(2)
s_name = col_sn.text_input("シーン名", max_chars=32)
s_zone = col_sz.selectbox("設定対象ゾーン", options=[""] + vz, key="sz_s")

if s_zone:
    if os.path.exists("synca_palette.png"):
        st.image("synca_palette.png", caption="Syncaパレット (1～11)", width=500)
    
    target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
    scene_tmp = []
    for g in target_gs:
        with st.expander(f"■ {g['名']} ({g['型']})", expanded=True):
            dim = st.slider(f"調光% ({g['名']})", 0, 100, 100, key=f"dim_{g['名']}_{s_name}")
            ex, ey, kel = "", "", "4000"
            if "Synca" in g['型']:
                mode = st.radio(f"設定方法 ({g['名']})", ["パレット(1-11)", "色温度(K)"], horizontal=True, key=f"mode_{g['名']}_{s_name}")
                if mode == "パレット(1-11)":
                    cx, cy = st.columns(2)
                    ex = cx.slider("演出X", 1, 11, 6, key=f"x_{g['名']}_{s_name}")
                    ey = cy.slider("演出Y", 1, 11, 6, key=f"y_{g['名']}_{s_name}")
                else: kel = st.text_input("色温度(K)", "4000", key=f"ks_{g['名']}_{s_name}")
            elif g['型'] == "調光調色":
                kel = st.text_input("色温度(K)", "4000", key=f"k_{g['名']}_{s_name}")
            scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
    
    if st.button("このシーン設定を保存", use_container_width=True):
        if s_name:
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
            st.session_state.s_list.extend(scene_tmp); st.rerun()

st.divider()

# --- 5. タイムテーブル設定 ---
st.header("3. タイムテーブル設定")
t_zone = st.selectbox("スケジュールを設定するゾーン", options=[""] + vz, key="t_sz")
if t_zone:
    scenes = sorted(list(set([s["sn"] for s in st.session_state.s_list if s["zn"] == t_zone])))
    st.subheader("⏰ タイムテーブル自動生成")
    if scenes:
        c1, c2, c3 = st.columns(3)
        start_t = c1.time_input("範囲開始", value=datetime.strptime("00:00", "%H:%M").time())
        end_t = c2.time_input("範囲終了", value=datetime.strptime("23:59", "%H:%M").time())
        interval = c3.number_input("間隔(分)", 1, 120, 8)
        
        if st.button("⏰ スケジュールを一括自動生成", use_container_width=True):
            new_slots = []
            curr = datetime.combine(datetime.today(), start_t)
            end = datetime.combine(datetime.today(), end_t)
            # マニュアル上限100スロット 
            while curr <= end and len(new_slots) < 100:
                new_slots.append({"時刻": curr.strftime("%H:%M"), "シーン": scenes[0]})
                curr += timedelta(minutes=interval)
            st.session_state[f"tt_{t_zone}"] = new_slots

    if f"tt_{t_zone}" not in st.session_state:
        st.session_state[f"tt_{t_zone}"] = [{"時刻": "00:00", "シーン": scenes[0] if scenes else ""}]
    
    tt_data = st.data_editor(st.session_state[f"tt_{t_zone}"], num_rows="dynamic", use_container_width=True, key=f"ed_{t_zone}")
    
    if st.button("タイムテーブル保存"):
        if not tt_data or tt_data[0]["時刻"] != "00:00":
            st.error("最初の時刻は 00:00 に設定してください。")
        else:
            st.session_state.t_list = [t for t in st.session_state.t_list if t["zn"] != t_zone]
            st.session_state.t_list.append({"zn": t_zone, "tn": f"{t_zone}_TT", "slots": tt_data}); st.success("保存完了")

st.divider()

# --- 6. データ出力 ---
st.header("4. データ書き出し")
if st.button("📦 ゲートウェイ用 .tar を生成", type="primary", use_container_width=True):
    df_data = pd.DataFrame("", index=range(1000), columns=range(NUM_COLS))
    for i, z in enumerate(st.session_state.z_list): df_data.iloc[i, 0:3] = [z["名"], "", z["秒"]]
    for i, g in enumerate(st.session_state.g_list): df_data.iloc[i, 4:8] = [g["名"], G_ID_BASE + i, GROUP_TYPES[g["型"]], g["ゾ"]]
    for i, r in enumerate(st.session_state.s_list):
        color = f"{r['ex']}/{r['ey']}" if r['ex'] != "" else r['kel']
        df_data.iloc[i, 9:17] = [r["sn"], "", r["dim"], color, "static", "", r["zn"], r["gn"]]
    for i, t in enumerate(st.session_state.t_list):
        df_data.iloc[i, 18:21] = [t["tn"], T_ID_BASE + i, t["zn"]]
        for j, slot in enumerate(t["slots"][:80]):
            if 23 + j*2 + 1 < NUM_COLS:
                df_data.iloc[i, 23 + j*2] = slot["時刻"]
                df_data.iloc[i, 23 + j*2 + 1] = slot["シーン"]

    h0 = [""] * NUM_COLS
    h0[0], h0[4], h0[9], h0[17], h0[35], h0[45] = 'Zone情報','Group情報','Scene情報','Timetable情報','Timetable-schedule情報','Timetable期間/特異日情報'
    h2 = [""] * NUM_COLS
    h2[0:3] = ['[zone]','[id]','[fade]']
    h2[4:8] = ['[group]','[id]','[type]','[zone]']
    h2[9:17] = ['[scene]','[id]','[dimming]','[color]','[perform]','[fresh-key]','[zone]','[group]']
    h2[18:23] = ['[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]']
    for j in range(23, min(34, NUM_COLS-1), 2): h2[j], h2[j+1] = '[time]','[scene]'

    final_df = pd.concat([pd.DataFrame([h0, [""]*NUM_COLS, h2]), df_data], ignore_index=True)
    csv_buf = io.BytesIO(); final_df.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        b = csv_buf.getvalue(); info = tarfile.TarInfo(name="setting_data.csv"); info.size = len(b); tar.addfile(info, io.BytesIO(b))
        j = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8'); ji = tarfile.TarInfo(name="temp.json"); ji.size = len(j); tar.addfile(ji, io.BytesIO(j))

    st.download_button(f"📥 {shop_name}_FitPlus.tar を保存", tar_buf.getvalue(), f"{shop_name}.tar")
