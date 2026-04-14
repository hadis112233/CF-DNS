#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import requests

# ========== 1. 配置 ==========
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

IP_FILE = "cloudflare_ips.txt"
HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

def get_best_ip_from_file():
    """读取文件第一行，提取最快 IP 和速度"""
    if not os.path.exists(IP_FILE):
        print(f"❌ 找不到文件: {IP_FILE}")
        return None
    ip_pattern = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
    try:
        with open(IP_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                match = ip_pattern.search(line)
                if match:
                    best_ip = match.group(1)
                    speed_match = re.search(r'(\d+\.?\d*MB/s)', line)
                    speed = speed_match.group(1) if speed_match else "未知"
                    return best_ip, speed
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
    return None

def update_dns_and_push(ip, speed):
    """更新 DNS 并强制推送通知"""
    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        records = [r for r in res.get("result", []) if r['name'] == CF_DNS_NAME and r['type'] == 'A']
        
        status_msg = ""
        
        if not records:
            status_msg = "⚠️ 未在 CF 发现 A 记录，仅推送当前最快 IP"
        else:
            target_record = records[0]
            # 检查 IP 是否需要物理更新
            if target_record['content'] == ip:
                status_msg = "✅ IP 未变动（已是最新）"
                print(f"ℹ️ {ip} 已在解析中，跳过 API 写入")
            else:
                # 执行更新
                update_url = f"{url}/{target_record['id']}"
                data = {"type": "A", "name": CF_DNS_NAME, "content": ip, "ttl": 60, "proxied": False}
                update_res = requests.put(update_url, headers=HEADERS, json=data, timeout=10).json()
                if update_res.get("success"):
                    status_msg = "🚀 成功更新至最快节点"
                else:
                    status_msg = "❌ Cloudflare API 更新失败"

        # --- 强制推送逻辑 ---
        push_content = f"### 🌩️ Cloudflare 优选监控\n\n" \
                       f"- **目标域名**: `{CF_DNS_NAME}`\n" \
                       f"- **最快节点**: `{ip}`\n" \
                       f"- **实测速度**: `{speed}`\n" \
                       f"- **处理状态**: {status_msg}"
        
        send_push(push_content)
        print(f"📢 推送已发送：{status_msg}")

    except Exception as e:
        print(f"❌ 运行异常: {e}")

def send_push(content):
    if not PUSHPLUS_TOKEN: return
    requests.post("http://www.pushplus.plus/send", json={
        "token": PUSHPLUS_TOKEN,
        "title": "Cloudflare 节点状态推送",
        "content": content,
        "template": "markdown"
    })

def main():
    result = get_best_ip_from_file()
    if result:
        ip, speed = result
        update_dns_and_push(ip, speed)
    else:
        print("❌ 未提取到 IP")

if __name__ == "__main__":
    main()
