#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 DeepSeek API 是否正常工作
诊断 AI 图表生成失败的原因
"""

import requests
import json

# API 配置
DEEPSEEK_API_KEY = "sk-5545acb4abb541008691f1f9de8b4671"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

def test_api_connection():
    """测试 API 基本连接"""
    print("=" * 70)
    print("测试 1: API 基本连接")
    print("=" * 70)
    
    try:
        response = requests.get("https://api.deepseek.com", timeout=5)
        print("✓ 可以访问 DeepSeek 服务器")
        return True
    except Exception as e:
        print(f"✗ 无法访问 DeepSeek 服务器: {str(e)}")
        return False

def test_api_credentials():
    """测试 API 凭证"""
    print("\n" + "=" * 70)
    print("测试 2: API 凭证验证")
    print("=" * 70)
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": "你好"}],
        "temperature": 0.3,
        "max_tokens": 100,
        "stream": False
    }
    
    print(f"API 密钥: {DEEPSEEK_API_KEY[:20]}...{DEEPSEEK_API_KEY[-5:]}")
    print(f"API 模型: {DEEPSEEK_MODEL}")
    print(f"API URL: {DEEPSEEK_API_URL}")
    
    try:
        print("\n发送请求中...")
        response = requests.post(
            DEEPSEEK_API_URL, 
            headers=headers, 
            json=payload, 
            timeout=30
        )
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✓ API 认证成功")
            
            # 检查响应结构
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                print(f"✓ 收到响应内容: {content[:100]}...")
                return True
            else:
                print(f"✗ 响应结构异常: {json.dumps(result, indent=2, ensure_ascii=False)}")
                return False
        else:
            print(f"✗ API 返回错误状态: {response.status_code}")
            print(f"错误信息: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print("✗ 请求超时（30秒未响应）")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"✗ 连接错误: {str(e)}")
        return False
    except json.JSONDecodeError as e:
        print(f"✗ JSON 解析失败: {str(e)}")
        return False
    except Exception as e:
        print(f"✗ 未知错误: {str(e)}")
        return False

def test_chart_generation_prompt():
    """测试图表生成提示词"""
    print("\n" + "=" * 70)
    print("测试 3: 模拟图表生成请求")
    print("=" * 70)
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 简化的提示词
    prompt = """
你是一个数据可视化专家。请生成一段 Python 代码，使用 plotly.express 绘制柱状图。

要求：
1. 只返回 Python 代码，不要包含任何解释或注释
2. 代码必须定义变量 fig
3. 所有标签必须使用中文

示例代码框架：
fig = px.bar(...)

代码：
"""
    
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 500,
        "stream": False
    }
    
    try:
        print("发送图表生成请求...")
        response = requests.post(
            DEEPSEEK_API_URL, 
            headers=headers, 
            json=payload, 
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print("✓ 成功获取 AI 代码生成响应")
            print(f"生成的代码片段:\n{content[:300]}...")
            return True
        else:
            print(f"✗ 图表生成请求失败: {response.status_code}")
            print(f"错误: {response.text[:300]}")
            return False
            
    except Exception as e:
        print(f"✗ 请求失败: {str(e)}")
        return False

def test_code_execution():
    """测试生成的代码是否能执行"""
    print("\n" + "=" * 70)
    print("测试 4: 生成代码的执行环境")
    print("=" * 70)
    
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    import numpy as np
    
    test_code = """
import pandas as pd
import plotly.express as px

# 创建测试数据
data = pd.DataFrame({
    'category': ['A', 'B', 'C'],
    'value': [10, 20, 15]
})

fig = px.bar(data, x='category', y='value', title='测试图表')
"""
    
    try:
        print("测试代码执行环境...")
        exec_globals = {
            'pd': pd,
            'px': px,
            'go': go,
            'np': np
        }
        exec(test_code, exec_globals)
        fig = exec_globals.get('fig', None)
        
        if fig is not None:
            print("✓ 代码执行环境正常，图表对象创建成功")
            return True
        else:
            print("✗ 图表对象未定义")
            return False
    except Exception as e:
        print(f"✗ 代码执行失败: {str(e)}")
        return False

def main():
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  DeepSeek API 和 AI 图表生成诊断".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    results = []
    
    # 运行所有测试
    results.append(("API 连接", test_api_connection()))
    results.append(("API 凭证", test_api_credentials()))
    results.append(("图表生成", test_chart_generation_prompt()))
    results.append(("执行环境", test_code_execution()))
    
    # 汇总结果
    print("\n" + "=" * 70)
    print("诊断结果汇总")
    print("=" * 70)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name:20} {status}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"\n总体状态: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n✓ 所有检查都通过。如果仍然无法生成图表，请检查:")
        print("  1. 网络连接是否稳定")
        print("  2. 是否有数据可用于生成图表")
        print("  3. AI 返回的代码是否包含 'import' 语句")
        return True
    else:
        print("\n✗ 检测到问题。建议步骤:")
        if not results[0][1]:
            print("  - 检查网络连接")
        if not results[1][1]:
            print("  - 检查 API 密钥是否有效")
            print("  - 检查 API 配额是否充足")
            print("  - 尝试使用新的 API 密钥")
        print("  - 查看错误日志获取更多信息")
        return False

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n诊断脚本出错: {str(e)}")
        exit(1)
