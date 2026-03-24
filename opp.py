import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time

# --- スロット上限の拡張 ---
MAX_SLOTS = 150      # 限界値を150個まで大幅に拡張（10分間隔で24時間分でも144個）
TOTAL_COLS = 400     # 全体の列数も余裕を持って拡張

IDX_SCENE_START = 9
IDX_TT_NAME = 17     # R列
IDX_TT_ZONE = 19     # T列
IDX_TIME_START = 22  # W列: スロット開始

# スロット上限(MAX_SLOTS)に合わせて、後ろのブロックを自動でズラす
IDX_ZONE_TS = IDX_TIME_START + (MAX_SLOTS * 2) + 1  # スロット終了後に1列空ける
IDX_PERIOD_NAME = IDX_ZONE_TS + 10                  # スケジュール割当終了後に1列空ける

GROUP_TYPES = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
DAY_OPTIONS = ["(空白)", "毎日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

# 最初から左メニューを開いた状態にする設定
st.set_page_config(page_title="FitPlus Setting Tool", layout="wide", initial_sidebar_state="expanded")

# セッション管理
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []
if 'p_list' not in st.session_state: st.session_state.p_list = []
if 'timelines' not in st.session_state: st.session_state.timelines = []

def fmt_t(t): return f"{t.hour}:{t.minute:02}"
def fmt_d(d): return f"{d.month}月{d.day}日"

# 削除用コールバック (UID特定方式)
def delete_slot_by_uid(tl_idx, slot_uid):
    st.session_state.timelines[tl_idx]['slots'] = [
        s for s in st.session_state.timelines[tl_idx]['slots'] if s['uid'] != slot_uid
    ]

# --- 途中セーブ・ロード機能 ---
def export_session_to_json():
    export_data = {
        "z_list": st.session_state.z_list,
        "g_list": st.session_state.g_list,
        "s_list": st.session_state.s_list,
        "p_list": [],
        "timelines": []
    }
    for p in st.session_state.p_list:
        export_data["p_list"].append({
            "名": p["名"], "sd": p["sd"].isoformat(), "ed": p["ed"].isoformat(), "sn": p["sn"], "zn": p["zn"]
        })
    for tl in st.session_state.timelines:
        tl_copy = tl.copy()
        tl_copy["slots"] = [{"uid": s.get("uid", ""), "time": s["time"].strftime("%H:%M"), "scene": s["scene"]} for s in tl["slots"]]
        export_data["timelines"].append(tl_copy)
    return json.dumps(export_data, ensure_ascii=False)

def import_session_from_json(json_str):
    data = json.loads(json_str)
    st.session_state.z_list = data.get("z_list", [])
    st.session_state.g_list = data.get("g_list", [])
    st.session_state.s_list = data.get("s_list", [])
    
    p_list = []
    for p in data.get("p_list", []):
        p["sd"] = datetime.fromisoformat(p["sd"]).date()
        p["ed"] = datetime.fromisoformat(p["ed"]).date()
        p_list.append(p)
    st.session_state.p_list = p_list
    
    timelines = []
    for tl in data.get("timelines", []):
        for s in tl["slots"]:
            s["time"] = datetime.strptime(s["time"], "%H:%M").time()
        timelines.append(tl)
    st.session_state.timelines = timelines

# サイドバー設定 (セーブ・ロード・リセット)
with st.sidebar:
    st.header("セーブ / ロード")
    st.write("途中から再開するための専用ファイル(.json)を保存・読み込みします。")
    
    # セーブ
    save_data = export_session_to_json()
    st.download_button(
        label="セーブデータをダウンロード",
        data=save_data,
        file_name=f"fitplus_save_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
        mime="application/json",
        type="primary"
    )
    
    st.divider()
    
    # ロード
    uploaded_file = st.file_uploader("セーブデータを読み込む", type=["json"])
    if uploaded_file is not None:
        if st.button("データを復元する"):
            import_session_from_json(uploaded_file.getvalue().decode("utf-8"))
            st.success("データを復元しました！")
            st.rerun()
            
    st.divider()
    if st.button("全データを完全にリセット"):
        st.session_state.clear()
        st.rerun()

st.title("FitPlus 設定ツール")
# 【修正】デフォルトの文字をなくし、最初から空白になるようにしました
shop_name = st.text_input("店舗名を入力", "")

# 1. ゾーン & グループ
st.header("1. ゾーン & グループ登録")
vz = [z["名"] for z in st.session_state.z_list]
c1, c2 = st.columns(2)
with c1:
    with st.container(border=True):
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
    st.write("登録履歴")
    for i, z in enumerate(st.session_state.z_list):
        cl1, cl2 = st.columns([4, 1])
        cl1.info(f"ゾーン: {z['名']} (フェード: {z['秒']}秒)")
        if cl2.button("削除", key=f"dz_{i}"):
            st.session_state.z_list.pop(i)
            st.rerun()
            
    for i, g in enumerate(st.session_state.g_list):
        cl1, cl2 = st.columns([4, 1])
        cl1.success(f"グループ: {g['名']} ({g['ゾ']})")
        if cl2.button("削除", key=f"dg_{i}"):
            st.session_state.g_list.pop(i)
            st.rerun()

# 2. シーン作成
st.divider()
st.header("2. シーン作成")
sn_in, sz_in = st.text_input("作成シーン名"), st.selectbox("対象ゾーン選択", options=[""] + vz)
if sz_in:
    scene_tmp = []
    for g in [g for g in st.session_state.g_list if g["ゾ"] == sz_in]:
        with st.expander(f"{g['名']} 設定"):
            dim = st.slider("調光%", 0, 100, 100, key=f"d_{g['名']}")
            ex, ey, kel = "", "", "4000"
            if "Synca" in g['型']:
                m = st.radio("設定", ["パレット", "調色"], horizontal=True, key=f"m_{g['名']}")
                if m == "パレット": ex, ey = st.slider("演出X", 1, 11, 6, key=f"x_{g['名']}"), st.slider("演出Y", 1, 11, 6, key=f"y_{g['名']}")
                else: kel = st.text_input("色温度", "4000", key=f"ks_{g['名']}")
            elif g['型'] == "調光調色": kel = st.text_input("色温度", "4000", key=f"k_{g['名']}")
            scene_tmp.append({"sn": sn_in, "gn": g['名'], "zn": sz_in, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
    if st.button("このシーンを保存"):
        if sn_in:
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == sn_in and s["zn"] == sz_in)]
            st.session_state.s_list.extend(scene_tmp); st.rerun()

st.subheader("シーン履歴")
if st.session_state.s_list:
    h_df = pd.DataFrame(st.session_state.s_list)
    for (sn, zn), data in h_df.groupby(['sn', 'zn']):
        with st.expander(f"{sn} ({zn})"):
            for _, r in data.iterrows():
                c_info = f" {r['ex']}-{r['ey']}" if r['ex'] != "" else f"{r['kel']}K"
                st.write(f"・{r['gn']}: {r['dim']}% / {c_info}")
            if st.button("このシーンのみ削除", key=f"del_s_{sn}_{zn}"):
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == sn and s["zn"] == zn)]; st.rerun()

