import json
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL
from data_utils import format_col_name


def call_deepseek_api(prompt: str, temperature: float = 0.3, max_tokens: int = 1500):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"], True
    except Exception as e:
        return f"API调用失败: {str(e)}", False


def _clean_ai_code(code: str):
    code = code.strip()
    if code.startswith("```python"):
        code = code[9:]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    return code.strip()


def _normalize_figure(fig):
    if isinstance(fig, go.Figure):
        return fig
    if isinstance(fig, dict):
        try:
            return go.Figure(fig)
        except Exception:
            return None
    return None


def create_default_chart(df: pd.DataFrame, data_type: str, chart_type: str = 'auto'):
    if df.empty:
        return None
    try:
        if chart_type == 'auto':
            if data_type == "生产任务" and 'task_status' in df.columns:
                status_counts = df['task_status'].value_counts().reset_index()
                status_counts.columns = ['状态', '数量']
                return px.pie(status_counts, values='数量', names='状态', title='生产任务状态分布')
            if data_type == "设备" and {'equip_name', 'capacity_daily'}.issubset(df.columns):
                fig = px.bar(df, x='equip_name', y='capacity_daily', color='equip_type' if 'equip_type' in df.columns else None,
                             title='设备日产能分布', text_auto=True,
                             labels={'equip_name': '设备名称', 'capacity_daily': '日产能', 'equip_type': '设备类型'})
                fig.update_layout(xaxis_tickangle=-45)
                return fig
            if data_type == "物料" and {'material_name', 'stock_quantity'}.issubset(df.columns):
                top10 = df.nlargest(10, 'stock_quantity')
                fig = px.bar(top10, x='material_name', y='stock_quantity', color='supplier' if 'supplier' in df.columns else None,
                             title='物料库存 Top 10', text_auto=True,
                             labels={'material_name': '物料名称', 'stock_quantity': '库存数量', 'supplier': '供应商'})
                fig.update_layout(xaxis_tickangle=-45)
                return fig
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols and df.columns.any():
                x_col = df.columns[0]
                y_col = numeric_cols[0]
                return px.bar(df, x=x_col, y=y_col, title=f'{data_type}数据概览',
                              labels={x_col: format_col_name(x_col), y_col: format_col_name(y_col)})
        if chart_type == '柱状图':
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols and df.columns.any():
                x_col = df.columns[0]
                y_col = numeric_cols[0]
                return px.bar(df, x=x_col, y=y_col, title=f'{data_type}柱状图', text_auto=True,
                              labels={x_col: format_col_name(x_col), y_col: format_col_name(y_col)})
        if chart_type == '饼图':
            value_col = df.select_dtypes(include=['number']).columns.tolist()
            if value_col and len(df) <= 20:
                return px.pie(df, values=value_col[0], names=df.columns[0], title=f'{data_type}饼图')
        if chart_type == '折线图':
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols and df.columns.any():
                x_col = df.columns[0]
                y_col = numeric_cols[0]
                return px.line(df, x=x_col, y=y_col, title=f'{data_type}折线图', markers=True,
                               labels={x_col: format_col_name(x_col), y_col: format_col_name(y_col)})
        if chart_type == '散点图':
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if len(numeric_cols) >= 2:
                return px.scatter(df, x=numeric_cols[0], y=numeric_cols[1], title=f'{data_type}散点图',
                                  labels={numeric_cols[0]: format_col_name(numeric_cols[0]), numeric_cols[1]: format_col_name(numeric_cols[1])})
    except Exception:
        return None
    return None


