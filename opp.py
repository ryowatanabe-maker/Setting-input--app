import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta

# --- 1. 定数とヘッダー定義 ---
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
NUM_COLS = 236 

ROW1 = [None] * NUM_COLS
ROW1[0], ROW1[4], ROW1[9], ROW1[17], ROW1[197], ROW1[207] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報', 'Timetable-schedule情報', 'Timetable期間/特異日情報'
ROW3 = [None] * NUM_COLS
ROW3[0:3], ROW3[4:8] = ['[zone]', '[id]', '[fade]'], ['[group]', '[id]', '[type]', '[zone]']
ROW3[9:16] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]']
ROW3[17:22] = ['[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]']
for i in range(22, 196, 2): ROW3[i], ROW3[i+1] = '[time]', '[scene]'
ROW3[197:206] = ['[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]']
ROW3[207:212] = ['[zone-period]', '[id]', '[start]', '[end]', '[timetable]', '[zone]']

CSV_HEADER = [ROW1, [None] * NUM_COLS, ROW3]

# --- 2. アプリ設定とデータ初期化 ---
st.set_page_config(page_title="設定データ作成アプリ", layout="wide")
st.title("設定データ作成アプリ ⚙️")

for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
    if key not in st.session_state: st.session_state[key] = []
if 'tt_slots_count' not in st.session_state: st.session_state.tt_slots_count = 1
if 'auto_scene_count' not in st.session_state: st.session_state.auto_scene_count = 2

# --- 3. 各登録セクション (省略なしで継続) ---
st.header("1. 店舗名入力 🏢")
shop_name = st.text_input("店舗名", value="")
st.divider()

# 2-4は現在の仕様を維持 (ゾーン、グループ、シーン)
# ... (既存のフォームをそのまま使用) ...

# --- 5. タイムテーブル作成 (詳細表示付き) ---
st.header("5. タイムテーブル作成 ⏳")
v_scenes = [""] + sorted(list(set([s["シーン名"] for s in st.session_state.s_list])))
v_zones = [""] + [z["ゾーン名"] for z in st.session_state.z_list]

with st.expander("スケジュール自動作成"):
    with st.form("at_v41"):
        ca1, ca2, ca3, ca4 = st.columns(4)
        az, stt, edt, inv = ca1.selectbox("対象ゾーン", v_zones), ca2.text_input("開始", "10:00"), ca3.text_input("終了", "21:00"), ca4.number_input("間隔(分) ※6分以上", 6, 120, 8)
        ascs = []
        acols = st.columns(4)
        for i in range(st.session_state.auto_scene_count):
            with acols[i % 4]:
                v = st.selectbox(f"シーン{i+1}", v_scenes, key=f"as_{i}")
                if v: ascs.append(v)
        if st.form_submit_button("セット"):
            try:
                curr, limit = datetime.strptime(stt, "%H:%M"), datetime.strptime(edt, "%H:%M")
                slots, idx = [], 0
                while curr <= limit:
                    slots.append({"time": curr.strftime("%H:%M"), "scene": ascs[idx % len(ascs)]})
                    curr += timedelta(minutes=inv); idx += 1
                st.session_state.temp_slots, st.session_state.temp_tt_zone, st.session_state.tt_slots_count = slots, az, len(slots)
                st.rerun()
            except: st.error("時刻形式エラー")
    if st.button("繰り返し用シーン枠を追加 ➕"): st.session_state.auto_scene_count += 1; st.rerun()

