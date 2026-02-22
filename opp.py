import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time
import os

# --- 1. 定数設定 (赤池店モデル: 約230列構成) ---
# スケジュールスロットを90件(180列分)確保
NUM_SLOTS = 90
COL_ZONE_TS = 22 + (NUM_SLOTS * 2) # [zone-ts] の開始位置
COL_PERIOD = COL_ZONE_TS + 10      # [zone-period] の開始位置
TOTAL_COLS = COL_PERIOD + 10       # 余裕を持たせた総列数

GROUP_TYPES = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
DAY_OPTIONS = ["毎日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

st.set_page_config(page_title="FitPlus Pro v5000", layout="wide")

# セッション状態の初期化
for k in ['z_list', 'g_list', 's_list', 't_df', 'p_list', 'loop_scenes']:
    if k not in st.session_state:
        if k == 't_df': st.session_state[k] = pd.DataFrame(columns=["時刻", "シーン選択", "繰り返し"])
        else: st.session_state[k] = []

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
st.title("FitPlus ⚙️ 統合設定ツール (赤池店モデル対応)")
shop_name_input = st.text_input("🏢 店舗名を入力してください（ファイル名になります）", "FitPlus_Project")

if st.sidebar.button("全データをクリア"):
    for k in ['z_list', 'g_list', 's_list', 'p_list', 'loop_scenes']: st.session_state[k] = []
    st.session_state.t_df = pd.DataFrame(columns=["時刻", "シーン選択", "繰り返し"])
    st.rerun()

st.divider()

# --- 1. ゾーン & グループ登録 ---
st.header("1. ゾーン & グループ登録")
c_reg, c_view = st.columns([1, 1])
vz = [z["名"] for z in st.session_state.z_list]

with c_reg:
    with st.container(border=True):
        st.write("**ゾーン追加**")
        zn, zf = st.text_input("ゾーン名"), st.number_input("フェード時間(秒)", 0, 3600, 0)
        if st.button("ゾーンを保存"):
            if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    with st.container(border=True):
        st.write("**グループ追加**")
        gn, gt = st.text_input("グループ名"), st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.button("グループを保存"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()

with c_view:
    st.subheader("📜 登録済み履歴")
    for i, z in enumerate(st.session_state.z_list):
        cc1, cc2 = st.columns([4, 1]); cc1.info(f"ゾーン: {z['名']} / フェード:{z['秒']}秒")
        if cc2.button("削除", key=f"dz_{i}"): st.session_state.z_list.pop(i); st.rerun()
    for i, g in enumerate(st.session_state.g_list):
        cc1, cc2 = st.columns([4, 1]); cc1.success(f"グループ: {g['名']} / タイプ:{g['型']}")
        if cc2.button("削除", key=f"dg_{i}"): st.session_state.g_list.pop(i); st.rerun()

st.divider()

# --- 2. シーン作成 & 詳細履歴 ---
st.header("2. シーン作成 & 詳細確認")
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
                        ex, ey = cx.slider("X", 1, 11, 6, key=f"x_{g['名']}"), cy.slider("Y", 1, 11, 6, key=f"y_{g['名']}")
                    else: kel = st.text_input("色温度", "4000", key=f"ks_{g['名']}")
                elif g['型'] == "調光調色": kel = st.text_input("色温度", "4000", key=f"k_{g['名']}")
                scene_tmp.append({"sn": s_name_in, "gn": g['名'], "zn": s_zone_in, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
        if st.button("このシーンを保存"):
            if s_name_in:
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name_in and s["zn"] == s_zone_in)]
                st.session_state.s_list.extend(scene_tmp); st.rerun()

with c_s_view:
    st.subheader("📜 シーン詳細履歴")
    if st.session_state.s_list:
        h_df_view = pd.DataFrame(st.session_state.s_list)
        for (sn, zn), group_data in h_df_view.groupby(['sn', 'zn']):
            with st.expander(f"➕ {sn} ({zn})"):
                for _, row in group_data.iterrows():
                    c_info = f"{row['ex']}-{row['ey']} (パレット)" if row['ex'] != "" else f"{row['kel']}K"
                    st.write(f"・{row['gn']}: {row['dim']}% / {c_info}")
                if st.button("削除", key=f"ds_{sn}_{zn}"):
                    st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == sn and s["zn"] == zn)]; st.rerun()

