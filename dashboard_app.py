# dashboard_app.py (最终版 - 支持管理员/用户双角色)
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from itertools import combinations
from collections import Counter
import re
import os

# --- 页面基础设置 ---
st.set_page_config(layout="wide", page_title="交团团经营分析看板")

# --- 应用核心配置 ---
# !!! 请在这里设置您的管理员密码 !!!
ADMIN_PASSWORD = "jtt"  # 您可以修改成更复杂的密码
DATA_DIR = "data"  # 用于在服务器上存储数据文件的文件夹名
ORDERS_FILE_PATH = os.path.join(DATA_DIR, "latest_orders.csv")
PRODUCTS_FILE_PATH = os.path.join(DATA_DIR, "latest_products.csv")

# 确保数据文件夹存在
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# --- 中文字体加载 ---
@st.cache_resource
def load_font():
    try:
        fm.fontManager.addfont('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc')
        plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei']
        plt.rcParams['axes.unicode_minus'] = False
    except Exception:
        plt.rcParams['font.sans-serif'] = ['SimHei', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
load_font()

# --- 管理员上传模块 ---
st.sidebar.title("管理面板")
password = st.sidebar.text_input("请输入管理员密码:", type="password")

if password == ADMIN_PASSWORD:
    st.sidebar.success("密码正确！已解锁管理员功能。")
    st.sidebar.header('上传新数据')
    
    # 允许多文件上传
    uploaded_files = st.sidebar.file_uploader(
        "请同时上传“订单列表”和“商品列表”的CSV文件",
        type="csv",
        accept_multiple_files=True
    )

    if st.sidebar.button("开始处理上传的文件"):
        if len(uploaded_files) != 2:
            st.sidebar.error("请确保您同时上传了两个文件。")
        else:
            with st.spinner('正在智能识别并处理文件...'):
                try:
                    df1 = pd.read_csv(uploaded_files[0])
                    df2 = pd.read_csv(uploaded_files[1])

                    # 智能识别文件类型
                    if '订单金额' in df1.columns and '商品种类数' in df1.columns:
                        orders_df_new = df1
                        products_df_new = df2
                    elif '订单金额' in df2.columns and '商品种类数' in df2.columns:
                        orders_df_new = df2
                        products_df_new = df1
                    else:
                        raise ValueError("上传的文件中无法识别出订单列表和商品列表，请检查文件内容。")
                    
                    # 保存到服务器
                    orders_df_new.to_csv(ORDERS_FILE_PATH, index=False)
                    products_df_new.to_csv(PRODUCTS_FILE_PATH, index=False)
                    
                    # 清理缓存，以便下次加载新数据
                    st.cache_data.clear()
                    st.sidebar.success("数据上传并处理成功！所有访客现在将看到最新数据。")
                except Exception as e:
                    st.sidebar.error(f"处理失败: {e}")

# --- 数据加载与主看板展示 ---
st.title('交团团经营分析看板')

if not (os.path.exists(ORDERS_FILE_PATH) and os.path.exists(PRODUCTS_FILE_PATH)):
    st.warning("系统内暂无数据。请管理员在左侧管理面板输入密码以上传数据。")
else:
    @st.cache_data
    def load_saved_data():
        orders_df = pd.read_csv(ORDERS_FILE_PATH)
        products_df = pd.read_csv(PRODUCTS_FILE_PATH)
        orders_df['支付时间'] = pd.to_datetime(orders_df['支付时间'], errors='coerce')
        orders_df.dropna(subset=['支付时间'], inplace=True)
        return orders_df, products_df

    orders_df, products_df = load_saved_data()

    # --- 侧边栏筛选器 (对所有用户可见) ---
    st.sidebar.title("数据筛选")
    min_date = orders_df['支付时间'].min().date()
    max_date = orders_df['支付时间'].max().date()
    start_date, end_date = st.sidebar.date_input('选择时间范围:', [min_date, max_date], min_value=min_date, max_value=max_date)

    # --- 数据筛选与看板内容 (和之前版本相同) ---
    start_datetime = pd.to_datetime(start_date)
    end_datetime = pd.to_datetime(end_date) + pd.Timedelta(days=1)
    filtered_orders = orders_df[(orders_df['支付时间'] >= start_datetime) & (orders_df['支付时间'] < end_datetime)]
    successful_orders = filtered_orders[filtered_orders['订单状态'].isin(['已收货', '已发货', '已支付'])].copy()
    b2c_orders = successful_orders[~successful_orders['团购标题'].str.contains('走账', na=False)].copy()
    b2c_products = products_df[products_df['订单号'].isin(b2c_orders['订单号'])].copy()

    # 1. 总体经营概览
    st.header('一、总体经营概览')
    unique_b2c_orders = b2c_orders.drop_duplicates(subset=['订单号'])
    gmv = unique_b2c_orders['订单金额'].sum()
    total_orders = unique_b2c_orders['订单号'].nunique()
    total_customers = unique_b2c_orders['下单人'].nunique()
    aov = gmv / total_orders if total_orders > 0 else 0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总销售额 (GMV)", f"¥{gmv:,.2f}"); col2.metric("有效订单总数", f"{total_orders:,}")
    col3.metric("服务客户总数", f"{total_customers:,}"); col4.metric("平均客单价 (AOV)", f"¥{aov:,.2f}")
    if not unique_b2c_orders.empty:
        weekly_sales = unique_b2c_orders.set_index('支付时间')['订单金额'].resample('W-MON').sum()
        fig1, ax1 = plt.subplots(figsize=(12, 5)); weekly_sales.plot(kind='line', marker='o', ax=ax1)
        ax1.set_title('每周销售额 (GMV) 趋势'); ax1.set_xlabel('日期'); ax1.set_ylabel('销售额 (元)')
        ax1.grid(True, linestyle='--', alpha=0.6); st.pyplot(fig1)

    # (后续的品类分析、RFM、关联分析代码与之前版本相同，为简洁省略，实际代码中应完整保留)
    # 2. 核心品类分析
    st.header('二、核心品类分析')
    if not b2c_products.empty:
        category_sales = b2c_products.groupby('分类')['商品金额'].sum().sort_values(ascending=False)
        col_cat1, col_cat2 = st.columns([1, 2])
        with col_cat1: st.dataframe(category_sales.reset_index().head(10))
        with col_cat2:
            if not category_sales.empty:
                plot_data = category_sales.head(9)
                if len(category_sales) > 9: plot_data['其他'] = category_sales[9:].sum()
                fig2, ax2 = plt.subplots(figsize=(10, 6))
                plot_data.plot(kind='pie', autopct='%1.1f%%', startangle=90, ax=ax2)
                ax2.set_title('各商品品类销售额贡献占比'); ax2.set_ylabel(''); st.pyplot(fig2)

    # 3. 高价值用户分层 (RFM)
    st.header('三、高价值用户分层 (RFM)')
    if not unique_b2c_orders.empty and unique_b2c_orders['下单人'].nunique() > 10:
        # ... (RFM code block) ...
        snapshot_date = unique_b2c_orders['支付时间'].max() + pd.Timedelta(days=1)
        rfm_data = unique_b2c_orders.groupby('下单人').agg(Recency=('支付时间', lambda x: (snapshot_date - x.max()).days),Frequency=('订单号', 'nunique'),MonetaryValue=('订单金额', 'sum'))
        try:
            r_labels=range(5,0,-1); f_labels=range(1,6); m_labels=range(1,6)
            rfm_data['R_score'] = pd.qcut(rfm_data['Recency'], 5, labels=r_labels, duplicates='drop').astype(int)
            rfm_data['F_score'] = pd.qcut(rfm_data['Frequency'].rank(method='first'), 5, labels=f_labels, duplicates='drop').astype(int)
            rfm_data['M_score'] = pd.qcut(rfm_data['MonetaryValue'].rank(method='first'), 5, labels=m_labels, duplicates='drop').astype(int)
            r_avg = rfm_data['R_score'].mean(); f_avg = rfm_data['F_score'].mean(); m_avg = rfm_data['M_score'].mean()
            def segment_customer(row):
                if row['R_score'] > r_avg and row['F_score'] > f_avg and row['M_score'] > m_avg: return '高价值客户'
                if row['F_score'] > f_avg and row['M_score'] > m_avg: return '需激活的核心客户'
                if row['R_score'] > r_avg: return '潜力与新客户'
                if not row['R_score'] > r_avg: return '需挽留客户'
                return '一般客户'
            rfm_data['Segment'] = rfm_data.apply(segment_customer, axis=1)
            segment_summary = rfm_data['Segment'].value_counts()
            fig3, ax3 = plt.subplots(figsize=(10, 5)); segment_summary.sort_values().plot(kind='barh', ax=ax3)
            ax3.set_title('客户分层结果'); ax3.set_xlabel('客户数量'); st.pyplot(fig3)
        except Exception as e:
            st.warning(f"RFM分析失败: {e}")
            
    # 4. “神仙搭配”跨品类洞察
    st.header('四、“神仙搭配”跨品类洞察')
    if not b2c_products.empty:
        # ... (Association rule code block) ...
        def clean_product_name(name): return re.sub(r'[\(（].*?[\)）]', '', name).strip()
        b2c_products['商品_cleaned'] = b2c_products['商品'].apply(clean_product_name)
        transactions = b2c_products.dropna(subset=['商品_cleaned']).groupby('订单号')['商品_cleaned'].apply(list)
        multi_item_transactions = transactions[transactions.apply(len) >= 2].tolist()
        if len(multi_item_transactions) > 1:
            pair_counts = Counter(pair for basket in multi_item_transactions for pair in combinations(sorted(set(basket)), 2))
            item_counts = Counter(item for basket in transactions for item in set(basket))
            rules = []
            for pair, count in pair_counts.items():
                itemA, itemB = pair; total_trans = len(transactions)
                if item_counts.get(itemA,0) > 0 and item_counts.get(itemB,0) > 0:
                    lift = (count / total_trans) / ((item_counts[itemA] / total_trans) * (item_counts[itemB] / total_trans))
                    rules.append({"商品A": itemA, "商品B": itemB, "一同购买次数": count, "Lift(惊喜度)": lift})
            if rules:
                rules_df = pd.DataFrame(rules)
                unexpected_pairs = rules_df[(rules_df['Lift(惊喜度)'] > 5) & (rules_df['一同购买次数'] >= 2)].sort_values('Lift(惊喜度)', ascending=False)
                st.dataframe(unexpected_pairs.head(10))
