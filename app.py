# ====================== 生产排程与供应链智能分析系统（最终版） ======================
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import requests
import json
from datetime import datetime, timedelta
import warnings
from difflib import SequenceMatcher
import numpy as np
import time
warnings.filterwarnings("ignore")

# -------------------------- DeepSeek API 配置（请替换为您的密钥） --------------------------
DEEPSEEK_API_KEY = "sk-5545acb4abb541008691f1f9de8b4671"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# -------------------------- 数据库初始化（含BOM表）--------------------------
def init_database():
    conn = sqlite3.connect("production_system.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS production_tasks (
        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_name TEXT NOT NULL,
        product_name TEXT NOT NULL,
        production_quantity INTEGER NOT NULL,
        responsible_person TEXT,
        start_date TEXT,
        end_date TEXT,
        task_status TEXT DEFAULT '待排程',
        assigned_equipment TEXT,
        priority INTEGER DEFAULT 5,
        material_required TEXT,
        create_time TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS equipment_info (
        equip_id INTEGER PRIMARY KEY AUTOINCREMENT,
        equip_name TEXT NOT NULL UNIQUE,
        equip_type TEXT NOT NULL,
        capacity_daily INTEGER NOT NULL,
        equip_status TEXT DEFAULT '正常',
        maintenance_time TEXT,
        last_maintenance TEXT,
        next_maintenance TEXT,
        utilization_rate REAL DEFAULT 0,
        create_time TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS material_info (
        material_id INTEGER PRIMARY KEY AUTOINCREMENT,
        material_name TEXT NOT NULL,
        supplier TEXT NOT NULL,
        stock_quantity INTEGER NOT NULL DEFAULT 0,
        safety_stock INTEGER DEFAULT 1000,
        lead_time INTEGER DEFAULT 1,
        unit_price REAL DEFAULT 0,
        update_time TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS schedule_history (
        schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        equipment_name TEXT,
        start_time TEXT,
        end_time TEXT,
        schedule_type TEXT,
        create_time TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bom_info (
        bom_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        material_name TEXT NOT NULL,
        quantity_per_unit REAL NOT NULL,
        create_time TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_name, material_name)
    )''')
    conn.commit()
    return conn

conn = init_database()
cursor = conn.cursor()

# -------------------------- DeepSeek API 调用 --------------------------
def call_deepseek_api(prompt, temperature=0.3, max_tokens=1500):
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

# -------------------------- 字段映射模块（稳定版）--------------------------
class FieldMapper:
    TASK_MAPPINGS = {
        '任务名称': 'task_name',
        '产品': 'product_name',
        '数量': 'production_quantity',
        '负责人': 'responsible_person',
        '开始时间': 'start_date',
        '结束时间': 'end_date',
    }
    EQUIP_MAPPINGS = {
        '设备名称': 'equip_name',
        '设备类型': 'equip_type',
        '日产能': 'capacity_daily',
        '维护时间': 'maintenance_time',
    }
    MATERIAL_MAPPINGS = {
        '物料名称': 'material_name',
        '供应商': 'supplier',
        '库存数量': 'stock_quantity',
        '采购周期': 'lead_time',
    }
    BOM_MAPPINGS = {
        '产品名称': 'product_name',
        '物料名称': 'material_name',
        '单位用量': 'quantity_per_unit',
    }

    @staticmethod
    def _clean(col):
        if isinstance(col, str):
            col = col.lstrip('\ufeff').strip()
            col = col.translate(str.maketrans('，。！？（）【】“”‘’', ',.!?()[]""\'\''))
        return col

    @classmethod
    def map_columns(cls, df, data_type):
        if data_type == '任务':
            mapping = cls.TASK_MAPPINGS
            required = ['task_name', 'product_name', 'production_quantity']
        elif data_type == '设备':
            mapping = cls.EQUIP_MAPPINGS
            required = ['equip_name', 'equip_type', 'capacity_daily']
        elif data_type == '物料':
            mapping = cls.MATERIAL_MAPPINGS
            required = ['material_name', 'supplier']
        elif data_type == 'BOM':
            mapping = cls.BOM_MAPPINGS
            required = ['product_name', 'material_name', 'quantity_per_unit']
        else:
            return df, {}, [], []

        cleaned_cols = {orig: cls._clean(orig) for orig in df.columns}
        rename_dict = {}
        mapped_report = {}
        unused = []
        for orig, cleaned in cleaned_cols.items():
            if cleaned in mapping:
                std = mapping[cleaned]
                rename_dict[orig] = std
                mapped_report[std] = orig
            else:
                unused.append(orig)

        df = df.rename(columns=rename_dict)
        missing = [f for f in required if f not in df.columns]
        return df, mapped_report, unused, missing

# -------------------------- CSV导入函数 --------------------------
def import_csv_with_preview(uploaded_file, data_type):
    try:
        df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
    except:
        try:
            df = pd.read_csv(uploaded_file, encoding='gbk')
        except Exception as e:
            return None, {}, [], [], False
    df, mapped, unused, missing = FieldMapper.map_columns(df, data_type)
    return df, mapped, unused, missing, True

# -------------------------- 列名中文映射（用于界面显示）--------------------------
COLUMN_NAME_MAP = {
    # 生产任务表
    'task_id': '任务ID',
    'task_name': '任务名称',
    'product_name': '产品',
    'production_quantity': '数量',
    'responsible_person': '负责人',
    'start_date': '开始时间',
    'end_date': '结束时间',
    'task_status': '任务状态',
    'assigned_equipment': '分配设备',
    'priority': '优先级',
    'material_required': '所需物料',
    'create_time': '创建时间',
    # 设备信息表
    'equip_id': '设备ID',
    'equip_name': '设备名称',
    'equip_type': '设备类型',
    'capacity_daily': '日产能',
    'equip_status': '设备状态',
    'maintenance_time': '维护时间',
    'last_maintenance': '上次维护',
    'next_maintenance': '下次维护',
    'utilization_rate': '利用率',
    # 物料信息表
    'material_id': '物料ID',
    'material_name': '物料名称',
    'supplier': '供应商',
    'stock_quantity': '库存数量',
    'safety_stock': '安全库存',
    'lead_time': '采购周期',
    'unit_price': '单价',
    'update_time': '更新时间',
    # 排程历史表
    'schedule_id': '排程ID',
    'task_id': '任务ID',
    'equipment_name': '设备名称',
    'start_time': '开始时间',
    'end_time': '结束时间',
    'schedule_type': '排程类型',
    # BOM表
    'bom_id': 'BOM ID',
    'product_name': '产品名称',
    'material_name': '物料名称',
    'quantity_per_unit': '单位用量',
}

def format_col_name(col):
    """将英文列名转换为中文显示"""
    return COLUMN_NAME_MAP.get(col, col)

# -------------------------- 物料需求计算器（基于BOM）--------------------------
class MaterialRequirementCalculator:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()
        self._load_bom()
    
    def _load_bom(self):
        self.bom_df = pd.read_sql("SELECT * FROM bom_info", self.conn)
        self.product_bom = {}
        for _, row in self.bom_df.iterrows():
            prod = row['product_name']
            if prod not in self.product_bom:
                self.product_bom[prod] = []
            self.product_bom[prod].append({
                'material': row['material_name'],
                'qty_per_unit': row['quantity_per_unit']
            })
    
    def get_requirements(self, product_name, quantity):
        if product_name not in self.product_bom:
            return None
        reqs = []
        for item in self.product_bom[product_name]:
            reqs.append({
                'material': item['material'],
                'required': item['qty_per_unit'] * quantity
            })
        return reqs
    
    def check_material_enough(self, product_name, quantity, stock_df):
        reqs = self.get_requirements(product_name, quantity)
        if reqs is None:
            return False, [f"产品 {product_name} 未在BOM中定义"]
        shortages = []
        enough = True
        for req in reqs:
            material = req['material']
            required = req['required']
            stock_row = stock_df[stock_df['material_name'] == material]
            if stock_row.empty:
                shortages.append(f"物料 {material} 不存在")
                enough = False
            else:
                stock = stock_row.iloc[0]['stock_quantity']
                if stock < required:
                    shortages.append(f"物料 {material} 需求 {required:.0f}，库存 {stock}")
                    enough = False
        return enough, shortages

# -------------------------- 基础排程模块（使用BOM）--------------------------
class ProductionScheduler:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()
        self.calculator = MaterialRequirementCalculator(conn)
    
    def run_scheduling(self):
        df_tasks = pd.read_sql("SELECT * FROM production_tasks WHERE task_status='待排程'", self.conn)
        df_equip = pd.read_sql("SELECT * FROM equipment_info WHERE equip_status='正常'", self.conn)
        df_materials = pd.read_sql("SELECT * FROM material_info", self.conn)
        if df_tasks.empty:
            return "暂无待排程任务"
        if df_equip.empty:
            return "无可用设备"
        
        task_status = []
        for _, task in df_tasks.iterrows():
            enough, shortages = self.calculator.check_material_enough(
                task['product_name'], task['production_quantity'], df_materials
            )
            task_status.append({
                'task_id': task['task_id'],
                'enough': enough,
                'shortages': shortages
            })
        
        schedulable = [t for t in task_status if t['enough']]
        if not schedulable:
            shortage_msgs = []
            for t in task_status:
                if not t['enough']:
                    shortage_msgs.append(f"任务 {t['task_id']} 物料不足: {', '.join(t['shortages'])}")
            return "物料不足，无法排程：\n" + "\n".join(shortage_msgs)
        
        task_ids = [t['task_id'] for t in schedulable]
        tasks_to_schedule = df_tasks[df_tasks['task_id'].isin(task_ids)].copy().sort_values('production_quantity')
        equip_names = df_equip['equip_name'].tolist()
        equip_capacities = dict(zip(df_equip['equip_name'], df_equip['capacity_daily']))
        current_time = datetime.now()
        schedule_count = 0
        for i, (_, task) in enumerate(tasks_to_schedule.iterrows()):
            equip = equip_names[i % len(equip_names)]
            days = max(1, int(np.ceil(task['production_quantity'] / equip_capacities[equip])))
            start = current_time.strftime("%Y-%m-%d %H:%M:%S")
            end = (current_time + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute('''
                UPDATE production_tasks SET task_status='已排程', assigned_equipment=?, start_date=?, end_date=?
                WHERE task_id=?
            ''', (equip, start, end, task['task_id']))
            self.cursor.execute('''
                INSERT INTO schedule_history (task_id, equipment_name, start_time, end_time, schedule_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (task['task_id'], equip, start, end, 'auto'))
            schedule_count += 1
            current_time += timedelta(hours=8)
        self.conn.commit()
        return f"排程完成！成功排程 {schedule_count} 个任务，物料不足 {len(df_tasks)-schedule_count} 个。"

# -------------------------- 优化排程模块（使用BOM，修复KeyError）--------------------------
class OptimizedScheduler(ProductionScheduler):
    def __init__(self, conn):
        super().__init__(conn)
    
    def _score_equipment(self, task, equip, task_priority=5):
        """计算设备-任务匹配得分"""
        # 使用 task['quantity'] 而不是 task['production_quantity']，因为 task 字典中使用的是 'quantity'
        capacity_diff = abs(equip['capacity_daily'] - task['quantity'])
        max_diff = max(equip['capacity_daily'], task['quantity'])
        capacity_score = (1 - capacity_diff / max_diff) * 40 if max_diff > 0 else 0
        status_score = {'正常': 100, '维护': 50, '故障': 0}.get(equip.get('equip_status', '正常'), 0) * 0.3
        priority_score = task_priority * 3
        return capacity_score + status_score + priority_score
    
    def run_optimized_scheduling(self, strategy='priority', priorities=None):
        df_tasks = pd.read_sql("SELECT * FROM production_tasks WHERE task_status='待排程'", self.conn)
        df_equip = pd.read_sql("SELECT * FROM equipment_info WHERE equip_status='正常'", self.conn)
        df_materials = pd.read_sql("SELECT * FROM material_info", self.conn)
        if df_tasks.empty:
            return "暂无待排程任务"
        if df_equip.empty:
            return "无可用设备"
        
        task_list = []
        for _, task in df_tasks.iterrows():
            enough, shortages = self.calculator.check_material_enough(
                task['product_name'], task['production_quantity'], df_materials
            )
            task_list.append({
                'task_id': task['task_id'],
                'task_name': task['task_name'],
                'product_name': task['product_name'],
                'quantity': task['production_quantity'],  # 注意这里用的是 'quantity'
                'enough': enough,
                'shortages': shortages,
                'priority': priorities.get(task['task_id'], 5) if priorities else task.get('priority', 5)
            })
        
        schedulable = [t for t in task_list if t['enough']]
        if not schedulable:
            shortage_msgs = []
            for t in task_list:
                if not t['enough']:
                    shortage_msgs.append(f"任务 {t['task_name']} 物料不足: {', '.join(t['shortages'])}")
            return "物料不足，无法排程：\n" + "\n".join(shortage_msgs)
        
        # 根据策略排序
        if strategy == 'shortest':
            # 最短工期：按数量从小到大，这样小任务先做，可以更快完成一批任务（但实际工期受设备产能影响）
            schedulable.sort(key=lambda x: x['quantity'])
        elif strategy == 'utilization':
            # 最高利用率：按数量从大到小，大任务优先，可能提高设备利用率
            schedulable.sort(key=lambda x: -x['quantity'])
        elif strategy == 'priority':
            # 优先级优先：按优先级从高到低，同优先级按数量从小到大
            schedulable.sort(key=lambda x: (-x['priority'], x['quantity']))
        else:
            return "未知策略"
        
        equip_list = df_equip.to_dict('records')
        equip_names = [e['equip_name'] for e in equip_list]
        equip_capacities = {e['equip_name']: e['capacity_daily'] for e in equip_list}
        current_time = datetime.now()
        equip_available_time = {name: current_time for name in equip_names}
        schedule_count = 0
        
        for task in schedulable:
            best_equip = None
            best_score = -1
            for equip in equip_list:
                score = self._score_equipment(task, equip, task['priority'])
                if score > best_score:
                    best_score = score
                    best_equip = equip['equip_name']
            if not best_equip:
                continue
            capacity = equip_capacities[best_equip]
            days = max(1, int(np.ceil(task['quantity'] / capacity)))
            start_time = max(equip_available_time[best_equip], current_time)
            end_time = start_time + timedelta(days=days)
            start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
            end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute('''
                UPDATE production_tasks SET task_status='已排程', assigned_equipment=?, start_date=?, end_date=?
                WHERE task_id=?
            ''', (best_equip, start_str, end_str, task['task_id']))
            self.cursor.execute('''
                INSERT INTO schedule_history (task_id, equipment_name, start_time, end_time, schedule_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (task['task_id'], best_equip, start_str, end_str, strategy))
            equip_available_time[best_equip] = end_time + timedelta(hours=8)
            schedule_count += 1
        
        self.conn.commit()
        return f"优化排程完成（策略：{strategy}）！成功排程 {schedule_count} 个任务，物料不足 {len(df_tasks)-schedule_count} 个。"

# -------------------------- 本地规则问答（使用BOM）--------------------------
class LocalQnA:
    def __init__(self, conn):
        self.conn = conn
        self.calculator = MaterialRequirementCalculator(conn)
    
    def answer(self, question):
        q = question.lower()
        df_tasks = pd.read_sql("SELECT * FROM production_tasks WHERE task_status='待排程'", self.conn)
        df_materials = pd.read_sql("SELECT * FROM material_info", self.conn)
        
        if "物料短缺" in q:
            if df_tasks.empty:
                return "暂无待排程任务，无需检查物料短缺。"
            shortages = []
            for _, task in df_tasks.iterrows():
                enough, msgs = self.calculator.check_material_enough(
                    task['product_name'], task['production_quantity'], df_materials
                )
                if not enough:
                    shortages.append(f"任务「{task['task_name']}」物料不足：{', '.join(msgs)}")
            return "以下任务物料短缺：\n" + "\n".join(shortages) if shortages else "所有待排程任务物料充足。"
        elif "排程完成率" in q:
            total = pd.read_sql("SELECT COUNT(*) as cnt FROM production_tasks", self.conn).iloc[0]['cnt']
            scheduled = pd.read_sql("SELECT COUNT(*) as cnt FROM production_tasks WHERE task_status='已排程'", self.conn).iloc[0]['cnt']
            rate = (scheduled/total*100) if total>0 else 0
            return f"排程完成率：{rate:.1f}%（总任务 {total}，已排程 {scheduled}）"
        elif "设备利用率" in q:
            df_equip = pd.read_sql("SELECT * FROM equipment_info", self.conn)
            total_cap = df_equip['capacity_daily'].sum() if not df_equip.empty else 0
            used_cap = 0
            df_scheduled = pd.read_sql("SELECT * FROM production_tasks WHERE task_status='已排程'", self.conn)
            for _, task in df_scheduled.iterrows():
                equip = task['assigned_equipment']
                if equip and equip in df_equip['equip_name'].values:
                    used_cap += df_equip[df_equip['equip_name']==equip]['capacity_daily'].iloc[0]
            utilization = (used_cap/total_cap*100) if total_cap>0 else 0
            return f"设备利用率约为 {utilization:.1f}%。可用设备 {len(df_equip[df_equip['equip_status']=='正常'])} 台。"
        else:
            return "请尝试询问物料短缺、排程完成率或设备利用率。"

# -------------------------- AI 可视化生成函数（增强版）--------------------------
def create_default_chart(df, data_type, chart_type='auto'):
    if df.empty:
        return None
    if chart_type == 'auto':
        if data_type == "生产任务" and 'task_status' in df.columns:
            status_counts = df['task_status'].value_counts().reset_index()
            status_counts.columns = ['状态', '数量']
            fig = px.pie(status_counts, values='数量', names='状态', title='生产任务状态分布')
            return fig
        elif data_type == "设备" and 'equip_name' in df.columns and 'capacity_daily' in df.columns:
            fig = px.bar(df, x='equip_name', y='capacity_daily', 
                         color='equip_type' if 'equip_type' in df.columns else None,
                         title='设备日产能分布', text_auto=True)
            fig.update_layout(xaxis_tickangle=-45)
            return fig
        elif data_type == "物料" and 'material_name' in df.columns and 'stock_quantity' in df.columns:
            top10 = df.nlargest(10, 'stock_quantity')
            fig = px.bar(top10, x='material_name', y='stock_quantity', 
                         color='supplier' if 'supplier' in df.columns else None,
                         title='物料库存 Top 10', text_auto=True)
            fig.update_layout(xaxis_tickangle=-45)
            return fig
        else:
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if numeric_cols and len(df.columns) > 0:
                x_col = df.columns[0]
                fig = px.bar(df, x=x_col, y=numeric_cols[0], title=f'{data_type}数据概览')
                return fig
    else:
        # 根据用户选择的图表类型生成
        if chart_type == '柱状图':
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if numeric_cols:
                x_col = df.columns[0]
                fig = px.bar(df, x=x_col, y=numeric_cols[0], title=f'{data_type}柱状图', text_auto=True)
                return fig
        elif chart_type == '饼图':
            value_col = df.select_dtypes(include=[np.number]).columns.tolist()
            if value_col and len(df) <= 20:
                fig = px.pie(df, values=value_col[0], names=df.columns[0], title=f'{data_type}饼图')
                return fig
        elif chart_type == '折线图':
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if numeric_cols:
                x_col = df.columns[0]
                fig = px.line(df, x=x_col, y=numeric_cols[0], title=f'{data_type}折线图', markers=True)
                return fig
        elif chart_type == '散点图':
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if len(numeric_cols) >= 2:
                fig = px.scatter(df, x=numeric_cols[0], y=numeric_cols[1], title=f'{data_type}散点图')
                return fig
    return None

def ai_generate_visualization(df, data_type):
    if df.empty:
        return None, "无数据可生成图表"
    summary = df.head(10).to_string()
    cols = list(df.columns)
    prompt = f"""
你是一个专业的数据可视化专家。基于以下{data_type}数据，请生成一段Python代码，使用plotly.express绘制一个最合适的图表。
数据列：{cols}
数据样例：
{summary}

要求：
1. 只返回Python代码，不要包含任何解释、注释或markdown标记。
2. 代码必须定义变量 fig，例如 fig = px.bar(...) 或 fig = px.pie(...) 等。
3. 图表要能直观展示数据特征，包含标题和轴标签。
4. 代码应可直接在streamlit中运行（使用st.plotly_chart(fig)）。

代码：
"""
    response, success = call_deepseek_api(prompt, temperature=0.2, max_tokens=1000)
    if not success:
        default_fig = create_default_chart(df, data_type, 'auto')
        if default_fig:
            return default_fig, f"AI服务不可用，使用默认{data_type}图表"
        else:
            return None, "无法生成默认图表"
    code = response.strip()
    if code.startswith("```python"):
        code = code[9:]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    code = code.strip()
    try:
        exec_globals = {'pd': pd, 'px': px, 'df': df}
        exec(code, exec_globals)
        fig = exec_globals.get('fig', None)
        if fig is None:
            default_fig = create_default_chart(df, data_type, 'auto')
            if default_fig:
                return default_fig, "AI生成的代码未定义fig变量，使用默认图表"
            else:
                return None, "AI生成的代码未定义fig变量，且无法生成默认图表"
        return fig, "AI生成图表成功"
    except Exception as e:
        default_fig = create_default_chart(df, data_type, 'auto')
        if default_fig:
            return default_fig, f"AI生成图表失败（{str(e)}），使用默认图表"
        else:
            return None, f"AI生成图表失败（{str(e)}），且无法生成默认图表"

# -------------------------- AI 排程分析函数 --------------------------
def ai_scheduling_analysis():
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
    if success:
        return response
    else:
        return "AI分析暂时不可用，请稍后再试。"

# -------------------------- 基础可视化仪表盘 --------------------------
def create_basic_dashboard():
    df_tasks = pd.read_sql("SELECT * FROM production_tasks", conn)
    df_equip = pd.read_sql("SELECT * FROM equipment_info", conn)
    df_mat = pd.read_sql("SELECT * FROM material_info", conn)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总任务", len(df_tasks))
    with col2:
        scheduled = len(df_tasks[df_tasks['task_status']=='已排程'])
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
            fig2 = px.bar(df_equip, x='equip_name', y='capacity_daily', color='equip_type', title='设备日产能分布', text_auto=True)
            fig2.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig2, use_container_width=True, key="dashboard_equip_bar")
    with col_right:
        if not df_mat.empty:
            top10 = df_mat.nlargest(10, 'stock_quantity')
            fig3 = px.bar(top10, x='material_name', y='stock_quantity', color='supplier', title='物料库存 Top 10', text_auto=True)
            fig3.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig3, use_container_width=True, key="dashboard_material_bar")

# -------------------------- 增强的多维可视化模块（中文界面）--------------------------
def create_enhanced_dashboard():
    st.subheader("多维分析（仿飞书多维表格风格）")
    
    # 获取数据
    df_tasks = pd.read_sql("SELECT * FROM production_tasks", conn)
    df_equip = pd.read_sql("SELECT * FROM equipment_info", conn)
    df_mat = pd.read_sql("SELECT * FROM material_info", conn)
    df_bom = pd.read_sql("SELECT * FROM bom_info", conn)
    
    # 数据源选择
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
    
    # 筛选器（列名显示中文）
    with st.expander("筛选器", expanded=False):
        filter_cols = st.multiselect(
            "选择筛选字段", 
            df.columns.tolist(), 
            format_func=format_col_name
        )
        filter_conditions = {}
        for col in filter_cols:
            display_name = format_col_name(col)
            if df[col].dtype in ['object', 'category']:
                unique_vals = df[col].dropna().unique().tolist()
                selected = st.multiselect(f"{display_name}", unique_vals, default=unique_vals)
                filter_conditions[col] = selected
            elif pd.api.types.is_numeric_dtype(df[col]):
                min_val = float(df[col].min())
                max_val = float(df[col].max())
                if min_val < max_val:
                    range_val = st.slider(f"{display_name}", min_val, max_val, (min_val, max_val))
                    filter_conditions[col] = range_val
        # 应用筛选
        for col, cond in filter_conditions.items():
            if isinstance(cond, list):
                df = df[df[col].isin(cond)]
            elif isinstance(cond, tuple):
                df = df[(df[col] >= cond[0]) & (df[col] <= cond[1])]
    
    # 显示数据表格
    st.dataframe(df, use_container_width=True)
    
    # 图表生成区
    st.markdown("#### 图表分析")
    col_chart1, col_chart2 = st.columns(2)
    
    # 辅助函数：格式化Y轴选项（数值列显示中文，加上“计数”）
    def get_y_axis_options(df):
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        return numeric_cols + ["计数"]
    
    def format_y_axis_option(opt):
        if opt == "计数":
            return "计数"
        return format_col_name(opt)
    
    with col_chart1:
        chart_type = st.selectbox("图表类型", ["自动", "柱状图", "饼图", "折线图", "散点图"], key="chart1")
        x_axis = st.selectbox("X轴", df.columns, format_func=format_col_name, key="x1")
        y_options = get_y_axis_options(df)
        y_axis = st.selectbox("Y轴", y_options, format_func=format_y_axis_option, key="y1")
        color = st.selectbox("分组/颜色", ["无"] + df.columns.tolist(), format_func=lambda x: "无" if x=="无" else format_col_name(x), key="color1")
        
        if y_axis == "计数":
            if color != "无":
                agg_df = df.groupby([x_axis, color]).size().reset_index(name='计数')
            else:
                agg_df = df[x_axis].value_counts().reset_index()
                agg_df.columns = [x_axis, '计数']
            fig_df = agg_df
            y = '计数'
        else:
            fig_df = df
            y = y_axis
        
        if chart_type == "自动":
            if y == '计数' or (y_axis == "计数"):
                fig = px.bar(fig_df, x=x_axis, y=y, color=color if color!="无" else None, title=f"{data_source}分析")
            else:
                fig = px.scatter(fig_df, x=x_axis, y=y, color=color if color!="无" else None, title=f"{data_source}分析")
        elif chart_type == "柱状图":
            fig = px.bar(fig_df, x=x_axis, y=y, color=color if color!="无" else None, title=f"{data_source}柱状图", text_auto=True)
        elif chart_type == "饼图":
            if y == '计数':
                fig = px.pie(fig_df, values=y, names=x_axis, title=f"{data_source}饼图")
            else:
                agg = df.groupby(x_axis)[y].sum().reset_index()
                fig = px.pie(agg, values=y, names=x_axis, title=f"{data_source}饼图")
        elif chart_type == "折线图":
            fig = px.line(fig_df, x=x_axis, y=y, color=color if color!="无" else None, title=f"{data_source}折线图", markers=True)
        elif chart_type == "散点图":
            fig = px.scatter(fig_df, x=x_axis, y=y, color=color if color!="无" else None, title=f"{data_source}散点图")
        else:
            fig = None
        
        if fig:
            st.plotly_chart(fig, use_container_width=True, key=f"enhanced_chart1_{time.time()}")
    
    with col_chart2:
        chart_type2 = st.selectbox("图表类型", ["自动", "柱状图", "饼图", "折线图", "散点图"], key="chart2")
        x_axis2 = st.selectbox("X轴", df.columns, format_func=format_col_name, key="x2")
        y_options2 = get_y_axis_options(df)
        y_axis2 = st.selectbox("Y轴", y_options2, format_func=format_y_axis_option, key="y2")
        color2 = st.selectbox("分组/颜色", ["无"] + df.columns.tolist(), format_func=lambda x: "无" if x=="无" else format_col_name(x), key="color2")
        
        if y_axis2 == "计数":
            if color2 != "无":
                agg_df = df.groupby([x_axis2, color2]).size().reset_index(name='计数')
            else:
                agg_df = df[x_axis2].value_counts().reset_index()
                agg_df.columns = [x_axis2, '计数']
            fig_df = agg_df
            y = '计数'
        else:
            fig_df = df
            y = y_axis2
        
        if chart_type2 == "自动":
            if y == '计数' or (y_axis2 == "计数"):
                fig = px.bar(fig_df, x=x_axis2, y=y, color=color2 if color2!="无" else None, title=f"{data_source}分析")
            else:
                fig = px.scatter(fig_df, x=x_axis2, y=y, color=color2 if color2!="无" else None, title=f"{data_source}分析")
        elif chart_type2 == "柱状图":
            fig = px.bar(fig_df, x=x_axis2, y=y, color=color2 if color2!="无" else None, title=f"{data_source}柱状图", text_auto=True)
        elif chart_type2 == "饼图":
            if y == '计数':
                fig = px.pie(fig_df, values=y, names=x_axis2, title=f"{data_source}饼图")
            else:
                agg = df.groupby(x_axis2)[y].sum().reset_index()
                fig = px.pie(agg, values=y, names=x_axis2, title=f"{data_source}饼图")
        elif chart_type2 == "折线图":
            fig = px.line(fig_df, x=x_axis2, y=y, color=color2 if color2!="无" else None, title=f"{data_source}折线图", markers=True)
        elif chart_type2 == "散点图":
            fig = px.scatter(fig_df, x=x_axis2, y=y, color=color2 if color2!="无" else None, title=f"{data_source}散点图")
        else:
            fig = None
        
        if fig:
            st.plotly_chart(fig, use_container_width=True, key=f"enhanced_chart2_{time.time()}")

# -------------------------- 页面配置 --------------------------
st.set_page_config(page_title="生产排程与供应链智能分析系统", layout="wide")
st.title("生产排程与供应链智能分析系统")
st.markdown("""
<div style='background-color: #e3f2fd; padding: 10px; border-radius: 5px; margin-bottom: 20px;'>
    <strong>系统特性：</strong> 精确字段映射 | BOM物料清单 | 多物料短缺判断 | 多策略优化排程 | 增强可视化（飞书风格） | AI问答 | 系统设置
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/factory--v1.png", width=80)
    st.header("功能导航")
    menu = st.radio("选择功能", ["数据导入", "数据查看", "智能排程", "可视化仪表盘", "智能问答", "系统设置"])

# -------------------------- 数据导入页面 --------------------------
if menu == "数据导入":
    st.subheader("CSV数据导入（字段映射模块未改动）")
    tab1, tab2, tab3, tab4 = st.tabs(["生产任务", "设备信息", "物料信息", "BOM物料清单"])
    
    with tab1:
        task_file = st.file_uploader("上传任务CSV文件", type="csv", key="task")
        if task_file:
            df, mapped, unused, missing, ok = import_csv_with_preview(task_file, "任务")
            if ok:
                st.success("文件读取成功！")
                if mapped:
                    st.write("字段映射结果：")
                    for std, orig in mapped.items():
                        st.write(f"`{std}` ← {orig}")
                if unused:
                    st.warning(f"以下列未能映射，将被忽略：{unused}")
                if missing:
                    st.error(f"缺少必填字段：{missing}")
                else:
                    st.dataframe(df.head(10), use_container_width=True)
                    if st.button("确认导入任务数据", key="import_task"):
                        for _, row in df.iterrows():
                            cursor.execute('''
                                INSERT INTO production_tasks 
                                (task_name, product_name, production_quantity, responsible_person, start_date, end_date, priority)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                row['task_name'],
                                row['product_name'],
                                int(row['production_quantity']),
                                row.get('responsible_person', ''),
                                row.get('start_date', ''),
                                row.get('end_date', ''),
                                int(row.get('priority', 5))
                            ))
                        conn.commit()
                        st.success(f"成功导入 {len(df)} 条任务数据！")
            else:
                st.error("文件读取失败，请检查格式或编码。")
    
    with tab2:
        equip_file = st.file_uploader("上传设备CSV文件", type="csv", key="equip")
        if equip_file:
            df, mapped, unused, missing, ok = import_csv_with_preview(equip_file, "设备")
            if ok:
                st.success("文件读取成功！")
                if mapped:
                    st.write("字段映射结果：")
                    for std, orig in mapped.items():
                        st.write(f"`{std}` ← {orig}")
                if unused:
                    st.warning(f"以下列未能映射，将被忽略：{unused}")
                if missing:
                    st.error(f"缺少必填字段：{missing}")
                else:
                    st.dataframe(df.head(10), use_container_width=True)
                    if st.button("确认导入设备数据", key="import_equip"):
                        inserted = 0
                        for _, row in df.iterrows():
                            try:
                                cursor.execute('''
                                    INSERT INTO equipment_info 
                                    (equip_name, equip_type, capacity_daily, maintenance_time, equip_status)
                                    VALUES (?, ?, ?, ?, ?)
                                ''', (
                                    row['equip_name'],
                                    row['equip_type'],
                                    int(row['capacity_daily']),
                                    row.get('maintenance_time', ''),
                                    row.get('equip_status', '正常')
                                ))
                                inserted += 1
                            except sqlite3.IntegrityError:
                                pass
                        conn.commit()
                        st.success(f"成功导入 {inserted} 条设备数据（重复设备已自动跳过）！")
            else:
                st.error("文件读取失败，请检查格式或编码。")
    
    with tab3:
        mat_file = st.file_uploader("上传物料CSV文件", type="csv", key="mat")
        if mat_file:
            df, mapped, unused, missing, ok = import_csv_with_preview(mat_file, "物料")
            if ok:
                st.success("文件读取成功！")
                if mapped:
                    st.write("字段映射结果：")
                    for std, orig in mapped.items():
                        st.write(f"`{std}` ← {orig}")
                if unused:
                    st.warning(f"以下列未能映射，将被忽略：{unused}")
                if missing:
                    st.error(f"缺少必填字段：{missing}")
                else:
                    st.dataframe(df.head(10), use_container_width=True)
                    if st.button("确认导入物料数据", key="import_mat"):
                        inserted = 0
                        for _, row in df.iterrows():
                            try:
                                cursor.execute('''
                                    INSERT INTO material_info 
                                    (material_name, supplier, stock_quantity, lead_time, safety_stock, unit_price)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                ''', (
                                    row['material_name'],
                                    row['supplier'],
                                    int(row['stock_quantity']),
                                    int(row.get('lead_time', 1)),
                                    int(row.get('safety_stock', 1000)),
                                    float(row.get('unit_price', 0))
                                ))
                                inserted += 1
                            except sqlite3.IntegrityError:
                                pass
                        conn.commit()
                        st.success(f"成功导入 {inserted} 条物料数据！")
            else:
                st.error("文件读取失败，请检查格式或编码。")
    
    with tab4:
        bom_file = st.file_uploader("上传BOM CSV文件", type="csv", key="bom")
        if bom_file:
            df, mapped, unused, missing, ok = import_csv_with_preview(bom_file, "BOM")
            if ok:
                st.success("文件读取成功！")
                if mapped:
                    st.write("字段映射结果：")
                    for std, orig in mapped.items():
                        st.write(f"`{std}` ← {orig}")
                if unused:
                    st.warning(f"以下列未能映射，将被忽略：{unused}")
                if missing:
                    st.error(f"缺少必填字段：{missing}")
                else:
                    st.dataframe(df.head(10), use_container_width=True)
                    if st.button("确认导入BOM数据", key="import_bom"):
                        inserted = 0
                        for _, row in df.iterrows():
                            try:
                                cursor.execute('''
                                    INSERT OR IGNORE INTO bom_info 
                                    (product_name, material_name, quantity_per_unit)
                                    VALUES (?, ?, ?)
                                ''', (
                                    row['product_name'],
                                    row['material_name'],
                                    float(row['quantity_per_unit'])
                                ))
                                inserted += 1
                            except Exception as e:
                                st.error(f"导入失败: {e}")
                        conn.commit()
                        st.success(f"成功导入 {inserted} 条BOM数据！")
            else:
                st.error("文件读取失败，请检查格式或编码。")

# -------------------------- 数据查看页面 --------------------------
elif menu == "数据查看":
    st.subheader("数据库内容查看")
    
    if st.button("刷新数据"):
        st.rerun()
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["生产任务", "设备信息", "物料信息", "排程历史", "BOM物料清单"])
    
    with tab1:
        df = pd.read_sql("SELECT * FROM production_tasks", conn)
        st.dataframe(df, use_container_width=True)
        st.caption(f"共 {len(df)} 条记录")
    
    with tab2:
        df = pd.read_sql("SELECT * FROM equipment_info", conn)
        st.dataframe(df, use_container_width=True)
        st.caption(f"共 {len(df)} 条记录")
    
    with tab3:
        df = pd.read_sql("SELECT * FROM material_info", conn)
        st.dataframe(df, use_container_width=True)
        st.caption(f"共 {len(df)} 条记录")
    
    with tab4:
        df = pd.read_sql("SELECT * FROM schedule_history", conn)
        st.dataframe(df, use_container_width=True)
        st.caption(f"共 {len(df)} 条记录")
    
    with tab5:
        df = pd.read_sql("SELECT * FROM bom_info", conn)
        st.dataframe(df, use_container_width=True)
        st.caption(f"共 {len(df)} 条记录")

# -------------------------- 智能排程页面（含重置按钮）--------------------------
elif menu == "智能排程":
    st.subheader("智能排程")
    
    col1, col2 = st.columns([1,1])
    with col1:
        st.metric("待排程任务", len(pd.read_sql("SELECT * FROM production_tasks WHERE task_status='待排程'", conn)))
        st.metric("可用设备", len(pd.read_sql("SELECT * FROM equipment_info WHERE equip_status='正常'", conn)))
        
        if st.button("执行基础排程（轮询）", type="secondary"):
            scheduler = ProductionScheduler(conn)
            with st.spinner("基础排程中..."):
                result = scheduler.run_scheduling()
            st.success(result)
    
    with col2:
        st.markdown("### AI排程分析")
        if st.button("获取AI优化建议"):
            with st.spinner("AI正在分析数据..."):
                advice = ai_scheduling_analysis()
            st.info(advice)
    
    # 重置排程按钮
    st.markdown("---")
    col_reset1, col_reset2 = st.columns([1,3])
    with col_reset1:
        if st.button("重置所有任务为待排程", type="primary"):
            cursor.execute("UPDATE production_tasks SET task_status='待排程', assigned_equipment=NULL, start_date=NULL, end_date=NULL WHERE task_status='已排程'")
            conn.commit()
            st.success("所有已排程任务已重置为待排程")
            st.rerun()
    with col_reset2:
        st.caption("点击后将所有已排程任务状态改为待排程，并清空分配的设备和时间，方便重新排程。")
    
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
                default_pri = int(row['priority']) if pd.notna(row['priority']) else 5
                priorities[row['task_id']] = st.slider(f"{row['task_name']}", 1, 10, default_pri, key=f"pri_{row['task_id']}")
        else:
            st.info("暂无待排程任务")
    
    if st.button("执行优化排程", type="primary"):
        if strategy == "优先级优先" and not priorities:
            st.warning("请先设置任务优先级")
        else:
            optimizer = OptimizedScheduler(conn)
            with st.spinner("优化排程中..."):
                result = optimizer.run_optimized_scheduling(strategy_map[strategy], priorities if strategy=="优先级优先" else None)
            st.success(result)
            st.rerun()
    
    st.divider()
    st.markdown("### 待排程任务列表")
    st.dataframe(pd.read_sql("SELECT task_id, task_name, product_name, production_quantity, priority FROM production_tasks WHERE task_status='待排程'", conn))
    
    st.markdown("### 已排程任务")
    df_scheduled = pd.read_sql("SELECT * FROM production_tasks WHERE task_status='已排程'", conn)
    if not df_scheduled.empty:
        st.dataframe(df_scheduled[['task_name', 'assigned_equipment', 'start_date', 'end_date', 'priority']])
        
        if 'start_date' in df_scheduled.columns and 'end_date' in df_scheduled.columns:
            gantt_df = df_scheduled[['task_name', 'assigned_equipment', 'start_date', 'end_date']].dropna()
            if not gantt_df.empty:
                gantt_df['start'] = pd.to_datetime(gantt_df['start_date'])
                gantt_df['end'] = pd.to_datetime(gantt_df['end_date'])
                fig_gantt = px.timeline(gantt_df, x_start='start', x_end='end', y='assigned_equipment',
                                         color='task_name', title='排程甘特图')
                st.plotly_chart(fig_gantt, use_container_width=True, key="scheduling_gantt")
    else:
        st.info("暂无已排程任务")

# -------------------------- 可视化仪表盘页面（增强版）--------------------------
elif menu == "可视化仪表盘":
    st.subheader("可视化仪表盘")
    
    # 基础仪表盘
    create_basic_dashboard()
    
    st.divider()
    
    # 增强多维分析
    create_enhanced_dashboard()
    
    st.divider()
    st.markdown("### AI动态生成图表")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("生成任务图表"):
            df = pd.read_sql("SELECT * FROM production_tasks", conn)
            fig, msg = ai_generate_visualization(df, "生产任务")
            if fig:
                st.plotly_chart(fig, use_container_width=True, key=f"ai_chart_task_{time.time()}")
            st.caption(msg)
    with col2:
        if st.button("生成设备图表"):
            df = pd.read_sql("SELECT * FROM equipment_info", conn)
            fig, msg = ai_generate_visualization(df, "设备")
            if fig:
                st.plotly_chart(fig, use_container_width=True, key=f"ai_chart_equip_{time.time()}")
            st.caption(msg)
    with col3:
        if st.button("生成物料图表"):
            df = pd.read_sql("SELECT * FROM material_info", conn)
            fig, msg = ai_generate_visualization(df, "物料")
            if fig:
                st.plotly_chart(fig, use_container_width=True, key=f"ai_chart_material_{time.time()}")
            st.caption(msg)

# -------------------------- 智能问答页面 --------------------------
elif menu == "智能问答":
    st.subheader("智能问答（AI优先）")
    
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
    
    local_qna = LocalQnA(conn)
    
    if "last_answer" not in st.session_state:
        st.session_state.last_answer = ""
    
    quick_questions = ["哪些任务物料短缺？", "当前排程完成率是多少？", "设备利用率如何？", "如何提升排程效率？"]
    cols = st.columns(2)
    for i, q in enumerate(quick_questions):
        if cols[i%2].button(q, key=f"q{i}"):
            with st.spinner("AI思考中..."):
                prompt = f"你是一个生产供应链专家。请基于以下数据回答问题：\n\n{context_summary}\n\n问题：{q}\n\n请给出专业、准确、简洁的回答。"
                answer, success = call_deepseek_api(prompt)
                if success:
                    st.session_state.last_answer = answer
                else:
                    st.session_state.last_answer = local_qna.answer(q) + "\n\n（注：AI服务不可用，此为本地规则回答）"
    
    user_q = st.text_input("或输入您的问题：", placeholder="例如：哪些任务物料短缺？")
    if st.button("向AI提问", type="primary") and user_q:
        with st.spinner("AI思考中..."):
            prompt = f"你是一个生产供应链专家。请基于以下数据回答问题：\n\n{context_summary}\n\n问题：{user_q}\n\n请给出专业、准确、简洁的回答。"
            answer, success = call_deepseek_api(prompt)
            if success:
                st.session_state.last_answer = answer
            else:
                st.session_state.last_answer = local_qna.answer(user_q) + "\n\n（注：AI服务不可用，此为本地规则回答）"
    
    if st.session_state.last_answer:
        st.info(st.session_state.last_answer)

# -------------------------- 系统设置页面 --------------------------
elif menu == "系统设置":
    st.subheader("系统设置")
    if st.button("清空所有数据（谨慎）"):
        if st.checkbox("确认清空所有数据？此操作不可恢复"):
            cursor.execute("DELETE FROM production_tasks")
            cursor.execute("DELETE FROM equipment_info")
            cursor.execute("DELETE FROM material_info")
            cursor.execute("DELETE FROM schedule_history")
            cursor.execute("DELETE FROM bom_info")
            conn.commit()
            st.success("所有数据已清空")