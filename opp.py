import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time
import os
import csv

# --- 1. 定数設定 (成功事例 73列モデルを完全再現) ---
NUM_COLS = 73 
Z_ID_START, G_ID_START, S_ID_START, T_ID_START = 4097, 32769, 8193, 12289
GROUP_TYPES = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
DAY_OPTIONS = ["毎日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

st.set_page_config(page_title="FitPlus Pro v900", layout="wide")

# セッション状態の初期化
for key in ['z_list', 'g_list', 's_list', 'p_list']:
    if key not in st.session_state: st.session_state[key] = []
if 't_df' not in st.session_state:
    st.session_state.t_df = pd.DataFrame(columns=["時刻", "シーン選択", "繰り返し"])

def safe_to_time(val):
    if isinstance(val, time): return val
    s = str(val).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try: return datetime.strptime(s, fmt).time()
        except: continue
    return time(0, 0)

# 成功事例の書式：0を抜く (9:00, 3月1日)
def format_endo_time(t):
    return f"{t.hour}:{t.minute:02}"

def format_endo_date(d):
    return f"{d.month}月{d.day}日"

st.title("FitPlus ⚙️ ゲートウェイ設定作成 (73列・成功事例準拠)")
shop_name = st.sidebar.text_input("店舗名", "FitPlus_Project")
if st.sidebar.button("全リセット"):
    st.session_state.z_list, st.session_state.g_list, st.session_state.s_list, st.session_state.p_list = [], [], [], []
    st.session_state.t_df = pd.DataFrame(columns=["時刻", "シーン選択", "繰り返し"])
    st.rerun()

# --- 1. ゾーン & グループ登録 ---
st.header("1. ゾーン & グループ登録")
c1, c2 = st.columns(2)
vz = [z["名"] for z in st.session_state.z_list]
with c1:
    with st.form("z_form", clear_on_submit=True):
        zn = st.text_input("ゾーン名")
        zf = st.number_input("フェード(秒)", 0, 3600, 0)
        if st.form_submit_button("追加") and zn:
            st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    for i, z in enumerate(st.session_state.z_list):
        st.info(f"ID:{Z_ID_START+i} / {z['名']}")
        if st.button("削除", key=f"dz_{i}"): st.session_state.z_list.pop(i); st.rerun()

with c2:
    with st.form("g_form", clear_on_submit=True):
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.form_submit_button("追加") and gn and gz:
            st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
    for i, g in enumerate(st.session_state.g_list):
        st.success(f"ID:{G_ID_START+i} / {g['名']} ({g['型']})")
        if st.button("削除", key=f"dg_{i}"): st.session_state.g_list.pop(i); st.rerun()

# --- 2. シーン作成 ---
st.header("2. シーン作成")
if os.path.exists("synca_palette.png"): st.image("synca_palette.png", width=400)
s_name = st.text_input("シーン名")
s_zone = st.selectbox("対象ゾーン", options=[""] + vz, key="sz_s")
if s_zone:
    target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
    scene_tmp = []
    for g in target_gs:
        with st.expander(f"■ {g['名']}"):
            dim = st.slider(f"調光%", 0, 100, 100, key=f"d_{g['名']}_{s_name}")
            ex, ey, kel = "", "", "4000"
            if "Synca" in g['型']:
                m = st.radio("設定", ["パレット", "色温度"], horizontal=True, key=f"m_{g['名']}")
                if m == "パレット":
                    cx, cy = st.columns(2)
                    ex, ey = cx.slider("X", 1, 11, 6, key=f"x_{g['名']}"), cy.slider("Y", 1, 11, 6, key=f"y_{g['名']}")
                else: kel = st.text_input("K", "4000", key=f"ks_{g['名']}")
            elif g['型'] == "調光調色": kel = st.text_input("K", "4000", key=f"k_{g['名']}")
            scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
    if st.button("シーン保存", use_container_width=True):
        st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
        st.session_state.s_list.extend(scene_tmp); st.rerun()

# --- 3. スケジュール ---
st.header("3. スケジュール & 特異日")
all_scene_opts = sorted(list(set([f"{s['sn']} [{s['zn']}]" for s in st.session_state.s_list])))
if all_scene_opts:
    st.subheader("⏰ 8分毎(交互)の自動生成")
    c1, c2, c3 = st.columns(3)
    g_start, g_end, g_int = c1.time_input("開始", value=time(10, 0)), c2.time_input("終了", value=time(21, 0)), c3.number_input("間隔(分)", 1, 120, 8)
    s_a = st.selectbox("メインA", options=all_scene_opts)
    s_b = st.selectbox("交互B", options=["なし"] + all_scene_opts)
    s_rep = st.selectbox("曜日", options=DAY_OPTIONS)
    if st.button("一括生成"):
        new_rows = []
        curr = datetime.combine(datetime.today(), g_start); end = datetime.combine(datetime.today(), g_end); idx = 0
        while curr <= end and len(new_rows) < 6: # 73列モデルはスロット数が限られるため注意
            target = s_a if (idx % 2 == 0 or s_b == "なし") else s_b
            new_rows.append({"時刻": curr.time(), "シーン選択": target, "繰り返し": s_rep})
            curr += timedelta(minutes=g_int); idx += 1
        st.session_state.t_df = pd.concat([st.session_state.t_df, pd.DataFrame(new_rows)]).drop_duplicates().sort_values("時刻")
    
    st.session_state.t_df["時刻"] = st.session_state.t_df["時刻"].apply(safe_to_time)
    st.session_state.t_df = st.data_editor(st.session_state.t_df, num_rows="dynamic", use_container_width=True)

    st.subheader("📅 特異日設定")
    with st.form("p_form", clear_on_submit=True):
        pn = st.text_input("名称")
        p_sd, p_ed = st.date_input("開始"), st.date_input("終了")
        p_target_z = st.selectbox("対象ゾーン", options=vz)
        p_rep = st.selectbox("適用スケジュール", options=DAY_OPTIONS)
        if st.form_submit_button("特異日追加"):
            st.session_state.p_list.append({"名": pn, "zn": p_target_z, "sd": p_sd, "ed": p_ed, "rep": p_rep}); st.rerun()

# --- 4. 出力 (73列・引用符なし・BOMあり) ---
st.header("4. 出力")
if st.button("📦 ゲートウェイ用 .tar を生成", type="primary", use_container_width=True):
    # 73列の空の器
    rows = [[""] * NUM_COLS for _ in range(1000)]
    
    # ゾーン
    for i, z in enumerate(st.session_state.z_list):
        rows[i][0], rows[i][1], rows[i][2] = z["名"], Z_ID_START + i, z["秒"]
    
    # グループ
    for i, g in enumerate(st.session_state.g_list):
        rows[i][4], rows[i][5], rows[i][6], rows[i][7] = g["名"], G_ID_START + i, GROUP_TYPES[g["型"]], g["ゾ"]
    
    # シーン
    unique_sn = sorted(list(set([s["sn"] for s in st.session_state.s_list])))
    for i, r in enumerate(st.session_state.s_list):
        color = f"{r['ex']}/{r['ey']}" if r['ex'] != "" else r['kel']
        # perform(13), fresh-key(14), zone(15), group(16)
        rows[i][9], rows[i][10], rows[i][11], rows[i][12], rows[i][13], rows[i][15], rows[i][16] = r["sn"], S_ID_START + unique_sn.index(r["sn"]), r["dim"], color, "static", r["zn"], r["gn"]
    
    # タイムテーブル
    idx_tt = 0
    for z_name in vz:
        for rep in DAY_OPTIONS:
            slots = st.session_state.t_df[st.session_state.t_df["シーン選択"].str.contains(f"\[{z_name}\]", na=False) & (st.session_state.t_df["繰り返し"] == rep)].copy()
            if not slots.empty:
                slots = slots.sort_values("時刻")
                tt_n = f"{z_name}_{rep}_TT"
                rows[idx_tt][18], rows[idx_tt][19], rows[idx_tt][20] = tt_n, T_ID_START + idx_tt, z_name
                # 73列モデルのスロット枠(23〜34列)に合わせて最大6つ
                for j, (_, s) in enumerate(slots.head(6).iterrows()):
                    rows[idx_tt][23 + j*2] = format_endo_time(s["時刻"])
                    rows[idx_tt][24 + j*2] = s["シーン選択"].split(" [")[0]
                rows[idx_tt][35] = z_name
                rep_c = 36 if rep == "毎日" else 37 + DAY_OPTIONS.index(rep) - 1
                rows[idx_tt][rep_c] = tt_n; idx_tt += 1

    # 特異日
    for i, p in enumerate(st.session_state.p_list):
        rows[i][45], rows[i][46], rows[i][47], rows[i][48], rows[i][49] = p["名"], format_endo_date(p["sd"]), format_endo_date(p["ed"]), f"{p['zn']}_{p['rep']}_TT", p['zn']

    # ヘッダー (カンマ数72個=73列を厳格に生成)
    h0 = [""] * NUM_COLS
    h0[0], h0[4], h0[9], h0[17], h0[35], h0[45] = 'Zone情報','Group情報','Scene情報','Timetable情報','Timetable-schedule情報','Timetable期間/特異日情報'
    h2 = [""] * NUM_COLS
    h2[0:3], h2[4:8], h2[9:17], h2[18:23], h2[35:44], h2[45:50] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]'], ['[scene]','[id]','[dimming]','[color]','[perform]','[fresh-key]','[zone]','[group]'], ['[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]'], ['[zone-ts]','[daily]','[monday]','[tuesday]','[wednesday]','[thursday]','[friday]','[saturday]','[sunday]'], ['[zone-period]','[start]','[end]','[timetable]','[zone]']
    for j in range(23, 34, 2): h2[j], h2[j+1] = '[time]','[scene]'

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_NONE, escapechar='', lineterminator='\r\n')
    writer.writerow(h0)
    writer.writerow([""] * NUM_COLS)
    writer.writerow(h2)
    for row in rows:
        if any(row): writer.writerow(row)
    
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        # 成功事例に合わせて BOM あり UTF-8
        csv_bytes = output.getvalue().encode("utf-8-sig")
        info = tarfile.TarInfo(name="setting_data.csv"); info.size = len(csv_bytes); tar.addfile(info, io.BytesIO(csv_bytes))
        j_bytes = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8')
        j_info = tarfile.TarInfo(name="temp.json"); j_info.size = len(j_bytes); tar.addfile(j_info, io.BytesIO(j_bytes))

    st.download_button(f"📥 {shop_name}_成功準拠版.tar を保存", tar_buf.getvalue(), f"{shop_name}.tar")
