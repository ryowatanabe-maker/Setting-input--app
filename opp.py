import streamlit as st
import pandas as pd
import io

# --- 1. 定数とヘッダーの定義 ---
GROUP_TYPE_MAP = {"調光": "1ch", "調光調色": "2ch", "Synca": "3ch", "Synca Bright": "fresh 3ch"}
NUM_COLS = 236 

# ヘッダー作成 (アップロードされたCSVの構造を再現)
ROW1 = [None] * NUM_COLS
ROW1[0], ROW1[4], ROW1[9], ROW1[17], ROW1[197], ROW1[207], ROW1[213], ROW1[218], ROW1[221], ROW1[231] = \
    'Zone情報', 'Group情報', 'Scene情報', 'Timetable情報', 'Timetable-schedule情報', 'Timetable期間/特異日情報', 'センサーパターン情報', 'センサータイムテーブル情報', 'センサータイムテーブル/スケジュール情報', 'センサータイムテーブル期間/特異日情報'

ROW3 = [None] * NUM_COLS
ROW3[0:3] = ['[zone]', '[id]', '[fade]']
ROW3[4:8] = ['[group]', '[id]', '[type]', '[zone]']
ROW3[9:16] = ['[scene]', '[id]', '[dimming]', '[color]', '[perform]', '[zone]', '[group]']
ROW3[17:22] = ['[zone-timetable]', '[id]', '[zone]', '[sun-start-scene]', '[sun-end-scene]']
for i in range(22, 196, 2):
    ROW3[i] = '[time]'
    ROW3[i+1] = '[scene]'
ROW3[197:206] = ['[zone-ts]', '[daily]', '[monday]', '[tuesday]', '[wednesday]', '[thursday]', '[friday]', '[saturday]', '[sunday]']
ROW3[207:212] = ['[zone-period]', '[start]', '[end]', '[timetable]', '[zone]']

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
for key in ['z_list', 'g_list', 's_list', 'tt_list']:
    if key not in st.session_state: st.session_state[key] = []

# --- 3. UIセクション ---

st.header("1. 店舗名入力")
shop_name = st.text_input("店舗名", value="店舗A")

st.divider()

# 2. ゾーン情報
st.header("2. ゾーン情報")
z_df = st.data_editor(pd.DataFrame(st.session_state.z_list if st.session_state.z_list else [{"ゾーン名": "", "フェード秒": 0}]), num_rows="dynamic", use_container_width=True, key="z_ed_v17")
v_zones = [""] + [z for z in z_df["ゾーン名"].tolist() if z]

# 3. グループ情報
st.header("3. グループ情報")
g_df = st.data_editor(pd.DataFrame(st.session_state.g_list if st.session_state.g_list else [{"グループ名": "", "グループタイプ": "調光", "紐づけるゾーン名": ""}]), 
                      column_config={"グループタイプ": st.column_config.SelectboxColumn(options=list(GROUP_TYPE_MAP.keys())), "紐づけるゾーン名": st.column_config.SelectboxColumn(options=v_zones)},
                      num_rows="dynamic", use_container_width=True, key="g_ed_v17")
g_to_zone = dict(zip(g_df["グループ名"], g_df["紐づけるゾーン名"]))
g_to_type = dict(zip(g_df["グループ名"], g_df["グループタイプ"]))
v_groups = [""] + [g for g in g_df["グループ名"].tolist() if g]

st.divider()

# 4. シーン情報
st.header("4. シーン情報の追加")
st.write("- **調光調色**: 2700 〜 6500 / **Synca**: 1800 〜 12000")

