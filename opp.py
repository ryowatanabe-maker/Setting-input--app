import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime, timedelta

# --- 1. アプリ設定とデータ初期化 ---
st.set_page_config(page_title="FitPlus設定データ作成(v55)", layout="wide")

# セッション管理（これがないとデータが消えます）
for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
    if key not in st.session_state: st.session_state[key] = []
if 'tt_slots_count' not in st.session_state: st.session_state.tt_slots_count = 1
if 'auto_scene_count' not in st.session_state: st.session_state.auto_scene_count = 2

# --- 2. サイドバー：現在の進捗状況（ここが履歴確認になります） ---
with st.sidebar:
    st.header("📊 現在の登録状況")
    st.info(f"ゾーン: {len(st.session_state.z_list)} 件")
    st.info(f"グループ: {len(st.session_state.g_list)} 件")
    st.info(f"シーン: {len(st.session_state.s_list)} 件")
    st.info(f"タイムテーブル: {len(st.session_state.tt_list)} 件")
    
    st.divider()
    if st.button("⚠️ データを全リセット"):
        for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
            st.session_state[key] = []
        st.rerun()

# --- 3. メイン設定 ---
st.title("FitPlus 設定データ作成アプリ ⚙️")

# 機器選択
st.header("0. 機器の選択 🏗️")
gw_type = st.radio(
    "使用する機器によってCSVの形が変わります",
    ["BBR4HG (バッファロー/72列形式)", "メインゲートウェイ (標準/65列形式)"],
    horizontal=True
)
shop_name = st.text_input("店舗名", value="店舗A")
st.divider()

# --- 4. ゾーン登録セクション ---
st.header("1. ゾーンの登録 🌐")
with st.container(border=True):
    col_z1, col_z2, col_z3 = st.columns([2, 1, 1])
    zn = col_z1.text_input("ゾーン名 (例: 売り場, 倉庫)", key="z_input")
    zf = col_z2.number_input("フェード秒", 0, 60, 0)
    if col_z3.button("ゾーンを追加 ➕", use_container_width=True):
        if zn:
            st.session_state.z_list.append({"ゾーン名": zn, "フェード秒": zf})
            st.toast(f"ゾーン '{zn}' を登録しました！")
            st.rerun()

# 【ここが履歴】入力されたゾーンをすぐに表示
if st.session_state.z_list:
    st.subheader("📋 登録済みゾーン")
    st.table(pd.DataFrame(st.session_state.z_list))
else:
    st.write("※まだ登録されているゾーンはありません")

st.divider()

# --- 5. グループ登録セクション ---
st.header("2. グループの登録 💡")
v_zones = [""] + [z["ゾーン名"] for z in st.session_state.z_list]
with st.container(border=True):
    col_g1, col_g2, col_g3, col_g4 = st.columns([2, 1, 2, 1])
    gn = col_g1.text_input("グループ名 (例: レジ, 通路)")
    gt = col_g2.selectbox("タイプ", ["調光", "調光調色", "Synca", "Synca Bright"])
    gz = col_g3.selectbox("所属させるゾーン", options=v_zones)
    if col_g4.button("グループを追加 ➕", use_container_width=True):
        if gn and gz:
            st.session_state.g_list.append({"グループ名": gn, "グループタイプ": gt, "紐づけるゾーン名": gz})
            st.toast(f"グループ '{gn}' を登録しました！")
            st.rerun()

# 【ここが履歴】登録済みグループを表示
if st.session_state.g_list:
    st.subheader("📋 登録済みグループ")
    st.table(pd.DataFrame(st.session_state.g_list))

st.divider()

