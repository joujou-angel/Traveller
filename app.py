import streamlit as st
import pandas as pd
from datetime import datetime
import json

# --- 核心數據 (Hard-Coded Itinerary Data) ---
# 日期已設為範例，請使用者自行修改
TRIP_START_DATE = datetime(2025, 11, 27)
TRIP_END_DATE = datetime(2025, 12, 1)

FLIGHTS = [
    {"type": "去程", "code": "JX800", "pnr": "6X2P9A", "date": "11/27", "from": "TPE (松山)", "to": "GMP (金浦)", "dep": "10:40", "arr": "14:00", "terminal": "T1"},
    {"type": "回程", "code": "JX801", "pnr": "6X2P9A", "date": "12/01", "from": "GMP (金浦)", "to": "TPE (松山)", "dep": "15:30", "arr": "18:50", "terminal": "T1"},
]

HOTEL = {
    "name": "Lotte Hotel Seoul",
    "eng_addr": "30 Eulji-ro, Jung-gu, Seoul, South Korea",
    "kor_addr": "서울특별시 중구 을지로 30",
    "phone": "+82-2-771-1000",
    "booking_ref": "RES-998877",
    "check_in": "15:00",
    "check_out": "11:00",
}

# --- Streamlit 頁面配置 ---
# 確保 page_icon 參數正確，可使用 Emoji 或公開 URL
st.set_page_config(
    layout="wide", 
    page_title="🇰🇷 首爾旅遊筆記本",
    page_icon="✈️" # 這裡使用 Emoji 作為簡易圖示
)

# 初始化會話狀態 (Session State) 儲存旅伴
if 'companions' not in st.session_state:
    st.session_state.companions = ["自己"]

# --- App 標題與資訊 ---
trip_days = (TRIP_START_DATE - datetime.now()).days
st.markdown(f"## 旅遊筆記本")
st.markdown(f"我的旅行 ({TRIP_START_DATE.year}/{TRIP_START_DATE.month}) | 距離出發還有 **{trip_days}** 天")

# --- 分頁導航 (還原底部五個圖示的 UX) ---
tab_titles = ["📄 資訊", "🗺️ 行程", "☀️ 天氣", "💰 記帳", "💬 助手"]
tabs = st.tabs(tab_titles)

with tabs[0]: # 📄 資訊 頁面 (還原截圖佈局)
    st.header("資訊總覽")
    
    # --- 航班資訊卡片 ---
    st.markdown("""
        <div style='padding: 15px; border-radius: 10px; border: 1px solid #C4D7ED; background-color: #E6EFFD; margin-bottom: 20px;'>
        <h3 style='margin: 0; padding-bottom: 10px; color: #1E40AF;'>✈️ 航班資訊</h3>
    """, unsafe_allow_html=True)
    
    for flight in FLIGHTS:
        with st.container(border=True):
            col_type, col_info, col_time = st.columns([1, 2, 2])
            
            with col_type:
                st.markdown(f"**{flight['type']}航班**")
                st.markdown(f"**{flight['code']}**")

            with col_info:
                st.markdown(f"**日期:** {flight['date']}")
                st.markdown(f"**訂位代碼:** `{flight['pnr']}`")
                st.markdown(f"**航廈:** {flight['terminal']}")
            
            with col_time:
                st.markdown(f"**{flight['from']} ({flight['dep']}) → {flight['to']} ({flight['arr']})**")
    
    st.markdown("</div>", unsafe_allow_html=True)


    # --- 住宿資訊卡片 ---
    st.markdown("""
        <div style='padding: 15px; border-radius: 10px; border: 1px solid #F5D0A9; background-color: #FEF3E6; margin-bottom: 20px;'>
        <h3 style='margin: 0; padding-bottom: 10px; color: #9A3412;'>🏨 住宿資訊</h3>
    """, unsafe_allow_html=True)
    
    st.subheader(f"**{HOTEL['name']}**")
    
    col_addr, col_ref = st.columns(2)
    
    with col_addr:
        st.markdown(f"**英文地址:** {HOTEL['eng_addr']}")
        st.markdown(f"**韓文地址:** {HOTEL['kor_addr']}")
    
    with col_ref:
        st.markdown(f"**訂位代碼:** `{HOTEL['booking_ref']}`")
        st.markdown(f"**電話:** {HOTEL['phone']}")

    col_time_in, col_time_out = st.columns(2)
    with col_time_in:
        st.markdown(f"**入住:** {HOTEL['check_in']}")
    with col_time_out:
        st.markdown(f"**退房:** {HOTEL['check_out']}")
        
    # --- 給司機看 按鈕功能 ---
    if st.button("🚖 給司機看 (放大地址)"):
        st.code(f"""
        [請向司機出示]
        飯店名稱: {HOTEL['name']}
        韓文地址: {HOTEL['kor_addr']}
        電話: {HOTEL['phone']}
        """, language='text')

    st.markdown("</div>", unsafe_allow_html=True)


    # --- 旅伴管理區塊 ---
    with st.expander("👥 旅伴管理 (用於記帳分攤)", expanded=True):
        st.markdown("目前的旅伴清單:")
        st.markdown(f"**{', '.join(st.session_state.companions)}**")
        
        new_companion = st.text_input("新增旅伴暱稱", key="new_comp")
        
        col_add, col_clear = st.columns(2)
        
        with col_add:
            if st.button("➕ 新增旅伴"):
                if new_companion and new_companion not in st.session_state.companions:
                    st.session_state.companions.append(new_companion)
                    st.experimental_rerun() # 重啟頁面更新清單
        
        with col_clear:
            if st.button("🗑️ 清空旅伴清單"):
                st.session_state.companions = ["自己"]
                st.experimental_rerun()


with tabs[1]: # 🗺️ 行程 頁面 (Placeholder)
    st.header("行程細節")
    st.info("此處將用於展示每日行程清單與地圖。")

with tabs[2]: # ☀️ 天氣 頁面 (Placeholder)
    st.header("首爾即時天氣")
    st.info("可規劃在此處展示即時天氣或氣溫預報圖。")

with tabs[3]: # 💰 記帳 頁面 (Placeholder)
    st.header("協作記帳本")
    st.warning("此為未來階段 (Phase 2) 的核心功能。若要實現多人共享記帳，需要 **Firebase/Supabase** 資料庫支援。")
    st.markdown("目前可做單人記帳功能模擬，將旅伴清單用於分攤計算。")
    if st.session_state.companions:
        st.subheader("旅伴分攤參考")
        st.write(f"可分攤的旅伴: {', '.join(st.session_state.companions)}")
        
with tabs[4]: # 💬 助手 頁面 (Placeholder)
    st.header("即時翻譯與助手")
    st.info("未來可整合 Gemini API，實現即時翻譯或旅遊問題問答。")
