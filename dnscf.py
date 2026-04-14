#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import requests

# ========== 1. 配置（请确保环境变量已设置） ==========
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME") # 要更新的域名，如 dns.example.com
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

IP_FILE = "cloudflare_ips.txt"
HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

def get_best_ip_from_file():
    """
    直接从文件第一行提取速度最快的 IP
    """
    if not os.path.exists(IP_FILE):
        print(f"❌ 找不到文件: {IP_FILE}")
        return None

    # 匹配 IP 的正则
    ip_pattern = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')

    try:
        with open(IP_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                
                # 提取 IP 和 备注信息（用于推送显示）
                match = ip_pattern.search(line)
                if match:
                    best_ip = match.group(1)
                    # 尝试提取速度信息，例如 "51.18MB/s"
                    speed_match = re.search(r'(\d+\.?\d*MB/s)', line)
                    speed = speed_match.group(1) if speed_match else "未知"
                    return best_ip, speed
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
    return None

def update_dns_and_push(ip, speed):
    """
    更新 Cloudflare DNS 并通过 PushPlus 推送
    """
    # 1. 获取 Cloudflare 记录
    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        records = [r for r in res.get("result", []) if r['name'] == CF_DNS_NAME and r['type'] == 'A']
        
        if not records:
            print(f"❌ 未找到域名 {CF_DNS_NAME} 的 A 记录")
            return

        target_record = records[0]
        
        # 2. 如果 IP 没变，不重复更新但可以选是否推送
        if target_record['content'] == ip:
            print(f"✅ 当前 DNS 已经是最高速 IP ({ip})，跳过更新")
            return

        # 3. 执行更新
        update_url = f"{url}/{target_record['id']}"
        data = {
            "type": "A",
            "name": CF_DNS_NAME,
            "content": ip,
            "ttl": 60,
            "proxied": False
        }
        update_res = requests.put(update_url, headers=HEADERS, json=data, timeout=10).json()
        
        if update_res.get("success"):
            msg = f"🚀 **Cloudflare 优选 IP 更新成功**\n\n" \
                  f"- **域名**: `{CF_DNS_NAME}`\n" \
                  f"- **最快 IP**: `{ip}`\n" \
                  f"- **下载速度**: `{speed}`\n" \
                  f"- **状态**: 已自动切换至最快节点"
            print(f"✅ 更新成功: {ip} ({speed})")
            send_push(msg)
        else:
            print(f"❌ 更新失败: {update_res}")

    except Exception as e:
        print(f"❌ 网络异常: {e}")

def send_push(content):
    if not PUSHPLUS_TOKEN: return
    requests.post("http://www.pushplus.plus/send", json={
        "token": PUSHPLUS_TOKEN,
        "title": "Cloudflare 速度最快节点推送",
        "content": content,
        "template": "markdown"
    })

def main():
    result = get_best_ip_from_file()
    if result:
        ip, speed = result
        print(f"📍 检测到最快节点: {ip}, 速度: {speed}")
        update_dns_and_push(ip, speed)
    else:
        print("❌ 未能从文件中提取到 IP")

if __name__ == "__main__":
    main()