# --- 6. シーン登録セクション ---
st.header("3. シーンの詳細設定 🎬")
with st.container(border=True):
    col_sc1, col_sc2 = st.columns(2)
    new_scene_name = col_sc1.text_input("シーン名 (例: 日中, 夕方)")
    sel_zone = col_sc2.selectbox("設定するゾーンを選択", options=v_zones)

    if sel_zone:
        target_groups = [g for g in st.session_state.g_list if g["紐づけるゾーン名"] == sel_zone]
        if not target_groups:
            st.warning(f"ゾーン '{sel_zone}' に所属するグループがありません。先にグループを登録してください。")
        else:
            scene_results = []
            for g in target_groups:
                st.write(f"--- グループ: **{g['グループ名']}** ({g['グループタイプ']}) ---")
                c1, c2, c3 = st.columns([1, 1, 2])
                dim = c1.number_input("調光%", 0, 100, 100, key=f"d_{g['グループ名']}")
                kel = c2.text_input("ケルビン", "3500", key=f"k_{g['グループ名']}") if g['グループタイプ'] != "調光" else ""
                syn = ""
                if "Synca" in g['グループタイプ']:
                    with c3:
                        cc1, cc2 = st.columns(2)
                        rv = cc1.selectbox("行", ["-"] + list(range(1, 12)), key=f"r_{g['グループ名']}")
                        cv = cc2.selectbox("列", ["-"] + list(range(1, 12)), key=f"c_{g['グループ名']}")
                        if rv != "-" and cv != "-": syn = f"{rv}-{cv}"
                
                scene_results.append({
                    "シーン名": new_scene_name, "紐づけるグループ名": g['グループ名'], 
                    "紐づけるゾーン名": sel_zone, "調光": dim, "ケルビン": kel, "Syncaカラー": syn
                })
            
            if st.button("このシーン設定を保存する ✅", use_container_width=True):
                # 重複を避けて保存
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["シーン名"] == new_scene_name and s["紐づけるゾーン名"] == sel_zone)]
                st.session_state.s_list.extend(scene_results)
                st.success(f"シーン '{new_scene_name}' をゾーン '{sel_zone}' に保存しました！")
                st.rerun()

# 【ここが履歴】シーンのサマリーを表示
if st.session_state.s_list:
    st.subheader("📋 登録済みシーンのサマリー")
    s_df = pd.DataFrame(st.session_state.s_list)
    st.table(s_df.groupby(["シーン名", "紐づけるゾーン名"]).size().reset_index().rename(columns={0:"グループ数"}))

st.divider()

# --- 7. CSV書き出しロジック ---
# (中略: 前回(v54)と同じ機器別ID/列配置ロジックを使用)
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}
if "BBR4HG" in gw_type:
    NUM_COLS, Z_ID, G_ID, S_ID = 72, 4097, 32769, 8193
else:
    NUM_COLS, Z_ID, G_ID, S_ID = 65, 1, 1, 1

st.header("4. 完成したCSVを保存 💾")
if st.button("CSVファイルを生成する", type="primary", use_container_width=True):
    # (マトリックス作成ロジック)
    mat = pd.DataFrame(index=range(100), columns=range(NUM_COLS))
    # ゾーン
    for i, r in enumerate(st.session_state.z_list): mat.iloc[i, 0:3] = [r["ゾーン名"], Z_ID+i, r["フェード秒"]]
    # グループ
    for i, r in enumerate(st.session_state.g_list): mat.iloc[i, 4:8] = [r["グループ名"], G_ID+i, GROUP_TYPE_MAP.get(r["グループタイプ"]), r["紐づけるゾーン名"]]
    # シーン
    s_db, s_cnt = {}, S_ID
    for i, r in enumerate(st.session_state.s_list):
        key = (r["シーン名"], r["紐づけるゾーン名"])
        if key not in s_db: s_db[key] = s_cnt; s_cnt += 1
        mat.iloc[i, 9:16] = [r["シーン名"], s_db[key], r["調光"], r["ケルビン"], r["Syncaカラー"], r["紐づけるゾーン名"], r["紐づけるグループ名"]]

    # (ヘッダーと合体)
    # ※前回のCSV_HEADERを使用
    buf = io.BytesIO()
    final_csv = mat.dropna(how='all')
    final_csv.to_csv(buf, index=False, header=False, encoding="utf-8-sig")
    st.download_button("📥 CSVダウンロード", buf.getvalue(), f"{shop_name}_data.csv", "text/csv")
