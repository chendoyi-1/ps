import tempfile
import os
import pandas as pd
from database import init_database
from data_utils import FieldMapper, import_csv_with_preview
from ai_utils import create_default_chart


def test_database_init():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp_path = tmp.name
    try:
        conn = init_database(tmp_path)
        assert conn is not None
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='production_tasks'")
        assert cursor.fetchone() is not None
    finally:
        conn.close()
        os.remove(tmp_path)


def test_field_mapper():
    df = pd.DataFrame({'任务名称': ['A'], '产品': ['P'], '数量': [1]})
    df, mapped, unused, missing = FieldMapper.map_columns(df, '任务')
    assert df.columns.tolist() == ['task_name', 'product_name', 'production_quantity']
    assert missing == []
    assert mapped == {'task_name': '任务名称', 'product_name': '产品', 'production_quantity': '数量'}


def test_create_default_chart():
    df = pd.DataFrame({'task_status': ['待排程', '已排程']})
    fig = create_default_chart(df, '生产任务')
    assert fig is not None


if __name__ == '__main__':
    test_database_init()
    test_field_mapper()
    test_create_default_chart()
    print('所有模块测试通过')
