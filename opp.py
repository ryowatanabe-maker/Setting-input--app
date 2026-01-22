import streamlit as st
import pandas as pd
import io
import json
import tarfile

# --- 定数 (インポート可能.tarの成功条件を完コピ) ---
NUM_COLS = 72
Z_ID, G_ID, S_ID = 4097, 32769, 8193
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

st.title("FitPlus 最終解決版 (直接tar出力) ⚙️")

# (中略: 登録UI部分はそのまま)

st.header("4. ゲートウェイ用インポートファイル作成 💾")
st.info("ボタンを押すと、そのままアップロード可能な .tar ファイルを作成します。")

if st.button("インポート用 .tar を作成して保存", type="primary"):
    # 1. CSVデータの作成 (72列・BOMなし)
    mat = pd.DataFrame(index=range(100), columns=range(NUM_COLS)).fillna('')
    for i, z in enumerate(st.session_state.z_list): mat.iloc[i, 0:3] = [z["名"], Z_ID + i, z["秒"]]
    for i, g in enumerate(st.session_state.g_list): mat.iloc[i, 4:8] = [g["名"], G_ID + i, GROUP_TYPE_MAP.get(g["型"]), g["ゾ"]]
    s_db, s_cnt = {}, S_ID
    for i, r in enumerate(st.session_state.s_list):
        key = (r["sn"], r["zn"])
        if key not in s_db: s_db[key] = s_cnt; s_cnt += 1
        mat.iloc[i, 9:16] = [r["sn"], s_db[key], r["dim"], r["kel"], r["syn"], r["zn"], r["gn"]]

    R1 = [''] * NUM_COLS
    R1[0], R1[4], R1[9], R1[17] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報'
    R3 = [''] * NUM_COLS
    R3[0:3], R3[4:8] = ['[zone]','[id]','[fade]'], ['[group]','[id]','[type]','[zone]']
    R3[9:16] = ['[scene]','[id]','[dimming]','[color]','[perform]','[zone]','[group]']
    
    final_df = pd.concat([pd.DataFrame([R1, ['']*NUM_COLS, R3]), mat], ignore_index=True).iloc[:, :72]
    
    # CSVをメモリ上でバイナリ化
    csv_buf = io.BytesIO()
    final_df.to_csv(csv_buf, index=False, header=False, encoding="utf-8", quoting=3, escapechar=' ', lineterminator='\r\n')
    csv_data = csv_buf.getvalue()

    # 2. JSONデータの作成
    json_data = json.dumps({"pair": [], "csv": "setting_data"}, indent=2).encode('utf-8')

    # 3. メモリ上で直接 TAR ファイルを作成 (ゴミが入らないように)
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        # CSVを追加
        csv_info = tarfile.TarInfo(name="setting_data.csv")
        csv_info.size = len(csv_data)
        tar.addfile(tarinfo=csv_info, fileobj=io.BytesIO(csv_data))
        
        # JSONを追加
        json_info = tarfile.TarInfo(name="temp.json")
        json_info.size = len(json_data)
        tar.addfile(tarinfo=json_info, fileobj=io.BytesIO(json_data))

    st.success("tarファイルの作成に成功しました！展開せず、そのままアップロードしてください。")
    st.download_button("📥 ゲートウェイ用tarを保存", tar_buf.getvalue(), "import_data.tar", "application/x-tar")
