import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time
import os

# --- 1. 定数設定 (73列CSV/マニュアル準拠) ---
NUM_COLS = 73 
Z_ID_BASE, G_ID_BASE, S_ID_BASE, T_ID_BASE = 4097, 32769, 8193, 12289
GROUP_TYPES = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}

st.set_page_config(page_title="FitPlus Pro v230", layout="wide")

# セッション初期化
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []
if 't_slots' not in st.session_state: st.session_state.t_slots = []
if 'p_list' not in st.session_state: st.session_state.p_list = []

st.sidebar.title("🏢 プロジェクト管理")
shop_name = st.sidebar.text_input("店舗名", "FitPlus_Project")
if st.sidebar.button("データをリセット"):
    for key in ['z_list', 'g_list', 's_list', 't_slots', 'p_list']: st.session_state[key] = []
    st.rerun()

st.title(f"FitPlus ⚙️ {shop_name}")

# --- 2. 構成登録 (削除機能復活) ---
st.header("1. ゾーン & グループ登録")
c1, c2 = st.columns(2)
vz = [z["名"] for z in st.session_state.z_list]

with c1:
    st.subheader("📍 ゾーン")
    with st.form("z_form", clear_on_submit=True):
        zn = st.text_input("ゾーン名")
        zf = st.number_input("フェード(秒)", 0, 3600, 0)
        if st.form_submit_button("追加"):
            if zn: 
                st.session_state.z_list.append({"名": zn, "秒": zf})
                st.rerun()
    
    # ゾーン削除
    for i, z in enumerate(st.session_state.z_list):
        cols = st.columns([4, 1])
        cols[0].info(f"ゾーン: {z['名']}")
        if cols[1].button("削除", key=f"dz_{z['名']}_{i}"):
            target_zn = st.session_state.z_list[i]["名"]
            # 連動削除: このゾーンに属するグループとシーンを削除
            st.session_state.g_list = [g for g in st.session_state.g_list if g["ゾ"] != target_zn]
            st.session_state.s_list = [s for s in st.session_state.s_list if s["zn"] != target_zn]
            st.session_state.z_list.pop(i)
            st.rerun()

with c2:
    st.subheader("💡 グループ")
    with st.form("g_form", clear_on_submit=True):
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.form_submit_button("追加"):
            if gn and gz: 
                st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz})
                st.rerun()
    
    # グループ削除
    for i, g in enumerate(st.session_state.g_list):
        cols = st.columns([4, 1])
        cols[0].success(f"グループ: {g['名']} ({g['ゾ']})")
        if cols[1].button("削除", key=f"dg_{g['名']}_{i}"):
            target_gn = st.session_state.g_list[i]["名"]
            target_zn = st.session_state.g_list[i]["ゾ"]
            # 連動削除: このグループに関連するシーン設定を削除
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["gn"] == target_gn and s["zn"] == target_zn)]
            st.session_state.g_list.pop(i)
            st.rerun()

st.divider()

# --- 3. シーン作成 & 履歴表示 ---
st.header("2. シーン作成 & 履歴")
c_edit, c_hist = st.columns([1, 1])

with c_edit:
    st.subheader("🎨 シーン新規作成")
    s_name = st.text_input("シーン名 (例: 日中)")
    s_zone = st.selectbox("対象ゾーン", options=[""] + vz, key="sz_s")

    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        scene_tmp = []
        for g in target_gs:
            with st.expander(f"■ {g['名']} 設定"):
                dim = st.slider(f"調光%", 0, 100, 100, key=f"d_{g['名']}_{s_name}")
                ex, ey, kel = "", "", "4000"
                if "Synca" in g['型']:
                    mode = st.radio("設定方法", ["パレット", "色温度"], horizontal=True, key=f"m_{g['名']}_{s_name}")
                    if mode == "パレット":
                        cx, cy = st.columns(2)
                        ex = cx.slider("演出X (1-11)", 1, 11, 6, key=f"x_{g['名']}_{s_name}")
                        ey = cy.slider("演出Y (1-11)", 1, 11, 6, key=f"y_{g['名']}_{s_name}")
                    else: kel = st.text_input("色温度(K)", "4000", key=f"k_{g['名']}_{s_name}")
                elif g['型'] == "調光調色":
                    kel = st.text_input("色温度(K)", "4000", key=f"k_{g['名']}_{s_name}")
                scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
        
        if st.button("シーンを履歴に保存", use_container_width=True):
            if s_name:
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
                st.session_state.s_list.extend(scene_tmp); st.rerun()

with c_hist:
    st.subheader("📜 作成済みシーン履歴")
    if not st.session_state.s_list:
        st.write("履歴はありません")
    else:
        hist_df = pd.DataFrame(st.session_state.s_list)
        for (sn, zn), group in hist_df.groupby(['sn', 'zn']):
            with st.container(border=True):
                st.markdown(f"**シーン: {sn}** (ゾーン: {zn})")
                details = [f"- {r['gn']}: {r['dim']}% / {f'X/Y:{r[ex]}/{r[ey]}' if r['ex'] else f'{r[kel]}K'}" for _, r in group.iterrows()]
                st.write("\n".join(details))
                if st.button("このシーンを削除", key=f"del_sh_{sn}_{zn}"):
                    st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == sn and s["zn"] == zn)]
                    st.rerun()

