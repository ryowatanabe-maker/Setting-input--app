import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta, time
import os

# --- 1. 定数設定 (赤池店 236列構成準拠) ---
NUM_COLS = 236 
GROUP_TYPES = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
DAY_OPTIONS = ["毎日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

st.set_page_config(page_title="FitPlus Pro v400", layout="wide")

# セッション状態の初期化
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []
if 't_slots' not in st.session_state: st.session_state.t_slots = []
if 'p_list' not in st.session_state: st.session_state.p_list = []

# --- 2. プロジェクト管理 ---
st.sidebar.title("🏢 プロジェクト管理")
shop_name = st.sidebar.text_input("店舗名", "FitPlus_Project")
if st.sidebar.button("全データをリセット"):
    for key in ['z_list', 'g_list', 's_list', 't_slots', 'p_list']: st.session_state[key] = []
    st.rerun()

st.title(f"FitPlus ⚙️ {shop_name}")

# --- 3. 構成登録 ---
st.header("1. ゾーン & グループ登録")
c1, c2 = st.columns(2)
vz = [z["名"] for z in st.session_state.z_list]

with c1:
    st.subheader("📍 ゾーン履歴")
    with st.form("z_form", clear_on_submit=True):
        zn = st.text_input("ゾーン名")
        zf = st.number_input("フェード時間(秒)", 0, 3600, 0)
        if st.form_submit_button("追加"):
            if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    for i, z in enumerate(st.session_state.z_list):
        cols = st.columns([4, 1])
        cols[0].info(f"ゾーン: {z['名']} / {z['秒']}s")
        if cols[1].button("削除", key=f"dz_{i}"):
            st.session_state.z_list.pop(i); st.rerun()

with c2:
    st.subheader("💡 グループ履歴")
    with st.form("g_form", clear_on_submit=True):
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(GROUP_TYPES.keys()))
        gz = st.selectbox("所属ゾーン", options=[""] + vz)
        if st.form_submit_button("追加"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
    for i, g in enumerate(st.session_state.g_list):
        cols = st.columns([4, 1])
        cols[0].success(f"{g['名']} [{g['型']}] ({g['ゾ']})")
        if cols[1].button("削除", key=f"dg_{i}"):
            st.session_state.g_list.pop(i); st.rerun()

st.divider()

# --- 4. シーン作成 & 履歴 ---
st.header("2. シーン作成 & 履歴")
c_edit, c_hist = st.columns([1, 1])

with c_edit:
    st.subheader("🎨 シーン新規作成")
    if os.path.exists("synca_palette.png"):
        st.image("synca_palette.png", caption="Synca演出パレット (1～11)", width=500)
    
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
                        ex = cx.slider("X", 1, 11, 6, key=f"x_{g['名']}_{s_name}")
                        ey = cy.slider("Y", 1, 11, 6, key=f"y_{g['名']}_{s_name}")
                    else: kel = st.text_input("色温度(K)", "4000", key=f"ks_{g['名']}")
                elif g['型'] == "調光調色":
                    kel = st.text_input("色温度(K)", "4000", key=f"k_{g['名']}")
                scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
        
        if st.button("このシーン設定を保存", use_container_width=True):
            if s_name:
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
                st.session_state.s_list.extend(scene_tmp); st.rerun()

with c_hist:
    st.subheader("📜 作成済みシーン詳細")
    if not st.session_state.s_list: st.write("なし")
    else:
        h_df = pd.DataFrame(st.session_state.s_list)
        for (sn, zn), group in h_df.groupby(['sn', 'zn']):
            with st.container(border=True):
                st.write(f"**{sn}** ({zn})")
                details = [f"- {r['gn']}: {r['dim']}% / {f'{r['ex']}/{r['ey']}' if r['ex'] else f'{r['kel']}K'}" for _, r in group.iterrows()]
                st.write("\n".join(details))
                if st.button("削除", key=f"del_sh_{sn}_{zn}"):
                    st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == sn and s["zn"] == zn)]
                    st.rerun()