# 3. シーンタイムテーブル設定
st.divider()
st.header("3. シーンタイムテーブル設定")
with st.container(border=True):
    tl_n = st.text_input("スケジュール名", "通常")
    tl_z = st.selectbox("適用ゾーン", options=[""]+vz, key="tlz")
    tl_d = st.selectbox("適用曜日", DAY_OPTIONS, index=1)
    if st.button("枠を作成") and tl_n and tl_z:
        st.session_state.timelines.append({
            "uid": f"tl_{datetime.now().timestamp()}",
            "name": tl_n, "zone": tl_z, "day": tl_d, 
            "slots": [{"uid": f"sl_{datetime.now().timestamp()}", "time": time(0, 0), "scene": ""}]
        }); st.rerun()

for i, tl in enumerate(st.session_state.timelines):
    with st.expander(f"{tl['name']} (ゾーン: {tl['zone']}) - {tl['day']}", expanded=True):
        z_scenes = sorted(list(set([s['sn'] for s in st.session_state.s_list if s['zn'] == tl['zone']])))
        with st.container(border=True):
            st.write("一括生成")
            bulk_scenes = st.multiselect("順序", options=z_scenes, key=f"bulk_s_{i}")
            ca, cb, cc = st.columns(3)
            b_st = ca.time_input("開始時刻", value=time(0,0), key=f"b_st_{i}")
            b_en = cb.time_input("終了まで", value=time(23,59), key=f"b_en_{i}")
            b_it = cc.number_input("間隔(分)", 1, 1440, 10, key=f"b_it_{i}")
            if st.button("一括生成実行", key=f"bulk_btn_{i}") and bulk_scenes:
                new_slots = []
                if b_st != time(0, 0): new_slots.append({"uid": f"b0_{datetime.now().timestamp()}", "time": time(0, 0), "scene": ""})
                dt, idx = datetime.combine(datetime.today(), b_st), 0
                while dt <= datetime.combine(datetime.today(), b_en) and len(new_slots) < MAX_SLOTS:
                    new_slots.append({"uid": f"b{idx}_{datetime.now().timestamp()}", "time": dt.time(), "scene": bulk_scenes[idx % len(bulk_scenes)]})
                    dt += timedelta(minutes=b_it); idx += 1
                st.session_state.timelines[i]['slots'] = new_slots; st.rerun()

        for j, slot in enumerate(tl['slots']):
            c1, c2, c3 = st.columns([1, 2, 0.5])
            if j == 0:
                tl['slots'][0]['time'] = time(0, 0); c1.write("00:00 (起点)")
            else:
                tl['slots'][j]['time'] = c1.time_input(f"時刻", slot['time'], key=f"t_v_{slot['uid']}")
            tl['slots'][j]['scene'] = c2.selectbox(f"シーン選択", options=[""]+z_scenes, index=z_scenes.index(slot['scene'])+1 if slot['scene'] in z_scenes else 0, key=f"s_v_{slot['uid']}")
            if j > 0:
                c3.button("削除", key=f"del_v_{slot['uid']}", on_click=delete_slot_by_uid, args=(i, slot['uid']))

        c_act1, c_act2 = st.columns(2)
        if c_act1.button("＋ 時刻を追加", key=f"add_v_{tl['uid']}"):
            st.session_state.timelines[i]['slots'].append({"uid": f"m_{datetime.now().timestamp()}", "time": time(0,0), "scene": ""}); st.rerun()
        if c_act2.button("この枠を削除", key=f"dtl_v_{tl['uid']}"):
            st.session_state.timelines.pop(i); st.rerun()

