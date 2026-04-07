import pandas as pd

COLUMN_NAME_MAP = {
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
    'equip_id': '设备ID',
    'equip_name': '设备名称',
    'equip_type': '设备类型',
    'capacity_daily': '日产能',
    'equip_status': '设备状态',
    'maintenance_time': '维护时间',
    'last_maintenance': '上次维护',
    'next_maintenance': '下次维护',
    'utilization_rate': '利用率',
    'material_id': '物料ID',
    'material_name': '物料名称',
    'supplier': '供应商',
    'stock_quantity': '库存数量',
    'safety_stock': '安全库存',
    'lead_time': '采购周期',
    'unit_price': '单价',
    'update_time': '更新时间',
    'schedule_id': '排程ID',
    'equipment_name': '设备名称',
    'start_time': '开始时间',
    'end_time': '结束时间',
    'schedule_type': '排程类型',
    'bom_id': 'BOM ID',
    'quantity_per_unit': '单位用量',
}


class FieldMapper:
    TASK_MAPPINGS = {
        '任务名称': 'task_name',
        '产品': 'product_name',
        '数量': 'production_quantity',
        '负责人': 'responsible_person',
        '开始时间': 'start_date',
        '结束时间': 'end_date',
        '优先级': 'priority',
        '所需物料': 'material_required',
    }
    EQUIP_MAPPINGS = {
        '设备名称': 'equip_name',
        '设备类型': 'equip_type',
        '日产能': 'capacity_daily',
        '维护时间': 'maintenance_time',
        '设备状态': 'equip_status',
    }
    MATERIAL_MAPPINGS = {
        '物料名称': 'material_name',
        '供应商': 'supplier',
        '库存数量': 'stock_quantity',
        '采购周期': 'lead_time',
        '安全库存': 'safety_stock',
        '单价': 'unit_price',
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
    def map_columns(cls, df: pd.DataFrame, data_type: str):
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


def read_csv_with_encodings(uploaded_file):
    for encoding in ["utf-8-sig", "gbk", "utf-8", "latin1"]:
        try:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding=encoding)
        except Exception:
            continue
    raise ValueError("无法读取CSV文件，可能是编码或格式问题")


def import_csv_with_preview(uploaded_file, data_type):
    try:
        df = read_csv_with_encodings(uploaded_file)
    except Exception:
        return None, {}, [], [], False
    df, mapped, unused, missing = FieldMapper.map_columns(df, data_type)
    return df, mapped, unused, missing, True


def format_col_name(col):
    return COLUMN_NAME_MAP.get(col, col)


def df_columns_to_chinese(df: pd.DataFrame):
    rename_dict = {col: format_col_name(col) for col in df.columns}
    return df.rename(columns=rename_dict)
