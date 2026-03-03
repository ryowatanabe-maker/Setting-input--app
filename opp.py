import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time
import os

# --- 1. 定数設定 (赤池店の236列構造を完全再現) ---
TOTAL_COLS = 236
IDX_SCENE_START = 9
IDX_TT_START = 17           # [zone-timetable] R列
IDX_TIME_SLOTS_START = 22   # [time] W列
IDX_ZONE_TS = 197           # [zone-ts] GS列
IDX_PERIOD = 207            # [zone-period] IC列
IDX_PERIOD_TT = 210         # [timetable] IF列
IDX_PERIOD_ZONE = 211       # [zone] IG列

GROUP_TYPES = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
DAY_OPTIONS = ["毎日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

st.set_page_config(page_title="FitPlus Pro v9600", layout="wide")

# セッション状態の初期化
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []
if 't_df' not in st.session_state:
    st.session_state.t_df = pd.DataFrame(columns=["スケジュール名", "時刻", "シーン選択", "繰り返し"])
if 'p_list' not in st.session_state: st.session_state.p_list = []
if 'loop_scenes' not in st.session_state: st.session_state.loop_scenes = []

def safe_to_time(val):
    if isinstance(val, time): return val
    s = str(val).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try: return datetime.strptime(s, fmt).time()
        except: continue
    return time(0, 0)

def fmt_t(t): return f"{t.hour}:{t.minute:02}"
def fmt_d(d): return f"{d.month}月{d.day}日"

# --- 0. 店舗名入力 ---
st.title("FitPlus ⚙️ 統合設定ツール (赤池店構造再現)")
shop_name_input = st.text_input("🏢 店舗名を入力（ファイル名になります）", "FitPlus_Project")

if st.sidebar.button("全データをクリア"):
    for k in ['z_list', 'g_list', 's_list', 'p_list', 'loop_scenes']: st.session_state[k] = []
    st.session_state.t_df = pd.DataFrame(columns=["スケジュール名", "時刻", "シーン選択", "繰り返し"])
    st.rerun()

st.divider()

# --- 1. ゾーン & グループ登録 ---
st.header("1. ゾーン & グループ登録")
c_reg, c_view = st.columns([1, 1])
vz = [z["名"] for z in st.session_state.z_list]
with c_reg:
    with st.container(border=True):
        st.write("**ゾーン追加**")
        zn, zf = st.text_input("ゾーン名"), st.number_input("フェード(秒)", 0, 3600, 0)
        if st.button("ゾーン保存"):
            if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    with st.container(border=True):
        st.write("**グループ追加**")
        gn, gt = st.text_input("グループ名"), st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.button("グループ保存"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()

with c_view:
    st.subheader("📜 登録済み")
    for i, z in enumerate(st.session_state.z_list):
        cc1, cc2 = st.columns([4, 1]); cc1.info(f"ゾーン: {z['名']} ({z['秒']}s)")
        if cc2.button("削除", key=f"dz_{i}"): st.session_state.z_list.pop(i); st.rerun()
    for i, g in enumerate(st.session_state.g_list):
        cc1, cc2 = st.columns([4, 1]); cc1.success(f"グループ: {g['名']} ({g['型']})")
        if cc2.button("削除", key=f"dg_{i}"): st.session_state.g_list.pop(i); st.rerun()

st.divider()

# --- 2. シーン作成 ---
st.header("2. シーン作成 & 詳細履歴")
c_s_reg, c_s_view = st.columns([1, 1])
with c_s_reg:
    s_name_in = st.text_input("シーン名")
    s_zone_in = st.selectbox("対象ゾーン選択", options=[""] + vz)
    if s_zone_in:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone_in]
        scene_tmp = []
        for g in target_gs:
            with st.expander(f"⚙️ {g['名']} 設定"):
                dim = st.slider("調光%", 0, 100, 100, key=f"d_{g['名']}")
                ex, ey, kel = "", "", "4000"
                if "Synca" in g['型']:
                    mode = st.radio("設定方法", ["パレット", "調色"], key=f"m_{g['名']}", horizontal=True)
                    if mode == "パレット":
                        cx, cy = st.columns(2)
                        ex, ey = cx.slider("演出X", 1, 11, 6, key=f"x_{g['名']}"), cy.slider("演出Y", 1, 11, 6, key=f"y_{g['名']}")
                    else: kel = st.text_input("K", "4000", key=f"ks_{g['名']}")
                elif g['型'] == "調光調色": kel = st.text_input("K", "4000", key=f"k_{g['名']}")
                scene_tmp.append({"sn": s_name_in, "gn": g['名'], "zn": s_zone_in, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
        if st.button("このシーンを保存"):
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name_in and s["zn"] == s_zone_in)]
            st.session_state.s_list.extend(scene_tmp); st.rerun()

with c_s_view:
    st.subheader("📜 詳細履歴")
    if st.session_state.s_list:
        h_df_view = pd.DataFrame(st.session_state.s_list)
        for (sn, zn), group_data in h_df_view.groupby(['sn', 'zn']):
            with st.expander(f"➕ {sn} ({zn})"):
                for _, row in group_data.iterrows():
                    c_info = f" {row['ex']}-{row['ey']}" if row['ex'] != "" else f"{row['kel']}K"
                    st.write(f"・{row['gn']}: {row['dim']}% / {c_info}")
                if st.button("削除", key=f"ds_{sn}_{zn}"):
                    st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == sn and s["zn"] == zn)]; st.rerun()