st.divider()

# --- 4. スケジュール設定 (シーンから選ぶ) ---
st.header("3. スケジュール設定")
all_scene_options = sorted(list(set([f"{s['sn']} [{s['zn']}]" for s in st.session_state.s_list])))

if not all_scene_options:
    st.warning("シーンを登録すると、ここでスケジュールを組めます。")
else:
    st.subheader("⏰ タイムライン (シーン主導)")
    st.caption("ここでシーンを並べると、各ゾーンのスケジュールに自動反映されます。")
    
    tt_editor = st.data_editor(
        st.session_state.t_slots,
        column_config={
            "時刻": st.column_config.TimeColumn("時刻", format="HH:mm", required=True),
            "シーン選択": st.column_config.SelectboxColumn("シーン選択 [ゾーン名]", options=all_scene_options, required=True)
        },
        num_rows="dynamic", use_container_width=True, key="main_tt_editor"
    )
    if st.button("スケジュール内容を確定"):
        st.session_state.t_slots = tt_editor
        st.success("スケジュールを保持しました。")

    st.subheader("☀️ 日の出・日の入り設定")
    sun_config = {}
    for z_name in vz:
        z_scenes = sorted(list(set([s["sn"] for s in st.session_state.s_list if s["zn"] == z_name])))
        if z_scenes:
            c1, c2 = st.columns(2)
            s_st = c1.selectbox(f"日の出シーン [{z_name}]", options=[""] + z_scenes)
            s_en = c2.selectbox(f"日の入りシーン [{z_name}]", options=[""] + z_scenes)
            sun_config[z_name] = {"start": s_st, "end": s_en}

st.divider()

# --- 5. データ書き出し ---
st.header("4. データ出力")
if st.button("📦 ゲートウェイ用 .tar を生成", type="primary", use_container_width=True):
    df = pd.DataFrame("", index=range(1000), columns=range(NUM_COLS))
    for i, z in enumerate(st.session_state.z_list): df.iloc[i, 0:3] = [z["名"], "", z["秒"]]
    for i, g in enumerate(st.session_state.g_list): df.iloc[i, 4:8] = [g["名"], G_ID_BASE + i, GROUP_TYPES[g["型"]], g["ゾ"]]
    for i, r in enumerate(st.session_state.s_list):
        color = f"{r['ex']}/{r['ey']}" if r['ex'] != "" else r['kel']
        df.iloc[i, 9:17] = [r["sn"], "", r["dim"], color, "static", "", r["zn"], r["gn"]]
    
    for idx, z_name in enumerate(vz):
        z_slots = []
        for slot in st.session_state.t_slots:
            if f"[{z_name}]" in slot["シーン選択"]:
                s_name_only = slot["シーン選択"].split(" [")[0]
                t_val = slot["時刻"].strftime("%H:%M") if hasattr(slot["時刻"], "strftime") else slot["時刻"]
                z_slots.append({"時刻": t_val, "シーン": s_name_only})
        
        if z_slots:
            z_slots.sort(key=lambda x: x["時刻"])
            if z_slots[0]["時刻"] != "00:00": z_slots.insert(0, {"時刻": "00:00", "シーン": z_slots[0]["シーン"]})
            tt_name = f"{z_name}_TT"
            sun = sun_config.get(z_name, {"start": "", "end": ""})
            df.iloc[idx, 18:23] = [tt_name, T_ID_BASE + idx, z_name, sun["start"], sun["end"]]
            for j, s in enumerate(z_slots[:80]):
                df.iloc[idx, 23 + j*2], df.iloc[idx, 23 + j*2 + 1] = s["時刻"], s["シーン"]
            df.iloc[idx, 35:37] = [z_name, tt_name]

    h0 = [""] * NUM_COLS
    h0[0], h0[4], h0[9], h0[17], h0[35] = 'Zone情報','Group情報','Scene情報','Timetable情報','Timetable-schedule情報'
    h2 = [""] * NUM_COLS
    h2[0:3], h2[4:8], h2[9:17], h2[18:23], h2[35:44] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]'], ['[scene]','[id]','[dimming]','[color]','[perform]','[fresh-key]','[zone]','[group]'], ['[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]'], ['[zone-ts]','[daily]','[monday]','[tuesday]','[wednesday]','[thursday]','[friday]','[saturday]','[sunday]']
    for j in range(23, 34, 2): h2[j], h2[j+1] = '[time]','[scene]'

    final_df = pd.concat([pd.DataFrame([h0, [""]*NUM_COLS, h2]), df], ignore_index=True)
    csv_buf = io.BytesIO(); final_df.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        b = csv_buf.getvalue(); info = tarfile.TarInfo(name="setting_data.csv"); info.size = len(b); tar.addfile(info, io.BytesIO(b))
        j = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8'); ji = tarfile.TarInfo(name="temp.json"); ji.size = len(j); tar.addfile(ji, io.BytesIO(j))

    st.download_button(f"📥 {shop_name}.tar を保存", tar_buf.getvalue(), f"{shop_name}.tar")
