import streamlit as st
import pandas as pd
import requests
import urllib3
import numpy as np # 新增：用來處理「空值」的數學套件
from io import BytesIO

# --- 忽略 SSL 警告 ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 設定網頁標題 ---
st.set_page_config(page_title="南瓜行情趨勢圖", page_icon="📈", layout="wide")
st.title("📈 南瓜 (FT1) 行情趨勢分析")
st.write("資料來源：農業部開放資料平台 (官方 API)")

# --- 側邊欄：使用者輸入區 ---
st.sidebar.header("🔎 查詢設定")

# 1. 日期選擇器
start_date = st.sidebar.date_input("開始日期")
end_date = st.sidebar.date_input("結束日期")

# 2. 市場選擇
market_options = [
    "台北一", "台北二", "板橋區", "三重區", "宜蘭市", 
    "桃園區", "台中市", "豐原區", "南投市", "嘉義市", 
    "高雄市", "鳳山區", "屏東市", "花蓮市", "台東市"
]

selected_markets = st.sidebar.multiselect(
    "選擇市場 (可多選比價)",
    options=market_options,
    default=["台北一", "台北二", "台中市", "高雄市"]
)

# 3. 價格指標選擇
price_type_mapping = {
    "Avg_Price(number):平均價(元/公斤)": "平均價",
    "Upper_Price(number):上價(元/公斤)": "上價",
    "Middle_Price(number):中價(元/公斤)": "中價",
    "Lower_Price(number):下價(元/公斤)": "下價"
}

selected_price_label = st.sidebar.radio(
    "選擇價格指標",
    options=list(price_type_mapping.keys()),
    index=0
)

target_col = price_type_mapping[selected_price_label]

# --- 輔助函式 ---
def to_roc_date_str(date_obj):
    roc_year = date_obj.year - 1911
    return f"{roc_year}.{date_obj.month:02d}.{date_obj.day:02d}"

def convert_roc_to_ad_datetime(roc_date_str):
    try:
        parts = roc_date_str.split('.')
        year = int(parts[0]) + 1911
        month = int(parts[1])
        day = int(parts[2])
        return pd.Timestamp(year=year, month=month, day=day)
    except:
        return None

# --- 主程式邏輯 ---
if st.sidebar.button("🚀 開始查詢與繪圖"):
    if not selected_markets:
        st.error("請至少選擇一個市場！")
    else:
        roc_start = to_roc_date_str(start_date)
        roc_end = to_roc_date_str(end_date)
        
        st.info(f"正在查詢：{roc_start} 至 {roc_end}，指標：{target_col}...")
        
        api_url = "https://data.moa.gov.tw/Service/OpenData/FromM/FarmTransData.aspx"
        params = {
            "CropCode": "FT1",
            "StartDate": roc_start,
            "EndDate": roc_end,
            "$top": "5000"
        }
        
        try:
            response = requests.get(api_url, params=params, verify=False)
            
            if response.status_code == 200:
                data_json = response.json()
                
                if len(data_json) > 0:
                    df = pd.DataFrame(data_json)
                    
                    if '市場名稱' in df.columns:
                        # 1. 篩選市場
                        df = df[df['市場名稱'].isin(selected_markets)]
                        
                        # 2. 轉數字並「處理 0 的問題」
                        price_cols = ['上價', '中價', '下價', '平均價']
                        for col in price_cols:
                            if col in df.columns:
                                # 先強制轉成數字 (非數字變 NaN)
                                df[col] = pd.to_numeric(df[col], errors='coerce')
                                
                                # 【關鍵修改】把 0 變成 NaN (空值)
                                # 這樣畫圖時線條就會斷開，而不是掉到 0
                                df[col] = df[col].replace(0, np.nan)

                        # 3. 轉日期
                        df['西元日期'] = df['交易日期'].apply(convert_roc_to_ad_datetime)
                        df = df.dropna(subset=['西元日期'])
                        
                        if not df.empty:
                            # --- A. 繪圖 ---
                            st.subheader(f"📊 各市場「{target_col}」走勢圖")
                            st.caption("註：線條中斷處代表該日休市或無交易 (價格為 0)")
                            
                            chart_data = df.pivot_table(
                                index='西元日期', 
                                columns='市場名稱', 
                                values=target_col
                            )
                            # Streamlit 的 line_chart 遇到 NaN 會自動斷開
                            st.line_chart(chart_data)

                            # --- B. 顯示表格 ---
                            st.subheader("📋 詳細數據表")
                            
                            # 排序
                            df_sorted = df.sort_values(by=['西元日期', '市場名稱'], ascending=[False, True])
                            
                            # 表格顯示處理：為了美觀，可以把 NaN 再轉回空字串或保留 NaN
                            display_cols = ['交易日期', '市場名稱', '作物名稱', '上價', '中價', '下價', '平均價', '交易量']
                            final_df = df_sorted[display_cols]
                            
                            st.dataframe(final_df)
                            
                            # --- C. 下載 Excel ---
                            output = BytesIO()
                            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                                final_df.to_excel(writer, index=False, sheet_name='南瓜行情')
                            output.seek(0)
                            
                            file_name = f"FT1南瓜_{roc_start.replace('.','')}-{roc_end.replace('.','')}.xlsx"
                            st.download_button("📥 下載 Excel", data=output, file_name=file_name)
                            
                        else:
                            st.warning(f"篩選後的資料為空。")
                    else:
                        st.error("API 回傳格式異常。")
                else:
                    st.warning("查無資料。")
            else:
                st.error(f"連線失敗，代碼：{response.status_code}")
                
        except Exception as e:
            st.error(f"發生錯誤：{str(e)}")