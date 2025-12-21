import streamlit as st
import pandas as pd
import io

# --- 1. 定数とヘッダー定義 ---
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
NUM_COLS = 236 

ROW1 = [None] * NUM_COLS
ROW1[0], ROW1[4], ROW1[9], ROW1[17], ROW1[197], ROW1[207] = 'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報', 'Timetable-schedule情報', 'Timetable期間/特異日情報'
ROW3 = [None] * NUM_COLS
ROW3[0:3], ROW3[4:8] = ['[zone]', '[id]', '[fade]'], ['[group]', '[id]', '[type]', '[zone]']
ROW3[9:17] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[fresh-key]', '[zone]', '[group]']
ROW3[17:22] = ['[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]']
for i in range(22, 196, 2): ROW3[i], ROW3[i+1] = '[time]', '[scene]'
CSV_HEADER = [ROW1, [None] * NUM_COLS, ROW3]

# --- 2. アプリ設定とデータ初期化 ---
st.set_page_config(page_title="設定データ作成アプリ", layout="wide")
st.title("設定データ作成アプリ ⚙️")

# セッション管理
for key in ['z_list', 'g_list', 's_list', 'tt_list']:
    if key not in st.session_state or not isinstance(st.session_state[key], list):
        st.session_state[key] = []

# --- 3. UIセクション ---

st.header("1. 店舗名入力")
shop_name = st.text_input("店舗名", value="店舗A")

st.divider()

# 2. ゾーン情報
st.header("2. ゾーン登録")
with st.form("z_form", clear_on_submit=True):
    col_z1, col_z2 = st.columns(2)
    z_name = col_z1.text_input("ゾーン名")
    z_fade = col_z2.number_input("フェード秒", 0, 60, 0)
    if st.form_submit_button("ゾーンを追加"):
        if z_name:
            st.session_state.z_list.append({"ゾーン名": z_name, "フェード秒": z_fade})
            st.rerun()

if st.session_state.z_list:
    z_disp = pd.DataFrame(st.session_state.z_list)
    z_disp.index += 1
    st.table(z_disp)
    del_z = st.number_input("削除するゾーンの番号", 1, len(st.session_state.z_list), step=1, key="del_z")
    if st.button("指定したゾーンを削除"):
        st.session_state.z_list.pop(del_z - 1)
        st.rerun()

# 3. グループ情報
st.header("3. グループ登録")
v_zones = [""] + [z["ゾーン名"] for z in st.session_state.z_list]
with st.form("g_form", clear_on_submit=True):
    col_g1, col_g2, col_g3 = st.columns(3)
    g_name = col_g1.text_input("グループ名")
    g_type = col_g2.selectbox("タイプ", list(GROUP_TYPE_MAP.keys()))
    g_zone = col_g3.selectbox("紐づけるゾーン", options=v_zones)
    if st.form_submit_button("グループを追加"):
        if g_name and g_zone:
            st.session_state.g_list.append({"グループ名": g_name, "グループタイプ": g_type, "紐づけるゾーン名": g_zone})
            st.rerun()

if st.session_state.g_list:
    g_disp = pd.DataFrame(st.session_state.g_list)
    g_disp.index += 1
    st.table(g_disp)
    del_g = st.number_input("削除するグループの番号", 1, len(st.session_state.g_list), step=1, key="del_g")
    if st.button("指定したグループを削除"):
        st.session_state.g_list.pop(del_g - 1)
        st.rerun()

st.divider()

# 4. シーン情報
st.header("4. シーン登録")
v_groups = [""] + [g["グループ名"] for g in st.session_state.g_list]
g_dict = {g["グループ名"]: g for g in st.session_state.g_list}

with st.form("s_form", clear_on_submit=False):
    c1, c2, c3 = st.columns([2, 2, 1])
    s_name = c1.text_input("シーン名")
    target_g = c2.selectbox("対象グループ", options=v_groups)
    dim = c3.number_input("調光(%)", 0, 100, 100)
    
    st.write("**調色設定** (Synca以外でカラーを選んだ場合は無視されます)")
    cc1, cc2, cc3 = st.columns([2, 1, 1])
    k_val = cc1.text_input("ケルビン (調光調色・Synca用)")
    row_val = cc2.selectbox("Synca 行(1-11)", ["-"] + list(range(1, 12)))
    col_val = cc3.selectbox("Synca 列(1-11)", ["-"] + list(range(1, 12)))

    if st.form_submit_button("シーンにグループを追加"):
        if s_name and target_g:
            g_info = g_dict[target_g]
            synca_code = f"{row_val}-{col_val}" if str(row_val) != "-" and str(col_val) != "-" else ""
            
            # --- 警告チェック ---
            if synca_code and g_info["グループタイプ"] not in ["Synca", "Synca Bright"]:
                st.error(f"警告：【{target_g}】は「{g_info['グループタイプ']}」のため、Syncaカラー(11-1等)は設定できません。ケルビンのみ入力してください。")
            else:
                st.session_state.s_list.append({
                    "シーン名": s_name, 
                    "紐づけるグループ名": target_g, 
                    "紐づけるゾーン名": g_info["紐づけるゾーン名"], 
                    "調光": dim, 
                    "ケルビン": k_val if not synca_code else "", 
                    "Syncaカラー": synca_code
                })
                st.success(f"追加: {s_name}")
        else:
            st.warning("名前とグループは必須です")