st.divider()

# --- 3. スケジュール & 特異日 ---
st.header("3. スケジュール & 特異日設定")
all_scene_opts = sorted(list(set([f"{s['sn']} [{s['zn']}]" for s in st.session_state.s_list]))) if st.session_state.s_list else []

if all_scene_opts:
    with st.container(border=True):
        st.subheader("🔄 多段ループ生成")
        c_add, c_clear = st.columns([2, 1])
        new_scene = c_add.selectbox("順序に追加", options=all_scene_opts)
        if c_add.button("＋ 追加"):
            st.session_state.loop_scenes.append(new_scene); st.rerun()
        if c_clear.button("クリア"):
            st.session_state.loop_scenes = []; st.rerun()
        
        if st.session_state.loop_scenes:
            st.info("順序: " + " ➔ ".join(st.session_state.loop_scenes))
            c1, c2, c3, c4 = st.columns(4)
            g_st, g_en = c1.time_input("開始", value=time(0, 0)), c2.time_input("終了", value=time(23, 59))
            g_it, g_rp = c3.number_input("間隔(分)", 1, 1440, 8), c4.selectbox("曜日", DAY_OPTIONS)
            if st.button("⏰ 一括生成", use_container_width=True):
                new_r = []
                dt, idx = datetime.combine(datetime.today(), g_st), 0
                while dt <= datetime.combine(datetime.today(), g_en) and len(new_r) < NUM_SLOTS:
                    new_r.append({"時刻": dt.time(), "シーン選択": st.session_state.loop_scenes[idx % len(st.session_state.loop_scenes)], "繰り返し": g_rp})
                    dt += timedelta(minutes=g_it); idx += 1
                st.session_state.t_df = pd.concat([st.session_state.t_df, pd.DataFrame(new_r)]).drop_duplicates().sort_values("時刻")

    st.session_state.t_df["時刻"] = st.session_state.t_df["時刻"].apply(safe_to_time)
    st.session_state.t_df = st.data_editor(st.session_state.t_df, column_config={
        "時刻": st.column_config.TimeColumn("時刻", format="HH:mm", required=True),
        "シーン選択": st.column_config.SelectboxColumn("シーン", options=all_scene_opts, required=True),
        "繰り返し": st.column_config.SelectboxColumn("曜日", options=DAY_OPTIONS, required=True)
    }, num_rows="dynamic", use_container_width=True)

    st.divider()
    st.subheader("📅 特異日設定")
    with st.form("p_form", clear_on_submit=True):
        pn, pz = st.text_input("名称"), st.selectbox("対象ゾーン", options=vz)
        ps_opts = [s['sn'] for s in st.session_state.s_list if s['zn'] == pz]
        ps_name = st.selectbox("適応シーン", options=list(set(ps_opts)))
        pc1, pc2 = st.columns(2); psd, ped = pc1.date_input("開始"), pc2.date_input("終了")
        if st.form_submit_button("特異日を保存"):
            st.session_state.p_list.append({"名": pn, "zn": pz, "sd": psd, "ed": ped, "sn": ps_name}); st.rerun()

