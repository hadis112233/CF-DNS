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
# 修正正则，确保匹配更精准
IP_PATTERN = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')

def load_ips_from_local():
    """
    按照文件顺序读取 IP，并保持顺序去重
    """
    raw_ips = []
    try:
        if not os.path.exists(IP_FILE):
            print(f"❌ 找不到文件: {IP_FILE}")
            return []
            
        with open(IP_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            # 找到文件中所有的 IP 匹配项
            raw_ips = IP_PATTERN.findall(content)

    except Exception as e:
        print(f"读取文件失败: {e}")

    # 【关键修复】：使用 dict.fromkeys 代替 set() 以保持文件原始顺序
    # 这样列表中的第 0 个元素 永远是文件里出现的第一个 IP
    unique_ips = list(dict.fromkeys(raw_ips))
    return unique_ips

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
        print(f"ℹ️ 当前解析已经是 {cf_ip}，无需更新")
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
            return f"✅ DNS 已成功更新为文件首行 IP: {cf_ip}"
        return f"❌ 更新失败: {response.text}"
    except:
        return "❌ 网络异常，更新失败"

def send_push(content):
    if not PUSHPLUS_TOKEN or not content:
        return
    try:
        requests.post("http://www.pushplus.plus/send", json={
            "token": PUSHPLUS_TOKEN,
            "title": "Cloudflare 更新通知",
            "content": content,
            "template": "markdown"
        }, timeout=5)
    except:
        pass

def main():
    # 1. 加载 IP（保持顺序）
    ips = load_ips_from_local()
    if not ips:
        print("❌ 文件中未检测到有效的 IP 地址")
        return

    # 2. 明确选择第一个
    first_ip = ips[0]
    print(f"📝 发现 {len(ips)} 个 IP，已选择文件中的第一个: {first_ip}")

    # 3. 获取 Cloudflare 记录
    records = get_dns_records(CF_DNS_NAME)
    if not records:
        print(f"❌ 找不到域名 {CF_DNS_NAME} 的 A 记录，请检查解析名是否正确")
        return

    # 4. 更新
    msg = update_dns_record(records[0], CF_DNS_NAME, first_ip)
    
    if msg:
        print(msg)
        send_push(msg)
    else:
        print("✅ 执行完毕，无需变动")

if __name__ == '__main__':
    main()
