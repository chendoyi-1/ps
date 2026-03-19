#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的 AI 图表生成功能测试
包括 API 调用、代码生成、代码执行等完整流程
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import requests
import json

# API 配置
DEEPSEEK_API_KEY = "sk-5545acb4abb541008691f1f9de8b4671"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

def call_deepseek_api(prompt, temperature=0.3, max_tokens=1500):
    """调用 DeepSeek API"""
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

def ai_generate_visualization(df, data_type, chart_style="自动选择"):
    """改进版本的 AI 图表生成函数"""
    if df.empty:
        return None, "无数据可生成图表"
    
    summary = df.head(10).to_string()
    cols = list(df.columns)
    
    style_hints = {
        "自动选择": "根据数据特征自动选择最合适的图表类型",
        "趋势分析": "使用折线图、面积图等展示数据趋势变化",
        "对比分析": "使用柱状图、雷达图等展示数据对比",
    }
    
    style_description = style_hints.get(chart_style, "")
    
    prompt = f"""
你是一个专业的数据可视化专家。基于以下{data_type}数据，请生成一段Python代码，使用plotly.express绘制图表。

数据列：{cols}
数据样例：
{summary}

可视化风格需求：{style_description}

重要提示：
- 代码会在已导入 pandas (pd)、plotly.express (px)、plotly.graph_objects (go)、numpy (np) 的环境中执行
- 不需要写 import 语句，这些库已经可用
- 直接使用 pd、px、go、np

要求：
1. 只返回Python代码，不要包含任何解释、注释或markdown符号
2. 代码必须定义变量 fig
3. 不要写任何 import 语句
4. 所有轴标签必须使用中文

代码：
"""
    
    print(f"正在调用 AI 生成 {data_type} 图表...")
    response, success = call_deepseek_api(prompt, temperature=0.2, max_tokens=800)
    
    if not success:
        return None, f"AI 调用失败: {response}"
    
    print(f"✓ 收到 AI 响应")
    
    # 解析响应
    code = response.strip()
    
    # 移除 markdown 代码块标记
    if code.startswith("```python"):
        code = code[9:]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    code = code.strip()
    
    print(f"生成的代码:\n{code[:200]}...\n")
    
    # 过滤掉 import 语句
    code_lines = []
    for line in code.split('\n'):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            print(f"  [过滤] {line}")
            continue
        code_lines.append(line)
    code = '\n'.join(code_lines)
    
    print(f"处理后的代码:\n{code[:200]}...\n")
    
    # 执行代码
    try:
        print("开始执行代码...")
        exec_globals = {
            'pd': pd, 
            'px': px, 
            'go': go, 
            'np': np, 
            'df': df
        }
        exec(code, exec_globals)
        fig = exec_globals.get('fig', None)
        
        if fig is None:
            return None, "AI生成的代码未定义fig变量"
        
        print("✓ 代码执行成功，图表生成完成")
        return fig, "AI生成图表成功"
        
    except Exception as e:
        error_msg = str(e)
        print(f"✗ 代码执行失败: {error_msg}")
        return None, f"代码执行失败: {error_msg}"

def main():
    print("\n")
    print("╔" + "=" * 70 + "╗")
    print("║" + " " * 70 + "║")
    print("║" + "  完整的 AI 图表生成功能测试".center(70) + "║")
    print("║" + " " * 70 + "║")
    print("╚" + "=" * 70 + "╝")
    print()
    
    # 准备测试数据
    print("=" * 70)
    print("准备测试数据")
    print("=" * 70)
    
    test_data = pd.DataFrame({
        'task_id': [1, 2, 3, 4, 5],
        'task_name': ['任务A', '任务B', '任务C', '任务D', '任务E'],
        'product_name': ['产品1', '产品2', '产品1', '产品3', '产品2'],
        'production_quantity': [100, 200, 150, 300, 120],
        'task_status': ['待排程', '已排程', '待排程', '已排程', '待排程']
    })
    
    print(f"✓ 创建了 {len(test_data)} 行测试数据")
    print(f"  数据列: {', '.join(test_data.columns.tolist())}\n")
    
    # 测试各种风格
    test_cases = [
        ("生产任务", test_data, "自动选择"),
        ("生产任务", test_data, "对比分析"),
    ]
    
    results = []
    
    for i, (data_type, df, style) in enumerate(test_cases, 1):
        print("=" * 70)
        print(f"测试 {i}: {data_type} - {style}")
        print("=" * 70)
        
        fig, msg = ai_generate_visualization(df, data_type, style)
        
        if fig is not None:
            print(f"✓ 测试通过: {msg}\n")
            results.append(True)
        else:
            print(f"✗ 测试失败: {msg}\n")
            results.append(False)
    
    # 汇总结果
    print("=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"通过测试: {passed}/{total}")
    
    if passed == total:
        print("\n✓ 所有测试通过！AI 图表生成功能工作正常。")
        return True
    else:
        print(f"\n✗ 有 {total - passed} 项测试失败。")
        return False

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n测试脚本出错: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)
