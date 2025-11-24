import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import time
import os
import requests 

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
            # 這是標準的Streamlit Cloud部署環境，若檔案不存在會報錯
            # 但在這裡我們假設部署者會確保檔案存在
            return None

        # 2. 檢查是否已初始化，避免重複初始化錯誤
        if not firebase_admin._apps:
            # 3. 從檔案路徑讀取憑證
            cred = credentials.Certificate(key_file_path)
            firebase_admin.initialize_app(cred)
            
        # 4. 連線到 Firestore 資料庫
        return firestore.client()
        
    # 如果運行環境沒有 service account file，則會捕獲異常
    except Exception as e:
        # st.error(f"❌ Firebase 連線失敗 (檔案模式)。請檢查 '{key_file_path}' 檔案內容是否完整無損：{e}")
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
            # st.success("✅ 資料已成功從 Firebase 讀取！") # 避免過多成功提示
            return data
        else:
            return None
    except Exception as e:
        st.error(f"❌ 讀取資料失敗：{e}")
        return None

# --- 記帳資料讀取/監聽函式 (新增) ---
def get_all_expenses(db):
    """從 Firestore 實時監聽 expense_records 集合"""
    if not db:
        return []
        
    if 'expense_data' not in st.session_state:
        st.session_state.expense_data = []

    try:
        # 讀取集合中的所有文件，按日期降序排列
        docs = db.collection('expense_records').order_by('date', direction=firestore.Query.DESCENDING).get()
        
        expense_list = []
        for doc in docs:
            # 將 Firestore Document ID 加入數據中，以便後續刪除或追蹤
            record = doc.to_dict()
            record['id'] = doc.id 
            expense_list.append(record)
        
        st.session_state.expense_data = expense_list
        return expense_list

    except Exception as e:
        st.error(f"❌ 讀取記帳記錄失敗：{e}")
        return []

# --- 記帳資料寫入函式 ---
def add_expense_record(db, record_data):
    """將新的記帳記錄寫入 Firestore 的 expense_records 集合中"""
    if not db:
        st.error("❌ 無法寫入記帳記錄：Firebase 連線失敗。")
        return False
    try:
        # 使用 addDoc 寫入新的文件到 'expense_records' 集合
        db.collection('expense_records').add(record_data)
        st.success("✅ 記帳記錄已成功儲存！")
        return True
    except Exception as e:
        st.error(f"❌ 記帳記錄寫入失敗：{e}")
        return False

# --- 行程資料操作函式 (修正：移除 order_by 以繞過複合索引限制) ---
def get_daily_itinerary(db, date_str):
    """
    從 Firestore 讀取特定日期的行程記錄。
    [重要修正]: 移除 order_by('time')，改在 Python 記憶體中排序，
    以避免因缺少複合索引而導致的 400 錯誤。
    """
    if not db:
        return []
    try:
        # 僅使用 where 篩選日期 (只需要單一索引)
        docs = db.collection('daily_itineraries').where('date', '==', date_str).get()
        itinerary = []
        for doc in docs:
            record = doc.to_dict()
            record['id'] = doc.id
            itinerary.append(record)
            
        # 透過 Python 進行記憶體內排序 (確保依時間排序)
        # 使用 lambda 函數來指定按 'time' 欄位排序
        itinerary.sort(key=lambda x: x.get('time', '23:59')) 
        
        return itinerary
    except Exception as e:
        # 這裡會捕獲錯誤，但如果索引問題已修正，就不會進入這個區塊
        st.error(f"❌ 讀取 {date_str} 行程失敗: {e}")
        return []

def add_itinerary_record(db, record_data):
    """將新的行程記錄寫入 Firestore 的 daily_itineraries 集合中"""
    if not db:
        st.error("❌ 無法寫入行程記錄：Firebase 連線失敗。")
        return False
    try:
        db.collection('daily_itineraries').add(record_data)
        st.success("✅ 行程記錄已成功儲存！")
        return True
    except Exception as e:
        st.error(f"❌ 行程記錄寫入失敗：{e}")
        return False

