import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# --- 核心數據 (已修正為首爾行程) ---
FLIGHT_INFO = {
    "去程": "11/27 (週一) TPE (桃園) -> GMP (金浦)",
    "回程": "12/01 (週五) GMP (金浦) -> TPE (桃園)",
    "航班代碼": "BR XXX / KE YYY",
}
HOTEL_INFO = "樂天酒店 (Lotte Hotel Seoul)"
TRIP_DAYS = (datetime(2025, 11, 27) - datetime.now()).days
CURRENCY_CODE = "KRW"

sst.set_page_config(
    layout="wide", 
    page_title="🇰🇷 首爾行動指揮中心", 
    page_icon="[https://drive.google.com/file/d/1E_lZCsdpqHNWbPzJW77GzYaJNaCdRfhh/view?usp=sharing]" # <--- 這裡是要修改的部分
)

# --- 介面呈現 ---
st.title("🇰🇷 首爾行動指揮中心")
st.markdown(f"### 倒數計時：距離出發還有 **{TRIP_DAYS}** 天！")

# --- 行程總覽 (Logistic) ---
st.header("✈️ 航班與住宿資訊")
col1, col2 = st.columns(2)

with col1:
    st.subheader("🛫 航班資訊")
    st.markdown(f"**去程:** {FLIGHT_INFO['去程']}")
    st.markdown(f"**回程:** {FLIGHT_INFO['回程']}")
    st.markdown(f"**訂位代碼:** {FLIGHT_INFO['航班代碼']}")

with col2:
    st.subheader("🏨 住宿資訊")
    st.markdown(f"**飯店:** {HOTEL_INFO}")
    st.markdown("**地址:** Jung-gu, Eulji-ro 30, Seoul")
    st.markdown("**入住/退房:** 15:00 / 11:00")

st.markdown("---")

# --- 簡易匯率計算 (Currency Exchange) ---
st.header("💰 韓元匯率快速換算")
st.caption("基於簡化原則，採用固定匯率，不進行即時 API 連線，確保穩定。")

# 設定簡化匯率 (假設 1 NTD = 42 KRW, 1000 KRW = 23.8 NTD)
EXCHANGE_RATE = 42
REVERSE_RATE = 1 / EXCHANGE_RATE

col3, col4 = st.columns(2)

with col3:
    ntd_amount = st.number_input("輸入台幣金額 (NTD)", min_value=0, value=1000)
    krw_estimated = ntd_amount * EXCHANGE_RATE
    st.success(f"約等於 **{int(krw_estimated):,} 韓元** (KRW)")

with col4:
    krw_amount = st.number_input("輸入韓元金額 (KRW)", min_value=0, value=10000)
    ntd_estimated = krw_amount * REVERSE_RATE
    st.info(f"約等於 **{ntd_estimated:.2f} 台幣** (NTD)")

# --- 觀光建議 (Discovery) ---
st.markdown("---")
st.header("🚶‍♀️ 行程建議與備註")
st.subheader("📍 必去清單 (明洞/南大門)")
st.write("* **明洞:** 專攻美妝與街頭小吃，建議晚上 6 點後前往，氣氛最好。")
st.write("* **南大門市場:** 體驗傳統市場氛圍，適合購買人蔘、紀念品，注意議價空間。")

st.subheader("📝 家庭備忘")
st.warning("提醒：青春期男孩可能會抱怨行程太無聊。建議準備 **韓式炸雞** 和 **電競咖啡廳** 作為備案。")
st.info("小女兒的購物行程需限制在一個小時內完成，並準備糖果補給。")