st.divider()

# --- 5. スケジュール & 特異日 ---
st.header("3. スケジュール & 特異日設定")
all_scene_opts = sorted(list(set([f"{s['sn']} [{s['zn']}]" for s in st.session_state.s_list])))

if not all_scene_opts:
    st.warning("先にシーンを登録してください。")
else:
    st.subheader("⏰ スケジュール自動生成 (間隔指定)")
    c1, c2, c3 = st.columns(3)
    gen_start = c1.time_input("開始時刻", value=time(9, 0))
    gen_end = c2.time_input("終了時刻", value=time(21, 0))
    gen_interval = c3.number_input("間隔(分)", 1, 120, 8)
    
    sc1, sc2 = st.columns(2)
    scene_a = sc1.selectbox("メインシーン(A)", options=all_scene_opts)
    scene_b = sc2.selectbox("交互シーン(B) ※任意", options=["なし"] + all_scene_opts)
    
    if st.button("⏰ スケジュールを一括自動生成", use_container_width=True):
        new_slots = []
        curr = datetime.combine(datetime.today(), gen_start)
        end = datetime.combine(datetime.today(), gen_end)
        count = 0
        while curr <= end and len(new_slots) < 80:
            s_target = scene_a
            if scene_b != "なし" and count % 2 != 0:
                s_target = scene_b
            new_slots.append({"時刻": curr.time(), "シーン選択": s_target, "繰り返し": "毎日"})
            curr += timedelta(minutes=gen_interval)
            count += 1
        st.session_state.t_slots = new_slots
        st.success(f"{len(new_slots)}件のスロットを生成しました。下の表で編集・保存してください。")

    st.subheader("📝 スケジュール個別編集・確定")
    # 時刻が文字列の場合はtimeオブジェクトに変換してエディタに渡す
    processed_t = []
    for s in st.session_state.t_slots:
        t_obj = s["時刻"]
        if isinstance(t_obj, str): t_obj = datetime.strptime(t_obj, "%H:%M").time()
        processed_t.append({"時刻": t_obj, "シーン選択": s["シーン選択"], "繰り返し": s["繰り返し"]})

    tt_editor = st.data_editor(
        processed_t,
        column_config={
            "時刻": st.column_config.TimeColumn("時刻", format="HH:mm", required=True),
            "シーン選択": st.column_config.SelectboxColumn("シーン [ゾーン]", options=all_scene_opts, required=True),
            "繰り返し": st.column_config.SelectboxColumn("適用曜日", options=DAY_OPTIONS, required=True)
        },
        num_rows="dynamic", use_container_width=True, key="main_tt_editor"
    )
    
    if st.button("スケジュールを保存して確定", use_container_width=True):
        st.session_state.t_slots = tt_editor
        st.success("保存しました。")

    st.subheader("📅 期間・特異日設定")
    with st.form("p_form", clear_on_submit=True):
        pn = st.text_input("特異日名称")
        pc1, pc2 = st.columns(2)
        p_sd, p_ed = pc1.date_input("開始日"), pc2.date_input("終了日")
        p_target_z = st.selectbox("対象ゾーン", options=vz)
        p_rep = st.selectbox("適用スケジュール種別", options=DAY_OPTIONS)
        if st.form_submit_button("特異日を追加"):
            st.session_state.p_list.append({"名": pn, "zn": p_target_z, "sd": p_sd, "ed": p_ed, "rep": p_rep})
            st.rerun()
    for i, p in enumerate(st.session_state.p_list):
        cols = st.columns([4, 1])
        cols[0].warning(f"🗓️ {p['名']}: {p['sd']}～{p['ed']} (ゾーン:{p['zn']} / 適用:{p['rep']})")
        if cols[1].button("削除", key=f"dp_{i}"): st.session_state.p_list.pop(i); st.rerun()