def ai_generate_visualization(df: pd.DataFrame, data_type: str, chart_style: str = "自动选择"):
    if df.empty:
        return None, "无数据可生成图表"

    summary = df.head(10).to_string()
    cols = list(df.columns)

    style_hints = {
        "自动选择": "根据数据特征自动选择最合适的图表类型",
        "趋势分析": "使用折线图、面积图等展示数据趋势变化",
        "对比分析": "使用柱状图、雷达图等展示数据对比",
        "分布分析": "使用直方图、箱线图等展示数据分布",
        "占比分析": "使用饼图、环形图、瀑布图等展示占比关系",
        "关联分析": "使用散点图、气泡图、热力图等展示数据关联",
        "排序展示": "使用横向柱状图、树形图等展示排序结果"
    }

    style_description = style_hints.get(chart_style, "")
    prompt = f"""
你是一个专业的数据可视化专家。基于以下{data_type}数据，请生成一段Python代码，使用plotly.express绘制图表。

数据已经在变量 df 中提供，这是一个 pandas DataFrame：
数据列：{cols}
数据样例：
{summary}

可视化风格需求：{style_description}

重要提示：
- 数据已经存储在 df 变量中，直接使用它，不要重新创建 DataFrame
- 代码会在已导入 pandas (pd)、plotly.express (px)、plotly.graph_objects (go)、numpy (np) 的环境中执行
- 不需要写 import 语句，这些库已经可用
- 直接使用 df、pd、px、go、np

要求：
1. 只返回Python代码，不要包含任何解释、注释或markdown符号
2. 代码必须定义变量 fig，例如 fig = px.bar(df, ...) 或 fig = px.pie(df, ...)
3. 不要写任何 import 语句，不要重新创建 df DataFrame
4. 使用 plotly.express (px) 和 pandas (pd) 生成可视化，必要时可用 plotly.graph_objects (go) 和 numpy (np)
5. 添加合适的图表参数以增强展示效果（如 text_auto=True）
6. 图表要能直观展示数据特征，包含标题和轴标签
7. 所有轴标签、图例标题必须使用中文
8. 确保代码能在 Python 中直接执行（无需额外依赖）
9. 优先使用不同于简单柱状图的图表类型以增加多样性
10. 避免使用仅在特定版本plotly中支持的特性

代码：
"""
    response, success = call_deepseek_api(prompt, temperature=0.2, max_tokens=1000)
    if not success:
        default_fig = create_default_chart(df, data_type, 'auto')
        return default_fig, f"AI服务不可用，使用默认{data_type}图表" if default_fig else (None, "无法生成默认图表")

    code = _clean_ai_code(response)
    filtered_lines = []
    for line in code.split('\n'):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            continue
        if stripped.startswith('df ') and '= pd.DataFrame' in stripped:
            continue
        filtered_lines.append(line)
    code = '\n'.join(filtered_lines)

    try:
        exec_globals = {'pd': pd, 'px': px, 'go': go, 'np': np, 'df': df}
        exec(code, exec_globals)
        fig = exec_globals.get('fig')
        fig = _normalize_figure(fig)
        if fig is None:
            default_fig = create_default_chart(df, data_type, 'auto')
            return default_fig, "AI生成的代码未返回有效图表，使用默认图表" if default_fig else (None, "AI生成的代码未返回有效图表，且无法生成默认图表")
        return fig, "AI生成图表成功"
    except Exception as e:
        default_fig = create_default_chart(df, data_type, 'auto')
        return default_fig, f"AI生成图表失败（{str(e)}），使用默认图表" if default_fig else (None, f"AI生成图表失败（{str(e)}），且无法生成默认图表")


def ai_scheduling_analysis(conn):
    df_tasks = pd.read_sql("SELECT * FROM production_tasks", conn)
    df_equip = pd.read_sql("SELECT * FROM equipment_info", conn)
    df_mat = pd.read_sql("SELECT * FROM material_info", conn)
    df_bom = pd.read_sql("SELECT * FROM bom_info", conn)

    if df_tasks.empty and df_equip.empty and df_mat.empty:
        return "暂无数据，无法分析。"

    context = f"""
当前生产数据：
- 任务总数：{len(df_tasks)}，其中已排程 {len(df_tasks[df_tasks['task_status']=='已排程'])}，待排程 {len(df_tasks[df_tasks['task_status']=='待排程'])}
- 设备总数：{len(df_equip)}，可用设备 {len(df_equip[df_equip['equip_status']=='正常'])}
- 物料种类：{len(df_mat)}，物料总库存：{df_mat['stock_quantity'].sum() if not df_mat.empty else 0}
- BOM条目数：{len(df_bom)}

任务示例（前5条）：
{df_tasks.head(5).to_string() if not df_tasks.empty else '无'}

设备示例（前5条）：
{df_equip.head(5).to_string() if not df_equip.empty else '无'}

物料示例（前5条）：
{df_mat.head(5).to_string() if not df_mat.empty else '无'}

BOM示例（前5条）：
{df_bom.head(5).to_string() if not df_bom.empty else '无'}

请根据以上数据，给出智能排程的优化建议，包括：
1. 识别生产瓶颈（物料、设备、任务优先级等）
2. 建议的排程策略
3. 具体的改进措施
4. 预计效果
回答要专业、简洁、可操作。
"""
    response, success = call_deepseek_api(context, temperature=0.4, max_tokens=1500)
    return response if success else "AI分析暂时不可用，请稍后再试。"