if st.session_state.s_list:
    s_disp = pd.DataFrame(st.session_state.s_list)
    s_disp.index += 1
    st.table(s_disp)
    del_s = st.number_input("削除するシーン行の番号", 1, len(st.session_state.s_list), step=1, key="del_s")
    if st.button("指定したシーン行を削除"):
        st.session_state.s_list.pop(del_s - 1)
        st.rerun()

st.divider()

# 5. タイムテーブル情報
st.header("5. タイムテーブル登録")
v_scenes = [""] + sorted(list(set([s["シーン名"] for s in st.session_state.s_list])))
with st.expander("タイムテーブル作成フォーム"):
    with st.form("tt_form"):
        ct1, ct2 = st.columns(2)
        tt_name = ct1.text_input("タイムテーブル名")
        tt_zone = ct2.selectbox("対象ゾーン", options=v_zones)
        slots = []
        rows = [st.columns(4) for _ in range(3)] 
        for i in range(12):
            with rows[i // 4][i % 4]:
                t = st.text_input(f"時間 {i+1}", key=f"t_{i}")
                s = st.selectbox(f"シーン {i+1}", options=v_scenes, key=f"s_{i}")
                if t and s: slots.append({"time": t, "scene": s})
        if st.form_submit_button("タイムテーブルを追加"):
            if tt_name and tt_zone and slots:
                st.session_state.tt_list.append({"tt_name": tt_name, "zone": tt_zone, "slots": slots})
                st.rerun()

if st.session_state.tt_list:
    tt_disp = pd.DataFrame([{"番号": i+1, "名": tt["tt_name"], "ゾーン": tt["zone"]} for i, tt in enumerate(st.session_state.tt_list)])
    st.table(tt_disp)
    del_tt = st.number_input("削除するタイムテーブルの番号", 1, len(st.session_state.tt_list), step=1, key="del_tt")
    if st.button("指定したタイムテーブルを削除"):
        st.session_state.tt_list.pop(del_tt - 1)
        st.rerun()

st.divider()

# --- 4. 出力処理 ---
if st.button("プレビューを確認してCSV作成", type="primary"):
    zf_f = pd.DataFrame(st.session_state.z_list)
    gf_f = pd.DataFrame(st.session_state.g_list)
    sf_f = pd.DataFrame(st.session_state.s_list)
    tt_f = st.session_state.tt_list
    
    mat = pd.DataFrame(index=range(max(len(zf_f), len(gf_f), len(sf_f), len(tt_f), 1)), columns=range(NUM_COLS))
    
    for i, r in zf_f.iterrows(): mat.iloc[i, 0:3] = [r["ゾーン名"], 4097+i, r["フェード秒"]]
    for i, r in gf_f.iterrows(): mat.iloc[i, 4:8] = [r["グループ名"], 32770+i, GROUP_TYPE_MAP.get(r["グループタイプ"], "1ch"), r["紐づけるゾーン名"]]
    
    scene_id_db = {}; sid_cnt = 8193
    for i, r in sf_f.iterrows():
        sn = r["シーン名"]
        if sn not in scene_id_db: scene_id_db[sn] = sid_cnt; sid_cnt += 1
        mat.iloc[i, 9:17] = [sn, scene_id_db[sn], r["調光"], r["ケルビン"], r["Syncaカラー"], "", r["紐づけるゾーン名"], r["紐づけるグループ名"]]
    
    for i, tt in enumerate(tt_f):
        mat.iloc[i, 17:20] = [tt["tt_name"], 12289+i, tt["zone"]]
        c_idx = 22
        for slot in tt["slots"]:
            if c_idx < 196:
                mat.iloc[i, c_idx], mat.iloc[i, c_idx+1] = slot["time"], slot["scene"]
                c_idx += 2

    final_df = pd.concat([pd.DataFrame(CSV_HEADER), mat], ignore_index=True)
    st.write("### 最終プレビュー")
    st.dataframe(final_df.iloc[3:].dropna(how='all', axis=0), use_container_width=True)
    
    buf = io.BytesIO()
    final_df.to_csv(buf, index=False, header=False, encoding="utf-8-sig")
    st.download_button("📥 CSVダウンロード", buf.getvalue(), f"{shop_name}_setting.csv", "text/csv")
