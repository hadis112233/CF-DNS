#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import requests

# ========== 1. 配置（请确保环境变量已设置） ==========
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

# 本地文件名
IP_FILE = "cloudflare_ips.txt"

HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

# 匹配 IP 的正则
IP_PATTERN = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')

def load_first_ip_from_file():
    """
    严格读取本地文件第一行
    """
    if not os.path.exists(IP_FILE):
        print(f"❌ 错误：找不到本地文件 {IP_FILE}")
        return None

    try:
        with open(IP_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                match = IP_PATTERN.search(line)
                if match:
                    found_ip = match.group(1)
                    print(f"📍 成功从文件第一行提取 IP: {found_ip}")
                    return found_ip
    except Exception as e:
        print(f"❌ 读取文件异常: {e}")
    return None

def get_dns_records(name):
    """
    获取 Cloudflare 中该域名所有的 A 记录
    """
    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res_json = res.json()
        if res_json.get("success"):
            # 找出所有名字相同且类型为 A 的记录
            return [r for r in res_json.get("result", []) 
                    if r.get("name") == name and r.get("type") == "A"]
    except Exception as e:
        print(f"❌ 获取 Cloudflare 记录异常: {e}")
    return []

def update_dns_record(record_id, name, new_ip):
    """
    执行具体的更新操作
    """
    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_id}"
    data = {
        'type': 'A',
        'name': name,
        'content': new_ip,
        'ttl': 60,
        'proxied': False
    }
    try:
        res = requests.put(url, headers=HEADERS, json=data, timeout=10)
        return res.status_code == 200
    except:
        return False

def send_push(content):
    if not PUSHPLUS_TOKEN: return
    try:
        requests.post("http://www.pushplus.plus/send", json={
            "token": PUSHPLUS_TOKEN,
            "title": "Cloudflare IP 更新结果",
            "content": content,
            "template": "markdown"
        }, timeout=5)
    except:
        pass

def main():
    # 1. 从文件获取第一个 IP
    target_ip = load_first_ip_from_file()
    if not target_ip:
        return

    # 2. 获取现有的 DNS 记录
    records = get_dns_records(CF_DNS_NAME)
    if not records:
        print(f"❌ 未在 Cloudflare 发现域名 {CF_DNS_NAME} 的 A 记录")
        return

    # 3. 更新所有匹配的记录（防止有多条记录导致显示不一致）
    updated_count = 0
    for rec in records:
        # 如果 IP 已经一致，跳过
        if rec.get('content') == target_ip:
            print(f"ℹ️ 记录 {rec['id'][:6]} 已是最新，无需更新")
            continue
            
        if update_dns_record(rec['id'], CF_DNS_NAME, target_ip):
            print(f"✅ 记录 {rec['id'][:6]} 更新成功 -> {target_ip}")
            updated_count += 1
        else:
            print(f"❌ 记录 {rec['id'][:6]} 更新失败")

    # 4. 推送结果
    if updated_count > 0:
        msg = f"成功将域名 `{CF_DNS_NAME}` 更新为文件首行 IP: `{target_ip}`"
        send_push(msg)
    else:
        print("✨ 检查完毕，所有记录均无需变动")

if __name__ == '__main__':
    main()
