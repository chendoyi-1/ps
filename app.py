import json
import time
import warnings
import streamlit as st
import pandas as pd
import plotly.express as px

from database import init_database
from data_utils import import_csv_with_preview, df_columns_to_chinese, format_col_name
from scheduler import ProductionScheduler, OptimizedScheduler
from ai_utils import ai_generate_visualization, ai_scheduling_analysis, call_deepseek_api
from qna import LocalQnA
from dashboard import create_basic_dashboard, create_enhanced_dashboard

warnings.filterwarnings("ignore")
conn = init_database()
cursor = conn.cursor()


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def safe_rerun():
    if hasattr(st, 'rerun'):
        return st.rerun()
    if hasattr(st, 'experimental_rerun'):
        return st.experimental_rerun()
    raise RuntimeError('当前 Streamlit 版本不支持 rerun')


def show_import_preview(df, mapped, unused, missing):
    if mapped:
        st.write("字段映射结果：")
        for std, orig in mapped.items():
            st.write(f"`{std}` ← {orig}")
    if unused:
        st.warning(f"以下列未能映射，将被忽略：{unused}")
    if missing:
        st.error(f"缺少必填字段：{missing}")
    else:
        st.dataframe(df_columns_to_chinese(df.head(10)), use_container_width=True)


def insert_task_records(df):
    inserted = 0
    for _, row in df.iterrows():
        try:
            cursor.execute(
                '''
                INSERT INTO production_tasks
                (task_name, product_name, production_quantity, responsible_person, start_date, end_date, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    row['task_name'],
                    row['product_name'],
                    safe_int(row.get('production_quantity', 0)),
                    row.get('responsible_person') or None,
                    row.get('start_date') or None,
                    row.get('end_date') or None,
                    safe_int(row.get('priority', 5), 5)
                )
            )
            inserted += 1
        except Exception:
            continue
    conn.commit()
    return f"成功导入 {inserted} 条任务数据！"


def insert_equipment_records(df):
    inserted = 0
    for _, row in df.iterrows():
        try:
            cursor.execute(
                '''
                INSERT INTO equipment_info
                (equip_name, equip_type, capacity_daily, maintenance_time, equip_status)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (
                    row['equip_name'],
                    row['equip_type'],
                    safe_int(row.get('capacity_daily', 0)),
                    row.get('maintenance_time') or None,
                    row.get('equip_status') or '正常'
                )
            )
            inserted += 1
        except Exception:
            continue
    conn.commit()
    return f"成功导入 {inserted} 条设备数据（重复记录已自动跳过）！"