# 4. 特異日設定
st.divider()
st.header("4. 特異日設定")
with st.form("p_form", clear_on_submit=True):
    pn = st.text_input("名称 [zone-period]")
    exist_tt = sorted(list(set([tl['name'] for tl in st.session_state.timelines])))
    ps_name = st.selectbox("適用スケジュール [timetable]", options=exist_tt if exist_tt else ["なし"])
    pc1, pc2 = st.columns(2); psd, ped = pc1.date_input("開始"), pc2.date_input("終了")
    if st.form_submit_button("特異日を追加") and ps_name != "なし":
        tz = next(tl['zone'] for tl in st.session_state.timelines if tl['name'] == ps_name)
        st.session_state.p_list.append({"名": pn, "sd": psd, "ed": ped, "sn": ps_name, "zn": tz}); st.rerun()

for i, p in enumerate(st.session_state.p_list):
    c1, c2 = st.columns([4, 1]); c1.write(f"日付: {p['名']} ({p['sd']}~{p['ed']}) -> {p['sn']}"); 
    if c2.button("削除", key=f"dp_{i}"): st.session_state.p_list.pop(i); st.rerun()

# 5. 出力
st.divider()
# 【修正】ファイル名が空欄の場合は「export.tar」になるように保険をかけています
download_filename = f"{shop_name}.tar" if shop_name.strip() else "export.tar"

