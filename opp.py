import streamlit as st
import pandas as pd
import io
import json

# --- 0. 互換性維持用の関数 ---
def safe_rerun():
    try:
        st.rerun()
    except:
        st.experimental_rerun()

# --- 1. 定数定義 (大利根店・自己圧縮成功ファイルに完全準拠) ---
NUM_COLS = 72
Z_ID, G_ID, S_ID, T_ID = 4097, 32769, 8193, 12289
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}

st.set_page_config(page_title="FitPlus 設定作成 v61-Fix", layout="wide")
st.title("FitPlus 設定データ作成 (v61ベース・BBR4HG対応) ⚙️")

# セッション状態の初期化
for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
    if key not in st.session_state:
        st.session_state[key] = []

# --- 2. 登録セクション ---

# ゾーン登録
st.header("1. ゾーン登録")
with st.container(border=True):
    cz1, cz2, cz3 = st.columns([2, 1, 1])
    z_n = cz1.text_input("ゾーン名 (例: 店内)", key="z_name_in")
    z_f = cz2.number_input("フェード秒", 0, 60, 0, key="z_fade_in")
    if cz3.button("ゾーンを追加 ➕", use_container_width=True, key="add_z"):
        if z_n:
            st.session_state.z_list.append({"名": z_n, "秒": z_f})
            safe_rerun()

if st.session_state.z_list:
    for i, z in enumerate(st.session_state.z_list):
        cl, cr = st.columns([5, 1])
        cl.write(f"📍 {z['名']} (ID: {Z_ID + i})")
        if cr.button("削除", key=f"dz_{i}"):
            st.session_state.z_list.pop(i)
            safe_rerun()

# グループ登録
st.header("2. グループ登録")
v_zones = [""] + [z["名"] for z in st.session_state.z_list]
with st.container(border=True):
    cg1, cg2, cg3, cg4 = st.columns([2, 1, 2, 1])
    gn = cg1.text_input("グループ名", key="g_name_in")
    gt = cg2.selectbox("タイプ", list(GROUP_TYPE_MAP.keys()), key="g_type_in")
    gz = cg3.selectbox("所属ゾーン", options=v_zones, key="g_zone_in")
    if cg4.button("グループ追加 ➕", use_container_width=True, key="add_g"):
        if gn and gz:
            st.session_state.g_list.append({"名": gn, "型": gt, "ゾ": gz})
            safe_rerun()

if st.session_state.g_list:
    for i, g in enumerate(st.session_state.g_list):
        cl,
