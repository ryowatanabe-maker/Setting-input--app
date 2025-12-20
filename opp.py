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

# 元のCSVのヘッダー構造を正確に定義
ROW1 = ['Zone情報', None, None, None, 'Group情報', None, None, None, None, 'Scene情報', None, None, None, None, None, None, None, 'Timetable情報', None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, 'Timetable-schedule情報', None, None, None, None, None, None, None, None, None, 'Timetable期間/特異日情報', None, None, None, None, None, 'センサーパターン情報', None, None, None, None, 'センサータイムテーブル情報', None, None, 'センサータイムテーブル/スケジュール情報', None, None, None, None, None, None, None, None, None, 'センサータイムテーブル期間/特異日情報', None, None, None, None]
ROW2 = [None] * NUM_COLS
ROW3 = ['[zone]', '[id]', '[fade]', None, '[group]', '[id]', '[type]', '[zone]', None, '[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]', None, '[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', '[time]', '[scene]', None, '[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]', None, '[zone-period]', '[start]', '[end]', '[timetable]', '[zone]', None, '[pattern]', '[id]', '[type]', '[mode]', None, '[sensor-timetable]', '[id]', None, '[sensor-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]', None, '[sensor-period]', '[start]', '[end]', '[timetable]', '[group]']

ROW1 = (ROW1 + [None] * NUM_COLS)[:NUM_COLS]
ROW3 = (ROW3 + [None] * NUM_COLS)[:NUM_COLS]
CSV_HEADER = [ROW1, ROW2, ROW3]

def make_unique_cols(header_row):
    """表示エラー回避のため列名をユニーク化"""
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

# --- アプリ設定 ---
st.set_page_config(page_title="設定データ作成アプリ", layout="wide")
st.title("店舗設定データ作成アプリ ⚙️")

# セッションステートの初期化
if 'zone_df' not in st.session_state:
    st.session_state.zone_df = pd.DataFrame([{"ゾーン名": "", "フェード秒": 0}])
if 'group_df' not in st.session_state:
    st.session_state.group_df = pd.DataFrame([{"グループ名": "", "グループタイプ": "調光", "紐づけるゾーン名": ""}])
if 'scene_df' not in st.session_state:
    st.session_state.scene_df = pd.DataFrame([{"シーン名": "", "紐づけるゾーン名": "", "紐づけるグループ名": "", "調光": 100, "調色": ""}])

# ① 店舗名入力
st.header("① 店舗
