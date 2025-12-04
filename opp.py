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

def create_csv_output(shop_name, zone_df, group_df):
    """
    ユーザー入力とヘッダー情報から最終的なCSVデータを生成します。
    - 条件②: 全てＣＳＶデータの4行目 (インデックス3) から記入されるように対応
    """
    
    # ----------------------------------------------------
    # 1. ゾーンIDとグループID、グループタイプを処理
    # ----------------------------------------------------
    # 入力データからゾーン名またはグループ名が空欄の行を除外
    zone_df_processed = zone_df[zone_df['ゾーン名'].astype(str).str.strip() != ''].copy().reset_index(drop=True)
    group_df_processed = group_df[group_df['グループ名'].astype(str).str.strip() != ''].copy().reset_index(drop=True)
    
    # IDの自動連番設定
    zone_df_processed["ゾーンID"] = 4097 + zone_df_processed.index
    group_df_processed["グループID"] = 32769 + group_df_processed.index
    
    # グループタイプからチャンネル情報を取得
    group_df_processed["G_OUTPUT"] = group_df_processed["グループタイプ"].apply(lambda x: GROUP_TYPES.get(x, ""))
    
    # ----------------------------------------------------
    # 2. 74列のデータフレームにマッピング
    # ----------------------------------------------------
    max_len = max(len(zone_df_processed), len(group_df_processed))
    
    # 入力データ用のDataFrameを準備 (4行目以降)
    input_data = pd.DataFrame(np.nan, index=range(max_len), columns=range(NUM_COLS))
    
    if max_len > 0:
        # ゾーン情報をマッピング (A, B, C列 -> Index 0, 1, 2)
        # ゾーン名 (A列: Index 0)
        input_data.loc[zone_df_processed.index, 0] = zone_df_processed["ゾーン名"]
        # ゾーンID (B列: Index 1)
        input_data.loc[zone_df_processed.index, 1] = zone_df_processed["ゾーンID"]
        # フェード秒 (C列: Index 2)
        input_data.loc[zone_df_processed.index, 2] = zone_df_processed["フェード秒"]
        
        # D列 (Index 3) は空欄(NaN/None)のまま
        
        # グループ情報をマッピング (E, F, G, H列 -> Index 4, 5, 6, 7)
        # グループ名 (E列: Index 4)
        input_data.loc[group_df_processed.index, 4] = group_df_processed["グループ名"]
        # グループID (F列: Index 5)
        input_data.loc[group_df_processed.index, 5] = group_df_processed["グループID"]
        # グループタイプ (G列: Index 6) - チャンネル情報
        input_data.loc[group_df_processed.index, 6] = group_df_processed["G_OUTPUT"]
        # 紐づけるゾーン名 (H列: Index 7)
        input_data.loc[group_df_processed.index, 7] = group_df_processed["紐づけるゾーン名"]
        
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
# エラーの原因となった変数名の修正: 'confirm' -> 'confirm_step'
if 'confirm_step' not in st.session_state:
    st.session_state.confirm_step = False

## ① 店舗名を入力
st.header("1. 店舗名入力")
shop_name = st.text_input("店舗名を入力してください（必須）", key="shop_name_input")
output_filename = f"{shop_name}_setting_data.csv"

st.subheader("出力ファイル名: **`{}`**".format(output_filename if shop_name else "店舗名_setting_data.csv"))

st.markdown("---")

## ② ゾーン情報を入力
st.header("2. ゾーン情報入力 (A, B, C列)")
st.caption("🚨 **B列ID**は自動で連番(4097〜)になります。**C列フェード秒**は0〜3599秒(59分59秒)で設定してください。")

# ゾーンIDの列設定 (表示専用/編集不可)
zone_id_col = st.column_config.NumberColumn(
    "ゾーンID (B列 - [id])",
    help="自動で4097から連番になります。",
    disabled=True,
    min_value=4097
)

# フェード秒の列設定 (0〜3599秒の範囲で制限)
fade_col = st.column_config.NumberColumn(
    "フェード秒 (C列 - [fade])",
    help="0秒〜59分59秒 (3599秒) の間で設定可能です。",
    min_value=0,
    max_value=3599,
    step=1
)

# st.data_editorでインタラクティブな表を作成 (条件①: +ボタンで行を追加できるように)
edited_zone_df = st.data_editor(
    st.session_state.zone_data,
    key="zone_editor",
    use_container_width=False,
    num_rows="dynamic", # 条件①: +ボタンで行を追加できるように
    column_config={
        "ゾーン名": st.column_config.TextColumn("ゾーン名 (A列 - [zone])"),
        "ゾーンID": zone_id_col,
        "フェード秒": fade_col
    }
)

# セッションステートを更新
st.session_state.zone_data = edited_zone_df.copy()

st.markdown("---")

## ③ グループ情報を入力
st.header("3. グループ情報入力 (E, F, G, H列)")
st.caption("🚨 **F列ID**は自動で連番(32769〜)になります。**G列グループタイプ**は選択肢に応じてチャンネル情報が反映されます。")

# ゾーン名の選択肢リストを作成
# ゾーン名が入力されている行のみを抽出し、一意なリストを作成
# NaNや空文字列も考慮してフィルタリング
zone_names_raw = st.session_state.zone_data["ゾーン名"].astype(str).str.strip()
zone_names_input = zone_names_raw[zone_names_raw != ''].unique().tolist()
zone_names = [""] + zone_names_input # 未記入も可とするため、空欄を先頭に追加

# グループIDの列設定 (表示専用/編集不可)
group_id_col = st.column_config.NumberColumn(
    "グループID (F列 - [id])",
    help="自動で32769から連番になります。",
    disabled=True,
    min_value=32769
)

# グループタイプの列設定 (プルダウンで4つから選ぶ)
group_type_col = st.column_config.SelectboxColumn(
    "グループタイプ (G列 - [type])",
    help="選択肢に応じてチャンネル情報(1ch, 2ch, 3ch, fresh 3ch)が反映されます。",
    options=list(GROUP_TYPES.keys())
)

# 紐づけるゾーン名の列設定 (プルダウンでゾーン名を選択)
link_zone_col = st.column_config.SelectboxColumn(
    "紐づけるゾーン名 (H列 - [zone])",
    help="2.で入力したゾーン名から選択します。（未記入可）",
    options=zone_names
)
