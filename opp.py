import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time
import os

# --- 1. 定数設定 (236列構成準拠) ---
NUM_COLS = 236 
GROUP_TYPES = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
DAY_OPTIONS = ["毎日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

st.set_page_config(page_title="FitPlus Pro v320", layout="wide")

# セッション状態の初期化
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []
if 't_slots' not in st.session_state: st.session_state.t_slots = []
if 'p_list' not in st.session_state: st.session_state.p_list = []

# --- 2. プロジェクト管理 ---
st.sidebar.title("🏢 プロジェクト管理")
shop_name = st.sidebar.text_input("店舗名", "FitPlus_Project")
if st.sidebar.button("全データをリセット"):
    for key in ['z_list', 'g_list', 's_list', 't_slots', 'p_list']: st.session_state[key] = []
    st.rerun()

st.title(f"FitPlus ⚙️ {shop_name}")

# --- 3. 構成登録 ---
st.header("1. ゾーン & グループ登録")
c1, c2 = st.columns(2)
vz = [z["名"] for z in st.session_state.z_list]

with c1:
    st.subheader("📍 ゾーン登録・履歴")
    with st.form("z_form", clear_on_submit=True):
        zn = st.text_input("ゾーン名")
        zf = st.number_input("フェード(秒)", 0, 3600, 0)
        if st.form_submit_button("追加"):
            if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    for i, z in enumerate(st.session_state.z_list):
        cols = st.columns([4, 1])
        cols[0].info(f"ゾーン: {z['名']} / {z['秒']}s")
        if cols[1].button("削除", key=f"dz_{i}"):
            st.session_state.z_list.pop(i); st.rerun()

with c2:
    st.subheader("💡 グループ登録・履歴")
    with st.form("g_form", clear_on_submit=True):
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.form_submit_button("追加"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
    for i, g in enumerate(st.session_state.g_list):
        cols = st.columns([4, 1])
        cols[0].success(f"{g['名']} [{g['型']}] ({g['ゾ']})")
        if cols[1].button("削除", key=f"dg_{i}"):
            st.session_state.g_list.pop(i); st.rerun()

st.divider()

# --- 4. シーン作成 & 履歴 ---
st.header("2. シーン作成 & 履歴")
c_edit, c_hist = st.columns([1, 1])

with c_edit:
    st.subheader("🎨 新規シーン作成")
    s_name = st.text_input("シーン名")
    s_zone = st.selectbox("対象ゾーン", options=[""] + vz, key="sz_s")

    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        scene_tmp = []
        for g in target_gs:
            with st.expander(f"■ {g['名']} ({g['型']})"):
                dim = st.slider(f"調光%", 0, 100, 100, key=f"d_{g['名']}_{s_name}")
                ex, ey, kel = "", "", "4000"
                if "Synca" in g['型']:
                    mode = st.radio("設定方法", ["パレット", "色温度"], horizontal=True, key=f"m_{g['名']}_{s_name}")
                    if mode == "パレット":
                        cx, cy = st.columns(2)
                        ex = cx.slider("X", 1, 11, 6, key=f"x_{g['名']}")
                        ey = cy.slider("Y", 1, 11, 6, key=f"y_{g['名']}")
                    else: kel = st.text_input("色温度(K)", "4000", key=f"ks_{g['名']}")
                elif g['型'] == "調光調色":
                    kel = st.text_input("色温度(K)", "4000", key=f"k_{g['名']}")
                scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
        
        if st.button("このシーン設定を保存", use_container_width=True):
            if s_name:
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
                st.session_state.s_list.extend(scene_tmp); st.rerun()

with c_hist:
    st.subheader("📜 作成済みシーン詳細")
    if not st.session_state.s_list: st.write("なし")
    else:
        h_df = pd.DataFrame(st.session_state.s_list)
        for (sn, zn), group in h_df.groupby(['sn', 'zn']):
            with st.container(border=True):
                st.write(f"**{sn}** ({zn})")
                details = [f"- {r['gn']}: {r['dim']}% / {r['ex']}/{r['ey'] if r['ex'] else r['kel']+'K'}" for _, r in group.iterrows()]
                st.write("\n".join(details))
                if st.button("削除", key=f"del_sh_{sn}_{zn}"):
                    st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == sn and s["zn"] == zn)]
                    st.rerun()

st.divider()

# --- 5. スケジュール & 特異日 ---
st.header("3. スケジュール & 特異日")
all_scene_opts = sorted(list(set([f"{s['sn']} [{s['zn']}]" for s in st.session_state.s_list])))

if not all_scene_opts:
    st.warning("シーンを登録してください")
