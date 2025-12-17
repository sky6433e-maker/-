import streamlit as st
import pandas as pd
import requests
import urllib3
import numpy as np
from io import BytesIO

# --- 忽略 SSL 警告 ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 設定網頁標題 ---
st.set_page_config(page_title="蔬菜行情分析", page_icon="🥗", layout="wide")
st.title("🥗 蔬菜批發市場行情分析")
st.write("資料來源：農業部開放資料平台 (官方 API)")

# --- 蔬菜代碼字典 ---
vegetable_map = {
    "🎃 南瓜-木瓜形 (FT1)": "FT1",
    "🎃 南瓜-圓形 (FT2)": "FT2",
    "🎃 南瓜-黃如意 (FT3)": "FT3",
    "🎃 南瓜-觀賞用 (FT4)": "FT4",
    "🎃 南瓜-青如意 (FT5)": "FT5",
    "🎃 南瓜-東昇 (FT6)": "FT6",
    "🎃 南瓜-栗子 (FT7)": "FT7",
    "🎃 南瓜-其他 (FT0)": "FT0",
    "🥬 甘藍-高麗菜 (LA1)": "LA1",
    "🥬 小白菜 (LC1)": "LC1",
    "🥬 青江白菜 (LD1)": "LD1",
    "🥬 菠菜 (LH1)": "LH1",
    "🥦 花椰菜 (FB1)": "FB1",
    "🥒 胡瓜-大黃瓜 (FC1)": "FC1",
    "🥒 花胡瓜-小黃瓜 (FC2)": "FC2",
    "🍆 茄子 (FI1)": "FI1",
    "🍅 番茄 (FJ1)": "FJ1",
    "🌽 甜玉米 (FK4)": "FK4",
    "🥕 胡蘿蔔 (SG1)": "SG1",
}

# --- 側邊欄：使用者輸入區 ---
st.sidebar.header("🔎 查詢設定")

# 1. 品種選擇
selected_veg_name = st.sidebar.selectbox(
    "選擇作物",
    options=list(vegetable_map.keys()),
    index=0 
)
target_crop_code = vegetable_map[selected_veg_name]

# 2. 日期選擇器
start_date = st.sidebar.date_input("開始日期")
end_date = st.sidebar.date_input("結束日期")

# 3. 市場選擇
# 【修正】：加入各種可能的桃園名稱，讓使用者可以多選嘗試
market_options = [
    "台北一", "台北二", "板橋區", "三重區", "宜蘭市", 
    "桃園區", "桃農", "新竹市", "台中市", "豐原區", 
    "南投市", "西螺鎮", "嘉義市", "高雄市", "鳳山區", 
    "屏東市", "花蓮市", "台東市"
]

selected_markets = st.sidebar.multiselect(
    "選擇市場 (建議勾選桃園區/桃農)",
    options=market_options,
    default=["台北一", "台北二", "桃園區"]
)

# 4. 價格指標
price_type_mapping = {
    "平均價(元/公斤)": "平均價",
    "上價(元/公斤)": "上價",
    "中價(元/公斤)": "中價",
    "下價(元/公斤)": "下價"
}
selected_price_label = st.sidebar.radio("選擇指標", list(price_type_mapping.keys()), index=0)
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
if st.sidebar.button("🚀 查詢"):
    if not selected_markets:
        st.error("請至少選擇一個市場！")
    else:
        roc_start = to_roc_date_str(start_date)
        roc_end = to_roc_date_str(end_date)
        
        st.info(f"正在查詢【{selected_veg_name}】...")
        
        api_url = "https://data.moa.gov.tw/Service/OpenData/FromM/FarmTransData.aspx"
        params = {
            "CropCode": target_crop_code,
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
                        # --- 關鍵修正：先顯示所有抓到的市場名稱 ---
                        # 這樣你就能看到桃園到底是叫「桃園區」還是「桃農」
                        unique_markets = df['市場名稱'].unique().tolist()
                        
                        st.warning(f"📢 系統在 API 資料中發現這些市場：{unique_markets}")
                        
                        # 自動比對：如果有抓到資料，但被篩選掉了，提示使用者
                        missed_markets = [m for m in unique_markets if m not in selected_markets]
                        if missed_markets:
                            st.caption(f"💡 還有這些市場有資料，但您沒勾選：{missed_markets}")

                        # 1. 篩選市場
                        df = df[df['市場名稱'].isin(selected_markets)]
                        
                        # 2. 處理數值與日期
                        for col in ['上價', '中價', '下價', '平均價']:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors='coerce')
                                df[col] = df[col].replace(0, np.nan)

                        df['西元日期'] = df['交易日期'].apply(convert_roc_to_ad_datetime)
                        df = df.dropna(subset=['西元日期'])
                        
                        if not df.empty:
                            # 繪圖
                            clean_name = selected_veg_name.split(' ')[1] 
                            st.subheader(f"📊 {clean_name} - {target_col}走勢")
                            
                            chart_data = df.pivot_table(index='西元日期', columns='市場名稱', values=target_col)
                            st.line_chart(chart_data)

                            # 表格
                            st.dataframe(df.sort_values(by=['西元日期', '市場名稱'], ascending=[False, True]))
                            
                            # 下載
                            output = BytesIO()
                            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                                df.to_excel(writer, index=False, sheet_name='行情')
                            output.seek(0)
                            
                            file_name = f"{target_crop_code}_{clean_name}.xlsx"
                            st.download_button("📥 下載 Excel", data=output, file_name=file_name)
                        else:
                            st.error(f"篩選後沒有資料。請看上方黃色文字，確認「桃園」在資料庫裡的名字是什麼？")
                    else:
                        st.error("API 回傳格式異常。")
                else:
                    st.warning("查無資料 (API 回傳空值)。")
            else:
                st.error(f"連線失敗：{response.status_code}")
                
        except Exception as e:
            st.error(f"錯誤：{str(e)}")
