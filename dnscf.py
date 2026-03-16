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

# 自动提取 IP
IP_PATTERN = re.compile(r'(\d+\.\d+\.\d+\.\d+)')

def load_ips_from_local():
    ips = []
    try:
        with open(IP_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = IP_PATTERN.findall(line)
            if match:
                ips.append(match[0])
    except Exception as e:
        print(f"读取 {IP_FILE} 失败：{e}")

    ips = list(set(ips))
    return ips

def get_dns_records(name):
    records = []
    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        for item in res.json().get("result", []):
            if item.get("name") == name and item.get("type") == "A":
                records.append({"id": item["id"], "content": item.get("content", "")})
    except:
        pass
    return records

def update_dns_record(record_info, name, cf_ip):
    record_id = record_info['id']
    current_ip = record_info.get('content', '')

    if current_ip == cf_ip:
        log = f"✅ {cf_ip} 已是最新"
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
            log = f"✅ {cf_ip} 更新成功"
        else:
            log = f"❌ {cf_ip} 更新失败"
    except:
        log = f"❌ {cf_ip} 更新异常"

    print(log)
    return log

def send_push(content):
    if not PUSHPLUS_TOKEN:
        return
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": "✅ Cloudflare DNS 更新结果",
        "content": content,
        "template": "markdown"
    }
    try:
        requests.post(url, json=data)
    except:
        pass

def main():
   ip_addresses_str = get_cf_speed_test_ip()
    if not ip_addresses_str:
        print("错误: 无法获取优选 IP")
        return
    
    # 读取本地IP
    ip_addresses = load_ips_from_local()
    if not ip_addresses:
        print("❌ 本地文件无有效IP")
        send_push("❌ DNS 更新失败：无有效IP")
        return

    # 获取DNS记录
    dns_records = get_dns_records(CF_DNS_NAME)
    if not dns_records:
        print(f"❌ 未找到 {CF_DNS_NAME} 的 DNS 记录")
        send_push("❌ DNS 更新失败：未找到记录")
        return

    # ======================
    # 你要的 记录数量检查 已加上
    # ======================
    if len(ip_addresses) > len(dns_records):
        print(f"警告: IP 数量({len(ip_addresses)})超过 DNS 记录数量({len(dns_records)})，只更新前 {len(dns_records)} 个")
        ip_addresses = ip_addresses[:len(dns_records)]

    # 开始更新
    push_content = []
    for index, ip_address in enumerate(ip_addresses):
        result = update_dns_record(dns_records[index], CF_DNS_NAME, ip_address)
        push_content.append(result)

    send_push("\n".join(push_content))
    print("✅ 执行完成")

if __name__ == '__main__':
    main()
