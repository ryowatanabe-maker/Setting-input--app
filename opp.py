import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time
import os

# --- 1. 定数設定 ---
NUM_COLS = 73 
GROUP_TYPES = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
DAY_OPTIONS = ["毎日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

st.set_page_config(page_title="FitPlus Pro v3000", layout="wide")

# セッション状態の保持
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []
if 't_df' not in st.session_state:
    st.session_state.t_df = pd.DataFrame(columns=["時刻", "シーン選択", "繰り返し"])
if 'loop_scenes' not in st.session_state: st.session_state.loop_scenes = []

def safe_to_time(val):
    if isinstance(val, time): return val
    s = str(val).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try: return datetime.strptime(s, fmt).time()
        except: continue
    return time(0, 0)

def fmt_t(t): return f"{t.hour}:{t.minute:02}"

# --- 店舗名入力 ---
st.title("FitPlus ⚙️ 統合設定ツール")
shop_name = st.text_input("🏢 店舗名を入力（ファイル名になります）", "FitPlus_Project")

if st.sidebar.button("データを全リセット"):
    for k in ['z_list', 'g_list', 's_list', 'loop_scenes']: st.session_state[k] = []
    st.session_state.t_df = pd.DataFrame(columns=["時刻", "シーン選択", "繰り返し"])
    st.rerun()

st.divider()

# --- 1. 登録 ---
st.header("1. ゾーン & グループ登録")
c_reg, c_view = st.columns([1, 1])
vz = [z["名"] for z in st.session_state.z_list]

with c_reg:
    with st.container(border=True):
        st.write("**ゾーン追加**")
        zn, zf = st.text_input("ゾーン名"), st.number_input("フェード(秒)", 0, 3600, 0)
        if st.button("ゾーンを保存"):
            if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
        st.divider()
        st.write("**グループ追加**")
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.button("グループを保存"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()

with c_view:
    st.subheader("📜 登録済み")
    for i, z in enumerate(st.session_state.z_list):
        cc1, cc2 = st.columns([4, 1]); cc1.info(f"ゾーン: {z['名']}")
        if cc2.button("削除", key=f"dz_{i}"): st.session_state.z_list.pop(i); st.rerun()
    for i, g in enumerate(st.session_state.g_list):
        cc1, cc2 = st.columns([4, 1]); cc1.success(f"グループ: {g['名']}")
        if cc2.button("削除", key=f"dg_{i}"): st.session_state.g_list.pop(i); st.rerun()

st.divider()

# --- 2. シーン作成 ---
st.header("2. シーン作成 & 履歴")
if os.path.exists("synca_palette.png"): st.image("synca_palette.png", width=400)
c_s_reg, c_s_view = st.columns([1, 1])

with c_s_reg:
    s_name_in = st.text_input("シーン名")
    s_zone_in = st.selectbox("対象ゾーン", options=[""] + vz)
    if s_zone_in:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone_in]
        scene_tmp = []
        for g in target_gs:
            with st.expander(f"⚙️ {g['名']} 設定"):
                dim = st.slider("調光%", 0, 100, 100, key=f"d_{g['名']}_{s_name_in}")
                ex, ey, kel = "", "", "4000"
                if "Synca" in g['型']:
                    mode = st.radio("設定方法", ["パレット(6-6)", "調色"], key=f"m_{g['名']}", horizontal=True)
                    if mode == "パレット(6-6)":
                        cx, cy = st.columns(2)
                        ex, ey = cx.slider("X", 1, 11, 6, key=f"x_{g['名']}"), cy.slider("Y", 1, 11, 6, key=f"y_{g['名']}")
                    else: kel = st.text_input("K", "4000", key=f"ks_{g['名']}")
                elif g['型'] == "調光調色": kel = st.text_input("K", "4000", key=f"k_{g['名']}")
                scene_tmp.append({"sn": s_name_in, "gn": g['名'], "zn": s_zone_in, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
        if st.button("このシーンを保存"):
            if s_name_in:
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name_in and s["zn"] == s_zone_in)]
                st.session_state.s_list.extend(scene_tmp); st.rerun()

with c_s_view:
    st.subheader("📜 シーン履歴削除")
    if st.session_state.s_list:
        for (sn, zn), group in pd.DataFrame(st.session_state.s_list).groupby(['sn', 'zn']):
            with st.container(border=True):
                st.write(f"**{sn}** ({zn})")
                if st.button("削除", key=f"ds_{sn}_{zn}"):
                    st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == sn and s["zn"] == zn)]; st.rerun()

st.divider()

