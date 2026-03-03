import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time
import os

# --- 基本設定 ---
NUM_COLS = 73 
GROUP_TYPES = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
DAY_OPTIONS = ["毎日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

st.set_page_config(page_title="FitPlus Pro v8000", layout="wide")

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

# --- 店舗名入力 ---
st.title("FitPlus ⚙️ 統合設定ツール")
shop_name_input = st.text_input("🏢 店舗名（ファイル名になります）", "FitPlus_Project")

if st.sidebar.button("全データをクリア"):
    for k in ['z_list', 'g_list', 's_list', 'p_list', 'loop_scenes']: st.session_state[k] = []
    st.session_state.t_df = pd.DataFrame(columns=["時刻", "シーン選択", "繰り返し"])
    st.rerun()

st.divider()

# --- 1. ゾーン & グループ登録 ---
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

# --- 2. シーン作成 & 詳細履歴 ---
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
                    mode = st.radio("設定", ["パレット", "調色"], key=f"m_{g['名']}", horizontal=True)
                    if mode == "パレット":
                        cx, cy = st.columns(2)
                        ex, ey = cx.slider("X", 1, 11, 6, key=f"x_{g['名']}"), cy.slider("Y", 1, 11, 6, key=f"y_{g['名']}")
                    else: kel = st.text_input("K", "4000", key=f"ks_{g['名']}")
                elif g['型'] == "調光調色": kel = st.text_input("K", "4000", key=f"k_{g['名']}")
                scene_tmp.append({"sn": s_name_in, "gn": g['名'], "zn": s_zone_in, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
        if st.button("このシーンを保存"):
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name_in and s["zn"] == s_zone_in)]
            st.session_state.s_list.extend(scene_tmp); st.rerun()

with c_s_view:
    st.subheader("📜 シーン詳細履歴")
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

# --- 3. スケジュール & 特異日 ---
all_scene_opts = sorted(list(set([f"{s['sn']} [{s['zn']}]" for s in st.session_state.s_list])))
# シーンが一つもない場合のエラー回避
if not all_scene_opts: all_scene_opts = ["シーンを登録してください"]

with st.container(border=True):
    st.subheader("🔄 多段ループ生成")
    c_add, c_clear = st.columns([2, 1])
    new_scene = c_add.selectbox("順序に追加", options=all_scene_opts)
    if c_add.button("＋ 追加"):
        if "登録" not in new_scene: st.session_state.loop_scenes.append(new_scene); st.rerun()
    if c_clear.button("クリア"): st.session_state.loop_scenes = []; st.rerun()
    
    if st.session_state.loop_scenes:
        st.info(" ➔ ".join(st.session_state.loop_scenes))
        c1, c2, c3, c4 = st.columns(4)
        g_st, g_en = c1.time_input("始"), c2.time_input("終")
        g_it, g_rp = c3.number_input("分", 1, 1440, 8), c4.selectbox("曜", DAY_OPTIONS)
        if st.button("⏰ スケジュール生成", use_container_width=True):
            new_r = []
            dt, idx = datetime.combine(datetime.today(), g_st), 0
            while dt <= datetime.combine(datetime.today(), g_en) and len(new_r) < 300:
                new_r.append({"時刻": dt.time(), "シーン選択": st.session_state.loop_scenes[idx % len(st.session_state.loop_scenes)], "繰り返し": g_rp})
                dt += timedelta(minutes=g_it); idx += 1
            st.session_state.t_df = pd.concat([st.session_state.t_df, pd.DataFrame(new_r)]).drop_duplicates().sort_values("時刻")

st.session_state.t_df["時刻"] = st.session_state.t_df["時刻"].apply(safe_to_time)
st.session_state.t_df = st.data_editor(st.session_state.t_df, column_config={
    "時刻": st.column_config.TimeColumn("時刻", format="HH:mm"),
    "シーン選択": st.column_config.SelectboxColumn("シーン", options=all_scene_opts),
    "繰り返し": st.column_config.SelectboxColumn("曜日", options=DAY_OPTIONS)
}, num_rows="dynamic", use_container_width=True)

st.subheader("📅 特異日設定")
with st.form("p_form", clear_on_submit=True):
    pn, pz = st.text_input("特異日名"), st.selectbox("対象ゾーン", options=vz if vz else ["登録なし"])
    ps_opts = [s['sn'] for s in st.session_state.s_list if s['zn'] == pz] if st.session_state.s_list else []
    ps_name = st.selectbox("シーン(AW列)", options=list(set(ps_opts)) if ps_opts else ["登録なし"])
    pc1, pc2 = st.columns(2); psd, ped = pc1.date_input("開始"), pc2.date_input("終了")
    if st.form_submit_button("特異日保存"):
        if pz != "登録なし": st.session_state.p_list.append({"名": pn, "zn": pz, "sd": psd, "ed": ped, "sn": ps_name}); st.rerun()

# --- 4. 出力 (BOMなし・実データ重視版) ---
st.divider()
if st.button("📦 ゲートウェイ用 .tar を生成", type="primary", use_container_width=True):
    # 行数を必要最低限（実データ + 50行の予備）にする
    data_rows_count = max(len(st.session_state.z_list), len(st.session_state.g_list), len(st.session_state.s_list), 50)
    rows = [[""] * NUM_COLS for _ in range(data_rows_count)]
    
    # ゾーン・グループ
    for i, z in enumerate(st.session_state.z_list): rows[i][0], rows[i][1], rows[i][2] = z["名"], "", z["秒"]
    for i, g in enumerate(st.session_state.g_list): rows[i][4], rows[i][5], rows[i][6], rows[i][7] = g["名"], "", GROUP_TYPES[g["型"]], g["ゾ"]
    
    # シーン
    for i, r in enumerate(st.session_state.s_list):
        p_val = f" {r['ex']}-{r['ey']}" if r['ex'] != "" else ""
        c_val = r['kel'] if r['ex'] == "" else ""
        rows[i][9], rows[i][11], rows[i][12], rows[i][13], rows[i][15], rows[i][16] = r["sn"], r["dim"], c_val, p_val, r["zn"], r["gn"]
    
    # Timetable (分割出力)
    idx_tt = 0
    for z_name in vz:
        for rep in DAY_OPTIONS:
            slots = st.session_state.t_df[st.session_state.t_df["シーン選択"].str.contains(f"\[{z_name}\]", na=False) & (st.session_state.t_df["繰り返し"] == rep)].copy()
            if not slots.empty:
                slots = slots.sort_values("時刻")
                for chunk_idx in range(0, len(slots), 6):
                    chunk = slots.iloc[chunk_idx : chunk_idx + 6]
                    sn_main = chunk.iloc[0]["シーン選択"].split(" [")[0]
                    tt_name = sn_main if chunk_idx == 0 else f"{sn_main}_{chunk_idx//6 + 1}"
                    rows[idx_tt][18], rows[idx_tt][20] = tt_name, z_name
                    for j, (_, s) in enumerate(chunk.iterrows()):
                        rows[idx_tt][23 + j*2], rows[idx_tt][24 + j*2] = fmt_t(s["時刻"]), s["シーン選択"].split(" [")[0]
                    rep_idx = 36 if rep == "毎日" else 37 + DAY_OPTIONS.index(rep) - 1
                    rows[idx_tt][35], rows[idx_tt][rep_idx] = z_name, tt_name
                    idx_tt += 1

    # 特異日
    for i, p in enumerate(st.session_state.p_list):
        rows[i][45], rows[i][46], rows[i][47], rows[i][48], rows[i][49] = p["名"], fmt_d(p["sd"]), fmt_d(p["ed"]), p["sn"], p["zn"]

    def to_line(arr): return ",".join([str(x) for x in arr]) + "\r\n"
    h1 = ["Zone情報","","","","Group情報","","","","","Scene情報","","","","","","","","Timetable情報","","","","","","","","","","","","","","","","","","Timetable-schedule情報","","","","","","","","","","Timetable期間/特異日情報","","","","","","","","","","","","","","","","","","","","","","","","","",""]
    h3 = ['[zone]','[id]','[fade]','','[group]','[id]','[type]','[zone]','','[scene]','[id]','[dimming]','[color]','[perform]','[fresh-key]','[zone]','[group]','','[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]','[time]','[scene]','[time]','[scene]','[time]','[scene]','[time]','[scene]','[time]','[scene]','[time]','[scene]','[zone-ts]','[daily]','[monday]','[tuesday]','[wednesday]','[thursday]','[friday]','[saturday]','[sunday]','','[zone-period]','[start]','[end]','[timetable]','[zone]','','','','','','','','','','','','','','','','','','','','','','','']
    
    # BOMなしUTF-8。過剰なパディングを廃止
    csv_str = to_line(h1) + ("," * 72 + "\r\n") + to_line(h3)
    for r in rows: csv_str += to_line(r)

    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        csv_bytes = csv_str.encode("utf-8") # BOMなし
        c_info = tarfile.TarInfo(name="setting_data.csv"); c_info.size = len(csv_bytes); tar.addfile(c_info, io.BytesIO(csv_bytes))
        j_data = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8')
        j_info = tarfile.TarInfo(name="temp.json"); j_info.size = len(j_data); tar.addfile(j_info, io.BytesIO(j_data))

    fn = f"{shop_name_input.replace(' ', '_')}.tar"
    st.download_button(f"📥 {fn} を保存", tar_buf.getvalue(), fn)
