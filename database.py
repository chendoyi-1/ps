import sqlite3
from config import DATABASE_PATH

TABLE_DEFINITIONS = [
    '''
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
    )''',
    '''
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
    )''',
    '''
    CREATE TABLE IF NOT EXISTS material_info (
        material_id INTEGER PRIMARY KEY AUTOINCREMENT,
        material_name TEXT NOT NULL,
        supplier TEXT NOT NULL,
        stock_quantity INTEGER NOT NULL DEFAULT 0,
        safety_stock INTEGER DEFAULT 1000,
        lead_time INTEGER DEFAULT 1,
        unit_price REAL DEFAULT 0,
        update_time TEXT DEFAULT CURRENT_TIMESTAMP
    )''',
    '''
    CREATE TABLE IF NOT EXISTS schedule_history (
        schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        equipment_name TEXT,
        start_time TEXT,
        end_time TEXT,
        schedule_type TEXT,
        create_time TEXT DEFAULT CURRENT_TIMESTAMP
    )''',
    '''
    CREATE TABLE IF NOT EXISTS bom_info (
        bom_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        material_name TEXT NOT NULL,
        quantity_per_unit REAL NOT NULL,
        create_time TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_name, material_name)
    )'''
]


def init_database(db_path: str = DATABASE_PATH):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    create_tables(conn)
    return conn


def create_tables(conn):
    cursor = conn.cursor()
    for statement in TABLE_DEFINITIONS:
        cursor.execute(statement)
    conn.commit()