def insert_material_records(df):
    inserted = 0
    for _, row in df.iterrows():
        try:
            cursor.execute(
                '''
                INSERT INTO material_info
                (material_name, supplier, stock_quantity, lead_time, safety_stock, unit_price)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    row['material_name'],
                    row['supplier'],
                    safe_int(row.get('stock_quantity', 0)),
                    safe_int(row.get('lead_time', 1), 1),
                    safe_int(row.get('safety_stock', 1000), 1000),
                    safe_float(row.get('unit_price', 0), 0.0)
                )
            )
            inserted += 1
        except Exception:
            continue
    conn.commit()
    return f"成功导入 {inserted} 条物料数据！"


def insert_bom_records(df):
    inserted = 0
    for _, row in df.iterrows():
        try:
            cursor.execute(
                '''
                INSERT OR IGNORE INTO bom_info
                (product_name, material_name, quantity_per_unit)
                VALUES (?, ?, ?)
                ''',
                (
                    row['product_name'],
                    row['material_name'],
                    safe_float(row.get('quantity_per_unit', 0), 0.0)
                )
            )
            inserted += 1
        except Exception:
            continue
    conn.commit()
    return f"成功导入 {inserted} 条BOM数据！"


def render_import_tab(title, data_type, upload_key, insert_func, button_label):
    uploaded_file = st.file_uploader(title, type='csv', key=upload_key)
    if not uploaded_file:
        return

    df, mapped, unused, missing, ok = import_csv_with_preview(uploaded_file, data_type)
    if not ok:
        st.error("文件读取失败，请检查CSV格式或编码。")
        return

    st.success("文件读取成功！")
    show_import_preview(df, mapped, unused, missing)

    if not missing:
        if st.button(button_label, key=f"import_{upload_key}"):
            message = insert_func(df)
            st.success(message)


def render_import_page():
    st.subheader("CSV数据导入")
    st.info("📌 上传CSV文件后，系统会自动映射列名。缺失必填字段时会提示，请按提示修正后重新上传。")
    tabs = st.tabs(["生产任务", "设备信息", "物料信息", "BOM物料清单"])

    with tabs[0]:
        render_import_tab("上传任务CSV文件", '任务', 'task', insert_task_records, "确认导入任务数据")
    with tabs[1]:
        render_import_tab("上传设备CSV文件", '设备', 'equip', insert_equipment_records, "确认导入设备数据")
    with tabs[2]:
        render_import_tab("上传物料CSV文件", '物料', 'mat', insert_material_records, "确认导入物料数据")
    with tabs[3]:
        render_import_tab("上传BOM CSV文件", 'BOM', 'bom', insert_bom_records, "确认导入BOM数据")


def render_data_view_page():
    st.subheader("数据库内容查看")
    if st.button("刷新数据"):
        safe_rerun()

    tab_info = [
        ("生产任务", "SELECT * FROM production_tasks", "production_tasks", "task_id"),
        ("设备信息", "SELECT * FROM equipment_info", "equipment_info", "equip_id"),
        ("物料信息", "SELECT * FROM material_info", "material_info", "material_id"),
        ("排程历史", "SELECT * FROM schedule_history", "schedule_history", "schedule_id"),
        ("BOM物料清单", "SELECT * FROM bom_info", "bom_info", "bom_id")
    ]

    tabs = st.tabs([info[0] for info in tab_info])
    for tab, (_, sql, table_name, id_field) in zip(tabs, tab_info):
        with tab:
            df = pd.read_sql(sql, conn)
            st.dataframe(df_columns_to_chinese(df), use_container_width=True)
            st.caption(f"共 {len(df)} 条记录")

            if df.empty:
                continue

            st.markdown("### 删除单条记录")
            for _, row in df.iterrows():
                col1, col2 = st.columns([4, 1])
                with col1:
                    # 显示行摘要
                    summary = f"ID: {row[id_field]} - " + ", ".join([f"{k}: {v}" for k, v in row.items() if k != id_field][:3])  # 前3个字段
                    st.write(summary)
                with col2:
                    if st.button("删除", key=f"delete_{table_name}_{row[id_field]}"):
                        cursor.execute(f"DELETE FROM {table_name} WHERE {id_field} = ?", (row[id_field],))
                        conn.commit()
                        st.success(f"已删除记录 ID: {row[id_field]}")
                        safe_rerun()


def render_scheduling_page():
    st.subheader("智能排程")
    st.caption("💡 提示：基础排程采用轮询分配，优化排程支持三种策略。如需重新排程，请先点击“重置所有任务为待排程”。")

    if "ai_advice" not in st.session_state:
        st.session_state.ai_advice = None

    col1, col2 = st.columns([1, 1])
    with col1:
        pending_count = len(pd.read_sql("SELECT * FROM production_tasks WHERE task_status='待排程'", conn))
        available_equip = len(pd.read_sql("SELECT * FROM equipment_info WHERE equip_status='正常'", conn))
        st.metric("待排程任务", pending_count)
        st.metric("可用设备", available_equip)
        if st.button("执行基础排程（轮询）", type='secondary'):
            scheduler = ProductionScheduler(conn)
            with st.spinner("基础排程中..."):
                result = scheduler.run_scheduling()
            st.success(result)

    with col2:
        st.markdown("### AI排程分析")
        if st.button("获取AI优化建议"):
            with st.spinner("AI正在分析数据..."):
                st.session_state.ai_advice = ai_scheduling_analysis(conn)

    reset_col, hint_col = st.columns([1, 3])
    with reset_col:
        if st.button("重置所有任务为待排程", type='primary'):
            cursor.execute("UPDATE production_tasks SET task_status='待排程', assigned_equipment=NULL, start_date=NULL, end_date=NULL WHERE task_status='已排程'")
            conn.commit()
            st.success("所有已排程任务已重置为待排程")
            safe_rerun()
    with hint_col:
        st.caption("将已排程任务恢复为待排程，清空设备分配和时间信息，便于重新排程。")

    if st.session_state.ai_advice:
        st.divider()
        st.markdown("### AI优化建议")
        st.info(st.session_state.ai_advice)

    st.divider()
    st.markdown("### 优化排程（动态约束管理）")
    strategy = st.radio("选择优化策略", ["优先级优先", "最短工期", "最高利用率"], horizontal=True)
    strategy_map = {"优先级优先": "priority", "最短工期": "shortest", "最高利用率": "utilization"}

    priorities = {}
    if strategy == "优先级优先":
        st.markdown("#### 设置任务优先级（数字越大优先级越高）")
        df_pending = pd.read_sql("SELECT task_id, task_name, priority FROM production_tasks WHERE task_status='待排程'", conn)
        if not df_pending.empty:
            for _, row in df_pending.iterrows():
                default_pri = safe_int(row.get('priority', 5), 5)
                priorities[row['task_id']] = st.slider(row['task_name'], 1, 10, default_pri, key=f"pri_{row['task_id']}")
        else:
            st.info("暂无待排程任务")

    if st.button("执行优化排程", type='primary'):
        if strategy == "优先级优先" and not priorities:
            st.warning("请先设置任务优先级")
        else:
            optimizer = OptimizedScheduler(conn)
            with st.spinner("优化排程中..."):
                result = optimizer.run_optimized_scheduling(strategy_map[strategy], priorities if strategy == "优先级优先" else None)
            st.success(result)
            safe_rerun()

    st.divider()
    st.markdown("### 待排程任务列表")
    df_pending = pd.read_sql("SELECT task_id, task_name, product_name, production_quantity, priority FROM production_tasks WHERE task_status='待排程'", conn)
    st.dataframe(df_columns_to_chinese(df_pending), use_container_width=True)

    st.markdown("### 已排程任务")
    df_scheduled = pd.read_sql("SELECT * FROM production_tasks WHERE task_status='已排程'", conn)
    if not df_scheduled.empty:
        scheduled_view = df_scheduled[['task_name', 'assigned_equipment', 'start_date', 'end_date', 'priority']]
        st.dataframe(df_columns_to_chinese(scheduled_view), use_container_width=True)
        if {'start_date', 'end_date'}.issubset(df_scheduled.columns):
            gantt_df = df_scheduled[['task_name', 'assigned_equipment', 'start_date', 'end_date']].dropna().copy()
            if not gantt_df.empty:
                gantt_df['start'] = pd.to_datetime(gantt_df['start_date'])
                gantt_df['end'] = pd.to_datetime(gantt_df['end_date'])
                fig_gantt = px.timeline(
                    gantt_df,
                    x_start='start',
                    x_end='end',
                    y='assigned_equipment',
                    color='task_name',
                    title='排程甘特图',
                    labels={'assigned_equipment': '设备', 'task_name': '任务'}
                )
                st.plotly_chart(fig_gantt, use_container_width=True, key="scheduling_gantt")
    else:
        st.info("暂无已排程任务")


def render_visualization_page():
    st.subheader("可视化仪表盘")
    create_basic_dashboard(conn)
    st.divider()
    st.info("📊 多维分析：选择数据源、图表类型、X/Y轴及分组，并可通过筛选器聚焦关注的数据。")
    create_enhanced_dashboard(conn)
    st.divider()
    st.markdown("### 🎨 AI多样化图表生成器")
    st.info("选择数据源和可视化风格，AI将生成不同类型的创意图表。")

    if "ai_generated_charts" not in st.session_state:
        st.session_state.ai_generated_charts = []
    if "ai_demo_charts" not in st.session_state:
        st.session_state.ai_demo_charts = {}

    col1, col2, col3 = st.columns(3)
    with col1:
        data_source = st.selectbox("📊 选择数据源", ["生产任务", "设备信息", "物料信息", "BOM清单", "排程历史"], key="ai_datasource")
    with col2:
        chart_style = st.selectbox("🎨 选择可视化风格", ["自动选择", "趋势分析", "对比分析", "分布分析", "占比分析", "关联分析", "排序展示"], key="ai_style")
    with col3:
        num_charts = st.slider("生成数量", min_value=1, max_value=3, value=1, key="ai_num_charts")

    data_source_map = {
        "生产任务": ("SELECT * FROM production_tasks", "生产任务"),
        "设备信息": ("SELECT * FROM equipment_info", "设备"),
        "物料信息": ("SELECT * FROM material_info", "物料"),
        "BOM清单": ("SELECT * FROM bom_info", "BOM"),
        "排程历史": ("SELECT * FROM schedule_history", "排程历史")
    }

    if st.button("🚀 生成创意图表", type='primary', use_container_width=True):
        sql_query, data_type = data_source_map[data_source]
        df = pd.read_sql(sql_query, conn)
        if df.empty:
            st.warning(f"❌ {data_source}中暂无数据")
        else:
            charts = []
            for i in range(num_charts):
                with st.spinner(f"正在生成第 {i+1}/{num_charts} 个图表（风格：{chart_style}）..."):
                    fig, msg = ai_generate_visualization(df, data_type, chart_style)
                if fig:
                    charts.append({"fig": fig, "msg": msg, "title": f"AI创意图表 {i+1}"})
                else:
                    st.error(f"图表 {i+1} 生成失败：{msg}")
            if charts:
                st.session_state.ai_generated_charts = charts

    if st.session_state.ai_generated_charts:
        cols_clear = st.columns([4, 1])
        with cols_clear[1]:
            if st.button("清空创意图表", key="clear_ai_generated_charts"):
                st.session_state.ai_generated_charts = []
                safe_rerun()
        st.markdown("####  已生成创意图表")
        for idx, chart_info in enumerate(st.session_state.ai_generated_charts, start=1):
            st.markdown(f"**{chart_info.get('title', f'图表 {idx}')}:**")
            st.plotly_chart(chart_info['fig'], use_container_width=True, key=f"stored_ai_chart_{idx}")
            st.caption(chart_info.get('msg', ''))
            if idx < len(st.session_state.ai_generated_charts):
                st.divider()

    st.markdown("---")
    st.markdown("#### 💡 快速生成演示")
    demo_cols = st.columns(3)

    if demo_cols[0].button("📈 任务趋势分析", use_container_width=True, key="demo_task_trend_btn"):
        df = pd.read_sql("SELECT * FROM production_tasks", conn)
        if df.empty:
            st.warning("📊 暂无生产任务数据，请先导入数据")
        else:
            with st.spinner("正在生成任务趋势分析..."):
                fig, msg = ai_generate_visualization(df, "生产任务", "趋势分析")
            if fig:
                st.session_state.ai_demo_charts["task_trend"] = {"fig": fig, "msg": msg, "title": "任务趋势分析"}
                st.success("✅ 图表生成成功")
            else:
                st.error("❌ 图表生成失败")
            st.caption(msg)

    if demo_cols[1].button("⚙️ 设备对比分析", use_container_width=True, key="demo_equip_compare_btn"):
        df = pd.read_sql("SELECT * FROM equipment_info", conn)
        if df.empty:
            st.warning("📊 暂无设备数据，请先导入数据")
        else:
            with st.spinner("正在生成设备对比分析..."):
                fig, msg = ai_generate_visualization(df, "设备", "对比分析")
            if fig:
                st.session_state.ai_demo_charts["equip_compare"] = {"fig": fig, "msg": msg, "title": "设备对比分析"}
                st.success("✅ 图表生成成功")
            else:
                st.error("❌ 图表生成失败")
            st.caption(msg)

    if demo_cols[2].button("📦 物料分布分析", use_container_width=True, key="demo_material_dist_btn"):
        df = pd.read_sql("SELECT * FROM material_info", conn)
        if df.empty:
            st.warning("📊 暂无物料数据，请先导入数据")
        else:
            with st.spinner("正在生成物料分布分析..."):
                fig, msg = ai_generate_visualization(df, "物料", "分布分析")
            if fig:
                st.session_state.ai_demo_charts["material_dist"] = {"fig": fig, "msg": msg, "title": "物料分布分析"}
                st.success("✅ 图表生成成功")
            else:
                st.error("❌ 图表生成失败")
            st.caption(msg)

    if st.session_state.ai_demo_charts:
        cols_clear_demo = st.columns([4, 1])
        with cols_clear_demo[1]:
            if st.button("清空快速演示", key="clear_ai_demo_charts"):
                st.session_state.ai_demo_charts = {}
                safe_rerun()
        st.markdown("#### 🧪 已生成快速演示图表")
        for key, chart_info in st.session_state.ai_demo_charts.items():
            st.markdown(f"**{chart_info.get('title', key)}**")
            st.plotly_chart(chart_info['fig'], use_container_width=True, key=f"stored_demo_{key}")
            st.caption(chart_info.get('msg', ''))
            st.divider()


def render_smart_qna_page():
    st.subheader("智能问答")
    local_qna = LocalQnA(conn)

    with st.expander("紧急订单插入", expanded=False):
        st.markdown("填写以下信息快速添加紧急生产任务（状态默认为待排程）")
        cols = st.columns([3, 3])
        task_name = cols[0].text_input("任务名称*", placeholder="例如：紧急订单A")
        product_name = cols[0].text_input("产品名称*", placeholder="例如：iPhone15手机壳")
        quantity = cols[0].number_input("生产数量*", min_value=1, value=100, step=10)
        responsible = cols[1].text_input("负责人", placeholder="张三")
        priority = cols[1].slider("优先级", 1, 10, 8, help="数字越大优先级越高")
        start_date = cols[1].date_input("计划开始日期（可选）", value=None)
        end_date = cols[1].date_input("计划结束日期（可选）", value=None)

        st.markdown("#### 物料需求（可选，若不填写则从BOM自动获取）")
        if "material_rows" not in st.session_state:
            st.session_state.material_rows = [0]

        existing_materials = pd.read_sql("SELECT material_name FROM material_info", conn)['material_name'].dropna().unique().tolist()
        existing_materials = sorted(set(existing_materials))
        material_options = ["手动输入"] + existing_materials if existing_materials else ["手动输入"]

        material_items = []
        for i, row_id in enumerate(st.session_state.material_rows):
            row_cols = st.columns([3, 2, 1])
            selected_material = row_cols[0].selectbox("已有物料", material_options, key=f"mat_option_{row_id}")
            if selected_material == "手动输入":
                mat_name = row_cols[0].text_input("物料名称", key=f"mat_name_{row_id}", placeholder="例如：ABS塑料")
            else:
                mat_name = selected_material
                row_cols[0].write(f"已选：{mat_name}")
            mat_qty = row_cols[1].number_input("数量", min_value=0.0, value=0.0, step=0.1, key=f"mat_qty_{row_id}")
            if row_cols[2].button("删除", key=f"del_{row_id}"):
                st.session_state.material_rows.pop(i)
                safe_rerun()
            if mat_name and mat_qty > 0:
                material_items.append({"material": mat_name, "required": mat_qty})

        if st.button("➕ 添加物料"):
            next_id = max(st.session_state.material_rows) + 1 if st.session_state.material_rows else 0
            st.session_state.material_rows.append(next_id)
            safe_rerun()

        if st.button("提交紧急订单", type='primary'):
            if not task_name or not product_name:
                st.error("任务名称和产品名称为必填项")
            else:
                invalid_items = [item for item in material_items if not item.get('material') or item.get('required', 0) <= 0]
                if invalid_items:
                    st.error("请确保所有物料项都填写了物料名称且数量大于0。")
                else:
                    df_bom_match = pd.read_sql("SELECT * FROM bom_info WHERE product_name = ?", conn, params=(product_name,))
                    if not material_items and df_bom_match.empty:
                        st.error("当前产品未在BOM中定义，请填写物料需求或先添加对应BOM信息。")
                    else:
                        existing_materials = pd.read_sql("SELECT material_name FROM material_info", conn)['material_name'].dropna().tolist()
                        missing_materials = [item['material'] for item in material_items if item['material'] not in existing_materials]
                        if missing_materials:
                            st.warning(f"以下物料尚未添加到物料信息中，将作为自定义物料记录：{', '.join(missing_materials)}")
                        material_json = None
                        if material_items:
                            material_json = json.dumps(material_items, ensure_ascii=False)
                        cursor.execute(
                            '''
                            INSERT INTO production_tasks
                            (task_name, product_name, production_quantity, responsible_person, start_date, end_date, priority, material_required)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''',
                            (
                                task_name,
                                product_name,
                                quantity,
                                responsible or None,
                                start_date.strftime("%Y-%m-%d") if start_date else None,
                                end_date.strftime("%Y-%m-%d") if end_date else None,
                                priority,
                                material_json
                            )
                        )
                        conn.commit()
                        st.success("紧急订单已添加，当前状态为「待排程」。请前往「智能排程」页面执行排程。")
                        st.session_state.material_rows = [0]

    df_tasks = pd.read_sql("SELECT * FROM production_tasks", conn)
    df_equip = pd.read_sql("SELECT * FROM equipment_info", conn)
    df_mat = pd.read_sql("SELECT * FROM material_info", conn)
    df_bom = pd.read_sql("SELECT * FROM bom_info", conn)
    context_summary = f"""
当前系统数据：
- 生产任务总数：{len(df_tasks)}，已排程 {len(df_tasks[df_tasks['task_status']=='已排程'])}，待排程 {len(df_tasks[df_tasks['task_status']=='待排程'])}
- 设备总数：{len(df_equip)}，可用设备 {len(df_equip[df_equip['equip_status']=='正常'])}
- 物料种类：{len(df_mat)}，物料总库存：{df_mat['stock_quantity'].sum() if not df_mat.empty else 0}
- BOM条目数：{len(df_bom)}

任务样例（前3条）：
{df_tasks.head(3).to_string() if not df_tasks.empty else '无'}

设备样例（前3条）：
{df_equip.head(3).to_string() if not df_equip.empty else '无'}

物料样例（前3条）：
{df_mat.head(3).to_string() if not df_mat.empty else '无'}

BOM样例（前3条）：
{df_bom.head(3).to_string() if not df_bom.empty else '无'}
"""

    if "last_answer" not in st.session_state:
        st.session_state.last_answer = ""

    quick_questions = ["哪些任务物料短缺？", "当前排程完成率是多少？", "设备利用率如何？", "如何提升排程效率？"]
    cols = st.columns(2)
    for i, q in enumerate(quick_questions):
        if cols[i % 2].button(q, key=f"q{i}"):
            with st.spinner("AI思考中..."):
                prompt = f"你是一个生产供应链专家。请基于以下数据回答问题：\n\n{context_summary}\n\n问题：{q}\n\n请给出专业、准确、简洁的回答。"
                answer, success = call_deepseek_api(prompt)
                if success:
                    st.session_state.last_answer = answer
                else:
                    st.session_state.last_answer = local_qna.answer(q) + "\n\n（注：AI服务不可用，此为本地规则回答）"

    user_q = st.text_input("或输入您的问题：", placeholder="例如：哪些任务物料短缺？")
    if st.button("向AI提问", type='primary') and user_q:
        with st.spinner("AI思考中..."):
            prompt = f"你是一个生产供应链专家。请基于以下数据回答问题：\n\n{context_summary}\n\n问题：{user_q}\n\n请给出专业、准确、简洁的回答。"
            answer, success = call_deepseek_api(prompt)
            if success:
                st.session_state.last_answer = answer
            else:
                st.session_state.last_answer = local_qna.answer(user_q) + "\n\n（注：AI服务不可用，此为本地规则回答）"

    if st.session_state.last_answer:
        st.info(st.session_state.last_answer)


def render_system_settings_page():
    st.subheader("系统设置")
    confirm_clear = st.checkbox("确认清空所有数据？此操作不可恢复", key="confirm_clear")
    if confirm_clear and st.button("清空所有数据（谨慎）", key="clear_all"):
        cursor.execute("DELETE FROM production_tasks")
        cursor.execute("DELETE FROM equipment_info")
        cursor.execute("DELETE FROM material_info")
        cursor.execute("DELETE FROM schedule_history")
        cursor.execute("DELETE FROM bom_info")
        # Reset SQLite AUTOINCREMENT counters so IDs start from 1 again after clearing all data.
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('production_tasks', 'equipment_info', 'material_info', 'schedule_history', 'bom_info')")
        conn.commit()
        st.success("所有数据已清空")


st.set_page_config(page_title="生产排程与供应链智能分析系统", layout="wide")
st.title("生产排程与供应链智能分析系统")
st.markdown(
    """
<style>
.system-features {
    padding: 15px;
    border-radius: 8px;
    margin-bottom: 20px;
    font-weight: bold;
    border-left: 6px solid;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}
@media (prefers-color-scheme: light) {
    .system-features {
        background: linear-gradient(135deg, #c3e7ff 0%, #e3f2fd 100%);
        color: #003d99;
        border-left-color: #0066ff;
    }
}
@media (prefers-color-scheme: dark) {
    .system-features {
        background: linear-gradient(135deg, #0d47a1 0%, #1565c0 100%);
        color: #ffffff;
        border-left-color: #64b5f6;
    }
}
</style>
<div class="system-features">
    <strong>✨ 系统特性：</strong> 精确字段映射 | BOM物料清单 | 多物料短缺判断 | 多策略优化排程 | 增强可视化 | AI问答 | 紧急订单插入
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/factory--v1.png", width=80)
    st.header("功能导航")
    menu = st.radio("选择功能", ["数据导入", "数据查看", "智能排程", "可视化仪表盘", "智能问答", "系统设置"])

if menu == "数据导入":
    render_import_page()
elif menu == "数据查看":
    render_data_view_page()
elif menu == "智能排程":
    render_scheduling_page()
elif menu == "可视化仪表盘":
    render_visualization_page()
elif menu == "智能问答":
    render_smart_qna_page()
elif menu == "系统设置":
    render_system_settings_page()
