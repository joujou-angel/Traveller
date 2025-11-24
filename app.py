import streamlit as st
import pandas as pd
from datetime import datetime
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import time
import os

# --- Streamlit 頁面配置 ---
st.set_page_config(
    layout="wide", 
    page_title="🇰🇷 首爾旅遊筆記本 (Firebase 連線中)",
    page_icon="✈️"
)

# --- Firebase 連線與初始化 ---
def initialize_firestore():
    """使用服務帳戶檔案來初始化 Firebase"""
    
    # 定義金鑰檔案在 Streamlit Cloud 環境中的預期路徑
    key_file_path = "firebase_key.json" 
    
    try:
        # 1. 檢查檔案是否存在 (務實策略：檔案部署模式)
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
    # 執行資料讀取
    trip_data = load_trip_data(db)
    
    # 定義 Firestore 文件參考，供後續寫入 (Update) 使用
    master_info_ref = db.collection('trip_data').document('master_info')
    
    if trip_data:
        # 設置標題和基本資訊
        st.markdown("## 旅遊筆記本")
        st.markdown(f"我的旅行 ({datetime.now().year}/{datetime.now().month}) | **數據源：Firebase**")
        
        # 從 Firebase 獲取當前旅伴清單 - 預設為空列表 []
        current_companions = trip_data.get('companions', [])
        
        # --- 核心更新函式 ---
        def update_companions_in_firebase(new_list):
            try:
                # 執行 Firestore 更新
                master_info_ref.update({"companions": new_list})
                st.success("✅ 旅伴清單已成功更新並同步至 Firebase！")
                st.rerun() # 重新執行以載入最新資料
            except Exception as e:
                st.error(f"❌ 旅伴清單寫入失敗。錯誤代碼: {e}")

        # --- 分頁導航 ---
        tab_titles = ["📄 資訊", "🗺️ 行程", "☀️ 天氣", "💰 記帳", "💬 助手"]
        tabs = st.tabs(tab_titles)

        with tabs[0]: # 📄 資訊 頁面 (使用 Firestore 資料)
            st.header("資訊總覽")
            
            # --- 航班資訊卡片 (整合編輯與顯示) ---
            flight_types = ["去程 (Outbound)", "回程 (Return)", "轉機 (Layover)"]
            current_flights = trip_data.get('flights', [])

            # 設置編輯狀態和暫存資料的 Session State
            if 'edit_flights' not in st.session_state:
                st.session_state.edit_flights = False
            # 只有在非編輯狀態讀取時才重置，否則保留編輯中的數據
            if 'flights_temp' not in st.session_state or not st.session_state.edit_flights:
                 # 確保 temp list 始終與當前資料同步
                st.session_state.flights_temp = current_flights[:]

            st.markdown("""
                <div style='padding: 15px; border-radius: 10px; border: 1px solid #C4D7ED; background-color: #E6EFFD; margin-bottom: 20px;'>
                <h3 style='margin: 0; padding-bottom: 10px; color: #1E40AF;'>✈️ 航班資訊</h3>
            """, unsafe_allow_html=True)

            # 編輯/取消編輯按鈕
            if st.button("✏️ 編輯/新增航班資訊", key="edit_flights_toggle"):
                st.session_state.edit_flights = not st.session_state.edit_flights
                # 重置 temp list 以確保資料新鮮度，或開始編輯
                st.session_state.flights_temp = current_flights[:] 
                st.rerun()

            # --- 編輯表單 (只有在編輯狀態下顯示) ---
            if st.session_state.edit_flights:
                
                # --- 新增航班按鈕 (必須在 st.form 之外，以觸發即時 RERUN) ---
                if st.button("➕ 點擊新增一筆航班", key="add_flight_btn"):
                    st.session_state.flights_temp.append({
                        "type": flight_types[0], "date": "", "code": "", "pnr": "", 
                        "terminal": "", "from": "", "dep": "", "to": "", "arr": ""
                    })
                    st.rerun() # 立即重繪以顯示新欄位
                    
                with st.form(key='flights_edit_form'):
                    st.markdown("##### 📝 航班編輯表單 - 同步寫回 Firebase")
                    st.markdown("---")
                    
                    # 遍歷並編輯現有航班
                    for i, flight in enumerate(st.session_state.flights_temp):
                        st.markdown(f"#### 航班 #{i + 1} - {flight.get('type', '單程')}")
                        
                        cols = st.columns([2, 2, 1])

                        with cols[0]:
                            # 允許選擇去程/回程/轉機
                            flight['type'] = st.selectbox("類型", options=flight_types, 
                                index=flight_types.index(flight.get('type', flight_types[0])) if flight.get('type') in flight_types else 0,
                                key=f"type_{i}"
                            )
                            flight['date'] = st.text_input("日期", value=flight.get("date", ""), key=f"date_{i}")
                            flight['code'] = st.text_input("航班編號", value=flight.get("code", ""), key=f"code_{i}")
                            flight['pnr'] = st.text_input("訂位代碼", value=flight.get("pnr", ""), key=f"pnr_{i}")
                            
                        with cols[1]:
                            flight['from'] = st.text_input("出發地 (e.g. TPE)", value=flight.get("from", ""), key=f"from_{i}")
                            flight['dep'] = st.text_input("預計起飛 (HH:MM)", value=flight.get("dep", ""), key=f"dep_{i}")
                            flight['to'] = st.text_input("目的地 (e.g. ICN)", value=flight.get("to", ""), key=f"to_{i}")
                            flight['arr'] = st.text_input("預計抵達 (HH:MM)", value=flight.get("arr", ""), key=f"arr_{i}")
                            flight['terminal'] = st.text_input("航廈資訊", value=flight.get("terminal", ""), key=f"terminal_{i}")

                        with cols[2]:
                            st.markdown("<br>"*5, unsafe_allow_html=True)
                            # 刪除按鈕：點擊後移除該項目並觸發重繪
                            if st.form_submit_button(f"❌ 刪除航班 #{i + 1}", help="點擊此按鈕將移除此航班並重新整理表單", key=f"delete_in_form_{i}"):
                                st.session_state.flights_temp.pop(i) 
                                st.session_state.edit_flights = True # 保持編輯模式
                                st.rerun() 
                        
                        st.markdown("---")
                        
                    submitted = st.form_submit_button("✅ 確認儲存所有航班更新至 Firebase")

                    if submitted:
                        final_flights = st.session_state.flights_temp
                        
                        try:
                            # 執行 Firestore 更新操作
                            master_info_ref.update({"flights": final_flights})
                            st.success("✅ 航班資訊已成功更新並同步至 Firebase！")
                            st.session_state.edit_flights = False
                            del st.session_state.flights_temp # 清理暫存狀態
                            st.rerun() 
                        except Exception as e:
                            st.error(f"❌ 資料寫入失敗。錯誤代碼: {e}")
                            
            # --- 航班資訊顯示 (非編輯狀態) ---
            if not st.session_state.edit_flights:
                flights_to_display = current_flights
                if not flights_to_display:
                    st.info("目前尚未設定任何航班資訊。請點擊 '編輯/新增航班資訊' 按鈕進行新增。")
                
                for flight in flights_to_display:
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


            # --- 住宿資訊卡片 (整合編輯與顯示) ---
            current_hotel = trip_data.get("hotel", {})
            
            st.markdown("""
            <div style='padding: 15px; border-radius: 10px; border: 1px solid #F5D0A9; background-color: #FEF3E6; margin-bottom: 20px;'>
            <h3 style='margin: 0; padding-bottom: 10px; color: #9A3412;'>🏨 住宿資訊</h3>
            """, unsafe_allow_html=True)
            
            # 設置編輯狀態的 Session State
            if 'edit_hotel' not in st.session_state:
                st.session_state.edit_hotel = False
                
            # 編輯/取消編輯按鈕
            if st.button("✏️ 編輯住宿資訊", key="edit_toggle"):
                st.session_state.edit_hotel = not st.session_state.edit_hotel
                
            # --- 編輯表單 (只有在編輯狀態下顯示) ---
            if st.session_state.edit_hotel:
                with st.form(key='hotel_edit_form'):
                    st.markdown("##### 📝 編輯表單 - 同步寫回 Firebase")
                    
                    # 使用 current_hotel 中的現有資料作為預設值
                    name = st.text_input("飯店名稱", value=current_hotel.get("name", ""))
                    kor_addr = st.text_area("韓文地址", value=current_hotel.get("kor_addr", ""))
                    eng_addr = st.text_area("英文地址", value=current_hotel.get("eng_addr", ""))
                    booking_ref = st.text_input("訂位代碼", value=current_hotel.get("booking_ref", ""))
                    phone = st.text_input("電話號碼", value=current_hotel.get("phone", ""))
                    check_in = st.text_input("入住時間 (e.g. 15:00)", value=current_hotel.get("check_in", "15:00"))
                    check_out = st.text_input("退房時間 (e.g. 11:00)", value=current_hotel.get("check_out", "11:00"))

                    submitted = st.form_submit_button("✅ 確認儲存並更新 Firebase")

                    if submitted:
                        # 構建新的 hotel 資料 Map
                        new_hotel_data = {
                            "name": name,
                            "kor_addr": kor_addr,
                            "eng_addr": eng_addr,
                            "booking_ref": booking_ref,
                            "phone": phone,
                            "check_in": check_in,
                            "check_out": check_out,
                            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S") 
                        }
                        
                        try:
                            # 執行 Firestore 更新操作 (核心的寫入操作)
                            master_info_ref.update({"hotel": new_hotel_data})
                            st.success("✅ 住宿資訊已成功更新並同步至 Firebase！")
                            st.session_state.edit_hotel = False 
                            st.rerun() 
                        except Exception as e:
                            st.error(f"❌ 資料寫入失敗。錯誤代碼: {e}")
            
            # --- 住宿資訊顯示 (非編輯狀態) ---
            if not st.session_state.edit_hotel:
                st.subheader(f"**{current_hotel.get('name', '未設定飯店名稱')}**")
                
                col_addr, col_ref = st.columns(2)
                with col_addr:
                    st.markdown(f"**英文地址:** {current_hotel.get('eng_addr', 'N/A')}")
                    st.markdown(f"**韓文地址:** {current_hotel.get('kor_addr', 'N/A')}")
                
                with col_ref:
                    st.markdown(f"**訂位代碼:** `{current_hotel.get('booking_ref', 'N/A')}`")
                    st.markdown(f"**電話:** {current_hotel.get('phone', 'N/A')}")

                col_time_in, col_time_out = st.columns(2)
                with col_time_in:
                    st.markdown(f"**入住:** {current_hotel.get('check_in', 'N/A')}")
                with col_time_out:
                    st.markdown(f"**退房:** {current_hotel.get('check_out', 'N/A')}")
                    
                # --- [整合舊版功能] 給司機看 按鈕功能 ---
                if st.button("🚖 給司機看 (放大地址)", key="driver_button"):
                    st.code(f"""
[請向司機出示]
飯店名稱: {current_hotel.get('name', 'N/A')}
韓文地址: {current_hotel.get('kor_addr', 'N/A')}
電話: {current_hotel.get('phone', 'N/A')}
""", language='text')

                updated_time = current_hotel.get('last_updated', '尚未紀錄')
                st.caption(f"數據新鮮度指標：最後更新於 {updated_time}")

            # --- [整合舊版功能] HTML 結尾 ---
            st.markdown("</div>", unsafe_allow_html=True)

            # --- 旅伴管理區塊 (升級至 Firebase 永久化，無預設「自己」) ---
            with st.expander("👥 旅伴管理 (用於記帳分攤)", expanded=True):
                st.markdown("目前的旅伴清單:")
                if current_companions:
                    st.markdown(f"**{', '.join(current_companions)}**")
                else:
                    st.info("目前旅伴清單為空。請新增您的暱稱和其他旅伴。")
                
                new_companion = st.text_input("新增旅伴暱稱", key="new_comp")
                
                col_add, col_clear = st.columns(2)
                
                with col_add:
                    if st.button("➕ 新增旅伴", key="add_comp_btn"):
                        # 檢查：非空且不在現有清單中
                        if new_companion and new_companion not in current_companions:
                            new_list = current_companions + [new_companion]
                            update_companions_in_firebase(new_list)
                        elif new_companion:
                             st.warning(f"旅伴 '{new_companion}' 已存在於清單中。")
                        else:
                            st.warning("請輸入旅伴暱稱。")
                
                with col_clear:
                    if st.button("🗑️ 清空旅伴清單", key="clear_comp_btn"):
                        # 清空列表到 []
                        if current_companions:
                            update_companions_in_firebase([])
                        else:
                             st.info("旅伴清單目前已清空。")
            
        with tabs[1]: # 🗺️ 行程 頁面 (Placeholder)
            st.header("行程細節")
            st.info("此處將用於展示每日行程清單與地圖。")

        with tabs[2]: # ☀️ 天氣 頁面 (Placeholder)
            st.header("首爾即時天氣")
            st.info("可規劃在此處展示即時天氣或氣溫預報圖。")

        with tabs[3]: # 💰 記帳 頁面 (Placeholder)
            st.header("協作記帳本")
            st.warning("💡 記帳功能將在下一步利用 Firebase 的寫入功能實現持久化。")
            if current_companions:
                st.subheader("旅伴分攤參考")
                # 此處直接使用從 Firebase 讀取的 current_companions
                st.write(f"可分攤的旅伴: {', '.join(current_companions)}")
            else:
                 st.subheader("旅伴分攤參考")
                 st.info("請先在「資訊」頁面新增旅伴才能進行分攤記帳。")
                
        with tabs[4]: # 💬 助手 頁面 (Placeholder)
            st.header("即時翻譯與助手")
            st.info("未來可整合 Gemini API，實現即時翻譯或旅遊問題問答。")

# --- 無法連線的提示 ---
if not db:
    st.markdown("## ❌ 系統初始化失敗")
    st.error("無法連線到您的 Firebase 資料庫。請檢查您的連線設定。")