with st.form("scene_form", clear_on_submit=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1: s_name = st.text_input("シーン名")
    with col2: target_g = st.selectbox("グループ名", options=v_groups)
    with col3: dim = st.number_input("調光(%)", 0, 100, 100)
    with col4: color = st.text_input("調色(K)")
    
    if st.form_submit_button("このシーンにグループを追加"):
        if s_name and target_g:
            st.session_state.s_list.append({"シーン名": s_name, "紐づけるグループ名": target_g, "紐づけるゾーン名": g_to_zone.get(target_g, ""), "調光": dim, "調色": color})
            st.toast(f"追加: {s_name}")
v_scenes = [""] + sorted(list(set([s["シーン名"] for s in st.session_state.s_list if s["シーン名"]])))

st.divider()

# 5. タイムテーブル情報
st.header("5. タイムテーブル情報の追加")
with st.expander("タイムテーブル作成フォームを開く"):
    with st.form("tt_form", clear_on_submit=True):
        col_t1, col_t2 = st.columns(2)
        with col_t1: tt_name = st.text_input("タイムテーブル名 (例: 通常, 春)")
        with col_t2: tt_zone = st.selectbox("対象ゾーン", options=v_zones)
        
        st.write("▼ 時間とシーンのスケジュールを設定")
        slots = []
        rows = [st.columns(4) for _ in range(3)] # 3行 x 4列 = 12スロット分
        for i in range(12):
            with rows[i // 4][i % 4]:
                t = st.text_input(f"時間 {i+1}", placeholder="9:00", key=f"t_{i}")
                s = st.selectbox(f"シーン {i+1}", options=v_scenes, key=f"s_{i}")
                if t and s: slots.append({"time": t, "scene": s})
        
        if st.form_submit_button("タイムテーブルをリストに追加"):
            if tt_name and tt_zone and slots:
                st.session_state.tt_list.append({"tt_name": tt_name, "zone": tt_zone, "slots": slots})
                st.success(f"'{tt_name}' を追加しました")
                st.rerun()

if st.session_state.tt_list:
    st.subheader("現在のタイムテーブル登録リスト")
    for tt in st.session_state.tt_list:
        st.text(f"● {tt['tt_name']} [{tt['zone']}]: " + " / ".join([f"{sl['time']} {sl['scene']}" for sl in tt['slots']]))

if st.button("全データをクリアしてやり直す"):
    st.session_state.s_list, st.session_state.tt_list = [], []
    st.rerun()

st.divider()

# --- 4. 出力処理 ---
if st.button("プレビューを確認してCSV作成", type="primary"):
    zf_f = z_df[z_df["ゾーン名"] != ""].reset_index(drop=True)
    gf_f = g_df[g_df["グループ名"] != ""].reset_index(drop=True)
    sf_f = pd.DataFrame(st.session_state.s_list)
    tt_f = st.session_state.tt_list
    
    # 巨大な行列を作成
    mat = pd.DataFrame(index=range(max(len(zf_f), len(gf_f), len(sf_f), len(tt_f), 1)), columns=range(NUM_COLS))
    
    # 1. ゾーン & グループ
    for i, r in zf_f.iterrows(): mat.iloc[i, 0:3] = [r["ゾーン名"], 4097+i, r["フェード秒"]]
    for i, r in gf_f.iterrows(): mat.iloc[i, 4:8] = [r["グループ名"], 32769+i, GROUP_TYPE_MAP.get(r["グループタイプ"], "1ch"), r["紐づけるゾーン名"]]
    
    # 2. シーン (ID同期 8193〜)
    scene_id_db = {}; sid_cnt = 8193
    if not sf_f.empty:
        for i, r in sf_f.iterrows():
            sn = r["シーン名"]
            if sn not in scene_id_db: scene_id_db[sn] = sid_cnt; sid_cnt += 1
            mat.iloc[i, 9:16] = [sn, scene_id_db[sn], r["調光"], r["調色"], "", r["紐づけるゾーン名"], r["紐づけるグループ名"]]
    
    # 3. タイムテーブル (ID同期 12289〜)
    for i, tt in enumerate(tt_f):
        mat.iloc[i, 17:20] = [tt["tt_name"], 12289+i, tt["zone"]]
        c_idx = 22
        for slot in tt["slots"]:
            if c_idx < 196:
                mat.iloc[i, c_idx] = slot["time"]
                mat.iloc[i, c_idx+1] = slot["scene"]
                c_idx += 2

    final_df = pd.concat([pd.DataFrame(CSV_HEADER), mat], ignore_index=True)
    st.session_state.final_csv = final_df
    st.write("### プレビュー")
    st.dataframe(final_df.iloc[3:].dropna(how='all', axis=0), use_container_width=True)

if 'final_csv' in st.session_state:
    buf = io.BytesIO()
    st.session_state.final_csv.to_csv(buf, index=False, header=False, encoding="utf-8-sig")
    st.download_button("📥 CSVダウンロード", buf.getvalue(), f"{shop_name}_setting.csv", "text/csv")