if st.button(".tar を生成", type="primary", use_container_width=True):
    rows = [[""] * TOTAL_COLS for _ in range(500)]
    for i, z in enumerate(st.session_state.z_list): rows[i][0], rows[i][2] = z["名"], z["秒"]
    for i, g in enumerate(st.session_state.g_list): rows[i][4], rows[i][6], rows[i][7] = g["名"], GROUP_TYPES[g["型"]], g["ゾ"]
    for i, r in enumerate(st.session_state.s_list):
        p_v, c_v = (f" {r['ex']}-{r['ey']}", "") if r['ex'] != "" else ("", r['kel'])
        rows[i][9], rows[i][11], rows[i][12], rows[i][13], rows[i][14], rows[i][15] = r["sn"], r["dim"], c_v, p_v, r["zn"], r["gn"]
    
    for i, tl in enumerate(st.session_state.timelines):
        rows[i][17], rows[i][19] = tl['name'], tl['zone']
        sort_s = sorted(tl['slots'], key=lambda x: x['time'])
        for j, s in enumerate(sort_s):
            col = IDX_TIME_START + j*2
            if col + 1 < IDX_ZONE_TS - 1: rows[i][col], rows[i][col+1] = fmt_t(s['time']), s['scene']
        
        rows[i][IDX_ZONE_TS] = tl['zone']
        if tl['day'] != "(空白)":
            day_idx = 0 if tl['day'] == "毎日" else DAY_OPTIONS.index(tl['day']) - 1
            rows[i][IDX_ZONE_TS + 1 + day_idx] = tl['name']

    for i, p in enumerate(st.session_state.p_list):
        rows[i][IDX_PERIOD_NAME], rows[i][IDX_PERIOD_NAME+1], rows[i][IDX_PERIOD_NAME+2], rows[i][IDX_PERIOD_NAME+3], rows[i][IDX_PERIOD_NAME+4] = p["名"], fmt_d(p["sd"]), fmt_d(p["ed"]), p["sn"], p["zn"]

    def to_line(arr): return ",".join([str(x) for x in arr]) + "\r\n"
    
    h1 = ["Zone情報","","","","Group情報","","","","","Scene情報","","","","","","","","Timetable情報"]
    h1 += [""] * (IDX_ZONE_TS - len(h1)) + ["Timetable-schedule情報"]
    h1 += [""] * (IDX_PERIOD_NAME - len(h1)) + ["Timetable期間/特異日情報"]
    
    h3 = ['[zone]','[id]','[fade]','','[group]','[id]','[type]','[zone]','','[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]','','[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]']
    
    for _ in range(MAX_SLOTS): h3 += ['[time]','[scene]']
    
    h3 += ['', '[zone-ts]','[daily]','[monday]','[tuesday]','[wednesday]','[thursday]','[friday]','[saturday]','[sunday]','', '[zone-period]','[start]','[end]','[timetable]','[zone]']
    
    csv_data = to_line(h1 + [""]*(TOTAL_COLS - len(h1))) + ("," * (TOTAL_COLS-1) + "\r\n") + to_line(h3 + [""]*(TOTAL_COLS - len(h3)))
    for r in rows: csv_data += to_line(r)

    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        b = csv_data.encode("utf-8-sig")
        ti = tarfile.TarInfo("setting_data.csv"); ti.size = len(b); tar.addfile(ti, io.BytesIO(b))
        jb = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8')
        tj = tarfile.TarInfo("temp.json"); tj.size = len(jb); tar.addfile(tj, io.BytesIO(jb))
    st.download_button(f"📥 {download_filename} を保存", tar_buf.getvalue(), download_filename)
