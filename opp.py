import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime, timedelta

# --- 1. 定数とヘッダー定義 ---
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "3ch"}
NUM_COLS = 236 

ROW1 = [None] * NUM_COLS
ROW1[0], ROW1[4], ROW1[9], ROW1[17], ROW1[197], ROW1[207] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報', 'Timetable-schedule情報', 'Timetable期間/特異日情報'
ROW3 = [None] * NUM_COLS
ROW3[0:3], ROW3[4:8] = ['[zone]', '[id]', '[fade]'], ['[group]', '[id]', '[type]', '[zone]']
ROW3[9:16] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]']
ROW3[17:22] = ['[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]']
for i in range(22, 196, 2): ROW3[i], ROW3[i+1] = '[time]', '[scene]'
ROW3[197:206] = ['[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]']
ROW3[207:212] = ['[zone-period]', '[start]', '[end]', '[timetable]', '[zone]']

CSV_HEADER = [ROW1, [None] * NUM_COLS, ROW3]

# --- 2. アプリ設定とデータ初期化 ---
st.set_page_config(page_title="設定データ作成アプリ", layout="wide")
st.title("設定データ作成アプリ ⚙️")

for key in ['z_list', 'g_list', 's_list', 'tt_list', 'ts_list', 'period_list']:
    if key not in st.session_state: st.session_state[key] = []
if 'tt_slots_count' not in st.session_state: st.session_state.tt_slots_count = 1
if 'auto_scene_count' not in st.session_state: st.session_state.auto_scene_count = 2
if 'scene_edit_buf' not in st.session_state: st.session_state.scene_edit_buf = {}

# --- 3. UIセクション ---
st.header("1. 店舗名入力 🏢")
shop_name = st.text_input("店舗名", value="")
st.divider()

# 2. ゾーン登録
st.header("2. ゾーン登録 🌐")
with st.form("z_form_v53", clear_on_submit=True):
    col_z1, col_z2 = st.columns(2)
    z_name = col_z1.text_input("ゾーン名")
    z_fade = col_z2.number_input("フェード秒", 0, 60, 0)
    if st.form_submit_button("ゾーンを追加 ➕"):
        if z_name:
            st.session_state.z_list.append({"ゾーン名": z_name, "フェード秒": z_fade})
            st.rerun()

# 3. グループ登録
st.header("3. グループ登録 💡")
v_zones = [""] + [z["ゾーン名"] for z in st.session_state.z_list]
with st.form("g_form_v53", clear_on_submit=True):
    col_g1, col_g2, col_g3 = st.columns(3)
    g_n, g_t, g_z = col_g1.text_input("グループ名"), col_g2.selectbox("タイプ", list(GROUP_TYPE_MAP.keys())), col_g3.selectbox("紐づけるゾーン", options=v_zones)
    if st.form_submit_button("グループを追加 ➕"):
        if g_n and g_z:
            st.session_state.g_list.append({"グループ名": g_n, "グループタイプ": g_t, "紐づけるゾーン名": g_z})
            st.rerun()

st.divider()

# 4. シーン登録（整合性エラー対策版）
st.header("4. シーン登録・編集 🎬")
if st.session_state.s_list:
    s_df_hist = pd.DataFrame(st.session_state.s_list)
    disp_df = s_df_hist.groupby(["シーン名", "紐づけるゾーン名"]).size().reset_index().rename(columns={0:"グループ数"})
    disp_df.index += 1
    st.subheader("現在のシーン登録状況")
    ev_s = st.dataframe(disp_df, use_container_width=True, on_select="rerun", selection_mode="single-row", key="s_v53")
    if len(ev_s.selection.rows) > 0:
        row = disp_df.iloc[ev_s.selection.rows[0]]
        st.session_state.scene_edit_buf = {"name": row["シーン名"], "zone": row["紐づけるゾーン名"]}
        if st.button("選択したシーンを削除 🗑️"):
            st.session_state.s_list = [s for s in st.session_state.s_list if not (s["シーン名"] == row["シーン名"] and s["紐づけるゾーン名"] == row["紐づけるゾーン名"])]
            st.session_state.scene_edit_buf = {}
            st.rerun()