else:
    st.subheader("⏰ スケジュールタイムライン (シーン選択)")
    # 初期値設定
    if not st.session_state.t_slots:
        st.session_state.t_slots = pd.DataFrame([{"時刻": time(0, 0), "シーン選択": all_scene_opts[0], "繰り返し": "毎日"}])
    elif isinstance(st.session_state.t_slots, list):
        st.session_state.t_slots = pd.DataFrame(st.session_state.t_slots)

    tt_editor = st.data_editor(st.session_state.t_slots, num_rows="dynamic", use_container_width=True,
                               column_config={
                                   "時刻": st.column_config.TimeColumn("時刻", format="HH:mm", required=True),
                                   "シーン選択": st.column_config.SelectboxColumn("シーン [ゾーン]", options=all_scene_opts, required=True),
                                   "繰り返し": st.column_config.SelectboxColumn("繰り返し", options=DAY_OPTIONS, required=True)
                               })
    if st.button("スケジュールを保存"): 
        st.session_state.t_slots = tt_editor
        st.success("保存完了")

    st.subheader("📅 特異日設定")
    with st.form("p_form", clear_on_submit=True):
        pn = st.text_input("名称 (例: 正月)")
        col_d1, col_d2 = st.columns(2)
        p_sd = col_d1.date_input("開始日")
        p_ed = col_d2.date_input("終了日")
        p_target_z = st.selectbox("対象ゾーン", options=vz)
        p_rep = st.selectbox("適用スケジュール", options=DAY_OPTIONS)
        if st.form_submit_button("特異日追加"):
            st.session_state.p_list.append({"名": pn, "zn": p_target_z, "sd": p_sd, "ed": p_ed, "rep": p_rep})
            st.rerun()
    for i, p in enumerate(st.session_state.p_list):
        cols = st.columns([4, 1])
        cols[0].warning(f"🗓️ {p['名']}: {p['sd']}～{p['ed']} ({p['zn']})")
        if cols[1].button("削除", key=f"dp_{i}"): st.session_state.p_list.pop(i); st.rerun()

st.divider()

# --- 6. 書き出し ---
st.header("4. データ書き出し")
if st.button("📦 ゲートウェイ用 .tar を生成", type="primary", use_container_width=True):
    df = pd.DataFrame("", index=range(1000), columns=range(NUM_COLS))
    # Zone/Group
    for i, z in enumerate(st.session_state.z_list): df.iloc[i, 0:3] = [z["名"], "", z["秒"]]
    for i, g in enumerate(st.session_state.g_list): df.iloc[i, 4:8] = [g["名"], "", GROUP_TYPES[g["型"]], g["ゾ"]]
    # Scene (ID/Perform空欄)
    for i, r in enumerate(st.session_state.s_list):
        # Syncaパレットを明示的に文字列として扱い、Excelの日付化を避ける
        color = f"'{r['ex']}/{r['ey']}" if r['ex'] != "" else r['kel']
        df.iloc[i, 9:16] = [r["sn"], "", r["dim"], color, "", r["zn"], r["gn"]]
    
    # タイムテーブル
    idx_tt = 0
    t_slots_df = pd.DataFrame(st.session_state.t_slots)
    for z_name in vz:
        for rep in DAY_OPTIONS:
            slots = t_slots_df[t_slots_df["シーン選択"].str.contains(f"\[{z_name}\]", na=False) & (t_slots_df["繰り返し"] == rep)].copy()
            if not slots.empty:
                slots = slots.sort_values("時刻")
                tt_n = f"{z_name}_{rep}_TT"
                df.iloc[idx_tt, 17:20] = [tt_n, "", z_name]
                for j, (_, s) in enumerate(slots.head(80).iterrows()):
                    t_str = s["時刻"].strftime("%H:%M") if hasattr(s["時刻"], "strftime") else str(s["時刻"])[:5]
                    df.iloc[idx_tt, 22 + j*2] = t_str
                    df.iloc[idx_tt, 23 + j*2] = s["シーン選択"].split(" [")[0]
                # 曜日スケジュール割当
                df.iloc[idx_tt, 183] = z_name
                rep_c = 184 if rep == "毎日" else 185 + DAY_OPTIONS.index(rep) - 1
                df.iloc[idx_tt, rep_c] = tt_n
                idx_tt += 1

    # 特異日
    for i, p in enumerate(st.session_state.p_list):
        df.iloc[i, 193:198] = [p["名"], p["sd"].strftime("%m月%d日"), p["ed"].strftime("%m月%d日"), f"{p['zn']}_{p['rep']}_TT", p['zn']]

    # ヘッダー構築 (236列完全再現)
    h0 = [""] * NUM_COLS
    h0[0], h0[4], h0[9], h0[17], h0[183], h0[193] = 'Zone情報','Group情報','Scene情報','Timetable情報','Timetable-schedule情報','Timetable期間/特異日情報'
    h2 = [""] * NUM_COLS
    h2[0:3], h2[4:8], h2[9:16] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]'], ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]']
    h2[17:22] = ['[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]']
    for j in range(22, 182, 2): h2[j], h2[j+1] = '[time]','[scene]'
    h2[183:192] = ['[zone-ts]','[daily]','[monday]','[tuesday]','[wednesday]','[thursday]','[friday]','[saturday]','[sunday]']
    h2[193:198] = ['[zone-period]','[start]','[end]','[timetable]','[zone]']

    final_df = pd.concat([pd.DataFrame([h0, [""]*NUM_COLS, h2]), df], ignore_index=True)
    csv_buf = io.BytesIO(); final_df.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        b = csv_buf.getvalue(); info = tarfile.TarInfo(name="setting_data.csv"); info.size = len(b); tar.addfile(info, io.BytesIO(b))
        j = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8'); ji = tarfile.TarInfo(name="temp.json"); ji.size = len(j); tar.addfile(ji, io.BytesIO(j))

    st.download_button(f"📥 {shop_name}_FitPlus.tar を保存", tar_buf.getvalue(), f"{shop_name}.tar")
