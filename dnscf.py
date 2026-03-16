#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare DNS 更新器
获取优选 IP 并更新 Cloudflare DNS 记录
"""

import json
import traceback
import time
import os
import re

import requests

# API 配置
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

# 请求头
HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

# 默认超时时间（秒）
DEFAULT_TIMEOUT = 30

# IPv4 正则校验（防止无效IP导致报错）
IP_REGEX = re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')


def get_cf_speed_test_ip(timeout=10, max_retries=5):
    """
    获取 Cloudflare 优选 IP 【已修复正确链接】
    """
    for attempt in range(max_retries):
        try:
            # ✅ 这里已经修复为纯文本 IP 地址
            response = requests.get(
                'https://raw.githubusercontent.com/hadis112233/CF-DNS/main/cloudflare_ips.txt',
                timeout=timeout
            )
            if response.status_code == 200 and response.text.strip():
                return response.text.strip()
        except Exception as e:
            print(f"获取优选 IP 失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                traceback.print_exc()
    return None


def get_dns_records(name):
    records = []
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records'
    try:
        response = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            result = response.json().get('result', [])
            for record in result:
                if record.get('name') == name and record.get('type') == 'A':
                    records.append({'id': record['id'], 'content': record.get('content', '')})
        else:
            print(f'获取 DNS 记录失败: {response.text}')
    except Exception as e:
        print(f'获取 DNS 记录异常: {e}')
        traceback.print_exc()
    return records


def update_dns_record(record_info, name, cf_ip):
    record_id = record_info['id']
    current_ip = record_info.get('content', '')

    if current_ip == cf_ip:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"cf_dns_change skip: ---- Time: {current_time} ---- ip：{cf_ip} (已是最新)")
        return f"ip:{cf_ip} 解析 {name} 跳过 (已是最新)"

    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_id}'
    data = {
        'type': 'A',
        'name': name,
        'content': cf_ip,
        'ttl': 60,
        'proxied': False
    }

    try:
        response = requests.put(url, headers=HEADERS, json=data, timeout=DEFAULT_TIMEOUT)
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        if response.status_code == 200:
            print(f"cf_dns_change success: ---- Time: {current_time} ---- ip：{cf_ip}")
            return f"ip:{cf_ip} 解析 {name} 成功"
        else:
            print(f"cf_dns_change ERROR: ---- Time: {current_time} ---- MESSAGE: {response.text}")
            return f"ip:{cf_ip} 解析 {name} 失败"
    except Exception as e:
        traceback.print_exc()
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"cf_dns_change ERROR: ---- Time: {current_time} ---- MESSAGE: {e}")
        return f"ip:{cf_ip} 解析 {name} 失败"


def push_plus(content):
    if not PUSHPLUS_TOKEN:
        print("PUSHPLUS_TOKEN 未设置，跳过消息推送")
        return

    url = 'http://www.pushplus.plus/send'
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": "IP优选DNSCF推送",
        "content": content,
        "template": "markdown",
        "channel": "wechat"
    }

    try:
        requests.post(url, json=data, timeout=DEFAULT_TIMEOUT)
    except Exception as e:
        print(f"消息推送失败: {e}")


def main():
    if not all([CF_API_TOKEN, CF_ZONE_ID, CF_DNS_NAME]):
        print("错误: 缺少必要的环境变量")
        return

    ip_addresses_str = get_cf_speed_test_ip()
    if not ip_addresses_str:
        print("错误: 无法获取优选 IP")
        return

    # ✅ 过滤合法IP，彻底杜绝 9005 错误
    ip_addresses = [ip.strip() for ip in ip_addresses_str.split(',') if ip.strip() and IP_REGEX.match(ip.strip())]
    if not ip_addresses:
        print("错误: 未解析到有效 IP 地址")
        return

    dns_records = get_dns_records(CF_DNS_NAME)
    if not dns_records:
        print(f"错误: 未找到 {CF_DNS_NAME} 的 DNS 记录")
        return

    if len(ip_addresses) > len(dns_records):
        ip_addresses = ip_addresses[:len(dns_records)]

    push_plus_content = []
    for index, ip_address in enumerate(ip_addresses):
        dns = update_dns_record(dns_records[index], CF_DNS_NAME, ip_address)
        push_plus_content.append(dns)

    push_plus('\n'.join(push_plus_content))


if __name__ == '__main__':
    main()
