#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import time
import requests

# 配置
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")

HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

# 本地 IP 文件路径（你自己放仓库里）
IP_FILE_PATH = "cloudflare_ips.txt"

# 匹配 IPv4
IP_REGEX = re.compile(r'^\d+\.\d+\.\d+\.\d+$')

def load_ips_from_file():
    """从本地TXT读取IP，自动去掉 :443"""
    ips = []
    try:
        with open(IP_FILE_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 自动去掉 :443
            if ":443" in line:
                line = line.replace(":443", "")

            # 只保留合法IP
            if IP_REGEX.match(line):
                ips.append(line)

    except Exception as e:
        print(f"读取IP文件失败: {e}")
        return []

    return ips

def get_dns_records(name):
    """获取现有A记录"""
    records = []
    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        for r in res.json()["result"]:
            if r["name"] == name and r["type"] == "A":
                records.append({"id": r["id"], "content": r["content"]})
    except:
        pass
    return records

def update_dns(record_id, name, ip):
    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_id}"
    data = {
        "type": "A",
        "name": name,
        "content": ip,
        "ttl": 60,
        "proxied": False
    }
    try:
        r = requests.put(url, json=data, headers=HEADERS, timeout=10)
        return r.status_code == 200
    except:
        return False

def main():
    ips = load_ips_from_file()
    if not ips:
        print("没有获取到有效IP")
        return

    records = get_dns_records(CF_DNS_NAME)
    if not records:
        print("未找到DNS记录")
        return

    print(f"成功加载IP: {len(ips)} 个")
    print(f"可更新记录: {len(records)} 条")

    count = min(len(ips), len(records))
    for i in range(count):
        ip = ips[i]
        record = records[i]
        if record["content"] == ip:
            print(f"✅ {ip} 已是最新")
            continue

        ok = update_dns(record["id"], CF_DNS_NAME, ip)
        if ok:
            print(f"✅ {ip} 更新成功")
        else:
            print(f"❌ {ip} 更新失败")

if __name__ == "__main__":
    main()
