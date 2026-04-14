#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

IP_FILE = "cloudflare_ips.txt"
# 更加严谨的 IP 匹配正则
IP_PATTERN = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')

def load_first_ip():
    """
    严格按照行序读取，拿到第一个有效 IP 后立即返回
    """
    try:
        if not os.path.exists(IP_FILE):
            print(f"❌ 错误：找不到文件 {IP_FILE}")
            return None
            
        with open(IP_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # 在这一行中查找 IP
                match = IP_PATTERN.search(line)
                if match:
                    found_ip = match.group(1)
                    print(f"📍 成功锁定第一行有效 IP: {found_ip}")
                    return found_ip
    except Exception as e:
        print(f"❌ 读取文件时出错: {e}")
    return None

def get_dns_records(name):
    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res_json = res.json()
        if not res_json.get("success"):
            return []
        return [item for item in res_json.get("result", []) 
                if item.get("name") == name and item.get("type") == "A"]
    except:
        return []

def update_dns_record(record_info, name, cf_ip):
    record_id = record_info['id']
    current_ip = record_info.get('content', '')

    if current_ip == cf_ip:
        print(f"ℹ️ 当前 DNS 已经是 {cf_ip}，无需变动。")
        return None

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
            return f"✅ DNS 已更新为首行 IP: {cf_ip}"
        return f"❌ 更新失败: {response.text}"
    except:
        return "❌ Cloudflare 接口请求异常"

def send_push(content):
    if not PUSHPLUS_TOKEN or not content:
        return
    try:
        requests.post("http://www.pushplus.plus/send", json={
            "token": PUSHPLUS_TOKEN,
            "title": "Cloudflare DNS 自动更新",
            "content": content,
            "template": "markdown"
        }, timeout=5)
    except:
        pass

def main():
    # 1. 严格获取第一个 IP
    target_ip = load_first_ip()
    
    if not target_ip:
        print("❌ 无法从文件中提取到任何有效 IP")
        return

    # 2. 获取 Cloudflare 现有的记录
    records = get_dns_records(CF_DNS_NAME)
    if not records:
        print(f"❌ 未能找到域名 {CF_DNS_NAME} 的 A 记录")
        return

    # 3. 执行更新
    msg = update_dns_record(records[0], CF_DNS_NAME, target_ip)
    
    if msg:
        print(msg)
        send_push(msg)
    else:
        print("✨ 任务结束，保持现状")

if __name__ == '__main__':
    main()
