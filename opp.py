import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time

# --- 定数設定 (赤池店236列モデルを厳密に再現) ---
TOTAL_COLS = 236
IDX_SCENE_START = 9
IDX_TT_NAME = 17     # [zone-timetable] R列
IDX_TT_ZONE = 19     # [zone] T列
IDX_TIME_START = 22  # [time] W列
IDX_ZONE_TS = 197    # [zone-ts] GS列
IDX_PERIOD_NAME = 207# [zone-period] IC列
IDX_PERIOD_TT = 210  # [timetable] IF列 (AW列相当)

GROUP_TYPES = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
DAY_OPTIONS = ["毎日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

st.set_page_config(page_title="FitPlus Pro v9700", layout="wide")

# セッション状態の初期化
for key in ['z_list', 'g_list', 's_list', 'p_list', 'loop_scenes']:
    if key not in st.session_state: st.session_state[key] = []
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

# --- 画面表示 ---
st.title("FitPlus ⚙️ 統合設定ツール")
shop_name = st.text_input("🏢 店舗名を入力", "FitPlus_Project")

if st.sidebar.button("データをリセット"):
    st.session_state.clear()
    st.rerun()

# 1. ゾーン/グループ登録
c1, c2 = st.columns(2)
with c1:
    with st.container(border=True):
        st.write("**ゾーン登録**")
        zn, zf = st.text_input("ゾーン名"), st.number_input("フェード(秒)", 0, 3600, 0)
        if st.button("ゾーン保存") and zn:
            st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    with st.container(border=True):
        st.write("**グループ登録**")
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + [z["名"] for z in st.session_state.z_list])
        if st.button("グループ保存") and gn and gz:
            st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()

# 2. シーン作成
st.divider()
st.header("2. シーン作成")
vz = [z["名"] for z in st.session_state.z_list]
s_name_in = st.text_input("作成シーン名")
s_zone_in = st.selectbox("対象ゾーン選択", options=[""] + vz)

if s_zone_in:
    scene_tmp = []
    for g in [g for g in st.session_state.g_list if g["ゾ"] == s_zone_in]:
        with st.expander(f"💡 {g['名']}"):
            dim = st.slider("調光%", 0, 100, 100, key=f"dim_{g['名']}")
            ex, ey, kel = "", "", "4000"
            if "Synca" in g['型']:
                m = st.radio("設定", ["パレット", "調色"], horizontal=True, key=f"m_{g['名']}")
                if m == "パレット":
                    ex, ey = st.slider("X", 1, 11, 6, key=f"x_{g['名']}"), st.slider("Y", 1, 11, 6, key=f"y_{g['名']}")
                else: kel = st.text_input("K", "4000", key=f"ks_{g['名']}")
            elif g['型'] == "調光調色": kel = st.text_input("K", "4000", key=f"k_{g['名']}")
            scene_tmp.append({"sn": s_name_in, "gn": g['名'], "zn": s_zone_in, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
    if st.button("このシーンを保存"):
        st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name_in and s["zn"] == s_zone_in)]
        st.session_state.s_list.extend(scene_tmp); st.rerun()

# 3. スケジュール
st.divider()
st.header("3. スケジュール設定")
all_scenes = sorted(list(set([f"{s['sn']} [{s['zn']}]" for s in st.session_state.s_list])))

