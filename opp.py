import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time

# --- 赤池店モデル (236列) 再現設定 ---
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
DAY_OPTIONS = ["(空白)", "毎日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

st.set_page_config(page_title="FitPlus Pro v17000", layout="wide")

# セッション状態の初期化
for k in ['z_list', 'g_list', 's_list', 'p_list', 'loop_scenes']:
    if k not in st.session_state: st.session_state[k] = []
if 't_df' not in st.session_state:
    # 初期状態で0:00の行を持たせる、または型を定義
    st.session_state.t_df = pd.DataFrame([
        {"スケジュール名": "通常", "時刻": time(0, 0), "シーン選択": "(未登録)", "繰り返し": "毎日"}
    ])

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
shop_name = st.text_input("🏢 店舗名を入力", "FitPlus_Project")

if st.sidebar.button("データをリセット"):
    st.session_state.clear()
    st.rerun()

# 1. ゾーン & グループ
st.header("1. ゾーン & グループ登録・修正")
c1, c2 = st.columns(2)
vz = [z["名"] for z in st.session_state.z_list]

with c1:
    with st.container(border=True):
        st.write("**ゾーン設定**")
        zn = st.text_input("ゾーン名")
        zf = st.number_input("フェード時間(秒)", 0, 3600, 0)
        if st.button("ゾーン保存") and zn:
            st.session_state.z_list = [z for z in st.session_state.z_list if z["名"] != zn]
            st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    with st.container(border=True):
        st.write("**グループ設定**")
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.button("グループ保存") and gn and gz:
            st.session_state.g_list = [g for g in st.session_state.g_list if g["名"] != gn]
            st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
with c2:
    st.write("📜 登録履歴")
    for z in st.session_state.z_list: st.info(f"ゾーン: {z['名']} ({z['秒']}s)")
    for g in st.session_state.g_list: st.success(f"グループ: {g['名']} (所属: {g['ゾ']})")

# 2. シーン作成
st.divider()
st.header("2. シーン作成・修正")
c_s1, c_s2 = st.columns(2)
with c_s1:
    sn_in, sz_in = st.text_input("作成シーン名"), st.selectbox("対象ゾーン選択", options=[""] + vz)
    if sz_in:
        scene_tmp = []
        for g in [g for g in st.session_state.g_list if g["ゾ"] == sz_in]:
            with st.expander(f"💡 {g['名']}"):
                dim = st.slider("調光%", 0, 100, 100, key=f"d_{g['名']}")
                ex, ey, kel = "", "", "4000"
                if "Synca" in g['型']:
                    m = st.radio("設定", ["パレット", "調色"], horizontal=True, key=f"m_{g['名']}")
                    if m == "パレット":
                        ex, ey = st.slider("X", 1, 11, 6, key=f"x_{g['名']}"), st.slider("Y", 1, 11, 6, key=f"y_{g['名']}")
                    else: kel = st.text_input("色温度", "4000", key=f"ks_{g['名']}")
                elif g['型'] == "調光調色": kel = st.text_input("色温度", "4000", key=f"k_{g['名']}")
                scene_tmp.append({"sn": sn_in, "gn": g['名'], "zn": sz_in, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
        if st.button("このシーンを保存"):
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == sn_in and s["zn"] == sz_in)]
            st.session_state.s_list.extend(scene_tmp); st.rerun()
with c_s2:
    if st.session_state.s_list:
        h_df = pd.DataFrame(st.session_state.s_list)
        for (sn, zn), data in h_df.groupby(['sn', 'zn']):
            with st.expander(f"＋ {sn} ({zn})"):
                for _, r in data.iterrows():
                    c_info = f" {r['ex']}-{r['ey']}" if r['ex'] != "" else f"{r['kel']}K"
                    st.write(f"・{r['gn']}: {r['dim']}% / {c_info}")
                if st.button("削除", key=f"ds_{sn}_{zn}"):
                    st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == sn and s["zn"] == zn)]; st.rerun()

# 3. スケジュール
st.divider()
st.header("3. スケジュール & 特異日")
all_scenes = sorted(list(set([f"{s['sn']} [{s['zn']}]" for s in st.session_state.s_list])))
current_scene_opts = all_scenes if all_scenes else ["(未登録)"]

