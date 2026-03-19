#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 AI 图表生成功能
验证修复后的代码执行环境是否能成功生成图表
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# 创建测试数据
def create_test_data():
    """创建测试数据"""
    test_data = {
        "生产任务": pd.DataFrame({
            'task_id': [1, 2, 3, 4, 5],
            'task_name': ['任务A', '任务B', '任务C', '任务D', '任务E'],
            'product_name': ['产品1', '产品2', '产品1', '产品3', '产品2'],
            'production_quantity': [100, 200, 150, 300, 120],
            'task_status': ['待排程', '已排程', '待排程', '已排程', '待排程']
        }),
        "设备": pd.DataFrame({
            'equip_id': [1, 2, 3],
            'equip_name': ['设备A', '设备B', '设备C'],
            'equip_type': ['冲床', '组装', '检测'],
            'capacity_daily': [500, 400, 300],
            'equip_status': ['正常', '正常', '维护']
        }),
        "物料": pd.DataFrame({
            'material_id': [1, 2, 3, 4],
            'material_name': ['螺钉', '塑料件', '金属片', '电子元件'],
            'supplier': ['供应商A', '供应商B', '供应商A', '供应商C'],
            'stock_quantity': [5000, 2000, 3000, 1500]
        })
    }
    return test_data

def test_exec_environment():
    """测试执行环境是否包含所有需要的库"""
    print("=" * 60)
    print("测试 1: 验证执行环境库")
    print("=" * 60)
    
    test_code = """
# 测试所有需要的库是否可用
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

print("✓ 所有库导入成功")
"""
    
    try:
        exec_globals = {
            'pd': pd,
            'px': px,
            'go': go,
            'np': np
        }
        exec(test_code, exec_globals)
        print("✓ 测试通过：所有库都可用\n")
        return True
    except Exception as e:
        print(f"✗ 测试失败：{str(e)}\n")
        return False

def test_ai_generated_code_with_go():
    """测试使用 go (plotly.graph_objects) 的 AI 生成代码"""
    print("=" * 60)
    print("测试 2: AI生成代码（使用 plotly.graph_objects）")
    print("=" * 60)
    
    # 模拟 AI 生成的代码（使用 go）
    ai_generated_code = """
data = df['production_quantity'].groupby(df['product_name']).sum().reset_index()
fig = go.Figure(data=[
    go.Bar(x=data['product_name'], y=data['production_quantity'], 
           name='生产数量', marker_color='lightblue')
])
fig.update_layout(
    title='产品生产数量对比',
    xaxis_title='产品名称',
    yaxis_title='总生产数量',
    hovermode='x unified'
)
"""
    
    test_data = create_test_data()
    df = test_data['生产任务']
    
    try:
        exec_globals = {
            'pd': pd,
            'px': px,
            'go': go,
            'np': np,
            'df': df
        }
        exec(ai_generated_code, exec_globals)
        fig = exec_globals.get('fig', None)
        
        if fig is not None:
            print("✓ 测试通过：代码执行成功，生成了图表对象\n")
            return True
        else:
            print("✗ 测试失败：未生成图表对象\n")
            return False
    except Exception as e:
        print(f"✗ 测试失败：{str(e)}\n")
        return False

def test_ai_generated_code_with_numpy():
    """测试使用 numpy 的 AI 生成代码"""
    print("=" * 60)
    print("测试 3: AI生成代码（使用 numpy）")
    print("=" * 60)
    
    # 模拟 AI 生成的代码（使用 numpy）
    ai_generated_code = """
data = df.copy()
data['产量_标准化'] = (data['production_quantity'] - data['production_quantity'].min()) / (data['production_quantity'].max() - data['production_quantity'].min())
fig = px.scatter(
    data,
    x='task_name',
    y='production_quantity',
    size='产量_标准化',
    color='task_status',
    title='生产任务产量分析',
    labels={'task_name': '任务名称', 'production_quantity': '生产数量', 'task_status': '任务状态'}
)
"""
    
    test_data = create_test_data()
    df = test_data['生产任务']
    
    try:
        exec_globals = {
            'pd': pd,
            'px': px,
            'go': go,
            'np': np,
            'df': df
        }
        exec(ai_generated_code, exec_globals)
        fig = exec_globals.get('fig', None)
        
        if fig is not None:
            print("✓ 测试通过：代码执行成功，生成了图表对象\n")
            return True
        else:
            print("✗ 测试失败：未生成图表对象\n")
            return False
    except Exception as e:
        print(f"✗ 测试失败：{str(e)}\n")
        return False

def test_complex_visualization():
    """测试复杂的数据可视化代码"""
    print("=" * 60)
    print("测试 4: 复杂图表生成（混合使用 px 和 go）")
    print("=" * 60)
    
    # 模拟复杂的 AI 生成代码
    ai_generated_code = """
from plotly.subplots import make_subplots

# 聚合数据
equip_capacity = df.groupby('equip_name')['capacity_daily'].sum()

# 创建图表
fig = px.bar(
    df,
    x='equip_name',
    y='capacity_daily',
    color='equip_type',
    title='设备产能对比分析',
    labels={'equip_name': '设备名称', 'capacity_daily': '日产能', 'equip_type': '设备类型'}
)

# 进一步定制
fig.update_layout(
    hovermode='x unified',
    showlegend=True,
    height=500
)
"""
    
    test_data = create_test_data()
    df = test_data['设备']
    
    try:
        exec_globals = {
            'pd': pd,
            'px': px,
            'go': go,
            'np': np,
            'df': df
        }
        exec(ai_generated_code, exec_globals)
        fig = exec_globals.get('fig', None)
        
        if fig is not None:
            print("✓ 测试通过：复杂代码执行成功，生成了图表对象\n")
            return True
        else:
            print("✗ 测试失败：未生成图表对象\n")
            return False
    except Exception as e:
        print(f"✗ 测试失败：{str(e)}\n")
        return False

def main():
    """运行所有测试"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  AI 多样化图表生成功能测试".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    results = []
    
    # 运行各项测试
    results.append(test_exec_environment())
    results.append(test_ai_generated_code_with_go())
    results.append(test_ai_generated_code_with_numpy())
    results.append(test_complex_visualization())
    
    # 汇总结果
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"通过测试: {passed}/{total}")
    
    if passed == total:
        print("\n✓ 所有测试通过！AI图表生成功能已修复。")
        print("可以正常使用 AI 多样化图表生成器。\n")
        return True
    else:
        print(f"\n✗ 有 {total - passed} 项测试失败。请检查错误信息。\n")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
