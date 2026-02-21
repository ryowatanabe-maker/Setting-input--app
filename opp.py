import streamlit as st
import pandas as pd
import io
import json
import tarfile

# --- 1. 定数 (見本データ・赤池店形式 236列を完全再現) ---
NUM_COLS = 236
Z_ID_BASE, G_ID_BASE, S_ID_BASE = 4097, 32769, 8193
TYPE_MAP = {"調光": "dim", "調光調色": "color", "Synca": "color"} # 見本のtype表記に合わせました

st.set_page_config(page_title="FitPlus 安定版 (CSV構造再現)", layout="wide")
st.title("FitPlus ⚙️ 赤池店形式・236列出力")

# セッション状態の維持
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []

# --- 2. 登録セクション (UI) ---
c1, c2 = st.columns(2)
with c1:
    with st.form("z_f", clear_on_submit=True):
        st.subheader("1. ゾーン登録")
        zn = st.text_input("ゾーン名 (例: 店内)")
        zf = st.number_input("フェード秒", 0, 60, 0)
        if st.form_submit_button("追加"):
            if zn: 
                st.session_state.z_list.append({"名": zn, "秒": zf})
                st.rerun()
    
    for i, z in enumerate(st.session_state.z_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"📍 {z['名']} (ID: {Z_ID_BASE+i})")
        if cr.button("削除", key=f"dz_{i}"):
            st.session_state.z_list.pop(i)
            st.rerun()

with c2:
    vz = [""] + [z["名"] for z in st.session_state.z_list]
    with st.form("g_f", clear_on_submit=True):
        st.subheader("2. グループ登録")
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(TYPE_MAP.keys()))
        gz = st.selectbox("所属ゾーン", options=vz)
        if st.form_submit_button("追加"):
            if gn and gz:
                st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz})
                st.rerun()
    
    for i, g in enumerate(st.session_state.g_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"💡 {g['名']} ({g['ゾ']})")
        if cr.button("削除", key=f"dg_{i}"):
            st.session_state.g_list.pop(i)
            st.rerun()

st.header("3. シーン設定")
with st.container(border=True):
    col_sn, col_sz = st.columns(2)
    s_name = col_sn.text_input("シーン名 (例: 全点灯)")
    s_zone = col_sz.selectbox("設定ゾーン", options=vz, key="sz_s")
    
    if s_zone:
        target_gs = [g for g in st.session_state.g_list if g["ゾ"] == s_zone]
        scene_tmp = []
        for g in target_gs:
            st.write(f"■ {g['名']}")
            cc1, cc2 = st.columns(2)
            dim = cc1.number_input("調光%", 0, 100, 100, key=f"d_{g['名']}_{s_name}")
            kel = cc2.text_input("色温度", "3500", key=f"k_{g['名']}_{s_name}") if g['型'] != "調光" else ""
            scene_tmp.append({"sn": s_name, "gn": g['名'], "zn": s_zone, "dim": dim, "kel": kel})
        
        if st.button("このシーン設定を保存", use_container_width=True):
            if s_name:
                # 既存の同じシーン名/ゾーンがあれば削除（上書き）
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
                st.session_state.s_list.extend(scene_tmp)
                st.success(f"シーン『{s_name}』を保存しました")

# --- 3. CSV生成ロジック (見本データのヘッダー構造を完全再現) ---
st.divider()
if st.button("📥 インポート専用 .tar を出力", type="primary", use_container_width=True):
    # 236列の空枠
    df = pd.DataFrame("", index=range(100), columns=range(NUM_COLS))
    
    # データの流し込み
    for i, z in enumerate(st.session_state.z_list):
        df.iloc[i, 0:3] = [z["名"], Z_ID_BASE + i, z["秒"]]
    
    for i, g in enumerate(st.session_state.g_list):
        df.iloc[i, 4:8] = [g["名"], G_ID_BASE + i, TYPE_MAP.get(g["型"]), g["ゾ"]]
    
    s_m, s_idx = {}, S_ID_BASE
    for i, r in enumerate(st.session_state.s_list):
        k = (r["sn"], r["zn"])
        if k not in s_m:
            s_m[k] = s_idx
            s_idx += 1
        df.iloc[i, 9:16] = [r["sn"], s_m[k], r["dim"], r["kel"], "static", r["zn"], r["gn"]]

    # ヘッダー作成 (見本CSVから抽出)
    h0 = [""] * NUM_COLS
    h0[0], h0[4], h0[9], h0[17], h0[194], h0[205], h0[212], h0[218], h0[221], h0[232] = 'Zone情報','Group情報','Scene情報','Timetable情報','Timetable-schedule情報','Timetable期間/特異日情報','センサーパターン情報','センサータイムテーブル情報','センサータイムテーブル/スケジュール情報','センサータイムテーブル期間/特異日情報'
    
    h2 = [""] * NUM_COLS
    h2[0:3] = ['[zone]','[id]','[fade]']
    h2[4:8] = ['[group]','[id]','[type]','[zone]']
    h2[9:16] = ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]']
    # タイムテーブル等の拡張ヘッダー
    h2[17:22] = ['[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]']
    for j in range(22, 194, 2): h2[j], h2[j+1] = '[time]','[scene]'
    h2[195:204] = ['[zone-ts]','[daily]','[monday]','[tuesday]','[wednesday]','[thursday]','[friday]','[saturday]','[sunday]']
    h2[206:211] = ['[zone-period]','[start]','[end]','[timetable]','[zone]']

    # 結合 (1行目:タイトル, 2行目:空, 3行目:ブラケットヘッダー)
    final_csv = pd.concat([pd.DataFrame([h0, [""]*NUM_COLS, h2]), df], ignore_index=True)

    # バイナリ化
    csv_buf = io.BytesIO()
    final_csv.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    csv_bytes = csv_buf.getvalue()

    # TAR作成
    json_bytes = json.dumps({"pair": [], "csv": "setting_data.csv"}, indent=2).encode('utf-8')
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        c_info = tarfile.TarInfo(name="setting_data.csv"); c_info.size = len(csv_bytes)
        tar.addfile(c_info, io.BytesIO(csv_bytes))
        j_info = tarfile.TarInfo(name="temp.json"); j_info.size = len(json_bytes)
        tar.addfile(j_info, io.BytesIO(json_bytes))

    st.success("書き出し準備完了！")
    st.download_button("📥 ゲートウェイ用tarを保存", tar_buf.getvalue(), "FitPlus_Setup.tar")