# --- 3. スケジュール ---
st.header("3. 多段ループスケジュール生成")
all_scene_opts = sorted(list(set([f"{s['sn']} [{s['zn']}]" for s in st.session_state.s_list])))
if all_scene_opts:
    with st.container(border=True):
        st.subheader("🔄 ループ設定")
        c_add, c_clear = st.columns([2, 1])
        new_scene = c_add.selectbox("順番に追加", options=all_scene_opts)
        if c_add.button("＋ 追加"):
            st.session_state.loop_scenes.append(new_scene); st.rerun()
        if c_clear.button("クリア"):
            st.session_state.loop_scenes = []; st.rerun()
        
        if st.session_state.loop_scenes:
            st.info("順序: " + " ➔ ".join(st.session_state.loop_scenes))
            c1, c2, c3, c4 = st.columns(4)
            g_st, g_en = c1.time_input("開始"), c2.time_input("終了")
            g_it, g_rp = c3.number_input("間隔(分)", 1, 120, 8), c4.selectbox("曜日", DAY_OPTIONS)
            if st.button("⏰ スケジュールを一括生成", use_container_width=True):
                new_r = []
                dt, idx = datetime.combine(datetime.today(), g_st), 0
                loop_len = len(st.session_state.loop_scenes)
                while dt <= datetime.combine(datetime.today(), g_en) and len(new_r) < 100:
                    new_r.append({"時刻": dt.time(), "シーン選択": st.session_state.loop_scenes[idx % loop_len], "繰り返し": g_rp})
                    dt += timedelta(minutes=g_it); idx += 1
                st.session_state.t_df = pd.concat([st.session_state.t_df, pd.DataFrame(new_r)]).drop_duplicates().sort_values("時刻")

    st.session_state.t_df["時刻"] = st.session_state.t_df["時刻"].apply(safe_to_time)
    # プルダウンを確実に表示させる設定
    st.session_state.t_df = st.data_editor(
        st.session_state.t_df,
        column_config={
            "時刻": st.column_config.TimeColumn("時刻", format="HH:mm", required=True),
            "シーン選択": st.column_config.SelectboxColumn("シーン選択", options=all_scene_opts, required=True),
            "繰り返し": st.column_config.SelectboxColumn("曜日", options=DAY_OPTIONS, required=True)
        },
        num_rows="dynamic", use_container_width=True
    )

# --- 4. 出力 (引用符なし・ID/Perform空欄・1000行パディング) ---
st.divider()
if st.button("📦 ゲートウェイ用設定ファイルを生成", type="primary", use_container_width=True):
    rows = [[""] * NUM_COLS for _ in range(1000)]
    for i, z in enumerate(st.session_state.z_list): rows[i][0], rows[i][1], rows[i][2] = z["名"], "", z["秒"]
    for i, g in enumerate(st.session_state.g_list): rows[i][4], rows[i][5], rows[i][6], rows[i][7] = g["名"], "", GROUP_TYPES[g["型"]], g["ゾ"]
    for i, r in enumerate(st.session_state.s_list):
        # 6-6問題対策：末尾にスペース2つ。Excelの日付変換を無効化し、ゲートウェイでは無視される形式
        color_val = f"{r['ex']}-{r['ey']}  " if r['ex'] != "" else r['kel']
        rows[i][9], rows[i][10], rows[i][11], rows[i][12], rows[i][13], rows[i][15], rows[i][16] = r["sn"], "", r["dim"], color_val, "", r["zn"], r["gn"]
    
    idx_tt = 0
    for z_name in vz:
        for rep in DAY_OPTIONS:
            slots = st.session_state.t_df[st.session_state.t_df["シーン選択"].str.contains(f"\[{z_name}\]", na=False) & (st.session_state.t_df["繰り返し"] == rep)].copy()
            if not slots.empty:
                slots = slots.sort_values("時刻")
                sn_main = slots.iloc[0]["シーン選択"].split(" [")[0]
                rows[idx_tt][18], rows[idx_tt][19], rows[idx_tt][20] = sn_main, "", z_name
                for j, (_, s) in enumerate(slots.head(6).iterrows()):
                    rows[idx_tt][23 + j*2], rows[idx_tt][24 + j*2] = fmt_t(s["時刻"]), s["シーン選択"].split(" [")[0]
                rows[idx_tt][35] = z_name
                rep_c = 36 if rep == "毎日" else 37 + DAY_OPTIONS.index(rep) - 1
                rows[idx_tt][rep_c] = sn_main; idx_tt += 1

    h0 = [""] * NUM_COLS
    h0[0], h0[4], h0[9], h0[17], h0[35], h0[45] = 'Zone情報','Group情報','Scene情報','Timetable情報','Timetable-schedule情報','Timetable期間/特異日情報'
    h2 = [""] * NUM_COLS
    h2[0:3], h2[4:8], h2[9:17], h2[18:23], h2[35:44], h2[45:50] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]'], ['[scene]','[id]','[dimming]','[color]','[perform]','[fresh-key]','[zone]','[group]'], ['[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]'], ['[zone-ts]','[daily]','[monday]','[tuesday]','[wednesday]','[thursday]','[friday]','[saturday]','[sunday]'], ['[zone-period]','[start]','[end]','[timetable]','[zone]']
    for j in range(23, 34, 2): h2[j], h2[j+1] = '[time]','[scene]'

    def to_line(arr): return ",".join([str(x) for x in arr]) + "\r\n"
    csv_str = to_line(h0) + ("," * (NUM_COLS - 1)) + "\r\n" + to_line(h2)
    for r in rows: csv_str += to_line(r)

    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        csv_bytes = csv_str.encode("utf-8-sig")
        c_info = tarfile.TarInfo(name="setting_data.csv"); c_info.size = len(csv_bytes); tar.addfile(c_info, io.BytesIO(csv_bytes))
        j_data = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8')
        j_info = tarfile.TarInfo(name="temp.json"); j_info.size = len(j_data); tar.addfile(j_info, io.BytesIO(j_data))

    final_fn = f"{shop_name.replace(' ', '_')}.tar"
    st.download_button(f"📥 {final_fn} を保存", tar_buf.getvalue(), final_fn)
