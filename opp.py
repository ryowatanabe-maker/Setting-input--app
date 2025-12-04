import streamlit as st
import pandas as pd
import io
import numpy as np

# --- 定数設定 ---

# グループタイプの選択肢とそれに対応するチャンネル数/タイプ
GROUP_TYPES = {
    "調光": "1ch",
    "調光調色": "2ch",
    "Synca": "3ch",
    "Synca Bright": "fresh 3ch"
}

# CSVの全列数 (setting_data (見本).csv から読み取った列数: 74列)
NUM_COLS = 74

# CSVのヘッダー行（3行分）をハードコード (74列を維持)
# ユーザーの要求に従い、添付ファイルの内容に基づき定義
# NoneはCSV出力時に空欄（カンマのみ）として扱われます
ROW1 = ['Zone情報', None, None, None, 'Group情報', None, None, None, None, 'Scene情報', None, None, None, None, None, None, None, 'Timetable情報', None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, 'Timetable-schedule情報', None, None, None, None, None, None, None, None, None, 'Timetable期間/特異日情報', None, None, None, None, None, 'センサーパターン情報', None, None, None, None, 'センサータイムテーブル情報', None, None, 'センサータイムテーブル/スケジュール情報', None, None, None, None, None, None, None, None, None, 'センサータイムテーブル期間/特異日情報', None, None, None, None]
ROW2 = [None] * NUM_COLS
ROW3_BASE = ['[zone]', '[id]', '[fade]', None, '[group]', '[id]', '[type]', '[zone]', None, '[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]', None, '[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', None, '[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]', None, '[zone-period]', '[start]', '[end]', '[timetable]', '[zone]', None, '[pattern]', '[id]', '[type]', '[mode]', None, '[sensor-timetable]', '[id]', None, '[sensor-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]', None, '[sensor-period]', '[start]', '[end]', '[timetable]', '[group]']

# 念のため74列にパディング
ROW1 = ROW1[:NUM_COLS] + [None] * (NUM_COLS - len(ROW1))
ROW3 = ROW3_BASE[:NUM_COLS] + [None] * (NUM_COLS - len(ROW3_BASE))

CSV_HEADER_LIST = [ROW1, ROW2, ROW3]


# --- ヘルパー関数 ---

def create_initial_zone_data():
    """ゾーン情報の初期DataFrameを作成"""
    return pd.DataFrame({
        "ゾーン名": [""],
        "ゾーンID": [4097],
        "フェード秒": [0],
    })

def create_initial_group_data():
    """グループ情報の初期DataFrameを作成"""
    return pd.DataFrame({
        "グループ名": [""],
        "グループID": [32769],
        "グループタイプ": [""],
        "紐づけるゾーン名": [""]
    })

def create_initial_scene_data():
    """シーン情報の初期DataFrameを作成"""
    return pd.DataFrame({
        "シーン名": [""],
        "シーンID": [8193],
        "調光": [100],
        "調色": [""] , # K
        "紐づけるゾーン名": [""],
        "紐づけるグループ名": [""],
    })

