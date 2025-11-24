import streamlit as st
import pandas as pd
from datetime import datetime
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import time

# --- Streamlit 頁面配置 ---
st.set_page_config(
    layout="wide", 
    page_title="🇰🇷 首爾旅遊筆記本 (Firebase 連線中)",
    page_icon="✈️"
)

# --- Firebase 連線與初始化 ---
# 將 @st.cache_resource 拿掉，以便在找不到檔案時顯示錯誤
def initialize_firestore():
    """使用服務帳戶檔案來初始化 Firebase"""
    
    # 定義金鑰檔案在 Streamlit Cloud 環境中的預期路徑
    key_file_path = "firebase_key.json" 
    
    try:
        # 1. 檢查檔案是否存在 (假設檔案已被部署)
        import os
        if not os.path.exists(key_file_path):
            st.error(f"❌ 關鍵檔案 '{key_file_path}' 缺失。請確保該檔案已上傳至 GitHub 倉庫根目錄！")
            return None

        # 2. 檢查是否已初始化，避免重複初始化錯誤
        if not firebase_admin._apps:
            # 3. 從檔案路徑讀取憑證
            cred = credentials.Certificate(key_file_path)
            firebase_admin.initialize_app(cred)
            
        # 4. 連線到 Firestore 資料庫
        return firestore.client()
        
    except Exception as e:
        st.error(f"❌ Firebase 連線失敗 (檔案模式)。請檢查 '{key_file_path}' 檔案內容是否完整無損：{e}")
        return None

# 初始化連線
db = initialize_firestore() 

# --- 資料讀取函式 ---
def load_trip_data(db):
    """從 Firestore 讀取行程主要資料"""
    if not db:
        return None
    try:
        # 嘗試從 'trip_data' Collection 的 'master_info' Document 讀取
        doc_ref = db.collection('trip_data').document('master_info')
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            st.success("✅ 資料已成功從 Firebase 讀取！")
            return data
        else:
            st.warning("⚠️ Firestore 中找不到 'trip_data/master_info' 文件。請手動建立資料。")
            return None
    except Exception as e:
        st.error(f"❌ 讀取資料失敗：{e}")
        return None

# --- 主要程式邏輯 ---
if db:
    trip_data = load_trip_data(db)
    
    if trip_data:
        # 設置標題和基本資訊
        st.markdown("## 旅遊筆記本")
        st.markdown(f"我的旅行 ({datetime.now().year}/{datetime.now().month}) | **數據源：Firebase**")

        # 初始化 Session State (旅伴管理)
        if 'companions' not in st.session_state:
            st.session_state.companions = trip_data.get('companions', ["自己"])
        
        # --- 分頁導航 (與舊版相同) ---
        tab_titles = ["📄 資訊", "🗺️ 行程", "☀️ 天氣", "💰 記帳", "💬 助手"]
        tabs = st.tabs(tab_titles)

        with tabs[0]: # 📄 資訊 頁面 (使用 Firestore 資料)
            st.header("資訊總覽")
            
            # --- 航班資訊卡片 ---
            st.markdown("""
                <div style='padding: 15px; border-radius: 10px; border: 1px solid #C4D7ED; background-color: #E6EFFD; margin-bottom: 20px;'>
                <h3 style='margin: 0; padding-bottom: 10px; color: #1E40AF;'>✈️ 航班資訊</h3>
            """, unsafe_allow_html=True)
            
            flights = trip_data.get('flights', [])
            for flight in flights:
                with st.container(border=True):
                    col_type, col_info, col_time = st.columns([1, 2, 2])
                    
                    with col_type:
                        st.markdown(f"**{flight.get('type', '單程')}航班**")
                        st.markdown(f"**{flight.get('code', 'N/A')}**")

                    with col_info:
                        st.markdown(f"**日期:** {flight.get('date', 'N/A')}")
                        st.markdown(f"**訂位代碼:** `{flight.get('pnr', 'N/A')}`")
                        st.markdown(f"**航廈:** {flight.get('terminal', 'N/A')}")
                    
                    with col_time:
                        st.markdown(f"**{flight.get('from', 'N/A')} ({flight.get('dep', 'N/A')}) → {flight.get('to', 'N/A')} ({flight.get('arr', 'N/A')})**")
            
            st.markdown("</div>", unsafe_allow_html=True)

            # --- 住宿資訊卡片 ---
            hotel = trip_data.get('hotel', {})
            st.markdown("""
                <div style='padding: 15px; border-radius: 10px; border: 1px solid #F5D0A9; background-color: #FEF3E6; margin-bottom: 20px;'>
                <h3 style='margin: 0; padding-bottom: 10px; color: #9A3412;'>🏨 住宿資訊</h3>
            """, unsafe_allow_html=True)
            
            st.subheader(f"**{hotel.get('name', '未設定飯店名稱')}**")
            
            col_addr, col_ref = st.columns(2)
            
            with col_addr:
                st.markdown(f"**英文地址:** {hotel.get('eng_addr', 'N/A')}")
                st.markdown(f"**韓文地址:** {hotel.get('kor_addr', 'N/A')}")
            
            with col_ref:
                st.markdown(f"**訂位代碼:** `{hotel.get('booking_ref', 'N/A')}`")
                st.markdown(f"**電話:** {hotel.get('phone', 'N/A')}")

            col_time_in, col_time_out = st.columns(2)
            with col_time_in:
                st.markdown(f"**入住:** {hotel.get('check_in', 'N/A')}")
            with col_time_out:
                st.markdown(f"**退房:** {hotel.get('check_out', 'N/A')}")
                
            # --- 給司機看 按鈕功能 ---
            if st.button("🚖 給司機看 (放大地址)"):
                st.code(f"""
                [請向司機出示]
                飯店名稱: {hotel.get('name', 'N/A')}
                韓文地址: {hotel.get('kor_addr', 'N/A')}
                電話: {hotel.get('phone', 'N/A')}
                """, language='text')

            st.markdown("</div>", unsafe_allow_html=True)

            # --- 旅伴管理區塊 (暫時保持 Session State，未來升級至 Firebase) ---
            with st.expander("👥 旅伴管理 (用於記帳分攤)", expanded=True):
                st.markdown("目前的旅伴清單:")
                st.markdown(f"**{', '.join(st.session_state.companions)}**")
                
                new_companion = st.text_input("新增旅伴暱稱", key="new_comp")
                
                col_add, col_clear = st.columns(2)
                
                with col_add:
                    if st.button("➕ 新增旅伴"):
                        if new_companion and new_companion not in st.session_state.companions:
                            st.session_state.companions.append(new_companion)
                            st.experimental_rerun()
                
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
            st.warning("💡 記帳功能將在下一步利用 Firebase 的寫入功能實現持久化。")
            if st.session_state.companions:
                st.subheader("旅伴分攤參考")
                st.write(f"可分攤的旅伴: {', '.join(st.session_state.companions)}")
                
        with tabs[4]: # 💬 助手 頁面 (Placeholder)
            st.header("即時翻譯與助手")
            st.info("未來可整合 Gemini API，實現即時翻譯或旅遊問題問答。")

# --- 無法連線的提示 ---
if not db:
    st.markdown("## ❌ 系統初始化失敗")
    st.error("無法連線到您的 Firebase 資料庫。請檢查 Streamlit Secrets 中的 JSON 金鑰格式。")
