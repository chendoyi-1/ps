import pandas as pd
from scheduler import MaterialRequirementCalculator


class LocalQnA:
    def __init__(self, conn):
        self.conn = conn
        self.calculator = MaterialRequirementCalculator(conn)

    def answer(self, question: str):
        q = question.lower()
        df_tasks = pd.read_sql("SELECT * FROM production_tasks WHERE task_status='待排程'", self.conn)
        df_materials = pd.read_sql("SELECT * FROM material_info", self.conn)

        if "物料短缺" in q:
            if df_tasks.empty:
                return "暂无待排程任务，无需检查物料短缺。"
            shortages = []
            for _, task in df_tasks.iterrows():
                enough, msgs = self.calculator.check_material_enough(task, df_materials)
                if not enough:
                    shortages.append(f"任务「{task['task_name']}」物料不足：{', '.join(msgs)}")
            return "以下任务物料短缺：\n" + "\n".join(shortages) if shortages else "所有待排程任务物料充足。"

        if "排程完成率" in q:
            total = pd.read_sql("SELECT COUNT(*) as cnt FROM production_tasks", self.conn).iloc[0]['cnt']
            scheduled = pd.read_sql("SELECT COUNT(*) as cnt FROM production_tasks WHERE task_status='已排程'", self.conn).iloc[0]['cnt']
            rate = (scheduled / total * 100) if total > 0 else 0
            return f"排程完成率：{rate:.1f}%（总任务 {total}，已排程 {scheduled}）"

        if "设备利用率" in q:
            df_equip = pd.read_sql("SELECT * FROM equipment_info", self.conn)
            total_cap = df_equip['capacity_daily'].sum() if not df_equip.empty else 0
            used_cap = 0
            df_scheduled = pd.read_sql("SELECT * FROM production_tasks WHERE task_status='已排程'", self.conn)
            for _, task in df_scheduled.iterrows():
                equip = task.get('assigned_equipment')
                if equip and equip in df_equip['equip_name'].values:
                    used_cap += df_equip.loc[df_equip['equip_name'] == equip, 'capacity_daily'].iloc[0]
            utilization = (used_cap / total_cap * 100) if total_cap > 0 else 0
            return f"设备利用率约为 {utilization:.1f}%。可用设备 {len(df_equip[df_equip['equip_status'] == '正常'])} 台。"

        return "请尝试询问物料短缺、排程完成率或设备利用率。"
