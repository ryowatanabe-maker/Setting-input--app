import streamlit as st
import pandas as pd
import io
import json
import tarfile
from datetime import datetime, timedelta

# --- 1. 設定 ---
NUM_COLS = 236
G_ID_BASE = 32769
TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch"}

st.set_page_config(page_title="FitPlus Pro v90", layout="wide")

# サイドバー：店舗名とデータ管理
st.sidebar.title("🏢 プロジェクト管理")
shop_name = st.sidebar.text_input("店舗名", "FitPlus_Project")

if st.sidebar.button("データをすべて消去"):
    for key in ['z_list', 'g_list', 's_list', 't_list']: st.session_state[key] = []
    st.rerun()

# セッション状態の初期化 (履歴保持用)
for key in ['z_list', 'g_list', 's_list', 't_list']:
    if key not in st.session_state: st.session_state[key] = []

st.title(f"FitPlus ⚙️ {shop_name}")

# --- 2. UIセクション ---
tab1, tab2, tab3, tab4 = st.tabs(["🏗️ 構成登録", "🎨 シーン作成", "📅 スケジュール", "📥 書き出し"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. ゾーン登録")
        with st.form("z_form", clear_on_submit=True):
            zn = st.text_input("ゾーン名", max_chars=32)
            zf = st.number_input("フェード(秒)", 0, 3600, 0)
            if st.form_submit_button("追加"):
                if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
        
        # 履歴表示と削除
        for i, z in enumerate(st.session_state.z_list):
            cols = st.columns([3, 1])
            cols[0].write(f"📍 {z['名']} ({z['秒']}s)")
            if cols[1].button("削除", key=f"dz_{i}"):
                st.session_state.z_list.pop(i); st.rerun()

    with c2:
        st.subheader("2. グループ登録")
        vz = [z["名"] for z in st.session_state.z_list]
        with st.form("g_form", clear_on_submit=True):
            gn = st.text_input("グループ名", max_chars=32)
            gt = st.selectbox("タイプ", list(TYPE_MAP.keys()))
            gz = st.selectbox("所属ゾーン", options=[""] + vz)
            if st.form_submit_button("追加"):
                if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
        
        for i, g in enumerate(st.session_state.g_list):
            cols = st.columns([3, 1])
            cols[0].write(f"💡 {g['名']} ({g['ゾ']})")
            if cols[1].button("削除", key=f"dg_{i}"):
                st.session_state.g_list.pop(i); st.rerun()

with tab2:
    st.subheader("3. シーン設定")
    s_name = st.text_input("シーン名", max_chars=32)
    s_zone = st.selectbox("対象ゾーン", options=[""] + vz, key="sz")
    
    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        for g in target_gs:
            with st.expander(f"■ {g['名']} の設定"):
                dim = st.slider(f"調光%", 0, 100, 100, key=f"d_{g['名']}_{s_name}")
                ex, ey, kel = "", "", "4000"
                if g['型'] == "Synca":
                    c_ex, c_ey = st.columns(2)
                    ex = c_ex.slider("X (1-11)", 1, 11, 6, key=f"x_{g['名']}_{s_name}")
                    ey = c_ey.slider("Y (1-11)", 1, 11, 6, key=f"y_{g['名']}_{s_name}")
                elif g['型'] == "調光調色":
                    kel = st.text_input("色温度(K)", "4000", key=f"k_{g['名']}_{s_name}")
                
                if st.button(f"保存: {g['名']}", key=f"bs_{g['名']}"):
                    st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["gn"] == g['名'])]
                    st.session_state.s_list.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel, "ex": ex, "ey": ey})
                    st.toast(f"{g['名']} を保存しました")

with tab3:
    st.subheader("4. スケジュール")
    t_zone = st.selectbox("ゾーン選択", options=[""] + vz, key="tz")
    if t_zone:
        scenes = sorted(list(set([s["sn"] for s in st.session_state.s_list if s["zn"] == t_zone])))
        if st.button("⏰ 6分間隔で作成"):
            st.session_state[f"edit_{t_zone}"] = [{"時刻": (datetime.strptime("09:00", "%H:%M") + timedelta(minutes=i*6)).strftime("%H:%M"), "シーン": scenes[0] if scenes else ""} for i in range(10)]
        
        if f"edit_{t_zone}" not in st.session_state: st.session_state[f"edit_{t_zone}"] = []
        data = st.data_editor(st.session_state[f"edit_{t_zone}"], num_rows="dynamic")
        if st.button("スケジュール保存"):
            st.session_state.t_list = [t for t in st.session_state.t_list if t["zn"] != t_zone]
            st.session_state.t_list.append({"zn": t_zone, "slots": data})
            st.success("保存しました")

with tab4:
    if st.button("📦 1枚のCSVを含む .tar を生成", type="primary", use_container_width=True):
        df = pd.DataFrame("", index=range(730), columns=range(NUM_COLS))
        # Zone
        for i, z in enumerate(st.session_state.z_list): df.iloc[i, 0:3] = [z["名"], "", z["秒"]]
        # Group
        for i, g in enumerate(st.session_state.g_list): df.iloc[i, 4:8] = [g["名"], G_ID_BASE + i, TYPE_MAP[g["型"]], g["ゾ"]]
        # Scene (IDなし, 名称紐付け, static)
        for i, r in enumerate(st.session_state.s_list):
            color = f"{r['ex']}/{r['ey']}" if r['ex'] else r['kel']
            df.iloc[i, 9:16] = [r["sn"], "", r["dim"], color, "static", r["zn"], r["gn"]]
        # Timetable
        for i, t in enumerate(st.session_state.t_list):
            df.iloc[i, 17:20] = [f"{t['zn']}_TT", "", t['zn']]
            for j, s in enumerate(t["slots"]):
                df.iloc[i, 22+j*2], df.iloc[i, 23+j*2] = s["時刻"], s["シーン"]

        # ヘッダー (1枚のシートに統合)
        h0 = [""] * NUM_COLS
        h0[0], h0[4], h0[9], h0[17] = 'Zone情報','Group情報','Scene情報','Timetable情報'
        h2 = [""] * NUM_COLS
        h2[0:3], h2[4:8], h2[9:16], h2[17:22] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]'], ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]'], ['[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]']
        for j in range(22, 194, 2): h2[j], h2[j+1] = '[time]','[scene]'

        final = pd.concat([pd.DataFrame([h0, [""]*NUM_COLS, h2]), df], ignore_index=True)
        csv_out = io.BytesIO()
        final.to_csv(csv_out, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
        
        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
            b = csv_out.getvalue()
            info = tarfile.TarInfo(name="setting_data.csv"); info.size = len(b)
            tar.addfile(info, io.BytesIO(b))
            j = json.dumps({"pair": [], "csv": "setting_data.csv"}).encode('utf-8')
            j_info = tarfile.TarInfo(name="temp.json"); j_info.size = len(j)
            tar.addfile(j_info, io.BytesIO(j))

        st.download_button(f"📥 {shop_name}.tar を保存", tar_buf.getvalue(), f"{shop_name}.tar")
