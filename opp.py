import streamlit as st
import pandas as pd
import io
import json

# --- 1. 定数定義 (BBR4HG / 大利根店形式を完全コピー) ---
NUM_COLS = 72
Z_ID, G_ID, S_ID, T_ID = 4097, 32769, 8193, 12289
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

st.set_page_config(page_title="FitPlus 自己圧縮完全対応版", layout="wide")
st.title("FitPlus 設定作成 (BBR4HG / 自己圧縮対応) ⚙️")

# セッション初期化
for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
    if key not in st.session_state: st.session_state[key] = []

# --- 2. 登録UI (中略: これまでの入力フォームを使用) ---
# ※ ここにゾーン、グループ、シーンの登録UIが入ります

# --- 3. 出力ロジック (ここが運命の分かれ目) ---
st.divider()
st.header("3. インポート用データの書き出し 💾")

if st.button("setting_data.csv と temp.json を生成", type="primary", use_container_width=True):
    # 72列の白紙シート
    mat = pd.DataFrame(index=range(200), columns=range(NUM_COLS))
    
    # 1. ゾーン情報 (4097〜)
    for i, z in enumerate(st.session_state.z_list):
        mat.iloc[i, 0:3] = [z["名"], Z_ID + i, z["秒"]]
    
    # 2. グループ情報 (32769〜 / 7列目に親ゾーン名を固定)
    for i, g in enumerate(st.session_state.g_list):
        mat.iloc[i, 4:8] = [g["名"], G_ID + i, GROUP_TYPE_MAP.get(g["型"], "1ch"), g["ゾ"]]
    
    # 3. シーン情報 (8193〜 / 14列目に親ゾーン名を固定)
    s_db, s_cnt = {}, S_ID
    for i, s in enumerate(st.session_state.s_list):
        key = (s["sn"], s["zn"])
        if key not in s_db: s_db[key] = s_cnt; s_cnt += 1
        mat.iloc[i, 9:16] = [s["sn"], s_db[key], s["dim"], s["kel"], s["syn"], s["zn"], s["gn"]]

    # --- CSVヘッダー再現 ---
    ROW1 = [None] * NUM_COLS
    ROW1[0], ROW1[4], ROW1[9], ROW1[17], ROW1[33], ROW1[43] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報', 'Timetable-schedule情報', 'Timetable期間/特異日情報'
    ROW3 = [None] * NUM_COLS
    ROW3[0:3] = ['[zone]', '[id]', '[fade]']
    ROW3[4:8] = ['[group]', '[id]', '[type]', '[zone]']
    ROW3[9:16] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]']
    
    final_df = pd.concat([pd.DataFrame([ROW1, [None]*NUM_COLS, ROW3]), mat.dropna(how='all')], ignore_index=True)

    # --- 【重要】BOMなしUTF-8で出力 ---
    buf_csv = io.BytesIO()
    # encoding="utf-8" (sigなし) にすることでBOMを排除！
    final_df.to_csv(buf_csv, index=False, header=False, encoding="utf-8", lineterminator='\r\n')
    
    # --- JSON作成 ---
    json_str = json.dumps({"pair": [], "csv": "setting_data"}, indent=2)
    buf_json = io.BytesIO(json_str.encode('utf-8'))

    st.success("BOMなし・4097形式で生成しました！")
    st.download_button("1. setting_data.csv を保存", buf_csv.getvalue(), "setting_data.csv")
    st.download_button("2. temp.json を保存", buf_json.getvalue(), "temp.json")
