#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断"任务趋势分析"功能的问题
"""

import sqlite3
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

def diagnose_production_tasks():
    """诊断生产任务表的数据结构"""
    print("=" * 70)
    print("诊断 1: 查看生产任务表数据结构")
    print("=" * 70)
    
    try:
        conn = sqlite3.connect("production_system.db", check_same_thread=False)
        df = pd.read_sql("SELECT * FROM production_tasks LIMIT 5", conn)
        
        print(f"\n数据列: {', '.join(df.columns.tolist())}")
        print(f"数据行数: {len(df)}")
        print(f"\n数据类型:")
        print(df.dtypes)
        print(f"\n前 3 行数据:")
        print(df.head(3).to_string())
        
        return df
    except Exception as e:
        print(f"✗ 错误: {str(e)}")
        return None

def test_trend_analysis_prompt(df):
    """测试趋势分析的 prompt"""
    print("\n" + "=" * 70)
    print("诊断 2: 测试趋势分析 prompt")
    print("=" * 70)
    
    if df is None or df.empty:
        print("✗ 没有数据可用")
        return
    
    summary = df.head(10).to_string()
    cols = list(df.columns)
    
    prompt = f"""
你是一个专业的数据可视化专家。基于以下生产任务数据，请生成一段Python代码，使用plotly.express绘制图表。

数据已经在变量 df 中提供，这是一个 pandas DataFrame：
数据列：{cols}
数据样例：
{summary}

可视化风格需求：使用折线图、面积图等展示数据趋势变化

重要提示：
- 数据已经存储在 df 变量中，直接使用它，不要重新创建 DataFrame
- 代码会在已导入 pandas (pd)、plotly.express (px)、plotly.graph_objects (go)、numpy (np) 的环境中执行
- 不需要写 import 语句，这些库已经可用
- 直接使用 df、pd、px、go、np

要求：
1. 只返回Python代码，不要包含任何解释、注释或markdown符号
2. 代码必须定义变量 fig，例如 fig = px.line(df, ...) 或 fig = px.area(df, ...)
3. 不要写任何 import 语句，不要重新创建 df DataFrame
4. 使用 plotly.express (px) 的折线图或面积图展示趋势
5. 所有轴标签、图例标题必须使用中文
6. 如果没有时间序列列，可以按 task_id 或其他数值列创建趋势

代码：
"""
    
    print("\n发送 prompt 到 AI...")
    response, success = call_deepseek_api(prompt, temperature=0.2, max_tokens=800)
    
    if success:
        print("✓ 收到 AI 响应")
        print(f"\nAI 生成的代码:\n{response[:500]}...")
        return response
    else:
        print(f"✗ API 调用失败: {response}")
        return None

def test_code_execution(code, df):
    """测试代码执行"""
    print("\n" + "=" * 70)
    print("诊断 3: 测试代码执行")
    print("=" * 70)
    
    if code is None:
        print("✗ 没有代码可执行")
        return None
    
    # 清理代码
    code = code.strip()
    if code.startswith("```python"):
        code = code[9:]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    code = code.strip()
    
    # 过滤掉 import 和 df 重新赋值
    code_lines = []
    for line in code.split('\n'):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            continue
        if stripped.startswith('df ') and '= pd.DataFrame' in stripped:
            continue
        code_lines.append(line)
    code = '\n'.join(code_lines)
    
    print(f"处理后的代码:\n{code[:300]}...")
    
    try:
        print("\n尝试执行代码...")
        exec_globals = {
            'pd': pd, 
            'px': px, 
            'go': go, 
            'np': np, 
            'df': df
        }
        exec(code, exec_globals)
        fig = exec_globals.get('fig', None)
        
        if fig is not None:
            print("✓ 代码执行成功，图表生成完成")
            return fig
        else:
            print("✗ 图表对象未定义")
            return None
    except Exception as e:
        print(f"✗ 代码执行失败: {str(e)}")
        # 打印更详细的错误信息
        import traceback
        print("\n错误追踪:")
        print(traceback.format_exc())
        return None

def suggest_improvements(df):
    """建议改进方案"""
    print("\n" + "=" * 70)
    print("建议改进方案")
    print("=" * 70)
    
    if df is None or df.empty:
        print("✗ 没有数据")
        return
    
    print("\n当前数据分析:")
    print(f"- 行数: {len(df)}")
    print(f"- 列数: {len(df.columns)}")
    print(f"- 列名: {', '.join(df.columns.tolist())}")
    
    # 检查时间相关列
    time_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    print(f"\n- 时间列: {time_cols if time_cols else '无'}")
    print(f"- 数值列: {numeric_cols if numeric_cols else '无'}")
    
    if not time_cols and not numeric_cols:
        print("\n⚠️ 警告：没有找到适合趋势分析的列")
        print("需要时间序列数据或数值列来创建趋势图")
    else:
        print("\n✓ 有可用的列用于趋势分析")
        if time_cols:
            print(f"  建议使用 {time_cols[0]} 作为 X 轴")
        if numeric_cols:
            print(f"  建议使用 {numeric_cols[0]} 作为 Y 轴")

def main():
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  任务趋势分析功能诊断".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    # 诊断步骤
    df = diagnose_production_tasks()
    
    if df is not None and not df.empty:
        suggest_improvements(df)
        code = test_trend_analysis_prompt(df)
        if code:
            fig = test_code_execution(code, df)
            if fig:
                print("\n" + "=" * 70)
                print("✓ 诊断完成：功能正常")
                print("=" * 70)
            else:
                print("\n" + "=" * 70)
                print("✗ 诊断完成：代码执行失败")
                print("=" * 70)
        else:
            print("\n" + "=" * 70)
            print("✗ 诊断完成：AI 生成失败")
            print("=" * 70)
    else:
        print("\n✗ 数据库中没有生产任务数据")
        print("请先在应用中导入生产任务数据")

if __name__ == "__main__":
    main()
