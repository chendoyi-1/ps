import json
from datetime import datetime, timedelta
import numpy as np
import pandas as pd


class MaterialRequirementCalculator:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()
        self.product_bom = {}
        self._load_bom()

    def _load_bom(self):
        bom_df = pd.read_sql("SELECT * FROM bom_info", self.conn)
        for _, row in bom_df.iterrows():
            self.product_bom.setdefault(row['product_name'], []).append({
                'material': row['material_name'],
                'qty_per_unit': row['quantity_per_unit']
            })

    def get_requirements(self, task):
        if task.get('material_required'):
            try:
                manual_reqs = json.loads(task['material_required'])
                if isinstance(manual_reqs, list):
                    return manual_reqs
            except Exception:
                pass

        product_name = task.get('product_name')
        quantity = task.get('production_quantity', 0)
        if not product_name or product_name not in self.product_bom:
            return None

        return [
            {
                'material': item['material'],
                'required': item['qty_per_unit'] * quantity
            }
            for item in self.product_bom[product_name]
        ]

    def check_material_enough(self, task, stock_df):
        reqs = self.get_requirements(task)
        if reqs is None:
            return False, [f"产品 {task.get('product_name')} 未在BOM中定义且未手动指定物料"]

        shortages = []
        enough = True
        for req in reqs:
            material = req['material']
            required = req['required']
            stock_row = stock_df[stock_df['material_name'] == material]
            if stock_row.empty:
                shortages.append(f"物料 {material} 不存在")
                enough = False
                continue
            stock = stock_row.iloc[0]['stock_quantity']
            if stock < required:
                shortages.append(f"物料 {material} 需求 {required:.0f}，库存 {stock}")
                enough = False
        return enough, shortages


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
            enough, shortages = self.calculator.check_material_enough(task, df_materials)
            task_status.append({
                'task_id': task['task_id'],
                'enough': enough,
                'shortages': shortages
            })

        schedulable = [t for t in task_status if t['enough']]
        if not schedulable:
            shortage_msgs = [
                f"任务 {t['task_id']} 物料不足: {', '.join(t['shortages'])}"
                for t in task_status if not t['enough']
            ]
            return "物料不足，无法排程：\n" + "\n".join(shortage_msgs)

        equip_names = df_equip['equip_name'].tolist()
        equip_capacities = dict(zip(df_equip['equip_name'], df_equip['capacity_daily']))
        current_time = datetime.now()
        schedule_count = 0

        tasks_to_schedule = df_tasks[df_tasks['task_id'].isin([t['task_id'] for t in schedulable])].copy()
        tasks_to_schedule = tasks_to_schedule.sort_values('production_quantity')

        for i, (_, task) in enumerate(tasks_to_schedule.iterrows()):
            equip = equip_names[i % len(equip_names)]
            capacity = equip_capacities.get(equip, 1)
            days = max(1, int(np.ceil(task['production_quantity'] / capacity)))
            start = current_time.strftime("%Y-%m-%d %H:%M:%S")
            end = (current_time + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute(
                '''
                UPDATE production_tasks SET task_status='已排程', assigned_equipment=?, start_date=?, end_date=?
                WHERE task_id=?
                ''',
                (equip, start, end, task['task_id'])
            )
            self.cursor.execute(
                '''
                INSERT INTO schedule_history (task_id, equipment_name, start_time, end_time, schedule_type)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (task['task_id'], equip, start, end, 'auto')
            )
            schedule_count += 1
            current_time += timedelta(hours=8)

        self.conn.commit()
        return f"排程完成！成功排程 {schedule_count} 个任务，物料不足 {len(df_tasks) - schedule_count} 个。"


class OptimizedScheduler(ProductionScheduler):
    def _score_equipment(self, task, equip, task_priority=5):
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
            enough, shortages = self.calculator.check_material_enough(task, df_materials)
            task_list.append({
                'task_id': task['task_id'],
                'task_name': task['task_name'],
                'product_name': task['product_name'],
                'quantity': task['production_quantity'],
                'enough': enough,
                'shortages': shortages,
                'priority': priorities.get(task['task_id'], int(task.get('priority', 5))) if priorities else int(task.get('priority', 5))
            })

        schedulable = [t for t in task_list if t['enough']]
        if not schedulable:
            shortage_msgs = [
                f"任务 {t['task_name']} 物料不足: {', '.join(t['shortages'])}"
                for t in task_list if not t['enough']
            ]
            return "物料不足，无法排程：\n" + "\n".join(shortage_msgs)

        if strategy == 'shortest':
            schedulable.sort(key=lambda x: x['quantity'])
        elif strategy == 'utilization':
            schedulable.sort(key=lambda x: -x['quantity'])
        elif strategy == 'priority':
            schedulable.sort(key=lambda x: (-x['priority'], x['quantity']))
        else:
            return "未知策略"

        equip_list = df_equip.to_dict('records')
        equip_capacities = {e['equip_name']: e['capacity_daily'] for e in equip_list}
        current_time = datetime.now()
        equip_available_time = {name: current_time for name in equip_capacities}
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

            capacity = equip_capacities.get(best_equip, 1)
            days = max(1, int(np.ceil(task['quantity'] / capacity)))
            start_time = max(equip_available_time[best_equip], current_time)
            end_time = start_time + timedelta(days=days)
            start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
            end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")

            self.cursor.execute(
                '''
                UPDATE production_tasks SET task_status='已排程', assigned_equipment=?, start_date=?, end_date=?
                WHERE task_id=?
                ''',
                (best_equip, start_str, end_str, task['task_id'])
            )
            self.cursor.execute(
                '''
                INSERT INTO schedule_history (task_id, equipment_name, start_time, end_time, schedule_type)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (task['task_id'], best_equip, start_str, end_str, strategy)
            )
            equip_available_time[best_equip] = end_time + timedelta(hours=8)
            schedule_count += 1

        self.conn.commit()
        return f"优化排程完成（策略：{strategy}）！成功排程 {schedule_count} 个任务，物料不足 {len(df_tasks) - schedule_count} 个。"