st.divider()

# --- 3. スケジュール ---
st.header("3. スケジュール & 特異日")
all_scene_opts = sorted(list(set([f"{s['sn']} [{s['zn']}]" for s in st.session_state.s_list])))
current_opts = all_scene_opts if all_scene_opts else ["(シーン未登録)"]

with st.container(border=True):
    st.subheader("🔄 スケジュール一括生成")
    tt_name_input = st.text_input("スケジュール名 (例: 通常, 春, 正月)", "通常")
    c_add, c_clear = st.columns([2, 1])
    new_scene = c_add.selectbox("シーン順序に追加", options=current_opts)
    if c_add.button("＋ 追加"):
        if "(シーン未登録)" not in new_scene: st.session_state.loop_scenes.append(new_scene); st.rerun()
    if c_clear.button("クリア"):
        st.session_state.loop_scenes = []; st.rerun()
    
    if st.session_state.loop_scenes:
        st.info("順序: " + " ➔ ".join(st.session_state.loop_scenes))
        c1, c2, c3, c4 = st.columns(4)
        g_st, g_en = c1.time_input("始"), c2.time_input("終")
        g_it, g_rp = c3.number_input("分", 1, 1440, 8), c4.selectbox("曜", DAY_OPTIONS)
        if st.button("⏰ スケジュールを生成", use_container_width=True):
            new_r = []
            dt, idx = datetime.combine(datetime.today(), g_st), 0
            while dt <= datetime.combine(datetime.today(), g_en) and len(new_r) < 80:
                new_r.append({"スケジュール名": tt_name_input, "時刻": dt.time(), "シーン選択": st.session_state.loop_scenes[idx % len(st.session_state.loop_scenes)], "繰り返し": g_rp})
                dt += timedelta(minutes=g_it); idx += 1
            st.session_state.t_df = pd.concat([st.session_state.t_df, pd.DataFrame(new_r)]).drop_duplicates().sort_values("時刻")

st.session_state.t_df["時刻"] = st.session_state.t_df["時刻"].apply(safe_to_time)
st.session_state.t_df = st.data_editor(st.session_state.t_df, column_config={
    "スケジュール名": st.column_config.TextColumn("スケジュール名", required=True),
    "時刻": st.column_config.TimeColumn("時刻", format="HH:mm"),
    "シーン選択": st.column_config.SelectboxColumn("シーン", options=current_opts),
    "繰り返し": st.column_config.SelectboxColumn("曜日", options=DAY_OPTIONS)
}, num_rows="dynamic", use_container_width=True)

st.subheader("📅 特異日設定")
with st.form("p_form", clear_on_submit=True):
    pn, pz = st.text_input("名称"), st.selectbox("対象ゾーン", options=vz if vz else ["なし"])
    # 特異日に割り当てるスケジュール名(AW列)を選択
    existing_tt_names = list(set(st.session_state.t_df["スケジュール名"].tolist()))
    ps_name = st.selectbox("適応スケジュール(AW列)", options=existing_tt_names if existing_tt_names else ["生成してください"])
    pc1, pc2 = st.columns(2); psd, ped = pc1.date_input("開始"), pc2.date_input("終了")
    if st.form_submit_button("特異日を追加"):
        if pz != "なし" and ps_name != "生成してください":
            st.session_state.p_list.append({"名": pn, "zn": pz, "sd": psd, "ed": ped, "sn": ps_name}); st.rerun()

# --- 4. 出力 ---
st.divider()
if st.button("📦 ゲートウェイ用 .tar を生成", type="primary", use_container_width=True):
    rows = [[""] * TOTAL_COLS for _ in range(1000)]
    # Zone/Group
    for i, z in enumerate(st.session_state.z_list): rows[i][0], rows[i][2] = z["名"], z["秒"]
    for i, g in enumerate(st.session_state.g_list): rows[i][4], rows[i][6], rows[i][7] = g["名"], GROUP_TYPES[g["型"]], g["ゾ"]
    # Scene
    for i, r in enumerate(st.session_state.s_list):
        p_val = f" {r['ex']}-{r['ey']}" if r['ex'] != "" else ""
        c_val = r['kel'] if r['ex'] == "" else ""
        rows[i][9], rows[i][11], rows[i][12], rows[i][13], rows[i][14], rows[i][15] = r["sn"], r["dim"], c_val, p_val, r["zn"], r["gn"]
    # Timetable (R列(17)にスケジュール名)
    idx_tt = 0