with st.form("tt_v41"):
    ct1, ct2 = st.columns(2)
    tt_n = ct1.text_input("タイムテーブル名", value="通常")
    tt_z = ct2.selectbox("対象ゾーン ", v_zones, index=v_zones.index(st.session_state.get("temp_tt_zone", "")) if st.session_state.get("temp_tt_zone", "") in v_zones else 0)
    cs1, cs2 = st.columns(2)
    ss, se = cs1.selectbox("日出シーン ☀️", v_scenes), cs2.selectbox("日没シーン 🌙", v_scenes)
    f_slots, b_slots = [], st.session_state.get("temp_slots", [])
    for i in range(st.session_state.tt_slots_count):
        c_t, c_s = st.columns([1, 2])
        dt = b_slots[i]["time"] if i < len(b_slots) else ""
        ds = b_slots[i]["scene"] if i < len(b_slots) else ""
        tv, sv = c_t.text_input(f"時間{i+1}", value=dt, key=f"t41_{i}"), c_s.selectbox(f"シーン{i+1}", v_scenes, index=v_scenes.index(ds) if ds in v_scenes else 0, key=f"s41_{i}")
        if tv and sv: f_slots.append({"time": tv, "scene": sv})
    if st.form_submit_button("タイムテーブル保存 ✅"):
        st.session_state.tt_list.append({"tt_name": tt_n, "zone": tt_z, "sun_start": ss, "sun_end": se, "slots": f_slots})
        st.session_state.tt_slots_count = 1; st.rerun()

if st.session_state.tt_list:
    st.subheader("タイムテーブル詳細確認 📋")
    tt_df = pd.DataFrame([{"タイムテーブル名": x["tt_name"], "ゾーン": x["zone"], "登録数": len(x["slots"])} for x in st.session_state.tt_list])
    ev = st.dataframe(tt_df, use_container_width=True, on_select="rerun", selection_mode="single-row")
    if len(ev.selection.rows) > 0:
        sel = st.session_state.tt_list[ev.selection.rows[0]]
        with st.expander(f"{sel['tt_name']} の詳細", expanded=True):
            st.table(pd.DataFrame(sel['slots']))
            if st.button("削除 🗑️"): st.session_state.tt_list.pop(ev.selection.rows[0]); st.rerun()

st.divider()

# --- 6. スケジュール適用設定 (ここを修正) ---
st.header("6. スケジュール適用・特異日設定 🗓️")
v_tt_names = [""] + [tt["tt_name"] for tt in st.session_state.tt_list]

col_apply1, col_apply2 = st.columns(2)

with col_apply1:
    st.subheader("通常スケジュール設定")
    with st.form("ts_v41"):
        tz = st.selectbox("対象ゾーン", v_zones)
        apply_type = st.radio("設定方法", ["毎日一括(daily)", "曜日を指定して登録"])
        
        target_tt = st.selectbox("適用するタイムテーブル", v_tt_names)
        
        selected_days = []
        if apply_type == "曜日を指定して登録":
            st.write("適用する曜日にチェックを入れてください")
            day_cols = st.columns(7)
            days = ["月", "火", "水", "木", "金", "土", "日"]
            for i, d in enumerate(days):
                if day_cols[i].checkbox(d): selected_days.append(d)
        
        if st.form_submit_button("通常スケジュールを保存 ✅"):
            if tz and target_tt:
                # 毎日一括の場合
                if apply_type == "毎日一括(daily)":
                    st.session_state.ts_list.append({
                        "zone": tz, 
                        "config": {"daily": target_tt, "mon":"", "tue":"", "wed":"", "thu":"", "fri":"", "sat":"", "sun":""}
                    })
                # 曜日の場合、指定された曜日の分だけ既存の設定を更新または追加する
                else:
                    # すでにそのゾーンの設定があれば取得、なければ新規
                    existing = next((item for item in st.session_state.ts_list if item["zone"] == tz), None)
                    if not existing:
                        cfg = {"daily": "", "mon":"", "tue":"", "wed":"", "thu":"", "fri":"", "sat":"", "sun":""}
                        existing = {"zone": tz, "config": cfg}
                        st.session_state.ts_list.append(existing)
                    
                    day_map = {"月":"mon", "火":"tue", "水":"wed", "木":"thu", "金":"fri", "土":"sat", "日":"sun"}
                    for d in selected_days:
                        existing["config"][day_map[d]] = target_tt
                st.rerun()

# --- 7. 特異日と出力 (既存維持) ---
# ... (略) ...