# --- 4. 出力 (赤池店モデル再現) ---
st.divider()
if st.button("📦 ゲートウェイ用 .tar を生成", type="primary", use_container_width=True):
    rows = [[""] * TOTAL_COLS for _ in range(1000)]
    
    # Zone/Group
    for i, z in enumerate(st.session_state.z_list): rows[i][0], rows[i][1], rows[i][2] = z["名"], "", z["秒"]
    for i, g in enumerate(st.session_state.g_list): rows[i][4], rows[i][5], rows[i][6], rows[i][7] = g["名"], "", GROUP_TYPES[g["型"]], g["ゾ"]
    
    # Scene (パレットはN列 index 13 に先頭スペース付き)
    for i, r in enumerate(st.session_state.s_list):
        if r['ex'] != "":
            palette_val = f" {r['ex']}-{r['ey']}"
            rows[i][9], rows[i][11], rows[i][12], rows[i][13], rows[i][14], rows[i][15] = r["sn"], r["dim"], "", palette_val, r["zn"], r["gn"]
        else:
            rows[i][9], rows[i][11], rows[i][12], rows[i][13], rows[i][14], rows[i][15] = r["sn"], r["dim"], r["kel"], "", r["zn"], r["gn"]
    
    # Timetable
    idx_tt = 0
    for z_name in vz:
        for rep in DAY_OPTIONS:
            slots = st.session_state.t_df[st.session_state.t_df["シーン選択"].str.contains(f"\[{z_name}\]", na=False) & (st.session_state.t_df["繰り返し"] == rep)].copy()
            if not slots.empty:
                slots = slots.sort_values("時刻")
                sn_main = slots.iloc[0]["シーン選択"].split(" [")[0]
                rows[idx_tt][17], rows[idx_tt][19] = sn_main, z_name
                for j, (_, s) in enumerate(slots.iterrows()):
                    col_base = 22 + j*2
                    if col_base + 1 < COL_ZONE_TS:
                        rows[idx_tt][col_base], rows[idx_tt][col_base + 1] = fmt_t(s["時刻"]), s["シーン選択"].split(" [")[0]
                
                rows[idx_tt][COL_ZONE_TS] = z_name
                day_offset = 1 if rep == "毎日" else 2 + DAY_OPTIONS.index(rep) - 1
                rows[idx_tt][COL_ZONE_TS + day_offset] = sn_main
                idx_tt += 1

    # 特異日 (AW列相当の COL_PERIOD + 3 にシーン名)
    for i, p in enumerate(st.session_state.p_list):
        rows[i][COL_PERIOD], rows[i][COL_PERIOD+1], rows[i][COL_PERIOD+2], rows[i][COL_PERIOD+3], rows[i][COL_PERIOD+4] = p["名"], fmt_d(p["sd"]), fmt_d(p["ed"]), p["sn"], p["zn"]

    # ヘッダー構築 (赤池店の位置関係を再現)
    def to_line(arr): return ",".join([str(x) for x in arr]) + "\r\n"
    h0 = ["Zone情報","","","","Group情報","","","","","Scene情報","","","","","","","","Timetable情報"] + [""]*(COL_ZONE_TS-18) + ["Timetable-schedule情報"] + [""]*9 + ["Timetable期間/特異日情報"]
    h2 = ['[zone]','[id]','[fade]','','[group]','[id]','[type]','[zone]','','[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]','','[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]']
    for _ in range(NUM_SLOTS): h2 += ['[time]','[scene]']
    h2 += ['[zone-ts]','[daily]','[monday]','[tuesday]','[wednesday]','[thursday]','[friday]','[saturday]','[sunday]','','[zone-period]','[start]','[end]','[timetable]','[zone]']
    
    csv_str = to_line(h0 + [""]*(TOTAL_COLS - len(h0))) + ","*(TOTAL_COLS-1) + "\r\n" + to_line(h2 + [""]*(TOTAL_COLS - len(h2)))
    for r in rows: csv_str += to_line(r)

    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        csv_bytes = csv_str.encode("utf-8-sig")
        c_info = tarfile.TarInfo(name="setting_data.csv"); c_info.size = len(csv_bytes); tar.addfile(c_info, io.BytesIO(csv_bytes))
        j_data = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8')
        j_info = tarfile.TarInfo(name="temp.json"); j_info.size = len(j_data); tar.addfile(j_info, io.BytesIO(j_data))

    fn = f"{shop_name_input.replace(' ', '_')}.tar"
    st.download_button(f"📥 {fn} を保存", tar_buf.getvalue(), fn)
