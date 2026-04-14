#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import traceback
import time
import os
import re
import requests

# ========== 配置 ==========
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

# 本地文件名称
IP_FILE = "cloudflare_ips.txt"

# 自动提取 IP 的正则
IP_PATTERN = re.compile(r'(\d+\.\d+\.\d+\.\d+)')

def load_ips_from_local():
    ips = []
    try:
        if not os.path.exists(IP_FILE):
            print(f"❌ 未找到文件: {IP_FILE}")
            return []
        with open(IP_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            match = IP_PATTERN.findall(line.strip())
            if match:
                ips.append(match[0])
    except Exception as e:
        print(f"读取 {IP_FILE} 失败：{e}")

    # 去重并保持顺序
    return list(dict.fromkeys(ips))

def get_dns_records(name):
    records = []
    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        data = res.json()
        if not data.get("success"):
            print(f"❌ 获取 DNS 记录失败: {data.get('errors')}")
            return []
        for item in data.get("result", []):
            if item.get("name") == name and item.get("type") == "A":
                records.append({"id": item["id"], "content": item.get("content", "")})
    except Exception as e:
        print(f"查询 DNS 异常: {e}")
    return records

def update_dns_record(record_info, name, cf_ip):
    record_id = record_info['id']
    current_ip = record_info.get('content', '')

    if current_ip == cf_ip:
        log = f"✅ IP 无变化 ({cf_ip})，无需更新"
        print(log)
        return log

    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_id}"
    data = {
        'type': 'A',
        'name': name,
        'content': cf_ip,
        'ttl': 60,
        'proxied': False
    }

    try:
        response = requests.put(url, headers=HEADERS, json=data, timeout=10)
        if response.status_code == 200:
            log = f"✅ 更新成功: {cf_ip}"
        else:
            log = f"❌ 更新失败: {response.text}"
    except Exception as e:
        log = f"❌ 更新异常: {e}"

    print(log)
    return log

def send_push(content):
    if not PUSHPLUS_TOKEN:
        return
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": "Cloudflare DNS 更新状态",
        "content": content,
        "template": "markdown"
    }
    try:
        requests.post(url, json=data, timeout=5)
    except:
        pass

def main():  
    # 1. 读取本地 IP
    ip_addresses = load_ips_from_local()
    if not ip_addresses:
        print("❌ 本地文件无有效 IP")
        return

    # 2. 获取第一个 IP
    target_ip = ip_addresses[0]
    print(f"🔹 目标 IP (列表第一个): {target_ip}")

    # 3. 获取并更新 DNS 记录
    dns_records = get_dns_records(CF_DNS_NAME)
    if not dns_records:
        print(f"❌ 未找到 {CF_DNS_NAME} 的 A 记录")
        send_push(f"❌ 更新失败：未找到 {CF_DNS_NAME} 的解析记录")
        return

    # 只更新第一条匹配的记录
    result_log = update_dns_record(dns_records[0], CF_DNS_NAME, target_ip)
    
    # 如果更新成功且不是“无变化”，则发送推送
    if "成功" in result_log:
        send_push(result_log)
    
    print("✅ 执行完成")

if __name__ == '__main__':
    main()
