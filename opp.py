import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time
import os
import csv

# --- 1. 定数設定 (236列構成準拠) ---
NUM_COLS = 236 
GROUP_TYPES = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
DAY_OPTIONS = ["毎日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

st.set_page_config(page_title="FitPlus Pro v430", layout="wide")

# セッション状態の初期化
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []
if 't_df' not in st.session_state: 
    st.session_state.t_df = pd.DataFrame(columns=["時刻", "シーン選択", "繰り返し"])
if 'p_list' not in st.session_state: st.session_state.p_list = []

# 時刻変換用の安全な関数
def safe_to_time(val):
    if isinstance(val, time): return val
    s = str(val).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try: return datetime.strptime(s, fmt).time()
        except: continue
    return time(0, 0)

# --- 2. プロジェクト管理 ---
st.sidebar.title("🏢 プロジェクト管理")
shop_name = st.sidebar.text_input("店舗名", "FitPlus_Project")
if st.sidebar.button("全データをリセット"):
    st.session_state.z_list = []
    st.session_state.g_list = []
    st.session_state.s_list = []
    st.session_state.t_df = pd.DataFrame(columns=["時刻", "シーン選択", "繰り返し"])
    st.session_state.p_list = []
    st.rerun()

st.title(f"FitPlus ⚙️ {shop_name}")

# --- 3. 構成登録 ---
st.header("1. ゾーン & グループ登録")
c1, c2 = st.columns(2)
vz = [z["名"] for z in st.session_state.z_list]

with c1:
    st.subheader("📍 ゾーン (履歴)")
    with st.form("z_form", clear_on_submit=True):
        zn = st.text_input("ゾーン名")
        zf = st.number_input("フェード(秒)", 0, 3600, 0)
        if st.form_submit_button("追加"):
            if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    for i, z in enumerate(st.session_state.z_list):
        cols = st.columns([4, 1])
        cols[0].info(f"{z['名']} ({z['秒']}s)")
        if cols[1].button("削除", key=f"dz_{i}"): st.session_state.z_list.pop(i); st.rerun()

with c2:
    st.subheader("💡 グループ (履歴)")
    with st.form("g_form", clear_on_submit=True):
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.form_submit_button("追加"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
    for i, g in enumerate(st.session_state.g_list):
        cols = st.columns([4, 1])
        cols[0].success(f"{g['名']} / {g['型']} ({g['ゾ']})")
        if cols[1].button("削除", key=f"dg_{i}"): st.session_state.g_list.pop(i); st.rerun()

st.divider()

# --- 4. シーン作成 ---
st.header("2. シーン作成 & パレット画像")
c_edit, c_pal = st.columns([1, 1])

with c_pal:
    if os.path.exists("synca_palette.png"):
        st.image("synca_palette.png", caption="Syncaパレット参照用", width=400)
    else:
        st.info("🎨 `synca_palette.png` を配置するとここにパレット画像が表示されます")

with c_edit:
    s_name = st.text_input("シーン名")
    s_zone = st.selectbox("対象ゾーン", options=[""] + vz, key="sz_s")

    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        scene_tmp = []
        for g in target_gs:
            with st.expander(f"■ {g['名']} ({g['型']})"):
                dim = st.slider(f"調光%", 0, 100, 100, key=f"d_{g['名']}_{s_name}")
                ex, ey, kel = "", "", "4000"
                if "Synca" in g['型']:
                    mode = st.radio("設定方法", ["パレット", "色温度"], horizontal=True, key=f"m_{g['名']}_{s_name}")
                    if mode == "パレット":
                        cx, cy = st.columns(2)
                        ex = cx.slider("X", 1, 11, 6, key=f"x_{g['名']}")
                        ey = cy.slider("Y", 1, 11, 6, key=f"y_{g['名']}")
                    else: kel = st.text_input("色温度(K)", "4000", key=f"ks_{g['名']}")
                elif g['型'] == "調光調色":
                    kel = st.text_input("色温度(K)", "4000", key=f"k_{g['名']}")
                scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
        
        if st.button("このシーンを保存", use_container_width=True):
            if s_name:
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
                st.session_state.s_list.extend(scene_tmp); st.rerun()

st.divider()

# --- 5. スケジュール自動生成 (赤池店スタイル) ---
st.header("3. スケジュール & 特異日設定")
all_scene_opts = sorted(list(set([f"{s['sn']} [{s['zn']}]" for s in st.session_state.s_list])))

if not all_scene_opts:
    st.warning("先にシーンを登録してください。")
else:
    st.subheader("⏰ 間隔指定・交互シーン生成")
    c1, c2, c3 = st.columns(3)
    g_start = c1.time_input("開始", value=time(10, 0))
    g_end = c2.time_input("終了", value=time(21, 0))
    g_int = c3.number_input("間隔(分)", 1, 120, 8)
    
    sc1, sc2, sc3 = st.columns(3)
    s_a = sc1.selectbox("メインシーン(A)", options=all_scene_opts)
    s_b = sc2.selectbox("交互シーン(B) ※任意", options=["なし"] + all_scene_opts)
    s_rep = sc3.selectbox("繰り返し", options=DAY_OPTIONS)
    
    if st.button("⏰ スケジュールを一括自動生成して追加"):
        new_rows = []
        curr = datetime.combine(datetime.today(), g_start)
        end = datetime.combine(datetime.today(), g_end)
        idx = 0
        while curr <= end:
            s_target = s_a if (idx % 2 == 0 or s_b == "なし") else s_b
            new_rows.append({"時刻": curr.time(), "シーン選択": s_target, "繰り返し": s_rep})
            curr += timedelta(minutes=g_int)
            idx += 1
        st.session_state.t_df = pd.concat([st.session_state.t_df, pd.DataFrame(new_rows)]).drop_duplicates().sort_values("時刻")
        st.success("追加しました。下の表で編集可能です。")

    # 常に時刻の型をきれいに保つ
    st.session_state.t_df["時刻"] = st.session_state.t_df["時刻"].apply(safe_to_time)

    st.session_state.t_df = st.data_editor(
        st.session_state.t_df,
        column_config={
            "時刻": st.column_config.TimeColumn("時刻", format="HH:mm", required=True),
            "シーン選択": st.column_config.SelectboxColumn("シーン選択", options=all_scene_opts, required=True),
            "繰り返し": st.column_config.SelectboxColumn("適用曜日", options=DAY_OPTIONS, required=True)
        },
        num_rows="dynamic", use_container_width=True
    )

    st.subheader("📅 特異日設定")
    with st.form("p_form", clear_on_submit=True):
        pn = st.text_input("特異日名称")
        pc1, pc2 = st.columns(2)
        p_sd, p_ed = pc1.date_input("開始日"), pc2.date_input("終了日")
        p_target_z = st.selectbox("対象ゾーン", options=vz)
        p_rep = st.selectbox("適用スケジュール", options=DAY_OPTIONS)
        if st.form_submit_button("追加"):
            st.session_state.p_list.append({"名": pn, "zn": p_target_z, "sd": p_sd, "ed": p_ed, "rep": p_rep})
            st.rerun()

st.divider()

# --- 6. 書き出し ---
st.header("4. データ書き出し")
if st.button("📦 ゲートウェイ用 .tar を生成", type="primary", use_container_width=True):
    df = pd.DataFrame("", index=range(1000), columns=range(NUM_COLS))
    for i, z in enumerate(st.session_state.z_list): df.iloc[i, 0:3] = [z["名"], "", z["秒"]]
    for i, g in enumerate(st.session_state.g_list): df.iloc[i, 4:8] = [g["名"], "", GROUP_TYPES[g["型"]], g["ゾ"]]
    for i, r in enumerate(st.session_state.s_list):
        color = f"{r['ex']}/{r['ey']}" if r['ex'] != "" else r['kel']
        # index 13: perform列を空欄
        df.iloc[i, 9:16] = [r["sn"], "", r["dim"], color, "", r["zn"], r["gn"]]
    
    idx_tt = 0
    t_df = st.session_state.t_df
    for z_name in vz:
        for rep in DAY_OPTIONS:
            slots = t_df[t_df["シーン選択"].str.contains(f"\[{z_name}\]", na=False) & (t_df["繰り返し"] == rep)].copy()
            if not slots.empty:
                slots = slots.sort_values("時刻")
                tt_n = f"{z_name}_{rep}_TT"
                df.iloc[idx_tt, 17:20] = [tt_n, "", z_name]
                for j, (_, s) in enumerate(slots.head(80).iterrows()):
                    t_str = s["時刻"].strftime("%H:%M")
                    df.iloc[idx_tt, 22 + j*2], df.iloc[idx_tt, 23 + j*2] = t_str, s["シーン選択"].split(" [")[0]
                df.iloc[idx_tt, 183] = z_name
                rep_c = 184 if rep == "毎日" else 185 + DAY_OPTIONS.index(rep) - 1
                df.iloc[idx_tt, rep_c] = tt_n
                idx_tt += 1

    for i, p in enumerate(st.session_state.p_list):
        df.iloc[i, 193:198] = [p["名"], p["sd"].strftime("%m月%d日"), p["ed"].strftime("%m月%d日"), f"{p['zn']}_{p['rep']}_TT", p['zn']]

    # ヘッダー構築 (236列完全再現)
    h0 = [""] * NUM_COLS
    h0[0], h0[4], h0[9], h0[17], h0[183], h0[193] = 'Zone情報','Group情報','Scene情報','Timetable情報','Timetable-schedule情報','Timetable期間/特異日情報'
    h2 = [""] * NUM_COLS
    h2[0:3], h2[4:8], h2[9:16], h2[17:22] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]'], ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]'], ['[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]']
    for j in range(22, 182, 2): h2[j], h2[j+1] = '[time]','[scene]'
    h2[183:192] = ['[zone-ts]','[daily]','[monday]','[tuesday]','[wednesday]','[thursday]','[friday]','[saturday]','[sunday]']
    h2[193:198] = ['[zone-period]','[start]','[end]','[timetable]','[zone]']

    final_df = pd.concat([pd.DataFrame([h0, [""]*NUM_COLS, h2]), df], ignore_index=True)
    csv_buf = io.BytesIO()
    # quoting=csv.QUOTE_ALL (1) で全ての値を強制的に引用符で囲み、日付変換を完全に防ぐ
    final_df.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n', quoting=csv.QUOTE_ALL)
    
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        b = csv_buf.getvalue(); info = tarfile.TarInfo(name="setting_data.csv"); info.size = len(b); tar.addfile(info, io.BytesIO(b))
        j = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8'); ji = tarfile.TarInfo(name="temp.json"); ji.size = len(j); tar.addfile(ji, io.BytesIO(j))

    st.download_button(f"📥 {shop_name}_FitPlus.tar を保存", tar_buf.getvalue(), f"{shop_name}.tar")
