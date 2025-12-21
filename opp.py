import streamlit as st
import pandas as pd
import io
import numpy as np

# --- 1. 定数とヘッダーの定義 ---
GROUP_TYPE_MAP = {
    "調光": "1ch",
    "調光調色": "2ch",
    "Synca": "3ch",
    "Synca Bright": "fresh 3ch"
}

NUM_COLS = 74

# 元のCSVヘッダー構造
ROW1 = ['Zone情報', None, None, None, 'Group情報', None, None, None, None, 'Scene情報', None, None, None, None, None, None, None, 'Timetable情報', None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, 'Timetable-schedule情報', None, None, None, None, None, None, None, None, None, 'Timetable期間/特異日情報', None, None, None, None, None, 'センサーパターン情報', None, None, None, None, 'センサータイムテーブル情報', None, None, 'センサータイムテーブル/スケジュール情報', None, None, None, None, None, None, None, None, None, 'センサータイムテーブル期間/特異日情報', None, None, None, None]
ROW2 = [None] * NUM_COLS
ROW3 = ['[zone]', '[id]', '[fade]', None, '[group]', '[id]', '[type]', '[zone]', None, '[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]', None, '[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', None, '[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]', None, '[zone-period]', '[start]', '[end]', '[timetable]', '[zone]', None, '[pattern]', '[id]', '[type]', '[mode]', None, '[sensor-timetable]', '[id]', None, '[sensor-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]', None, '[sensor-period]', '[start]', '[end]', '[timetable]', '[group]']

ROW1 = (ROW1 + [None] * NUM_COLS)[:NUM_COLS]
ROW3 = (ROW3 + [None] * NUM_COLS)[:NUM_COLS]
CSV_HEADER = [ROW1, ROW2, ROW3]

def make_unique_cols(header_row):
    seen = {}
    unique_names = []
    for i, name in enumerate(header_row):
        base = str(name) if name and str(name) != 'nan' else "col"
        if base not in seen:
            seen[base] = 0
            unique_names.append(base)
        else:
            seen[base] += 1
            unique_names.append(f"{base}_{seen[base]}")
    return unique_names

# --- 2. アプリ設定 ---
st.set_page_config(page_title="設定データ作成アプリ", layout="wide")
st.title("設定データ作成アプリ ⚙️")

# セッションステートの初期化
if 'z_df' not in st.session_state:
    st.session_state.z_df = pd.DataFrame([{"ゾーン名": "", "フェード秒": 0}])
if 'g_df' not in st.session_state:
    st.session_state.g_df = pd.DataFrame([{"グループ名": "", "グループタイプ": "調光", "紐づけるゾーン名": ""}])
if 's_df' not in st.session_state:
    st.session_state.s_df = pd.DataFrame([{"シーン名": "", "紐づけるグループ名": "", "紐づけるゾーン名": "", "調光": 100, "調色": ""}])
if 'scene_master' not in st.session_state:
    st.session_state.scene_master = []

# --- 3. UI セクション ---

st.header("1. 店舗名入力")
shop_name = st.text_input("店舗名", value="店舗A")
out_filename = f"{shop_name}_setting_data.csv"

st.divider()

# 2. ゾーン情報
st.header("2. ゾーン情報")
z_edit = st.data_editor(st.session_state.z_df, num_rows="dynamic", use_container_width=True, key="z_editor_v10")
st.session_state.z_df = z_edit
v_zones = [""] + [str(z).strip() for z in z_edit["ゾーン名"].tolist() if str(z).strip()]

# 3. グループ情報
st.header("3. グループ情報")
g_edit = st.data_editor(
    st.session_state.g_df,
    num_rows="dynamic",
    column_config={
        "グループタイプ": st.column_config.SelectboxColumn(options=list(GROUP_TYPE_MAP.keys())),
        "紐づけるゾーン名": st.column_config.SelectboxColumn(options=v_zones)
    },
    use_container_width=True,
    key="g_editor_v10"
)
st.session_state.g_df = g_edit
v_groups = [""] + [str(g).strip() for g in g_edit["グループ名"].tolist() if str(g).strip()]
g_to_zone_map = dict(zip(g_edit["グループ名"], g_edit["紐づけるゾーン名"]))
g_to_tp_map = dict(zip(g_edit["グループ名"], g_edit["グループタイプ"]))

st.divider()

# 4. シーン情報
st.header("4. シーン情報")

# シーン名マスター登録エリア
c1, c2 = st.columns([3, 1])
with c1:
    new_s_name = st.text_input("登録するシーン名を入力")
with c2:
    if st.button("登録") and new_s_name:
        if new_s_name not in st.session_state.scene_master:
            st.session_state.scene_master.append(new_s_name)
            st.rerun()

st.caption(f"登録済みシーン名: {', '.join(st.session_state.scene_master)}")

