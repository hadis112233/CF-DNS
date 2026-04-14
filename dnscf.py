#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import requests

# ========== 1. 配置（确保环境变量已设置） ==========
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

IP_FILE = "cloudflare_ips.txt"
HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

def get_first_line_ip():
    """
    严格按照行顺序读取，获取文件中出现的第一个 IP 后立即返回
    """
    if not os.path.exists(IP_FILE):
        print(f"❌ 错误：找不到文件 {IP_FILE}")
        return None

    # 匹配 IP 的正则表达式
    ip_pattern = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')

    try:
        with open(IP_FILE, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                match = ip_pattern.search(line)
                if match:
                    found_ip = match.group(1)
                    print(f"📍 在第 {line_num} 行锁定目标 IP: {found_ip}")
                    return found_ip # 核心：一旦找到第一个 IP，立即结束函数并返回
    except Exception as e:
        print(f"❌ 读取文件异常: {e}")
    return None

def update_cloudflare_dns(new_ip):
    """
    更新 Cloudflare 记录
    """
    # 1. 获取 DNS 记录 ID
    list_url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
    try:
        res = requests.get(list_url, headers=HEADERS, timeout=10).json()
        if not res.get("success"):
            print("❌ 获取记录失败，请检查 TOKEN 和 ZONE_ID")
            return

        # 筛选出名字匹配且类型为 A 的记录
        records = [r for r in res.get("result", []) if r['name'] == CF_DNS_NAME and r['type'] == 'A']
        
        if not records:
            print(f"❌ 未找到域名 {CF_DNS_NAME} 的 A 记录")
            return

        # 2. 逐个更新（防止有多条记录导致显示不一致）
        for rec in records:
            if rec['content'] == new_ip:
                print(f"✅ 记录 {rec['id'][:6]} 已是最新 IP，跳过更新")
                continue

            update_url = f"{list_url}/{rec['id']}"
            data = {
                "type": "A",
                "name": CF_DNS_NAME,
                "content": new_ip,
                "ttl": 60,
                "proxied": False
            }
            put_res = requests.put(update_url, headers=HEADERS, json=data, timeout=10).json()
            
            if put_res.get("success"):
                print(f"🚀 成功更新记录: {new_ip}")
                send_push(f"✅ DNS 更新成功\n域名: {CF_DNS_NAME}\n新 IP: {new_ip}")
            else:
                print(f"❌ 更新失败: {put_res.get('errors')}")

    except Exception as e:
        print(f"❌ 网络请求异常: {e}")

def send_push(content):
    if not PUSHPLUS_TOKEN: return
    try:
        requests.post("http://www.pushplus.plus/send", json={
            "token": PUSHPLUS_TOKEN,
            "title": "Cloudflare DDNS 结果",
            "content": content,
            "template": "markdown"
        }, timeout=5)
    except:
        pass

def main():
    # 只要第一行的 IP
    target_ip = get_first_line_ip()
    
    if target_ip:
        update_cloudflare_dns(target_ip)
    else:
        print("❌ 未能从文件中提取到 IP 地址")

if __name__ == "__main__":
    main()
