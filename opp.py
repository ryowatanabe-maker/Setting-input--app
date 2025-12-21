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
z_df = st.data_editor(pd.DataFrame(st.session_state.z_list if st.session_state.z_list else [{"ゾーン名": "", "フェード秒": 0}]), num_rows="dynamic", use_container_width=True, key="z_ed")
v_zones = [""] + [z for z in z_df["ゾーン名"].tolist() if z]

# 3. グループ情報
st.header("3. グループ情報")
g_df = st.data_editor(pd.DataFrame(st.session_state.g_list if st.session_state.g_list else [{"グループ名": "", "グループタイプ": "調光", "紐づけるゾーン名": ""}]), 
                      column_config={"グループタイプ": st.column_config.SelectboxColumn(options=list(GROUP_TYPE_MAP.keys())), "紐づけるゾーン名": st.column_config.SelectboxColumn(options=v_zones)},
                      num_rows="dynamic", use_container_width=True, key="g_ed")
g_to_zone = dict(zip(g_df["グループ名"], g_df["紐づけるゾーン名"]))
g_to_type = dict(zip(g_df["グループ名"], g_df["グループタイプ"]))
v_groups = [""] + [g for g in g_df["グループ名"].tolist() if g]

st.divider()

# 4. シーン情報 (フォーム形式)
st.header("4. シーン情報の追加")

st.write("- **調光調色**: 2700 〜 6500 (K不要)")
st.write("- **Synca / Synca Bright**: 1800 〜 12000 (K不要)")

with st.form("scene_form", clear_on_submit=False): # 同じシーン名を連続入力しやすいようclearはFalse
    col1, col2, col3, col4 = st.columns(4)
    with col1: s_name = st.text_input("シーン名")
    with col2: target_g = st.selectbox("グループ名", options=v_groups)
    with col3: dim = st.number_input("調光(%)", 0, 100, 100)
    with col4: color = st.text_input("調色(K)")
    
    if st.form_submit_button("このシーンにグループを追加"):
        if s_name and target_g:
            new_scene = {
                "シーン名": s_name,
                "紐づけるグループ名": target_g,
                "紐づけるゾーン名": g_to_zone.get(target_g, ""),
                "調光": dim,
                "調色": color
            }
            # リストに追加
            st.session_state.s_list.append(new_scene)
            st.toast(f"追加: {s_name} に {target_g} を紐づけました")
        else:
            st.warning("シーン名とグループ名を選択してください")

# 追加されたシーンの確認と個別削除
if st.session_state.s_list:
    st.subheader("現在のシーン登録リスト (プレビュー時に自動でID同期されます)")
    current_s_df = pd.DataFrame(st.session_state.s_list)
    
    # 簡易的な表示
    st.dataframe(current_s_df, use_container_width=True)
    
    col_cl1, col_cl2 = st.columns(2)
    with col_cl1:
        if st.button("最後の1件を取り消す"):
            st.session_state.s_list.pop()
            st.rer