def create_csv_output(shop_name, zone_df, group_df, scene_df):
    """
    ユーザー入力とヘッダー情報から最終的なCSVデータを生成します。
    - 条件②: 全てＣＳＶデータの4行目 (インデックス3) から記入されるように対応
    """
    
    # ----------------------------------------------------
    # 1. データのフィルタリングとID/タイプ処理
    # ----------------------------------------------------
    
    # 有効な行のみをフィルタリング (ゾーン名/グループ名/シーン名が空欄でないもの)
    zone_df_processed = zone_df[zone_df['ゾーン名'].astype(str).str.strip() != ''].copy().reset_index(drop=True)
    group_df_processed = group_df[group_df['グループ名'].astype(str).str.strip() != ''].copy().reset_index(drop=True)
    scene_df_processed = scene_df[scene_df['シーン名'].astype(str).str.strip() != ''].copy().reset_index(drop=True)
    
    # IDの自動連番設定
    zone_df_processed["ゾーンID"] = 4097 + zone_df_processed.index
    group_df_processed["グループID"] = 32769 + group_df_processed.index
    scene_df_processed["シーンID"] = 8193 + scene_df_processed.index
    
    # グループタイプからチャンネル情報を取得
    group_df_processed["G_OUTPUT"] = group_df_processed["グループタイプ"].apply(lambda x: GROUP_TYPES.get(x, ""))
    
    # ----------------------------------------------------
    # 2. 74列のデータフレームにマッピング
    # ----------------------------------------------------
    max_len = max(len(zone_df_processed), len(group_df_processed), len(scene_df_processed))
    
    # 入力データ用の空のDataFrameを準備 (4行目以降)
    input_data = pd.DataFrame(np.nan, index=range(max_len), columns=range(NUM_COLS))
    
    if max_len > 0:
        # --- ゾーン情報 (Index 0, 1, 2) ---
        input_data.loc[zone_df_processed.index, 0] = zone_df_processed["ゾーン名"]
        input_data.loc[zone_df_processed.index, 1] = zone_df_processed["ゾーンID"]
        input_data.loc[zone_df_processed.index, 2] = zone_df_processed["フェード秒"]
        # Index 3 (D列) は空欄(NaN/None)のまま
        
        # --- グループ情報 (Index 4, 5, 6, 7) ---
        input_data.loc[group_df_processed.index, 4] = group_df_processed["グループ名"]
        input_data.loc[group_df_processed.index, 5] = group_df_processed["グループID"]
        input_data.loc[group_df_processed.index, 6] = group_df_processed["G_OUTPUT"]
        input_data.loc[group_df_processed.index, 7] = group_df_processed["紐づけるゾーン名"]
        # Index 8 (I列) は空欄(NaN/None)のまま

        # --- シーン情報 (Index 9, 10, 11, 12, 14, 15) ---
        input_data.loc[scene_df_processed.index, 9] = scene_df_processed["シーン名"]         # J列 [scene]
        input_data.loc[scene_df_processed.index, 10] = scene_df_processed["シーンID"]        # K列 [id]
        input_data.loc[scene_df_processed.index, 11] = scene_df_processed["調光"]            # L列 [dimming]
        input_data.loc[scene_df_processed.index, 12] = scene_df_processed["調色"]            # M列 [color]
        # Index 13 (N列 - [perform]) は空欄(NaN/None)のまま
        input_data.loc[scene_df_processed.index, 14] = scene_df_processed["紐づけるゾーン名"] # O列 [zone]
        input_data.loc[scene_df_processed.index, 15] = scene_df_processed["紐づけるグループ名"] # P列 [group]
        
        # 全ての列をオブジェクト型にして、CSV出力時に適切に処理されるようにする
        input_data = input_data.astype(object)

    # ----------------------------------------------------
    # 3. ヘッダーとデータを結合
    # ----------------------------------------------------
    header_df = pd.DataFrame(CSV_HEADER_LIST)
    
    # ヘッダーとデータを結合 (条件②: データは4行目(Index 3)から開始)
    final_df = pd.concat([header_df, input_data], ignore_index=True)
    
    # ファイル名
    file_name = f"{shop_name}_setting_data.csv"
    
    # CSV文字列を生成 (BOM付きUTF-8でExcelでの文字化けを防ぐ)
    csv_buffer = io.StringIO()
    # ヘッダーはすでにDataFrameに含まれているため、header=False
    final_df.to_csv(csv_buffer, index=False, header=False, encoding='utf-8-sig')
    
    # プレビュー用に4行目以降のデータ部分を返す
    return csv_buffer.getvalue(), file_name, final_df.iloc[3:]

# --- Streamlit UI ---

st.set_page_config(layout="wide")
st.title("店舗設定データ作成アプリ ⚙️")

# セッションステートの初期化
if 'zone_data' not in st.session_state:
    st.session_state.zone_data = create_initial_zone_data()
if 'group_data' not in st.session_state:
    st.session_state.group_data = create_initial_group_data()
if 'scene_data' not in st.session_state:
    st.session_state.scene_data = create_initial_scene_data()
if 'confirm_step' not in st.session_state:
    st.session_state.confirm_step = False

## ① 店舗名を入力
st.header("1. 店舗名入力")
shop_name = st.text_input("店舗名を入力してください（必須）", key="shop_name_input")
output_filename = f"{shop_name}_setting_data.csv"

st.subheader("出力ファイル名: **`{}`**".format(output_filename if shop_name else "店舗名_setting_data.csv"))

st.markdown("---")

# データのフィルタリングと選択肢の作成
zone_names_raw = st.session_state.zone_data["ゾーン名"].astype(str).str.strip()
valid_zone_names = zone_names_raw[zone_names_raw != ''].unique().tolist()
zone_options = [""] + valid_zone_names # ゾーン名選択肢

group_names_raw = st.session_state.group_data["グループ名"].astype(str).str.strip()
valid_group_names = group_names_raw[group_names_raw != ''].unique().tolist()
group_options = [""] + valid_group_names # グループ名選択肢


# --- 2. ゾーン情報入力 ---
st.header("2. ゾーン情報入力 (A, B, C列)")
st.caption("🚨 **B列ID**は自動で連番(**4097〜**)になります。**C列フェード秒**は0〜3599秒(59分59秒)で設定してください。")

zone_id_col = st.column_config.NumberColumn("ゾーンID (B列 - [id])", disabled=True, min_value=4097)
fade_col = st.column_config.NumberColumn("フェード秒 (C列 - [fade])", min_value=0, max_value=3599, step=1)

