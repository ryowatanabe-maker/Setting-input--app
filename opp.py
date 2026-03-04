import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time

# --- 設定値 (赤池店モデル準拠) ---
TOTAL_COLS = 236
IDX_TT_NAME = 17     # R列
IDX_TT_ZONE = 19     # T列
IDX_TIME_START = 22  # W列
IDX_ZONE_TS = 197    # GS列
IDX_PERIOD_NAME = 207# IC列
IDX_PERIOD_START = 208# ID列
IDX_PERIOD_END = 209  # IE列
IDX_PERIOD_TT = 210  # IF列
IDX_PERIOD_ZONE = 211# IG列

GROUP_TYPES = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
DAY_OPTIONS = ["毎日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

st.set_page_config(page_title="FitPlus Pro v12000", layout="wide")

# セッション状態の初期化
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []
if 'p_list' not in st.session_state: st.session_state.p_list = []
if 'loop_scenes' not in st.session_state: st.session_state.loop_scenes = []
if 't_df' not in st.session_state:
    st.session_state.t_df = pd.DataFrame(columns=["スケジュール名", "時刻", "シーン選択", "繰り返し"])

def safe_to_time(val):
    if isinstance(val, time): return val
    s = str(val).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try: return datetime.strptime(s, fmt).time()
        except: continue
    return time(0, 0)

def fmt_t(t): return f"{t.hour}:{t.minute:02}"
def fmt_d(d): return f"{d.month}月{d.day}日"

# --- UI ---
st.title("FitPlus ⚙️ 統合設定ツール")
shop_name = st.text_input("🏢 店舗名（ファイル名になります）", "FitPlus_Project")

if st.sidebar.button("全データをリセット"):
    st.session_state.z_list = []
    st.session_state.g_list = []
    st.session_state.s_list = []
    st.session_state.p_list = []
    st.session_state.loop_scenes = []
    st.session_state.t_df = pd.DataFrame(columns=["スケジュール名", "時刻", "シーン選択", "繰り返し"])
    st.rerun()

# 1. 登録
st.header("1. ゾーン & グループ登録")
c1, c2 = st.columns(2)
vz = [z["名"] for z in st.session_state.z_list]
with c1:
    with st.container(border=True):
        zn, zf = st.text_input("ゾーン名"), st.number_input("フェード時間(秒)", 0, 3600, 0)
        if st.button("ゾーン保存") and zn:
            st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    with st.container(border=True):
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.button("グループ保存") and gn and gz:
            st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
with c2:
    st.write("📜 登録済み")
    for z in st.session_state.z_list: st.info(f"Z: {z['名']} ({z['秒']}s)")
    for g in st.session_state.g_list: st.success(f"G: {g['名']} ({g['型']})")

# 2. シーン作成
st.divider()
st.header("2. シーン作成")
sn_in = st.text_input("作成シーン名")
sz_in = st.selectbox("対象ゾーン選択", options=[""] + vz)

if sz_in:
    scene_tmp = []
    for g in [g for g in st.session_state.g_list if g["ゾ"] == sz_in]:
        with st.expander(f"💡 {g['名']} 設定"):
            dim = st.slider("調光%", 0, 100, 100, key=f"dim_{g['名']}")
            ex, ey, kel = "", "", "4000"
            if "Synca" in g['型']:
                m = st.radio("モード", ["パレット", "調色"], horizontal=True, key=f"m_{g['名']}")
                if m == "パレット":
                    ex, ey = st.slider("演出X", 1, 11, 6, key=f"x_{g['名']}"), st.slider("演出Y", 1, 11, 6, key=f"y_{g['名']}")
                else: kel = st.text_input("色温度(K)", "4000", key=f"ks_{g['名']}")
            elif g['型'] == "調光調色": kel = st.text_input("色温度(K)", "4000", key=f"k_{g['名']}")
            scene_tmp.append({"sn": sn_in, "gn": g['名'], "zn": sz_in, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
    if st.button("このシーンを保存"):
        st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == sn_in and s["zn"] == sz_in)]
        st.session_state.s_list.extend(scene_tmp); st.rerun()

# 3. スケジュール
st.divider()
st.header("3. スケジュール & 特異日")
all_scenes = sorted(list(set([f"{s['sn']} [{s['zn']}]" for s in st.session_state.s_list])))
current_scene_opts = all_scenes if all_scenes else ["(未登録)"]

tab1, tab2 = st.tabs(["シーンスケジュール", "特異日設定"])

with tab1:
    with st.expander("🔄 スケジュールを一括生成する (＋)"):
        tt_name_input = st.text_input("生成スケジュール名", "通常")
        sel_scene = st.selectbox("順序に追加", options=current_scene_opts)
        c_add, c_clear = st.columns([1, 1])
        if c_add.button("リストへ追加"):
            if "(未登録)" not in sel_scene: st.session_state.loop_scenes.append(sel_scene); st.rerun()
        if c_clear.button("順序をクリア"): st.session_state.loop_scenes = []; st.rerun()
        
        if st.session_state.loop_scenes:
            st.info("順序: " + " ➔ ".join(st.session_state.loop_scenes))
            ca, cb, cc = st.columns(3)
            g_st, g_en = ca.time_input("開始時刻", value=time(0,0)), cb.time_input("終了時刻", value=time(23,59))
            g_it = cc.number_input("間隔(分)", 1, 1440, 8)
            rep = st.selectbox("曜日指定", DAY_OPTIONS)
            if st.button("⏰ スケジュールを一括作成"):
                new_r = []
                dt, idx = datetime.combine(datetime.today(), g_st), 0
                while dt <= datetime.combine(datetime.today(), g_en) and len(new_r) < 80:
                    new_r.append({
                        "スケジュール名": str(tt_name_input),
                        "時刻": dt.time(),
                        "シーン選択": st.session_state.loop_scenes[idx % len(st.session_state.loop_scenes)],
                        "繰り返し": rep
                    })
                    dt += timedelta(minutes=g_it); idx += 1
                st.session_state.t_df = pd.concat([st.session_state.t_df, pd.DataFrame(new_r)]).drop_duplicates()
                st.rerun()

    st.write("**スケジュール表**")
    st.session_state.t_df["時刻"] = st.session_state.t_df["時刻"].apply(safe_to_time)
    # エラー防止のため型を強制
    st.session_state.t_df["スケジュール名"] = st.session_state.t_df["スケジュール名"].astype(str)
    
    st.session_state.t_df = st.data_editor(
        st.session_state.t_df,
        column_config={
            "スケジュール名": st.column_config.TextColumn("名前", required=True),
            "時刻": st.column_config.TimeColumn("時刻", format="HH:mm", required=True),
            "シーン選択": st.column_config.SelectboxColumn("シーン選択", options=current_scene_opts, required=True),
            "繰り返し": st.column_config.SelectboxColumn("繰り返し", options=DAY_OPTIONS, required=True)
        },
        num_rows="dynamic", use_container_width=True
    )

with tab2:
    with st.form("period_form", clear_on_submit=True):
        pn = st.text_input("特異日名称")
        pz = st.selectbox("対象ゾーン", options=vz)
        existing_tt = list(set(st.session_state.t_df["スケジュール名"].tolist()))
        ps_name = st.selectbox("適応スケジュール名", options=existing_tt if existing_tt else ["なし"])
        pc1, pc2 = st.columns(2)
        psd, ped = pc1.date_input("開始日"), pc2.date_input("終了日")
        if st.form_submit_button("特異日を追加"):
            if pz and ps_name != "なし":
                st.session_state.p_list.append({"名": pn, "zn": pz, "sd": psd, "ed": ped, "sn": ps_name})
                st.rerun()
    for i, p in enumerate(st.session_state.p_list):
        st.write(f"📅 {p['名']}: {p['sd']}~{p['ed']} ({p['zn']}->{p['sn']})")
        if st.button("削除", key=f"del_p_{i}"):
            st.session_state.p_list.pop(i); st.rerun()

# 4. 出力
st.divider()
if st.button("📦 ゲートウェイ用 .tar を生成", type="primary", use_container_width=True):
    rows = [[""] * TOTAL_COLS for _ in range(1000)]
    for i, z in enumerate(st.session_state.z_list): rows[i][0], rows[i][2] = z["名"], z["秒"]
    for i, g in enumerate(st.session_state.g_list): rows[i][4], rows[i][6], rows[i][7] = g["名"], GROUP_TYPES[g["型"]], g["ゾ"]
    for i, r in enumerate(st.session_state.s_list):
        p_val = f" {r['ex']}-{r['ey']}" if r['ex'] != "" else ""
        c_val = r['kel'] if r['ex'] == "" else ""
        rows[i][9], rows[i][11], rows[i][12], rows[i][13], rows[i][14], rows[i][15] = r["sn"], r["dim"], c_val, p_val, r["zn"], r["gn"]
    
    idx_tt = 0
    grouped = st.session_state.t_df.groupby(["スケジュール名", "繰り返し"])
    for (name, rep), data in grouped:
        z_match = [z for z in vz if f"[{z}]" in data.iloc[0]["シーン選択"]]
        if z_match:
            rows[idx_tt][IDX_TT_NAME], rows[idx_tt][IDX_TT_ZONE] = name, z_match[0]
            for j, (_, s) in enumerate(data.sort_values("時刻").iterrows()):
                col = IDX_TIME_START + j*2
                if col + 1 < IDX_ZONE_TS:
                    rows[idx_tt][col], rows[idx_tt][col+1] = fmt_t(s["時刻"]), s["シーン選択"].split(" [")[0]
            rows[idx_tt][IDX_ZONE_TS] = z_match[0]
            day_idx = 0 if rep == "毎日" else DAY_OPTIONS.index(rep)
            rows[idx_tt][IDX_ZONE_TS + 1 + day_idx] = name
            idx_tt += 1

    for i, p in enumerate(st.session_state.p_list):
        rows[i][IDX_PERIOD_NAME], rows[i][IDX_PERIOD_START], rows[i][IDX_PERIOD_END], rows[i][IDX_PERIOD_TT], rows[i][IDX_PERIOD_ZONE] = p["名"], fmt_d(p["sd"]), fmt_d(p["ed"]), p["sn"], p["zn"]

    def to_line(arr): return ",".join([str(x) for x in arr]) + "\r\n"
    h1 = ["Zone情報","","","","Group情報","","","","","Scene情報","","","","","","","","Timetable情報"] + [""]*(IDX_ZONE_TS-18) + ["Timetable-schedule情報"] + [""]*9 + ["Timetable期間/特異日情報"]
    h3 = ['[zone]','[id]','[fade]','','[group]','[id]','[type]','[zone]','','[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]','','[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]']
    for _ in range(87): h3 += ['[time]','[scene]']
    h3 += ['[zone-ts]','[daily]','[monday]','[tuesday]','[wednesday]','[thursday]','[friday]','[saturday]','[sunday]','','[zone-period]','[start]','[end]','[timetable]','[zone]']
    csv_str = to_line(h1 + [""]*(TOTAL_COLS - len(h1))) + ("," * (TOTAL_COLS-1) + "\r\n") + to_line(h3 + [""]*(TOTAL_COLS - len(h3)))
    for r in rows: csv_str += to_line(r)

    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        csv_bytes = csv_str.encode("utf-8-sig")
        info = tarfile.TarInfo(name="setting_data.csv"); info.size = len(csv_bytes); tar.addfile(info, io.BytesIO(csv_bytes))
        j_data = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8')
        info_j = tarfile.TarInfo(name="temp.json"); info_j.size = len(j_data); tar.addfile(info_j, io.BytesIO(j_data))
    st.download_button(f"📥 {shop_name}.tar を保存", tar_buf.getvalue(), f"{shop_name}.tar")