st.divider()

# --- 6. データ書き出し (236列・ID/Perform空欄) ---
st.header("4. データ出力")
if st.button("📦 ゲートウェイ用 .tar を生成", type="primary", use_container_width=True):
    df = pd.DataFrame("", index=range(1000), columns=range(NUM_COLS))
    for i, z in enumerate(st.session_state.z_list): df.iloc[i, 0:3] = [z["名"], "", z["秒"]]
    for i, g in enumerate(st.session_state.g_list): df.iloc[i, 4:8] = [g["名"], "", GROUP_TYPES[g["型"]], g["ゾ"]]
    for i, r in enumerate(st.session_state.s_list):
        # Syncaの日付化防止
        color = f"'{r['ex']}/{r['ey']}" if r['ex'] != "" else r['kel']
        df.iloc[i, 9:16] = [r["sn"], "", r["dim"], color, "", r["zn"], r["gn"]]
    
    idx_tt = 0
    t_df = pd.DataFrame(st.session_state.t_slots)
    if not t_df.empty:
        for z_name in vz:
            for rep in DAY_OPTIONS:
                slots = t_df[t_df["シーン選択"].str.contains(f"\[{z_name}\]", na=False) & (t_df["繰り返し"] == rep)].copy()
                if not slots.empty:
                    slots = slots.sort_values("時刻")
                    tt_n = f"{z_name}_{rep}_TT"
                    df.iloc[idx_tt, 17:20] = [tt_n, "", z_name]
                    for j, (_, s) in enumerate(slots.head(80).iterrows()):
                        t_str = s["時刻"].strftime("%H:%M") if hasattr(s["時刻"], "strftime") else str(s["時刻"])[:5]
                        df.iloc[idx_tt, 22 + j*2] = t_str
                        df.iloc[idx_tt, 23 + j*2] = s["シーン選択"].split(" [")[0]
                    # スケジュール割当 (183:zone-ts, 184:daily...)
                    df.iloc[idx_tt, 183] = z_name
                    rep_c = 184 if rep == "毎日" else 185 + DAY_OPTIONS.index(rep) - 1
                    df.iloc[idx_tt, rep_c] = tt_n
                    idx_tt += 1

    for i, p in enumerate(st.session_state.p_list):
        df.iloc[i, 193:198] = [p["名"], p["sd"].strftime("%m月%d日"), p["ed"].strftime("%m月%d日"), f"{p['zn']}_{p['rep']}_TT", p['zn']]

    # ヘッダー (236列完全再現)
    h0 = [""] * NUM_COLS
    h0[0], h0[4], h0[9], h0[17], h0[183], h0[193] = 'Zone情報','Group情報','Scene情報','Timetable情報','Timetable-schedule情報','Timetable期間/特異日情報'
    h2 = [""] * NUM_COLS
    h2[0:3], h2[4:8], h2[9:16], h2[17:22] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]'], ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]'], ['[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]']
    for j in range(22, 182, 2): h2[j], h2[j+1] = '[time]','[scene]'
    h2[183:192] = ['[zone-ts]','[daily]','[monday]','[tuesday]','[wednesday]','[thursday]','[friday]','[saturday]','[sunday]']
    h2[193:198] = ['[zone-period]','[start]','[end]','[timetable]','[zone]']

    final_df = pd.concat([pd.DataFrame([h0, [""]*NUM_COLS, h2]), df], ignore_index=True)
    csv_buf = io.BytesIO(); final_df.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        b = csv_buf.getvalue(); info = tarfile.TarInfo(name="setting_data.csv"); info.size = len(b); tar.addfile(info, io.BytesIO(b))
        j = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8'); ji = tarfile.TarInfo(name="temp.json"); ji.size = len(j); tar.addfile(ji, io.BytesIO(j))

    st.download_button(f"📥 {shop_name}_FitPlus.tar を保存", tar_buf.getvalue(), f"{shop_name}.tar")