st.subheader("シーン設定フォーム")
with st.container(border=True):
    col_sn1, col_sn2 = st.columns(2)
    def_s_name = st.session_state.scene_edit_buf.get("name", "")
    def_s_zone = st.session_state.scene_edit_buf.get("zone", "")
    new_scene_name = col_sn1.text_input("シーン名", value=def_s_name)
    sel_zone_for_scene = col_sn2.selectbox("対象ゾーン", options=v_zones, index=v_zones.index(def_s_zone) if def_s_zone in v_zones else 0)

    if sel_zone_for_scene:
        # このゾーンに属するグループだけを抽出（ここが整合性のキモ）
        target_groups = [g for g in st.session_state.g_list if g["紐づけるゾーン名"] == sel_zone_for_scene]
        scene_results = []
        for g in target_groups:
            gn, gt, gz = g["グループ名"], g["グループタイプ"], g["紐づけるゾーン名"]
            st.write(f"**{gn}** ({gt})")
            existing_s = next((s for s in st.session_state.s_list if s["シーン名"] == def_s_name and s["紐づけるグループ名"] == gn), None)
            
            c_dim, c_color, c_synca = st.columns([1, 2, 3])
            dim_num = c_dim.number_input(f"調光 (%)", 0, 100, int(existing_s["調光"]) if existing_s else 100, key=f"n_dim_{gn}")
            k_val = c_color.text_input("ケルビン", value=existing_s["ケルビン"] if existing_s else "3500", key=f"k_{gn}") if gt != "調光" else ""
            
            synca_val = ""
            if "Synca" in gt:
                with c_synca:
                    with st.expander("🎨 パレット表示"):
                        if os.path.exists("synca_palette.png"): st.image("synca_palette.png")
                    c_s1, c_s2 = st.columns(2)
                    rv = c_s1.selectbox("行", ["-"] + list(range(1, 12)), key=f"sr_{gn}")
                    cv = c_s2.selectbox("列", ["-"] + list(range(1, 12)), key=f"sc_{gn}")
                    if rv != "-" and cv != "-": synca_val = f"'{rv}-{cv}"

            scene_results.append({
                "シーン名": new_scene_name,
                "紐づけるグループ名": gn,
                "紐づけるゾーン名": gz, # 常にグループの親ゾーンをセット
                "調光": dim_num,
                "ケルビン": k_val,
                "Syncaカラー": synca_val
            })

        if st.button("履歴に登録・上書き保存 ✅", use_container_width=True):
            if new_scene_name:
                # 既存の同一(シーン名+ゾーン名)の組み合わせを削除してから追加
                st.session_state.s_list = [s for s in st.session_state.s_list if not (s["シーン名"] == new_scene_name and s["紐づけるゾーン名"] == sel_zone_for_scene)]
                st.session_state.s_list.extend(scene_results)
                st.session_state.scene_edit_buf = {}
                st.rerun()

st.divider()

# --- 5. タイムテーブル・6. 適用 ---
# (前回の安定版ロジックを継承)
# ... (略) ...

# --- 7. 出力 (整合性エラー完全対策版) ---
if st.button("CSV作成・ダウンロード 💾", type="primary"):
    zf = pd.DataFrame(st.session_state.z_list)
    gf = pd.DataFrame(st.session_state.g_list)
    sf = pd.DataFrame(st.session_state.s_list)
    ttf, tsf, pf = st.session_state.tt_list, st.session_state.ts_list, st.session_state.period_list

    mat = pd.DataFrame(index=range(max(len(zf), len(gf), len(sf), 100)), columns=range(NUM_COLS))
    
    for i, r in zf.iterrows(): mat.iloc[i, 0:3] = [r["ゾーン名"], 4097+i, r["フェード秒"]]
    for i, r in gf.iterrows(): mat.iloc[i, 4:8] = [r["グループ名"], 32770+i, GROUP_TYPE_MAP.get(r["グループタイプ"], "1ch"), r["紐づけるゾーン名"]]
    
    s_db, s_cnt = {}, 8193
    for i, r in sf.iterrows():
        # キーにゾーン名を含めてIDを分ける
        key = (r["シーン名"], r["紐づけるゾーン名"])
        if key not in s_db:
            s_db[key] = s_cnt
            s_cnt += 1
        
        # 整合性のための固定順: [名前, ID, 調光, 色, Synca, ゾーン名, グループ名]
        # ※赤池店データに基づき、14列目(index13)にSynca/Perform, 15列目(index14)にゾーン名、16列目(index15)にグループ名を配置
        synca = str(r["Syncaカラー"]).replace("'", "") if r["Syncaカラー"] else ""
        mat.iloc[i, 9:16] = [r["シーン名"], s_db[key], r["調光"], r["ケルビン"], synca, r["紐づけるゾーン名"], r["紐づけるグループ名"]]

    for i, tt in enumerate(ttf):
        mat.iloc[i, 17:22] = [tt["tt_name"], 12289+i, tt["zone"], tt["sun_start"], tt["sun_end"]]
        c_idx = 22
        for slot in tt["slots"]:
            if c_idx < 196: mat.iloc[i, c_idx], mat.iloc[i, c_idx+1] = slot["time"], slot["scene"]; c_idx += 2
    
    for i, ts in enumerate(tsf):
        c = ts["config"]
        mat.iloc[i, 197:206] = [ts["zone"], c["daily"], c["mon"], c["tue"], c["wed"], c["thu"], c["fri"], c["sat"], c["sun"]]

    for i, p in enumerate(pf):
        sd = p["start"].replace("/", "月") + "日" if "/" in p["start"] else p["start"]
        ed = p["end"].replace("/", "月") + "日" if "/" in p["end"] else p["end"]
        mat.iloc[i, 207:212] = [p["name"], sd, ed, p["tt"], p["zone"]]

    mat = mat.dropna(how='all')
    buf = io.BytesIO()
    final_output = pd.concat([pd.DataFrame(CSV_HEADER), mat], ignore_index=True)
    final_output.to_csv(buf, index=False, header=False, encoding="utf-8-sig", lineterminator='\r\n')
    st.download_button("最終修正版(v53)をダウンロード 📥", buf.getvalue(), f"{shop_name}_final.csv", "text/csv")