# シーン情報の編集を監視して自動補完する関数
def on_scene_change():
    state = st.session_state["s_editor_v10"]
    # 既存のデータフレームをコピー
    df = st.session_state.s_df.copy()
    
    # 編集内容を反映 (edited_rows: {行番号: {カラム名: 新しい値}})
    for row_idx, changes in state["edited_rows"].items():
        for col, val in changes.items():
            df.at[row_idx, col] = val
            # グループ名が変更された場合、ゾーン名を自動セット
            if col == "紐づけるグループ名":
                if val in g_to_zone_map:
                    df.at[row_idx, "紐づけるゾーン名"] = g_to_zone_map[val]

    # 追加行の反映
    for row in state["added_rows"]:
        # 初期値セット
        new_row = {"シーン名": "", "紐づけるグループ名": "", "紐づけるゾーン名": "", "調光": 100, "調色": ""}
        new_row.update(row)
        # グループ名があればゾーンを補完
        gn = new_row["紐づけるグループ名"]
        if gn in g_to_zone_map:
            new_row["紐づけるゾーン名"] = g_to_zone_map[gn]
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    # 削除行の反映
    indices_to_drop = state["deleted_rows"]
    df = df.drop(indices_to_drop).reset_index(drop=True)

    st.session_state.s_df = df

# シーン情報テーブル
s_edit = st.data_editor(
    st.session_state.s_df,
    num_rows="dynamic",
    column_config={
        "シーン名": st.column_config.SelectboxColumn("シーン名 (J列)", options=st.session_state.scene_master),
        "紐づけるグループ名": st.column_config.SelectboxColumn("紐づけるグループ名 (P列)", options=v_groups),
        "紐づけるゾーン名": st.column_config.SelectboxColumn("紐づけるゾーン名 (O列)", options=v_zones),
        "調光": st.column_config.NumberColumn("調光 (L列)", min_value=0, max_value=100, format="%d%%")
    },
    use_container_width=True,
    key="s_editor_v10",
    on_change=on_scene_change
)

st.divider()

# --- 5. CSV出力処理 ---
if st.button("プレビューを確認する", type="primary"):
    zf_f = z_edit[z_edit["ゾーン名"].str.strip() != ""].reset_index(drop=True)
    gf_f = g_edit[g_edit["グループ名"].str.strip() != ""].reset_index(drop=True)
    sf_f = st.session_state.s_df[st.session_state.s_df["シーン名"].str.strip() != ""].reset_index(drop=True)
    
    # バリデーション
    errs = []
    for i, r in sf_f.iterrows():
        gn = r["紐づけるグループ名"]
        cv = str(r["調色"]).upper().replace("K", "").strip()
        if gn in g_to_tp_map and cv.isdigit():
            k = int(cv)
            tp = g_to_tp_map[gn]
            if tp == "調光調色" and not (2700 <= k <= 6500):
                errs.append(f"行{i+1}: {gn}(調光調色)は2700-6500Kで入力してください。")
            elif tp in ["Synca", "Synca Bright"] and not (1800 <= k <= 12000):
                errs.append(f"行{i+1}: {gn}({tp})は1800-12000Kで入力してください。")
    
    if errs:
        for e in errs: st.error(e)
    else:
        # ID同期ロジック (K列: 同じシーン名なら同じIDを付与)
        scene_id_db = {}
        current_sid = 8193
        
        max_r = max(len(zf_f), len(gf_f), len(sf_f))
        matrix = pd.DataFrame(index=range(max_r), columns=range(NUM_COLS))
        
        for i, r in zf_f.iterrows():
            matrix.iloc[i, 0], matrix.iloc[i, 1], matrix.iloc[i, 2] = r["ゾーン名"], 4097+i, r["フェード秒"]
        for i, r in gf_f.iterrows():
            matrix.iloc[i, 4], matrix.iloc[i, 5], matrix.iloc[i, 6], matrix.iloc[i, 7] = r["グループ名"], 32769+i, GROUP_TYPE_MAP.get(r["グループタイプ"], ""), r["紐づけるゾーン名"]
        for i, r in sf_f.iterrows():
            sn = r["シーン名"]
            if sn not in scene_id_db:
                scene_id_db[sn] = current_sid
                current_sid += 1
            
            matrix.iloc[i, 9] = sn
            matrix.iloc[i, 10] = scene_id_db[sn] # K列[id] シーン名一致なら同ID
            matrix.iloc[i, 11] = r["調光"]
            matrix.iloc[i, 12] = r["調色"]
            matrix.iloc[i, 14] = r["紐づけるゾーン名"]
            matrix.iloc[i, 15] = r["紐づけるグループ名"]

        st.session_state.final_df_v10 = pd.concat([pd.DataFrame([ROW1, ROW2, ROW3]), matrix], ignore_index=True)
        st.subheader("5. プレビュー確認")
        pdf = st.session_state.final_df_v10.copy()
        pdf.columns = make_unique_cols(ROW3)
        st.dataframe(pdf.iloc[3:], hide_index=True, use_container_width=True)

if 'final_df_v10' in st.session_state:
    b = io.BytesIO()
    st.session_state.final_df_v10.to_csv(b, index=False, header=False, encoding="utf-8-sig")
    st.download_button("📥 CSVダウンロード", b.getvalue(), out_filename, "text/csv")
