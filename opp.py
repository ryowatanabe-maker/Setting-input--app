import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time

# --- 赤池店モデル (236列) 設定 ---
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

st.set_page_config(page_title="FitPlus Timeline Pro v21000", layout="wide")

# セッション状態の初期化
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []
if 'p_list' not in st.session_state: st.session_state.p_list = []
if 'timelines' not in st.session_state: st.session_state.timelines = []

def fmt_t(t): return f"{t.hour}:{t.minute:02}"
def fmt_d(d): return f"{d.month}月{d.day}日"

st.title("FitPlus ⚙️ 統合設定ツール")
shop_name = st.text_input("🏢 店舗名を入力", "FitPlus_Project")

if st.sidebar.button("全データを完全にリセット"):
    st.session_state.clear()
    st.rerun()

# 1. ゾーン & グループ登録
st.header("1. ゾーン & グループ登録")
c1, c2 = st.columns(2)
vz = [z["名"] for z in st.session_state.z_list]
with c1:
    with st.container(border=True):
        st.write("**ゾーン設定**")
        zn, zf = st.text_input("ゾーン名"), st.number_input("フェード(秒)", 0, 3600, 0)
        if st.button("ゾーン保存") and zn:
            st.session_state.z_list = [z for z in st.session_state.z_list if z["名"] != zn]
            st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    with st.container(border=True):
        gn, gt = st.text_input("グループ名"), st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.button("グループ保存") and gn and gz:
            st.session_state.g_list = [g for g in st.session_state.g_list if g["名"] != gn]
            st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
with c2:
    st.subheader("📜 ゾーン・グループ履歴")
    for i, z in enumerate(st.session_state.z_list):
        col_z1, col_z2 = st.columns([4, 1])
        col_z1.info(f"ゾーン: {z['名']} ({z['秒']}s)")
        if col_z2.button("削除", key=f"del_z_{i}"): st.session_state.z_list.pop(i); st.rerun()
    
    for i, g in enumerate(st.session_state.g_list):
        col_g1, col_g2 = st.columns([4, 1])
        col_g1.success(f"グループ: {g['名']} (所属: {g['ゾ']})")
        if col_g2.button("削除", key=f"del_g_{i}"): st.session_state.g_list.pop(i); st.rerun()

# 2. シーン作成
st.divider()
st.header("2. シーン作成")
sn_in, sz_in = st.text_input("シーン名"), st.selectbox("対象ゾーン選択", options=[""] + vz)
if sz_in:
    scene_tmp = []
    for g in [g for g in st.session_state.g_list if g["ゾ"] == sz_in]:
        with st.expander(f"💡 {g['名']} 設定"):
            dim = st.slider("調光%", 0, 100, 100, key=f"d_{g['名']}")
            ex, ey, kel = "", "", "4000"
            if "Synca" in g['型']:
                m = st.radio("設定", ["パレット", "調色"], horizontal=True, key=f"m_{g['名']}")
                if m == "パレット":
                    ex, ey = st.slider("演出X", 1, 11, 6, key=f"x_{g['名']}"), st.slider("演出Y", 1, 11, 6, key=f"y_{g['名']}")
                else: kel = st.text_input("色温度", "4000", key=f"ks_{g['名']}")
            elif g['型'] == "調光調色": kel = st.text_input("色温度", "4000", key=f"k_{g['名']}")
            scene_tmp.append({"sn": sn_in, "gn": g['名'], "zn": sz_in, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
    if st.button("シーンを保存"):
        if sn_in:
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == sn_in and s["zn"] == sz_in)]
            st.session_state.s_list.extend(scene_tmp); st.rerun()

st.subheader("📜 シーン履歴")
if st.session_state.s_list:
    h_df = pd.DataFrame(st.session_state.s_list)
    for (sn, zn), data in h_df.groupby(['sn', 'zn']):
        with st.expander(f"🎬 {sn} ({zn})"):
            for _, r in data.iterrows():
                c_info = f" {r['ex']}-{r['ey']}" if r['ex'] != "" else f"{r['kel']}K"
                st.write(f"・{r['gn']}: {r['dim']}% / {c_info}")
            if st.button("このシーンのみ削除", key=f"del_s_{sn}_{zn}"):
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == sn and s["zn"] == zn)]; st.rerun()

# 3. タイムライン
st.divider()
st.header("3. スケジュール (タイムライン)")

with st.container(border=True):
    st.subheader("🗓️ 新しいタイムライン枠の作成")
    new_tt_name = st.text_input("スケジュール名 (例: 通常)", "通常")
    target_z = st.selectbox("適用するゾーン", options=[""] + vz)
    rep_day = st.selectbox("適用する曜日", DAY_OPTIONS, index=1)
    if st.button("タイムラインを作成"):
        if new_tt_name and target_z:
            st.session_state.timelines.append({
                "name": new_tt_name, "zone": target_z, "day": rep_day, 
                "slots": [{"time": time(0, 0), "scene": ""}]
            }); st.rerun()

