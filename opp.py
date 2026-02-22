import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time
import os

# --- 1. 定数設定 (マニュアル・73列CSV準拠) ---
NUM_COLS = 73 
Z_ID_BASE, G_ID_BASE, S_ID_BASE, T_ID_BASE = 4097, 32769, 8193, 12289
GROUP_TYPES = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
DAY_OPTIONS = ["毎日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

st.set_page_config(page_title="FitPlus Pro v210", layout="wide")

# セッション初期化
for key in ['z_list', 'g_list', 's_list', 't_list', 'p_list']:
    if key not in st.session_state: st.session_state[key] = []

st.sidebar.title("🏢 プロジェクト管理")
shop_name = st.sidebar.text_input("店舗名", "FitPlus_Project")
if st.sidebar.button("データをリセット"):
    for key in ['z_list', 'g_list', 's_list', 't_list', 'p_list']: st.session_state[key] = []
    st.rerun()

st.title(f"FitPlus ⚙️ {shop_name}")

# --- 2. 構成登録 ---
st.header("1. ゾーン & グループ登録")
c1, c2 = st.columns(2)
vz = [z["名"] for z in st.session_state.z_list]
with c1:
    st.subheader("📍 ゾーン")
    with st.form("z_form", clear_on_submit=True):
        zn = st.text_input("ゾーン名")
        zf = st.number_input("フェード(秒)", 0, 3600, 0)
        if st.form_submit_button("追加"):
            if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    for i, z in enumerate(st.session_state.z_list):
        st.info(f"{z['名']} ({z['秒']}s)")

with c2:
    st.subheader("💡 グループ")
    with st.form("g_form", clear_on_submit=True):
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.form_submit_button("追加"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
    for g in st.session_state.g_list:
        st.success(f"{g['名']} ({g['ゾ']})")

st.divider()

# --- 3. シーン作成 ---
st.header("2. シーン作成")
col_sn, col_sz = st.columns(2)
s_name = col_sn.text_input("シーン名 (例: 日中, 閉店後)")
s_zone = col_sz.selectbox("設定対象ゾーン", options=[""] + vz, key="sz_s")

if s_zone:
    target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
    scene_tmp = []
    for g in target_gs:
        with st.expander(f"■ {g['名']} 設定"):
            dim = st.slider(f"調光%", 0, 100, 100, key=f"d_{g['名']}_{s_name}")
            ex, ey, kel = "", "", "4000"
            if "Synca" in g['型']:
                mode = st.radio("色設定", ["パレット", "色温度"], horizontal=True, key=f"m_{g['名']}_{s_name}")
                if mode == "パレット":
                    cx, cy = st.columns(2)
                    ex = cx.slider("演出X", 1, 11, 6, key=f"x_{g['名']}_{s_name}")
                    ey = cy.slider("演出Y", 1, 11, 6, key=f"y_{g['名']}_{s_name}")
                else: kel = st.text_input("色温度(K)", "4000", key=f"k_{g['名']}_{s_name}")
            elif g['型'] == "調光調色":
                kel = st.text_input("色温度(K)", "4000", key=f"k_{g['名']}_{s_name}")
            scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
    
    if st.button("シーンを保存", use_container_width=True):
        st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
        st.session_state.s_list.extend(scene_tmp); st.success("シーン保存完了")

st.divider()

# --- 4. タイムテーブル・特異日 ---
st.header("3. タイムテーブル・日の出日の入り・特異日設定")
t_zone = st.selectbox("ゾーン選択", options=[""] + vz, key="t_sz")

if t_zone:
    scenes = sorted(list(set([s["sn"] for s in st.session_state.s_list if s["zn"] == t_zone])))
    st.subheader("☀️ 日の出・日の入り設定 (Sun設定)")
    sc1, sc2 = st.columns(2)
    sun_start = sc1.selectbox("日の出時に切り替わるシーン", options=[""] + scenes)
    sun_end = sc2.selectbox("日の入り時に切り替わるシーン", options=[""] + scenes)

    st.subheader("⏰ スケジュール編集")
    if f"tt_{t_zone}" not in st.session_state:
        st.session_state[f"tt_{t_zone}"] = [{"時刻": time(0, 0), "シーン": scenes[0] if scenes else ""}]
    
    tt_data = st.data_editor(
        st.session_state[f"tt_{t_zone}"],
        column_config={
            "時刻": st.column_config.TimeColumn("時刻", format="HH:mm", required=True),
            "シーン": st.column_config.SelectboxColumn("シーン選択", options=scenes, required=True)
        },
        num_rows="dynamic", use_container_width=True, key=f"ed_{t_zone}"
    )
    
    st.subheader("📅 適用ルール")
    rc1, rc2 = st.columns(2)
    repeat_day = rc1.selectbox("適用の繰り返し設定", options=DAY_OPTIONS)

    if st.button("タイムテーブルを確定保存", use_container_width=True):
        if tt_data[0]["時刻"] != time(0, 0):
            st.error("最初の時刻は 00:00 である必要があります。")
        else:
            final_slots = [{"時刻": s["時刻"].strftime("%H:%M"), "シーン": s["シーン"]} for s in tt_data]
            st.session_state.t_list = [t for t in st.session_state.t_list if not (t["zn"] == t_zone and t["repeat"] == repeat_day)]
            st.session_state.t_list.append({
                "zn": t_zone, "tn": f"{t_zone}_{repeat_day}_TT", "slots": final_slots, 
                "repeat": repeat_day, "sun_start": sun_start, "sun_end": sun_end
            })
            st.success(f"{repeat_day} のスケジュールとして保存しました。")

    st.divider()
    st.subheader("📆 期間・特異日設定")
    tts_all = [t["tn"] for t in st.session_state.t_list if t["zn"] == t_zone]
    with st.form("p_form", clear_on_submit=True):
        pn = st.text_input("設定名称", max_chars=32)
        pc1, pc2 = st.columns(2)
        sd, ed = pc1.date_input("開始日"), pc2.date_input("終了日")
        ptt = st.selectbox("適用するタイムテーブル", options=tts_all)
        if st.form_submit_button("追加"):
            if pn and ptt:
                st.session_state.p_list.append({"名": pn, "zn": t_zone, "start": sd, "end": ed, "tt": ptt}); st.rerun()
    for p in st.session_state.p_list:
        if p["zn"] == t_zone: st.warning(f"🗓️ {p['名']}: {p['start']}～{p['end']} ({p['tt']})")

st.divider()

# --- 5. 書き出し ---
st.header("4. データ書き出し")
if st.button("📦 ゲートウェイ用 .tar を生成", type="primary", use_container_width=True):
    df = pd.DataFrame("", index=range(1000), columns=range(NUM_COLS))
    for i, z in enumerate(st.session_state.z_list): df.iloc[i, 0:3] = [z["名"], "", z["秒"]]
    for i, g in enumerate(st.session_state.g_list): df.iloc[i, 4:8] = [g["名"], G_ID_BASE + i, GROUP_TYPES[g["型"]], g["ゾ"]]
    for i, r in enumerate(st.session_state.s_list):
        color = f"{r['ex']}/{r['ey']}" if r['ex'] != "" else r['kel']
        df.iloc[i, 9:17] = [r["sn"], "", r["dim"], color, "static", "", r["zn"], r["gn"]]
    
    for i, t in enumerate(st.session_state.t_list):
        # 18:TT名, 19:ID, 20:Zone, 21:Sun始, 22:Sun終
        df.iloc[i, 18:23] = [t["tn"], T_ID_BASE + i, t["zn"], t["sun_start"], t["sun_end"]]
        for j, s in enumerate(t["slots"][:80]):
            df.iloc[i, 23 + j*2], df.iloc[i, 23 + j*2 + 1] = s["時刻"], s["シーン"]
        
        # 曜日割当 (36:Daily, 37:Mon...)
        df.iloc[i, 35] = t["zn"]
        rep_idx = 36 if t["repeat"] == "毎日" else 37 + DAY_OPTIONS.index(t["repeat"]) - 1
        df.iloc[i, rep_idx] = t["tn"]

    for i, p in enumerate(st.session_state.p_list):
        df.iloc[i, 45:50] = [p["名"], p["start"].strftime("%m月%d日"), p["end"].strftime("%m月%d日"), p["tt"], p["zn"]]

    h0 = [""] * NUM_COLS
    h0[0], h0[4], h0[9], h0[17], h0[35], h0[45] = 'Zone情報','Group情報','Scene情報','Timetable情報','Timetable-schedule情報','Timetable期間/特異日情報'
    h2 = [""] * NUM_COLS
    h2[0:3], h2[4:8], h2[9:17] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]'], ['[scene]','[id]','[dimming]','[color]','[perform]','[fresh-key]','[zone]','[group]']
    h2[18:23] = ['[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]']
    for j in range(23, 34, 2): h2[j], h2[j+1] = '[time]','[scene]'
    h2[35:44] = ['[zone-ts]','[daily]','[monday]','[tuesday]','[wednesday]','[thursday]','[friday]','[saturday]','[sunday]']
    h2[45:50] = ['[zone-period]','[start]','[end]','[timetable]','[zone]']

    final_df = pd.concat([pd.DataFrame([h0, [""]*NUM_COLS, h2]), df], ignore_index=True)
    csv_buf = io.BytesIO(); final_df.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        b = csv_buf.getvalue(); info = tarfile.TarInfo(name="setting_data.csv"); info.size = len(b); tar.addfile(info, io.BytesIO(b))
        j = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8'); ji = tarfile.TarInfo(name="temp.json"); ji.size = len(j); tar.addfile(ji, io.BytesIO(j))

    st.download_button(f"📥 {shop_name}.tar を保存", tar_buf.getvalue(), f"{shop_name}.tar")
