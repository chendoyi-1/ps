import pandas as pd
import plotly.express as px
import streamlit as st
import numpy as np
import time
from data_utils import df_columns_to_chinese, format_col_name


def create_basic_dashboard(conn):
    df_tasks = pd.read_sql("SELECT * FROM production_tasks", conn)
    df_equip = pd.read_sql("SELECT * FROM equipment_info", conn)
    df_mat = pd.read_sql("SELECT * FROM material_info", conn)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总任务", len(df_tasks))
    with col2:
        scheduled = len(df_tasks[df_tasks['task_status'] == '已排程'])
        st.metric("已排程", scheduled)
    with col3:
        st.metric("设备总数", len(df_equip))
    with col4:
        total_stock = df_mat['stock_quantity'].sum() if not df_mat.empty else 0
        st.metric("物料总库存", f"{total_stock:,}")

    if not df_tasks.empty:
        status_counts = df_tasks['task_status'].value_counts().reset_index()
        status_counts.columns = ['状态', '数量']
        fig1 = px.pie(status_counts, values='数量', names='状态', title='生产任务状态分布')
        st.plotly_chart(fig1, use_container_width=True, key="dashboard_tasks_pie")

    col_left, col_right = st.columns(2)
    with col_left:
        if not df_equip.empty:
            fig2 = px.bar(df_equip, x='equip_name', y='capacity_daily', color='equip_type',
                         title='设备日产能分布', text_auto=True,
                         labels={'equip_name': '设备名称', 'capacity_daily': '日产能', 'equip_type': '设备类型'})
            fig2.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig2, use_container_width=True, key="dashboard_equip_bar")
    with col_right:
        if not df_mat.empty:
            top10 = df_mat.nlargest(10, 'stock_quantity')
            fig3 = px.bar(top10, x='material_name', y='stock_quantity', color='supplier',
                         title='物料库存 Top 10', text_auto=True,
                         labels={'material_name': '物料名称', 'stock_quantity': '库存数量', 'supplier': '供应商'})
            fig3.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig3, use_container_width=True, key="dashboard_material_bar")