st.subheader("📊 タイムライン履歴")
for i, tl in enumerate(st.session_state.timelines):
    with st.expander(f"📊 {tl['name']} (ゾーン: {tl['zone']}) - {tl['day']}", expanded=True):
        z_scene_names = sorted(list(set([s['sn'] for s in st.session_state.s_list if s['zn'] == tl['zone']])))
        
        with st.container(border=True):
            st.write("🔄 **一括生成 (0:00〜開始)**")
            bulk_scenes = st.multiselect("繰り返すシーンの順序", options=z_scene_names, key=f"bulk_s_{i}")
            ca, cb, cc = st.columns(3)
            b_en = ca.time_input("終了時刻まで", value=time(23,59), key=f"b_en_{i}")
            b_it = cb.number_input("間隔(分)", 1, 1440, 10, key=f"b_it_{i}")
            if st.button("一括生成実行", key=f"bulk_btn_{i}"):
                if bulk_scenes:
                    new_slots = []
                    dt, idx = datetime.combine(datetime.today(), time(0, 0)), 0
                    while dt <= datetime.combine(datetime.today(), b_en) and len(new_slots) < 85:
                        new_slots.append({"time": dt.time(), "scene": bulk_scenes[idx % len(bulk_scenes)]})
                        dt += timedelta(minutes=b_it); idx += 1
                    tl['slots'] = new_slots; st.rerun()

        st.write("**個別スロット編集**")
        for j, slot in enumerate(tl['slots']):
            c_time, c_scene, c_del = st.columns([1, 2, 0.5])
            if j == 0: c_time.write("00:00 (起点)")
            else: tl['slots'][j]['time'] = c_time.time_input(f"時刻", slot['time'], key=f"t_{i}_{j}")
            
            tl['slots'][j]['scene'] = c_scene.selectbox(
                f"シーン", options=[""] + z_scene_names, 
                index=z_scene_names.index(slot['scene']) + 1 if slot['scene'] in z_scene_names else 0, 
                key=f"s_{i}_{j}"
            )
            if j > 0 and c_del.button("❌", key=f"del_slot_{i}_{j}"):
                tl['slots'].pop(j); st.rerun()
        
        col_act1, col_act2 = st.columns([1, 1])
        if col_act1.button("＋ 時刻を追加", key=f"add_slot_{i}"):
            tl['slots'].append({"time": time(12, 0), "scene": ""}); st.rerun()
        if col_act2.button("🗑️ この枠を削除", key=f"del_tl_{i}"):
            st.session_state.timelines.pop(i); st.rerun()

# 4. 特異日
st.divider()
st.subheader("📅 特異日設定")
with st.form("p_form", clear_on_submit=True):
    pn = st.text_input("名称")
    exist_tt_names = sorted(list(set([tl['name'] for tl in st.session_state.timelines])))
    ps_name = st.selectbox("適応スケジュール", options=exist_tt_names if exist_tt_names else ["なし"])
    pc1, pc2 = st.columns(2); psd, ped = pc1.date_input("開始日"), pc2.date_input("終了日")
    if st.form_submit_button("特異日を追加"):
        if ps_name != "なし":
            target_tl = next(tl for tl in st.session_state.timelines if tl['name'] == ps_name)
            st.session_state.p_list.append({"名": pn, "sd": psd, "ed": ped, "sn": ps_name, "zn": target_tl['zone']}); st.rerun()

st.subheader("📜 特異日履歴")
for i, p in enumerate(st.session_state.p_list):
    col_p1, col_p2 = st.columns([4, 1])
    col_p1.write(f"📅 {p['名']} ({p['sd']}~{p['ed']}) -> {p['sn']} ({p['zn']})")
    if col_p2.button("削除", key=f"del_p_{i}"): st.session_state.p_list.pop(i); st.rerun()

# 5. 出力
st.divider()
if st.button("📦 ゲートウェイ用 .tar を生成", type="primary", use_container_width=True):
    rows = [[""] * TOTAL_COLS for _ in range(1000)]
    for i, z in enumerate(st.session_state.z_list): rows[i][0], rows[i][2] = z["名"], z["秒"]
    for i, g in enumerate(st.session_state.g_list): rows[i][4], rows[i][6], rows[i][7] = g["名"], GROUP_TYPES[g["型"]], g["ゾ"]
    for i, r in enumerate(st.session_state.s_list):
        p_val, c_val = (f" {r['ex']}-{r['ey']}", "") if r['ex'] != "" else ("", r['kel'])
        rows[i][9], rows[i][11], rows[i][12], rows[i][13], rows[i][14], rows[i][15] = r["sn"], r["dim"], c_val, p_val, r["zn"], r["gn"]
    
    for i, tl in enumerate(st.session_state.timelines):
        rows[i][IDX_TT_NAME], rows[i][IDX_TT_ZONE] = tl['name'], tl['zone']
        sorted_slots = sorted(tl['slots'], key=lambda x: x['time'])
        for j, s in enumerate(sorted_slots):
            col = IDX_TIME_START + j*2
            if col + 1 < IDX_ZONE_TS: rows[i][col], rows[i][col+1] = fmt_t(s['time']), s['scene']
        rows[i][IDX_ZONE_TS] = tl['zone']
        if tl['day'] != "(空白)":
            day_idx = 0 if tl['day'] == "毎日" else DAY_OPTIONS.index(tl['day']) - 1
            rows[i][IDX_ZONE_TS + 1 + day_idx] = tl['name']
            
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
