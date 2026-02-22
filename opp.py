import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import time, timedelta, datetime

# --- 1. 定数・マニュアル準拠設定 ---
NUM_COLS = 236
Z_ID_BASE, G_ID_BASE, S_ID_BASE = 4097, 32769, 8193
TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch"}

st.set_page_config(page_title="FitPlus Pro v80", layout="wide")
st.title("FitPlus ⚙️ 統合設定ツール (スケジュール & パレット対応)")

# セッション状態の初期化
for key in ['z_list', 'g_list', 's_list', 't_list']:
    if key not in st.session_state: st.session_state[key] = []

# --- 2. 登録セクション ---
tab1, tab2, tab3, tab4 = st.tabs(["🏗️ ゾーン・グループ", "🎨 シーン作成", "📅 スケジュール", "📥 書き出し"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        with st.form("z_form", clear_on_submit=True):
            st.subheader("1. ゾーン登録")
            zn = st.text_input("ゾーン名 (最大32文字)", max_chars=32)
            zf = st.number_input("フェード時間(秒)", 0, 3600, 0)
            if st.form_submit_button("ゾーン追加"):
                if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
        for i, z in enumerate(st.session_state.z_list):
            st.write(f"📍 {z['名']} ({z['秒']}s)")

    with c2:
        vz = [z["名"] for z in st.session_state.z_list]
        with st.form("g_form", clear_on_submit=True):
            st.subheader("2. グループ登録")
            gn = st.text_input("グループ名 (最大32文字)", max_chars=32)
            gt = st.selectbox("タイプ", list(TYPE_MAP.keys()))
            gz = st.selectbox("所属ゾーン", options=[""] + vz)
            if st.form_submit_button("グループ追加"):
                if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
        for i, g in enumerate(st.session_state.g_list):
            st.write(f"💡 {g['名']} ({g['ゾ']} / {g['型']})")

with tab2:
    st.subheader("3. シーン設定 & カラーパレット")
    col_sn, col_sz = st.columns(2)
    s_name = col_sn.text_input("シーン名 (例: 朝の点灯)", max_chars=32)
    s_zone = col_sz.selectbox("対象ゾーン", options=[""] + vz, key="sel_sz")

    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        scene_tmp = []
        for g in target_gs:
            with st.expander(f"■ {g['名']} ({g['型']}) の設定", expanded=True):
                cc1, cc2, cc3 = st.columns([1, 1, 2])
                dim = cc1.number_input("調光%", 0, 100, 100, key=f"d_{g['名']}_{s_name}")
                kel = cc2.number_input("色温度(K)", 1800, 12000, 4000, key=f"k_{g['名']}_{s_name}") if g['型'] != "調光" else 4000
                
                # Synca用カラーパレット (11x11) 
                ex, ey = "", ""
                if g['型'] == "Synca":
                    st.write("演出カラーパレット (X, Y)")
                    palette_data = [[f"{x},{y}" for x in range(11)] for y in range(10, -1, -1)]
                    sel_color = st.selectbox(f"色選択 ({g['名']})", 
                                           options=[f"X:{x}, Y:{y}" for y in range(11) for x in range(11)],
                                           index=60) # 中心付近をデフォルト
                    parts = sel_color.replace("X:","").replace("Y:","").split(",")
                    ex, ey = parts[0].strip(), parts[1].strip()
                
                scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
        
        if st.button("このシーンを保存", use_container_width=True):
            if s_name:
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
                st.session_state.s_list.extend(scene_tmp); st.success("シーンを保存しました")

with tab3:
    st.subheader("4. タイムテーブル (スケジュール) 設定")
    t_zone = st.selectbox("ゾーン選択", options=[""] + vz, key="t_sz")
    if t_zone:
        t_name = st.text_input("タイムテーブル名", "基本スケジュール")
        # 該当ゾーンの登録済みシーン
        available_scenes = sorted(list(set([s["sn"] for s in st.session_state.s_list if s["zn"] == t_zone])))
        
        if not available_scenes:
            st.warning("このゾーンにはまだシーンが登録されていません。")
        else:
            # 6分間隔生成機能
            if st.button("⏰ 6分間隔でスロットを自動生成"):
                start_t = datetime.strptime("09:00", "%H:%M")
                new_slots = []
                for i in range(10): # とりあえず10個
                    curr = (start_t + timedelta(minutes=i*6)).strftime("%H:%M")
                    new_slots.append({"time": curr, "scene": available_scenes[0]})
                st.session_state[f"temp_t_{t_zone}"] = new_slots

            # スケジュール編集
            if f"temp_t_{t_zone}" not in st.session_state: st.session_state[f"temp_t_{t_zone}"] = [{"time": "09:00", "scene": available_scenes[0]}]
            
            edited_slots = st.data_editor(st.session_state[f"temp_t_{t_zone}"], num_rows="dynamic")
            
            if st.button("このスケジュールを確定"):
                st.session_state.t_list = [t for t in st.session_state.t_list if not (t["zn"] == t_zone and t["tn"] == t_name)]
                st.session_state.t_list.append({"zn": t_zone, "tn": t_name, "slots": edited_slots})
                st.success("スケジュールを保存しました")

with tab4:
    st.subheader("5. 236列 CSV / .tar 出力")
    if st.button("📦 ゲートウェイ用設定ファイルを生成", type="primary", use_container_width=True):
        df = pd.DataFrame("", index=range(725), columns=range(NUM_COLS))
        
        # マップ作成
        z_names = [z["名"] for z in st.session_state.z_list]
        g_map_id = {g["名"]: G_ID_BASE + i for i, g in enumerate(st.session_state.g_list)}

        # Zone (0-2)
        for i, z in enumerate(st.session_state.z_list):
            df.iloc[i, 0:3] = [z["名"], "", z["秒"]]

        # Group (4-7)
        for i, g in enumerate(st.session_state.g_list):
            df.iloc[i, 4:8] = [g["名"], g_map_id[g["名"]], TYPE_MAP.get(g["型"]), g["ゾ"]]

        # Scene (9-15) 
        for i, r in enumerate(st.session_state.s_list):
            # perform列(13)に 'static' を入力
            color_val = f"{r['kel']}" if not r['ex'] else f"{r['ex']}/{r['ey']}"
            df.iloc[i, 9:16] = [r["sn"], "", r["dim"], color_val, "static", r["zn"], r["gn"]]

        # Timetable (17-193) [cite: 9, 12]
        for i, t in enumerate(st.session_state.t_list):
            base_col = 17
            df.iloc[i, base_col:base_col+3] = [t["tn"], "", t["zn"]]
            # スロット配置 (col 22から)
            for j, slot in enumerate(t["slots"][:80]): # 最大80スロット
                df.iloc[i, 22 + j*2] = slot["time"]
                df.iloc[i, 23 + j*2] = slot["scene"]

        # ヘッダー構築 [cite: 12]
        h0 = [""] * NUM_COLS
        h0[0], h0[4], h0[9], h0[17] = 'Zone情報','Group情報','Scene情報','Timetable情報'
        h2 = [""] * NUM_COLS
        h2[0:3] = ['[zone]','[id]','[fade]']
        h2[4:8] = ['[group]','[id]','[type]','[zone]']
        h2[9:16] = ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]']
        h2[17:22] = ['[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]']
        for j in range(22, 194, 2): h2[j], h2[j+1] = '[time]','[scene]'

        final_csv = pd.concat([pd.DataFrame([h0, [""]*NUM_COLS, h2]), df], ignore_index=True)

        csv_buf = io.BytesIO()
        final_csv.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
        
        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
            c_bytes = csv_buf.getvalue()
            c_info = tarfile.TarInfo(name="setting_data.csv"); c_info.size = len(c_bytes)
            tar.addfile(c_info, io.BytesIO(c_bytes))
            j_bytes = json.dumps({"pair": [], "csv": "setting_data.csv"}, indent=2).encode('utf-8')
            j_info = tarfile.TarInfo(name="temp.json"); j_info.size = len(j_bytes)
            tar.addfile(j_info, io.BytesIO(j_bytes))

        st.success("236列マニュアル準拠形式でパッケージを作成しました！")
        st.download_button("📥 FitPlus_Setup_Full.tar を保存", tar_buf.getvalue(), "FitPlus_Setup_Full.tar")