def delete_itinerary_record(db, doc_id):
    """從 Firestore 刪除特定的行程記錄"""
    if not db:
        st.error("❌ 無法刪除行程記錄：Firebase 連線失敗。")
        return False
    try:
        db.collection('daily_itineraries').document(doc_id).delete()
        st.success("✅ 行程記錄已成功刪除！")
        return True
    except Exception as e:
        st.error(f"❌ 行程記錄刪除失敗：{e}")
        return False

# --- 核心計算引擎 (Settlement Engine) ---
def calculate_settlement(companions, expenses):
    """
    遍歷所有消費記錄，計算每個旅伴的總支付金額、總分攤金額和淨餘額。
    """
    # 初始化結算摘要
    settlement_summary = {comp: {'paid': 0.0, 'owed': 0.0, 'net': 0.0} for comp in companions}
    total_paid_all = 0.0
    
    for expense in expenses:
        payer = expense.get('payer')
        amount = expense.get('amount', 0.0)
        
        if payer in settlement_summary:
            settlement_summary[payer]['paid'] += amount
            total_paid_all += amount
            
        splits = expense.get('splits', [])
        split_count = len(splits)
        
        if split_count > 0:
            share_per_person = amount / split_count
            
            for comp in splits:
                if comp in settlement_summary:
                    settlement_summary[comp]['owed'] += share_per_person
    
    # 3. 計算淨餘額 (Net Balance)
    for comp in companions:
        summary = settlement_summary[comp]
        # 淨餘額 = 已付 - 應付
        summary['net'] = summary['paid'] - summary['owed']
        
        # 四捨五入到小數點第二位，避免浮點數誤差
        summary['paid'] = round(summary['paid'], 2)
        summary['owed'] = round(summary['owed'], 2)
        summary['net'] = round(summary['net'], 2)
        
    return total_paid_all, settlement_summary

# --- 匯率計算框架 (需呼叫外部 API 實作) ---
@st.cache_data(ttl=3600) # 快取 1 小時
def get_exchange_rate(from_currency, to_currency):
    """
    [待辦事項] 呼叫外部 API 獲取即時匯率。
    目前使用固定值作為演示。
    """
    if from_currency == "TWD" and to_currency == "KRW":
        # 假設 1 TWD = 40 KRW (用於演示)
        return 40.0
    elif from_currency == "KRW" and to_currency == "TWD":
        # 假設 1 KRW = 0.025 TWD (用於演示)
        return 0.025
    else:
        # 為了避免 API 金鑰問題，目前先固定回傳值
        return 1.0
        