with st.expander("🔄 スケジュールを一括生成する場合 (＋)"):
    tt_name_input = st.text_input("生成名", "通常")
    sel_scene = st.selectbox("追加シーン", options=current_scene_opts)
    if st.button("リストへ追加") and "(未登録)" not in sel_scene:
        st.session_state.loop_scenes.append(sel_scene); st.rerun()
    if st.button("クリア"): st.session_state.loop_scenes = []; st.rerun()
    if st.session_state.loop_scenes:
        st.info("順序: " + " ➔ ".join(st.session_state.loop_scenes))
        ca, cb, cc = st.columns(3)
        g_en, g_it = ca.time_input("終了時刻まで埋める", value=time(23,59)), cb.number_input("間隔(分)", 1, 1440, 8)
        rep_loop = cc.selectbox("繰り返し指定", DAY_OPTIONS, index=1)
        if st.button("⏰ 0:00から一括生成"):
            new_r = []
            dt, idx = datetime.combine(datetime.today(), time(0, 0)), 0
            while dt <= datetime.combine(datetime.today(), g_en) and len(new_r) < 85:
                new_r.append({"スケジュール名": str(tt_name_input), "時刻": dt.time(), "シーン選択": st.session_state.loop_scenes[idx % len(st.session_state.loop_scenes)], "繰り返し": rep_loop})
                dt += timedelta(minutes=g_it); idx += 1
            st.session_state.t_df = pd.concat([st.session_state.t_df, pd.DataFrame(new_r)]).drop_duplicates(); st.rerun()

st.write("**シーンスケジュール (0:00から開始してください)**")
st.session_state.t_df["時刻"] = st.session_state.t_df["時刻"].apply(safe_to_time)
# data_editorで「行追加」した時のデフォルト値を設定
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

st.subheader("📅 特異日(期間)設定")
with st.form("p_form", clear_on_submit=True):
    pn = st.text_input("特異日名称")
    exist_tt = sorted(list(set(st.session_state.t_df["スケジュール名"].astype(str).tolist())))
    ps_name = st.selectbox("適応スケジュール", options=exist_tt if exist_tt else ["なし"])
    pc1, pc2 = st.columns(2); psd, ped = pc1.date_input("開始日"), pc2.date_input("終了日")
    if st.form_submit_button("特異日を追加"):
        if ps_name != "なし":
            match_data = st.session_state.t_df[st.session_state.t_df["スケジュール名"] == ps_name]
            if not match_data.empty:
                found_zone = next((z for z in vz if f"[{z}]" in str(match_data.iloc[0]["シーン選択"])), "")
                st.session_state.p_list.append({"名": pn, "zn": found_zone, "sd": psd, "ed": ped, "sn": ps_name}); st.rerun()
for p in st.session_state.p_list:
    st.write(f"📅 {p['名']} ({p['sd']}~{p['ed']}) -> {p['sn']} ({p['zn']})")

# 4. 出力
st.divider()
if st.button("📦 ゲートウェイ用 .tar を生成", type="primary", use_container_width=True):
    rows = [[""] * TOTAL_COLS for _ in range(1000)]
    for i, z in enumerate(st.session_state.z_list): rows[i][0], rows[i][2] = z["名"], z["秒"]
    for i, g in enumerate(st.session_state.g_list): rows[i][4], rows[i][6], rows[i][7] = g["名"], GROUP_TYPES[g["型"]], g["ゾ"]
    for i, r in enumerate(st.session_state.s_list):
        p_val, c_val = (f" {r['ex']}-{r['ey']}", "") if r['ex'] != "" else ("", r['kel'])
        rows[i][9], rows[i][11], rows[i][12], rows[i][13], rows[i][14], rows[i][15] = r["sn"], r["dim"], c_val, p_val, r["zn"], r["gn"]
    
    idx_tt = 0
    grouped = st.session_state.t_df.groupby(["スケジュール名", "繰り返し"])
    for (name, rep), data in grouped:
        z_match = [z for z in vz if f"[{z}]" in str(data.iloc[0]["シーン選択"])]
        if z_match:
            rows[idx_tt][IDX_TT_NAME], rows[idx_tt][IDX_TT_ZONE] = name, z_match[0]
            for j, (_, s) in enumerate(data.sort_values("時刻").iterrows()):
                col = IDX_TIME_START + j*2
                if col + 1 < IDX_ZONE_TS: rows[idx_tt][col], rows[idx_tt][col+1] = fmt_t(s["時刻"]), str(s["シーン選択"]).split(" [")[0]
            rows[idx_tt][IDX_ZONE_TS] = z_match[0]
            if rep != "(空白)":
                day_idx = 0 if rep == "毎日" else DAY_OPTIONS.index(rep) - 1
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
    
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        csv_bytes = csv_str.encode("utf-8-sig")
        tar.addfile(tarfile.TarInfo(name="setting_data.csv"), io.BytesIO(csv_bytes))
        tar.getmembers()[-1].size = len(csv_bytes)
        tar.addfile(tarfile.TarInfo(name="temp.json"), io.BytesIO(json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8')))
        tar.getmembers()[-1].size = len(tar.getmembers()[-1].name)
    st.download_button(f"📥 {shop_name}.tar を保存", tar_buf.getvalue(), f"{shop_name}.tar")
