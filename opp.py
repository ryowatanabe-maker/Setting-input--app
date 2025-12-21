import streamlit as st
import pandas as pd
import io

# --- 1. 定数とヘッダーの定義 ---
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
NUM_COLS = 74

ROW1 = (['Zone情報', None, None, None, 'Group情報', None, None, None, None, 'Scene情報'] + [None] * 64)[:NUM_COLS]
ROW3 = (['[zone]', '[id]', '[fade]', None, '[group]', '[id]', '[type]', '[zone]', None, '[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]'] + [None] * 58)[:NUM_COLS]
CSV_HEADER = [ROW1, [None] * NUM_COLS, ROW3]

def make_unique_cols(header_row):
    seen = {}
    unique_names = []
    for i, name in enumerate(header_row):
        base = str(name) if name and str(name) != 'nan' else f"col_{i}"
        if base not in seen:
            seen[base] = 0; unique_names.append(base)
        else:
            seen[base] += 1; unique_names.append(f"{base}_{seen[base]}")
    return unique_names

# --- 2. アプリ設定 ---
st.set_page_config(page_title="設定データ作成アプリ", layout="wide")
st.title("設定データ作成アプリ ⚙️")

# セッションステートの初期化
if 'z_list' not in st.session_state: st.session_state.z_list = []
if 'g_list' not in st.session_state: st.session_state.g_list = []
if 's_list' not in st.session_state: st.session_state.s_list = []

# --- 3. UIセクション ---

st.header("1. 店舗名入力")
shop_name = st.text_input("店舗名", value="店舗A")

st.divider()

# 2. ゾーン情報
st.header("2. ゾーン情報")
z_df = st.data_editor(pd.DataFrame(st.session_state.z_list if st.session_state.z_list else [{"ゾーン名": "", "フェード秒": 0}]), num_rows="dynamic", use_container_width=True, key="z_ed_v16")
v_zones = [""] + [z for z in z_df["ゾーン名"].tolist() if z]

# 3. グループ情報
st.header("3. グループ情報")
g_df = st.data_editor(pd.DataFrame(st.session_state.g_list if st.session_state.g_list else [{"グループ名": "", "グループタイプ": "調光", "紐づけるゾーン名": ""}]), 
                      column_config={"グループタイプ": st.column_config.SelectboxColumn(options=list(GROUP_TYPE_MAP.keys())), "紐づけるゾーン名": st.column_config.SelectboxColumn(options=v_zones)},
                      num_rows="dynamic", use_container_width=True, key="g_ed_v16")
g_to_zone = dict(zip(g_df["グループ名"], g_df["紐づけるゾーン名"]))
g_to_type = dict(zip(g_df["グループ名"], g_df["グループタイプ"]))
v_groups = [""] + [g for g in g_df["グループ名"].tolist() if g]

st.divider()

# 4. シーン情報 (フォーム形式)
st.header("4. シーン情報の追加")

st.write("- **調光調色**: 2700 〜 6500 (K不要)")
st.write("- **Synca / Synca Bright**: 1800 〜 12000 (K不要)")

with st.form("scene_form", clear_on_submit=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1: s_name = st.text_input("シーン名")
    with col2: target_g = st.selectbox("グループ名", options=v_groups)
    with col3: dim = st.number_input("調光(%)", 0, 100, 100)
    with col4: color = st.text_input("調色(K)")
    
    if st.form_submit_button("このシーンにグループを追加"):
        if s_name and target_g:
            new_row = {
                "シーン名": s_name,
                "紐づけるグループ名": target_g,
                "紐づけるゾーン名": g_to_zone.get(target_g, ""),
                "調光": dim,
                "調色": color
            }
            st.session_state.s_list.append(new_row)
            st.toast(f"追加: {s_name} に {target_g} を紐づけました")
        else:
            st.warning("シーン名とグループ名を選択してください")

# リストの表示と削除
if st.session_state.s_list:
    st.subheader("現在のシーン登録リスト")
    current_s_df = pd.DataFrame(st.session_state.s_list)
    st.dataframe(current_s_df, use_container_width=True)
    
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("最後の1件を削除"):
            if st.session_state.s_list:
                st.session_state.s_list.pop()
                st.rerun()
    with c_btn2:
        if st.button("リストを全クリア"):
            st.session_state.s_list = []
            st.rerun()

st.divider()

# --- 4. 出力処理 ---
if st.button("プレビューを確認してCSV作成", type="primary"):
    zf_f = z_df[z_df["ゾーン名"] != ""].reset_index(drop=True)
    gf_f = g_df[g_df["グループ名"] != ""].reset_index(drop=True)
    sf_f = pd.DataFrame(st.session_state.s_list)
    
    if sf_f.empty:
        st.warning("シーンを登録してください。")
    else:
        # 範囲バリデーション
        errors = []
        for idx, r in sf_f.iterrows():
            gn = r["紐づけるグループ名"]
            tp = g_to_type.get(gn, "調光")
            cv = str(r["調色"]).upper().replace("K", "").strip()
            if tp != "調光" and cv.isdigit():
                k_num = int(cv)
                if tp == "調光調色" and not (2700 <= k_num <= 6500):
                    errors.append(f"❌ 行{idx+1}: {gn} (2700-6500K)")
                elif tp in ["Synca", "Synca Bright"] and not (1800 <= k_num <= 12000):
                    errors.append(f"❌ 行{idx+1}: {gn} (1800-12000K)")
        
        if errors:
            for e in errors: st.error(e)
            st.stop()

        # ID同期
        scene_id_map = {}; sid_cnt = 8193
        max_r = max(len(zf_f), len(gf_f), len(sf_f))
        mat = pd.DataFrame(index=range(max_r), columns=range(NUM_COLS))
        
        for i, r in zf_f.iterrows():
            mat.iloc[i, 0], mat.iloc[i, 1], mat.iloc[i, 2] = r["ゾーン名"], 4097+i, r["フェード秒"]
        for i, r in gf_f.iterrows():
            mat.iloc[i, 4], mat.iloc[i, 5], mat.iloc[i, 6], mat.iloc[i, 7] = r["グループ名"], 32769+i, GROUP_TYPE_MAP.get(r["グループタイプ"], "1ch"), r["紐づけるゾーン名"]
        for i, r in sf_f.iterrows():
            name = r["シーン名"]
            if name not in scene_id_map:
                scene_id_map[name] = sid_cnt; sid_cnt += 1
            mat.iloc[i, 9], mat.iloc[i, 10], mat.iloc[i, 11], mat.iloc[i, 12], mat.iloc[i, 14], mat.iloc[i, 15] = name, scene_id_map[name], r["調光"], r["調色"], r["紐づけるゾーン名"], r["紐づけるグループ名"]

        final_df = pd.concat([pd.DataFrame(CSV_HEADER), mat], ignore_index=True)
        st.session_state.final_csv_v16 = final_df
        st.write("### 5. 最終プレビュー")
        st.dataframe(final_df.iloc[3:], use_container_width=True)

if 'final_csv_v16' in st.session_state:
    buf = io.BytesIO()
    st.session_state.final_csv_v16.to_csv(buf, index=False, header=False, encoding="utf-8-sig")
    st.download_button("📥 CSVダウンロード", buf.getvalue(), f"{shop_name}_setting.csv", "text/csv")