with st.container(border=True):
    st.write("**一括生成**")
    tt_name = st.text_input("スケジュール名", "通常")
    sel_scene = st.selectbox("追加シーン", options=all_scenes if all_scenes else ["未登録"])
    if st.button("リストに追加") and all_scenes:
        st.session_state.loop_scenes.append(sel_scene); st.rerun()
    if st.session_state.loop_scenes:
        st.info("順序: " + " ➔ ".join(st.session_state.loop_scenes))
        ca, cb, cc = st.columns(3)
        g_st, g_en = ca.time_input("開始", value=time(0,0)), cb.time_input("終了", value=time(23,59))
        g_it = cc.number_input("間隔(分)", 1, 1440, 8)
        rep = st.selectbox("繰り返し", DAY_OPTIONS)
        if st.button("⏰ スケジュールを生成"):
            new_r = []
            dt, idx = datetime.combine(datetime.today(), g_st), 0
            while dt <= datetime.combine(datetime.today(), g_en) and len(new_r) < 80:
                new_r.append({"スケジュール名": tt_name, "時刻": dt.time(), "シーン選択": st.session_state.loop_scenes[idx % len(st.session_state.loop_scenes)], "繰り返し": rep})
                dt += timedelta(minutes=g_it); idx += 1
            st.session_state.t_df = pd.concat([st.session_state.t_df, pd.DataFrame(new_r)]).drop_duplicates().sort_values("時刻")

st.session_state.t_df = st.data_editor(st.session_state.t_df, num_rows="dynamic", use_container_width=True)

# 4. 出力
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
        
    # Timetable (赤池店インデックス再現)
    idx_tt = 0
    grouped = st.session_state.t_df.groupby(["スケジュール名", "繰り返し"])
    for (name, rep), data in grouped:
        sample_scene = data.iloc[0]["シーン選択"]
        z_name = [z for z in vz if f"[{z}]" in sample_scene][0]
        
        # R列(17)スケジュール名, T列(19)ゾーン名
        rows[idx_tt][IDX_TT_NAME], rows[idx_tt][IDX_TT_ZONE] = name, z_name
        
        # W列(22)からスロット
        for j, (_, s) in enumerate(data.sort_values("時刻").iterrows()):
            col = IDX_TIME_START + j*2
            if col + 1 < IDX_ZONE_TS:
                rows[idx_tt][col], rows[idx_tt][col+1] = fmt_t(s["時刻"]), s["シーン選択"].split(" [")[0]
        
        # スケジュール適用 (Index 197〜)
        rows[idx_tt][IDX_ZONE_TS] = z_name
        day_idx = 0 if rep == "毎日" else DAY_OPTIONS.index(rep)
        rows[idx_tt][IDX_ZONE_TS + 1 + day_idx] = name
        idx_tt += 1

    # 特異日
    for i, p in enumerate(st.session_state.p_list):
        rows[i][IDX_PERIOD_NAME], rows[i][IDX_PERIOD_TT], rows[i][IDX_PERIOD_ZONE] = p["名"], p["sn"], p["zn"]

    # ヘッダーと結合
    def to_line(arr): return ",".join([str(x) for x in arr]) + "\r\n"
    h1 = ["Zone情報","","","","Group情報","","","","","Scene情報","","","","","","","","Timetable情報"] + [""]*(IDX_ZONE_TS-18) + ["Timetable-schedule情報"] + [""]*9 + ["Timetable期間/特異日情報"]
    h3 = ['[zone]','[id]','[fade]','','[group]','[id]','[type]','[zone]','','[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]','','[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]']
    for _ in range(87): h3 += ['[time]','[scene]']
    h3 += ['[zone-ts]','[daily]','[monday]','[tuesday]','[wednesday]','[thursday]','[friday]','[saturday]','[sunday]','','[zone-period]','[start]','[end]','[timetable]','[zone]']
    
    csv_str = to_line(h1 + [""]*(TOTAL_COLS - len(h1))) + ("," * (TOTAL_COLS-1) + "\r\n") + to_line(h3 + [""]*(TOTAL_COLS - len(h3)))
    for r in rows: csv_str += to_line(r)

    # TAR生成
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        csv_bytes = csv_str.encode("utf-8-sig")
        info = tarfile.TarInfo(name="setting_data.csv"); info.size = len(csv_bytes); tar.addfile(info, io.BytesIO(csv_bytes))
        j_data = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8')
        info_j = tarfile.TarInfo(name="temp.json"); info_j.size = len(j_data); tar.addfile(info_j, io.BytesIO(j_data))

    fn = f"{shop_name.replace(' ', '_')}.tar"
    st.download_button(f"📥 {fn} を保存", tar_buf.getvalue(), fn)