def create_enhanced_dashboard(conn):
    st.subheader("多维分析")

    df_tasks = pd.read_sql("SELECT * FROM production_tasks", conn)
    df_equip = pd.read_sql("SELECT * FROM equipment_info", conn)
    df_mat = pd.read_sql("SELECT * FROM material_info", conn)
    df_bom = pd.read_sql("SELECT * FROM bom_info", conn)

    data_source = st.selectbox("选择数据源", ["生产任务", "设备信息", "物料信息", "BOM清单", "排程历史"])
    if data_source == "生产任务":
        df = df_tasks
    elif data_source == "设备信息":
        df = df_equip
    elif data_source == "物料信息":
        df = df_mat
    elif data_source == "BOM清单":
        df = df_bom
    else:
        df = pd.read_sql("SELECT * FROM schedule_history", conn)

    if df.empty:
        st.warning("该数据源暂无数据")
        return

    with st.expander("筛选器", expanded=False):
        filter_cols = st.multiselect("选择筛选字段", df.columns.tolist(), format_func=format_col_name)
        filter_conditions = {}
        for col in filter_cols:
            if df[col].dtype == 'object' or df[col].dtype.name == 'category':
                unique_vals = df[col].dropna().unique().tolist()
                selected = st.multiselect(format_col_name(col), unique_vals, default=unique_vals)
                filter_conditions[col] = selected
            elif pd.api.types.is_numeric_dtype(df[col]):
                min_val = float(df[col].min())
                max_val = float(df[col].max())
                if min_val < max_val:
                    filter_conditions[col] = st.slider(format_col_name(col), min_val, max_val, (min_val, max_val))
        for col, cond in filter_conditions.items():
            if isinstance(cond, list):
                df = df[df[col].isin(cond)]
            elif isinstance(cond, tuple):
                df = df[(df[col] >= cond[0]) & (df[col] <= cond[1])]

    st.dataframe(df_columns_to_chinese(df), use_container_width=True)
    st.markdown("#### 图表分析")
    col_chart1, col_chart2 = st.columns(2)

    def build_chart_choices(df, chart_type, x_axis, y_axis, color):
        if y_axis == '计数':
            if color != '无':
                fig_df = df.groupby([x_axis, color]).size().reset_index(name='计数')
            else:
                fig_df = df[x_axis].value_counts().reset_index()
                fig_df.columns = [x_axis, '计数']
        else:
            fig_df = df
        if chart_type == '自动':
            if y_axis == '计数':
                return px.bar(fig_df, x=x_axis, y='计数', color=None if color == '无' else color,
                              title=f"{data_source}分析",
                              labels={x_axis: format_col_name(x_axis), '计数': '计数', color: format_col_name(color) if color != '无' else None})
            return px.scatter(fig_df, x=x_axis, y=y_axis, color=None if color == '无' else color,
                              title=f"{data_source}分析",
                              labels={x_axis: format_col_name(x_axis), y_axis: format_col_name(y_axis), color: format_col_name(color) if color != '无' else None})
        if chart_type == '柱状图':
            return px.bar(fig_df, x=x_axis, y='计数' if y_axis == '计数' else y_axis,
                          color=None if color == '无' else color, title=f"{data_source}柱状图", text_auto=True,
                          labels={x_axis: format_col_name(x_axis), '计数': '计数', y_axis: format_col_name(y_axis), color: format_col_name(color) if color != '无' else None})
        if chart_type == '饼图':
            if y_axis == '计数' or x_axis == y_axis:
                agg = df[x_axis].value_counts().reset_index()
                agg.columns = [x_axis, '计数']
                return px.pie(agg, values='计数', names=x_axis, title=f"{data_source}饼图")
            agg = df.groupby(x_axis, as_index=False)[y_axis].sum()
            return px.pie(agg, values=y_axis, names=x_axis, title=f"{data_source}饼图")
        if chart_type == '折线图':
            return px.line(fig_df, x=x_axis, y='计数' if y_axis == '计数' else y_axis,
                           color=None if color == '无' else color, title=f"{data_source}折线图", markers=True,
                           labels={x_axis: format_col_name(x_axis), '计数': '计数', y_axis: format_col_name(y_axis), color: format_col_name(color) if color != '无' else None})
        if chart_type == '散点图':
            return px.scatter(fig_df, x=x_axis, y='计数' if y_axis == '计数' else y_axis,
                              color=None if color == '无' else color, title=f"{data_source}散点图",
                              labels={x_axis: format_col_name(x_axis), '计数': '计数', y_axis: format_col_name(y_axis), color: format_col_name(color) if color != '无' else None})
        return None

    def get_y_axis_options(df):
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        return numeric_cols + ['计数']

    def format_y_axis_option(opt):
        return '计数' if opt == '计数' else format_col_name(opt)

    with col_chart1:
        chart_type = st.selectbox("图表类型", ["自动", "柱状图", "饼图", "折线图", "散点图"], key="chart1")
        x_axis = st.selectbox("X轴", df.columns, format_func=format_col_name, key="x1")
        y_options = get_y_axis_options(df)
        y_axis = st.selectbox("Y轴", y_options, format_func=format_y_axis_option, key="y1")
        color = st.selectbox("分组/颜色", ["无"] + df.columns.tolist(), format_func=lambda x: "无" if x == "无" else format_col_name(x), key="color1")
        fig = build_chart_choices(df, chart_type, x_axis, y_axis, color)
        if fig:
            st.plotly_chart(fig, use_container_width=True, key=f"enhanced_chart1_{time.time()}")

    with col_chart2:
        chart_type2 = st.selectbox("图表类型", ["自动", "柱状图", "饼图", "折线图", "散点图"], key="chart2")
        x_axis2 = st.selectbox("X轴", df.columns, format_func=format_col_name, key="x2")
        y_options2 = get_y_axis_options(df)
        y_axis2 = st.selectbox("Y轴", y_options2, format_func=format_y_axis_option, key="y2")
        color2 = st.selectbox("分组/颜色", ["无"] + df.columns.tolist(), format_func=lambda x: "无" if x == "无" else format_col_name(x), key="color2")
        fig2 = build_chart_choices(df, chart_type2, x_axis2, y_axis2, color2)
        if fig2:
            st.plotly_chart(fig2, use_container_width=True, key=f"enhanced_chart2_{time.time()}")