edited_zone_df = st.data_editor(
    st.session_state.zone_data,
    key="zone_editor",
    use_container_width=False,
    num_rows="dynamic", 
    column_config={
        "ゾーン名": st.column_config.TextColumn("ゾーン名 (A列 - [zone])"),
        "ゾーンID": zone_id_col,
        "フェード秒": fade_col
    }
)
st.session_state.zone_data = edited_zone_df.copy()
st.markdown("---")


# --- 3. グループ情報入力 ---
st.header("3. グループ情報入力 (E, F, G, H列)")
st.caption("🚨 **F列ID**は自動で連番(**32769〜**)になります。**G列グループタイプ**は選択肢に応じてチャンネル情報が反映されます。")

group_id_col = st.column_config.NumberColumn("グループID (F列 - [id])", disabled=True, min_value=32769)
group_type_col = st.column_config.SelectboxColumn("グループタイプ (G列 - [type])", options=list(GROUP_TYPES.keys()))
link_zone_col_group = st.column_config.SelectboxColumn("紐づけるゾーン名 (H列 - [zone])", options=zone_options)

edited_group_df = st.data_editor(
    st.session_state.group_data,
    key="group_editor",
    use_container_width=False,
    num_rows="dynamic", 
    column_config={
        "グループ名": st.column_config.TextColumn("グループ名 (E列 - [group])"),
        "グループID": group_id_col,
        "グループタイプ": group_type_col,
        "紐づけるゾーン名": link_zone_col_group
    }
)
st.session_state.group_data = edited_group_df.copy()
st.markdown("---")


# --- 4. シーン情報入力 ---
st.header("4. シーン情報入力 (J, K, L, M, O, P列)")
st.caption("🚨 **K列ID**は自動で連番(**8193〜**)になります。**L列調光**は0〜100%で入力してください。")

scene_id_col = st.column_config.NumberColumn("シーンID (K列 - [id])", disabled=True, min_value=8193)
dimming_col = st.column_config.NumberColumn("調光 (L列 - [dimming], %)", min_value=0, max_value=100, step=1)
color_col = st.column_config.TextColumn("調色 (M列 - [color], K)")
link_zone_col_scene = st.column_config.SelectboxColumn("紐づけるゾーン名 (O列 - [zone])", options=zone_options)
link_group_col_scene = st.column_config.SelectboxColumn("紐づけるグループ名 (P列 - [group])", options=group_options)


edited_scene_df = st.data_editor(
    st.session_state.scene_data,
    key="scene_editor",
    use_container_width=True,
    num_rows="dynamic", 
    column_config={
        "シーン名": st.column_config.TextColumn("シーン名 (J列 - [scene])"),
        "シーンID": scene_id_col,
        "調光": dimming_col,
        "調色": color_col,
        "紐づけるゾーン名": link_zone_col_scene,
        "紐づけるグループ名": link_group_col_scene
    }
)
st.session_state.scene_data = edited_scene_df.copy()

st.markdown("---")

## 最終処理実行ボタン
if st.button("設定データを出力用に準備", type="primary"):
    if not shop_name:
        st.error("🚨 **店舗名**を入力してください。")
    else:
        # 処理を実行
        st.session_state.csv_data, st.session_state.file_name, st.session_state.preview_df = create_csv_output(
            shop_name,
            st.session_state.zone_data,
            st.session_state.group_data,
            st.session_state.scene_data
        )
        st.session_state.confirm_step = True
        st.success("出力データの準備ができました。最終確認に進んでください。")

st.markdown("---")

## 最後にこれで合っているか確認してから出力
if st.session_state.confirm_step:
    st.header("5. 最終確認と出力 (条件③)")
    
    st.subheader(f"✅ 出力ファイル名: **`{st.session_state.file_name}`**")

    st.warning("⚠️ **4行目以降**のデータ（実際に記入される部分）を最終確認してください。")
    
    # 4行目以降のデータ部分を表示
    header_row_3 = [str(x) if x is not None and str(x) != 'nan' else '' for x in CSV_HEADER_LIST[2]]
    
    preview_df_display = st.session_state.preview_df.copy()
    
    # プレビューの列数がヘッダー行3の列数より少ない場合にエラーを避けるための処理
    if len(preview_df_display.columns) <= len(header_row_3):
        preview_df_display.columns = header_row_3[:len(preview_df_display.columns)]
    
    st.dataframe(
        preview_df_display, 
        use_container_width=True, 
        hide_index=True
    )

    st.download_button(
        label="📥 確認OK！ CSVファイルをダウンロード",
        data=st.session_state.csv_data,
        file_name=st.session_state.file_name,
        mime='text/csv'
    )
