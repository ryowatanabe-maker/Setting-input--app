import streamlit as st
import pandas as pd
import io
import json
import tarfile

# --- 1. 定数 (見本CSV 236列を完全再現) ---
NUM_COLS = 236
Z_ID_BASE, G_ID_BASE, S_ID_BASE = 4097, 32769, 8193
TYPE_MAP = {"調光": "dim", "調光調色": "color", "Synca": "color"}

st.set_page_config(page_title="FitPlus 最終解決版", layout="wide")
st.title("FitPlus ⚙️ 厳密配置・インポート復旧版")

if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []

# --- 2. 登録セクション (UI) ---
c1, c2 = st.columns(2)
with c1:
    with st.form("z_f", clear_on_submit=True):
        st.subheader("1. ゾーン登録")
        zn = st.text_input("ゾーン名")
        zf = st.number_input("フェード秒", 0, 60, 0)
        if st.form_submit_button("追加"):
            if zn: st.session_state.z_list.append({"名": zn, "秒": zf}); st.rerun()
    
    for i, z in enumerate(st.session_state.z_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"📍 {z['名']}")
        if cr.button("削除", key=f"dz_{i}"): st.session_state.z_list.pop(i); st.rerun()

with c2:
    vz = [""] + [z["名"] for z in st.session_state.z_list]
    with st.form("g_f", clear_on_submit=True):
        st.subheader("2. グループ登録")
        gn = st.text_input("グループ名")
        gt = st.selectbox("タイプ", list(TYPE_MAP.keys()))
        gz = st.selectbox("所属ゾーン", options=vz)
        if st.form_submit_button("追加"):
            if gn and gz: st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz}); st.rerun()
    
    for i, g in enumerate(st.session_state.g_list):
        cl, cr = st.columns([4, 1])
        cl.write(f"💡 {g['名']} ({g['ゾ']})")
        if cr.button("削除", key=f"dg_{i}"): st.session_state.g_list.pop(i); st.rerun()

st.header("3. シーン設定")
with st.container(border=True):
    col_sn, col_sz = st.columns(2)
    s_name = col_sn.text_input("シーン名")
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
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["sn"] == s_name and s["zn"] == s_zone)]
                st.session_state.s_list.extend(scene_tmp); st.rerun()

# --- 3. CSV生成 (見本CSVの列・カンマの数を完全再現) ---
st.divider()
if st.button("📥 インポート専用 .tar を出力", type="primary", use_container_width=True):
    # データ部分 (200行 x 236列)
    df = pd.DataFrame("", index=range(200), columns=range(NUM_COLS))
    
    # ゾーン(0-2)
    for i, z in enumerate(st.session_state.z_list):
        df.iloc[i, 0:3] = [z["名"], Z_ID_BASE + i, z["秒"]]
    
    # グループ(4-7) ※3列目は空
    for i, g in enumerate(st.session_state.g_list):
        df.iloc[i, 4:8] = [g["名"], G_ID_BASE + i, TYPE_MAP.get(g["型"]), g["ゾ"]]
    
    # シーン(9-15) ※8列目は空
    s_m, s_idx = {}, S_ID_BASE
    for i, r in enumerate(st.session_state.s_list):
        k = (r["sn"], r["zn"])
        if k not in s_m: s_m[k] = s_idx; s_idx += 1
        # シーン配置: [scene],[id],[dimming],[color],[perform],[zone],[group]
        # index 9, 10, 11, 12, 13, 14, 15
        df.iloc[i, 9:16] = [r["sn"], s_m[k], r["dim"], r["kel"], "static", r["zn"], r["gn"]]

    # ヘッダー (見本CSVをバイナリ解析した結果に基づく厳密な配置)
    h0 = [""] * NUM_COLS
    h0[0], h0[4], h0[9], h0[17], h0[35], h0[45], h0[51], h0[56], h0[59], h0[70] = \
        'Zone情報','Group情報','Scene情報','Timetable情報','Timetable-schedule情報','Timetable期間/特異日情報','センサーパターン情報','センサータイムテーブル情報','センサータイムテーブル/スケジュール情報','センサータイムテーブル期間/特異日情報'
    
    h2 = [""] * NUM_COLS
    h2[0:3] = ['[zone]','[id]','[fade]']
    h2[4:8] = ['[group]','[id]','[type]','[zone]']
    h2[9:16] = ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]']
    # 17列目以降も見本に忠実に
    h2[17:22] = ['[zone-timetable]','[id]','[zone]','[sun-start-scene]','[sun-end-scene]']

    final_csv = pd.concat([pd.DataFrame([h0, [""]*NUM_COLS, h2]), df], ignore_index=True)

    csv_buf = io.BytesIO()
    # ゲートウェイの仕様に合わせ BOMありUTF-8 + CRLF
    final_csv.to_csv(csv_buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    
    # TAR作成
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        c_bytes = csv_buf.getvalue()
        c_info = tarfile.TarInfo(name="setting_data.csv"); c_info.size = len(c_bytes)
        tar.addfile(c_info, io.BytesIO(c_bytes))
        j_bytes = json.dumps({"pair": [], "csv": "setting_data.csv"}, indent=2).encode('utf-8')
        j_info = tarfile.TarInfo(name="temp.json"); j_info.size = len(j_bytes)
        tar.addfile(j_info, io.BytesIO(j_bytes))

    st.success("列配置を修正しました。これでインポートを試してください。")
    st.download_button("📥 ゲートウェイ用tarを保存", tar_buf.getvalue(), "FitPlus_Fix.tar")