# --- 新增: 計算行程日期範圍的函式 ---
def calculate_trip_dates(flights):
    """
    根據航班資料計算整個旅程的日期範圍。
    Args:
        flights (list): 航班記錄清單，每個項目包含 'date' 欄位 (e.g., "2025-06-15")。
    Returns:
        list: 包含旅程所有日期的字串列表 (e.g., ["2025-06-15", "2025-06-16", ...])。
    """
    if not flights:
        return [datetime.now().strftime("%Y-%m-%d")] # 預設今天

    # 1. 提取所有有效的日期
    date_strings = []
    for flight in flights:
        date_str = flight.get('date')
        if date_str:
            try:
                date_strings.append(date_str)
            except Exception:
                continue

    if not date_strings:
        return [datetime.now().strftime("%Y-%m-%d")]

    # 2. 將日期字串轉換為 datetime 物件
    dates = []
    for ds in date_strings:
        try:
            dates.append(datetime.strptime(ds, "%Y-%m-%d").date())
        except ValueError:
            # 處理可能存在的日期格式錯誤
            continue
            
    if not dates:
        return [datetime.now().strftime("%Y-%m-%d")]
        
    # 3. 找出最早和最晚的日期
    start_date = min(dates)
    end_date = max(dates)

    # 4. 生成從開始到結束日期的所有日期列表
    trip_dates = []
    current_date = start_date
    while current_date <= end_date:
        trip_dates.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)
        
    return trip_dates


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
        current_flights = trip_data.get('flights', []) # 新增: 獲取航班資訊
        
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

        # [START_TAB_0]
        with tabs[0]: # 📄 資訊 頁面 (使用 Firestore 資料)
            st.header("資訊總覽")
            
            # --- 航班資訊卡片 (整合編輯與顯示) ---
            flight_types = ["去程 (Outbound)", "回程 (Return)", "轉機 (Layover)"]
            

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
                            # 設置為 text_input 方便使用者輸入 "YYYY-MM-DD" 格式
                            flight['date'] = st.text_input("日期 (YYYY-MM-DD)", value=flight.get("date", ""), key=f"date_{i}")
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
                
                # 輸入欄位的 key 是 "new_comp"
                new_companion = st.text_input("新增旅伴暱稱", key="new_comp")
                
                col_add, col_clear = st.columns(2)
                
                with col_add:
                    if st.button("➕ 新增旅伴", key="add_comp_btn"):
                        # 檢查：非空且不在現有清單中
                        if new_companion and new_companion not in current_companions:
                            new_list = current_companions + [new_companion]
                            # 新增邏輯：成功寫入前，將 session_state 設為空字串以清除輸入欄位
                            st.session_state.new_comp = "" 
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
        # [END_TAB_0]
        
        with tabs[1]: # 🗺️ 行程 頁面 (核心重構)
            st.header("每日行程細節")
            
            # --- 1. 計算日期範圍並設定 Session State ---
            trip_dates = calculate_trip_dates(current_flights)
            
            if not trip_dates:
                st.warning("請先在「資訊」頁面的航班資訊中設定去程及回程日期 (YYYY-MM-DD)，系統才能產生行程日期範圍。")
                # 預設今天日期作為唯一選項
                default_date = datetime.now().strftime("%Y-%m-%d")
                trip_dates.append(default_date)
            else:
                default_date = trip_dates[0]
            
            if 'selected_itinerary_date' not in st.session_state:
                st.session_state.selected_itinerary_date = default_date

            # --- 2. 日期選擇介面 (模擬滑動/點擊) ---
            st.markdown("### 📅 選擇日期")
            
            # 找到當前選中日期的索引
            try:
                current_index = trip_dates.index(st.session_state.selected_itinerary_date)
            except ValueError:
                current_index = 0
                st.session_state.selected_itinerary_date = trip_dates[0] # 重設為有效日期
                
            col_prev, col_date_picker, col_next = st.columns([1, 4, 1])

            with col_prev:
                if current_index > 0 and st.button("⬅️ 前一天", key="prev_day_btn"):
                    st.session_state.selected_itinerary_date = trip_dates[current_index - 1]
                    st.rerun()

            with col_date_picker:
                # 使用 selectbox 作為主要的日期導航
                st.session_state.selected_itinerary_date = st.selectbox(
                    "選擇行程日期",
                    options=trip_dates,
                    index=current_index,
                    key="date_selector",
                    label_visibility="collapsed"
                )
                
            with col_next:
                if current_index < len(trip_dates) - 1 and st.button("後一天 ➡️", key="next_day_btn"):
                    st.session_state.selected_itinerary_date = trip_dates[current_index + 1]
                    st.rerun()

            selected_date = st.session_state.selected_itinerary_date
            st.markdown(f"### {selected_date} 行程")
            st.markdown("---")

            # --- 3. 讀取並顯示當日行程 ---
            # 由於 get_daily_itinerary 已修正為記憶體內排序，這裡可以直接使用結果
            daily_itinerary = get_daily_itinerary(db, selected_date)
            
            if not daily_itinerary:
                st.info("當日行程尚無記錄。請使用下方表單新增行程。")
            else:
                # 顯示行程清單
                for item in daily_itinerary:
                    
                    # 構造 Google Maps 連結，用於點擊展開
                    # URL 編碼地址，確保在 URL 中安全傳輸
                    address_encoded = requests.utils.quote(item.get('address', ''))
                    map_link = f"https://www.google.com/maps/search/?api=1&query={address_encoded}"
                    
                    with st.container(border=True):
                        col_time, col_details, col_action = st.columns([1, 4, 1])

                        with col_time:
                            st.markdown(f"## **{item.get('time', 'N/A')}**")
                            
                        with col_details:
                            st.markdown(f"#### **{item.get('location_name', '未知地點')}**")
                            # 點擊地址即可開啟 Google Map
                            st.markdown(f"""
                                <a href="{map_link}" target="_blank" style="text-decoration: none; color: #1E40AF; font-weight: bold;">
                                    📍 {item.get('address', 'N/A')}
                                </a>
                            """, unsafe_allow_html=True)
                            st.markdown(f"📞 {item.get('phone', 'N/A')}")
                            st.markdown(f"*{item.get('notes', '')}*")
                            
                        with col_action:
                            st.markdown("<br>", unsafe_allow_html=True)
                            # 刪除按鈕
                            if st.button("🗑️ 刪除", key=f"del_{item['id']}"):
                                delete_itinerary_record(db, item['id'])
                                st.rerun()

            st.markdown("---")

            # --- 4. 新增行程表單 ---
            st.markdown("### ➕ 新增行程項目")
            with st.form(key="add_itinerary_form"):
                
                col1, col2 = st.columns(2)
                
                with col1:
                    location_name = st.text_input("地名/活動名稱", key="it_name")
                    time_str = st.text_input("時間 (HH:MM)", placeholder="例如: 09:30 或 20:00", key="it_time")
                    address = st.text_input("地址", placeholder="準確的地址，有利於地圖連結", key="it_addr")
                
                with col2:
                    phone = st.text_input("電話號碼", key="it_phone")
                    category = st.selectbox("分類", options=["景點", "餐飲", "交通", "購物", "住宿", "其他"], key="it_category")
                    notes = st.text_area("備註", key="it_notes")
                
                submitted = st.form_submit_button("✅ 儲存這筆行程")
                
                if submitted:
                    # 簡單的時間格式驗證 (確保能排序)
                    if not time_str or not location_name or not address:
                        st.error("地名、時間和地址為必填欄位。")
                    else:
                        try:
                            # 嘗試將時間轉換為 datetime.time 進行排序驗證
                            datetime.strptime(time_str, "%H:%M") 
                            
                            record = {
                                "date": selected_date,
                                "time": time_str, # 格式 HH:MM
                                "location_name": location_name.strip(),
                                "address": address.strip(),
                                "phone": phone.strip(),
                                "category": category,
                                "notes": notes.strip(),
                                "timestamp": firestore.SERVER_TIMESTAMP 
                            }
                            
                            if add_itinerary_record(db, record):
                                st.rerun()
                        except ValueError:
                            st.error("時間格式錯誤。請使用 HH:MM (例如 09:30) 格式。")

        with tabs[2]: # ☀️ 天氣 頁面 (Placeholder)
            st.header("首爾即時天氣")
            st.info("可規劃在此處展示即時天氣或氣溫預報圖。")

        with tabs[3]: # 💰 記帳 頁面 (核心功能重構)
            st.header("協作記帳本")
            
            # --- 0. 讀取所有記帳記錄 ---
            expense_records = get_all_expenses(db)
            
            # --- 1. 簡易匯率計算機 ---
            st.markdown("### 💱 簡易匯率換算 (KRW/TWD)")
            
            col_from_currency, col_from_amount, col_equal, col_to_currency, col_to_amount = st.columns([1, 2, 0.5, 1, 2])
            
            with col_from_currency:
                from_currency = st.selectbox("從", options=["KRW", "TWD", "USD"], index=0, key="from_cur")
            with col_from_amount:
                from_amount = st.number_input("金額", min_value=0.0, value=10000.0, step=100.0, key="from_amt")
            with col_equal:
                st.markdown("### =")
            with col_to_currency:
                to_currency = st.selectbox("換算為", options=["TWD", "KRW", "USD"], index=0, key="to_cur")

            # 獲取匯率並計算結果
            rate = get_exchange_rate(from_currency, to_currency)
            to_amount = from_amount * rate
            
            with col_to_amount:
                st.text_input("約為", value=f"{to_amount:,.2f}", disabled=True, key="to_amt_display")
            
            st.info(f"當前匯率: 1 {from_currency} 約等於 {rate:.4f} {to_currency} (目前為固定演示值)。")
            st.markdown("---")
            
            # --- 2. 記帳輸入表單 ---
            st.markdown("### 📝 新增一筆消費記錄")
            
            if not current_companions:
                st.warning("請先在「資訊」頁面新增旅伴暱稱，才能進行記帳與分攤設定。")
            else:
                with st.form(key="expense_form"):
                    # 基本資訊
                    expense_name = st.text_input("消費項目", placeholder="例如：晚餐、計程車、景點門票", key="exp_name")
                    
                    col_date, col_category = st.columns(2)
                    with col_date:
                        expense_date = st.date_input("消費日期", value="today", key="exp_date")
                    with col_category:
                        categories = ["餐飲", "交通", "住宿", "門票/活動", "購物", "其他"]
                        expense_category = st.selectbox("分類", options=categories, key="exp_category")

                    col_amount, col_currency = st.columns(2)
                    with col_amount:
                        # 設定 min_value=1.0，避免輸入零或負數
                        expense_amount = st.number_input("金額", min_value=1.0, value=10000.0, step=100.0, format="%.2f", key="exp_amount")
                    with col_currency:
                        # 為了簡化結算邏輯，強制選擇 KRW
                        expense_currency = st.selectbox("幣別 (目前結算僅支持 KRW)", options=["KRW", "TWD", "USD"], index=0, key="exp_currency")

                    st.markdown("#### 誰先付的 (Payer)?")
                    # 使用 radio button 確保只有一位付費者
                    payer = st.radio(
                        "選擇付費者",
                        options=current_companions,
                        index=0, 
                        key="exp_payer",
                        horizontal=True
                    )

                    st.markdown("#### 有誰要分攤這筆金額 (Splits)?")
                    # 使用 multiselect 選擇所有分攤者 (預設全選)
                    split_companions = st.multiselect(
                        "選擇分攤者",
                        options=current_companions,
                        default=current_companions,
                        key="exp_splits"
                    )

                    submitted = st.form_submit_button("✅ 儲存這筆帳目")

                    if submitted:
                        if not expense_name.strip():
                            st.error("請輸入消費項目名稱。")
                        elif not split_companions:
                            st.error("請至少選擇一位分攤者。")
                        else:
                            # 構建新的記帳記錄
                            record = {
                                "name": expense_name.strip(),
                                "date": expense_date.strftime("%Y-%m-%d"),
                                "category": expense_category,
                                "amount": expense_amount,
                                "currency": expense_currency,
                                "payer": payer,
                                "splits": split_companions,
                                "split_count": len(split_companions),
                                # 計算每人分攤金額，並四捨五入到小數點第二位
                                "per_person_share": round(expense_amount / len(split_companions), 2), 
                                "timestamp": firestore.SERVER_TIMESTAMP 
                            }
                            
                            # 寫入 Firestore
                            if add_expense_record(db, record):
                                # 寫入成功後強制重新整理，確保數據立即更新
                                st.rerun()
            
            st.markdown("---")
            
            # --- 3. 結算概況 (根據圖片需求實作) ---
            st.markdown("### 📊 結算概況 (幣別：KRW)")
            
            if not expense_records:
                st.info("目前尚無消費記錄可供結算。")
            else:
                total_paid_all, settlement_summary = calculate_settlement(current_companions, expense_records)
                
                # 總支出標籤
                st.metric("總支出", f"{total_paid_all:,.2f} KRW", delta_color="off")
                
                # 顯示每個旅伴的結算卡片
                for companion, summary in settlement_summary.items():
                    net_balance = summary['net']
                    
                    # 決定卡片樣式：應收 (綠) 或 應付 (紅)
                    if net_balance > 0:
                        # 應收 (Paid > Owed)
                        status_label = "收回"
                        status_amount = f"+{net_balance:,.0f} KRW"
                        color_class = "green"
                    elif net_balance < 0:
                        # 應付 (Paid < Owed)
                        status_label = "支付"
                        status_amount = f"{abs(net_balance):,.0f} KRW"
                        color_class = "red"
                    else:
                        # 平衡
                        status_label = "平衡"
                        status_amount = "0 KRW"
                        color_class = "blue"

                    # 為了在 Streamlit 中實現樣式，我們使用 HTML + CSS
                    st.markdown(f"""
                        <div style="
                            padding: 15px; 
                            margin-bottom: 10px; 
                            border: 1px solid #ddd; 
                            border-left: 5px solid {'#10B981' if color_class == 'green' else '#EF4444' if color_class == 'red' else '#3B82F6'}; 
                            border-radius: 8px;
                            display: flex;
                            align-items: center;
                        ">
                            <span style="
                                font-size: 24px; 
                                font-weight: bold; 
                                color: white; 
                                background-color: {'#10B981' if color_class == 'green' else '#60A5FA'}; 
                                border-radius: 50%; 
                                width: 40px; 
                                height: 40px; 
                                display: flex; 
                                justify-content: center; 
                                align-items: center; 
                                margin-right: 15px;
                            ">{companion[0]}</span>
                            <div style="flex-grow: 1;">
                                <h4 style="margin: 0; color: #333;">{companion}</h4>
                                <div style="display: flex; gap: 20px; font-size: 14px; margin-top: 5px;">
                                    <span>**已付:** {summary['paid']:,.0f} KRW</span>
                                    <span>**應付:** {summary['owed']:,.0f} KRW</span>
                                </div>
                            </div>
                            <div style="
                                text-align: right; 
                                padding: 8px 15px; 
                                border-radius: 5px; 
                                background-color: {'#D1FAE5' if color_class == 'green' else '#FEE2E2' if color_class == 'red' else '#EFF6FF'};
                                color: {'#065F46' if color_class == 'green' else '#991B1B' if color_class == 'red' else '#1E40AF'};
                                font-weight: bold;
                                min-width: 120px;
                            ">
                                {status_label}
                                <div style="font-size: 18px; margin-top: 2px;">{status_amount}</div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)


            st.markdown("<br>", unsafe_allow_html=True)
            # --- 4. 流水帳 (根據圖片需求實作) ---
            st.markdown("### 📜 最近記錄 (流水帳)")
            
            if not expense_records:
                st.info("尚無消費記錄。")
            else:
                for record in expense_records:
                    split_count = len(record.get('splits', []))
                    
                    # 顏色條用於視覺分隔
                    st.markdown(f"""
                        <div style="
                            padding: 10px 15px; 
                            margin-bottom: 8px; 
                            border-radius: 5px; 
                            background-color: #F9FAFB;
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                            border: 1px solid #EDEDED;
                        ">
                            <div style="flex-grow: 1;">
                                <h5 style="margin: 0 0 4px 0; color: #1F2937;">{record.get('name', '未知項目')}</h5>
                                <p style="margin: 0; font-size: 12px; color: #6B7280;">
                                    {record.get('payer', 'N/A')} 先付 • 分給 {split_count} 人
                                </p>
                            </div>
                            <div style="text-align: right;">
                                <h5 style="margin: 0; color: #1F2937;">
                                    {record.get('amount', 0):,.0f} {record.get('currency', 'KRW')}
                                </h5>
                                <p style="margin: 0; font-size: 12px; color: #9CA3AF;">
                                    {record.get('date', 'N/A')}
                                </p>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

        with tabs[4]: # 💬 助手 頁面 (Placeholder)
            st.header("即時翻譯與助手")
            st.info("未來可整合 Gemini API，實現即時翻譯或旅遊問題問答。")

# --- 無法連線的提示 ---
if not db:
    st.markdown("## ❌ 系統初始化失敗")
    st.error("無法連線到您的 Firebase 資料庫。請檢查您的連線設定。")
