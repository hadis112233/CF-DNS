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

# IPv4 正则校验
IP_REGEX = re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')


def get_cf_speed_test_ip(timeout=10, max_retries=5):
    """
    获取 Cloudflare 优选 IP（已修复原始文件地址）
    """
    for attempt in range(max_retries):
        try:
            # 已修复：使用 raw 地址获取纯文本 IP
            response = requests.get(
                'https://raw.githubusercontent.com/hadis112233/CF-DNS/main/cloudflare_ips.txt',
                timeout=timeout
            )
            if response.status_code == 200 and response.text.strip():
                return response.text.strip()
        except Exception as e:
            print(f"获取优选 IP 失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
            if attempt == max_retries - 1:
                traceback.print_exc()
    return None


def get_dns_records(name):
    """
    获取指定名称的 DNS A 记录
    """
    records = []
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records'

    try:
        response = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            result = response.json().get('result', [])
            for record in result:
                if record.get('name') == name and record.get('type') == 'A':
                    records.append({
                        'id': record['id'],
                        'content': record.get('content', '')
                    })
        else:
            print(f'获取 DNS 记录失败: {response.text}')
    except Exception as e:
        print(f'获取 DNS 记录异常: {str(e)}')
        traceback.print_exc()

    return records


def update_dns_record(record_info, name, cf_ip):
    """
    更新单条 DNS 记录
    """
    record_id = record_info['id']
    current_ip = record_info.get('content', '')

    if current_ip == cf_ip:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"✅ 无需更新 | {current_time} | IP：{cf_ip}（已是最新）")
        return f"IP:{cf_ip} 解析 {name} 跳过（已是最新）"

    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_id}'
    data = {
        'type': 'A',
        'name': name,
        'content': cf_ip,
        'ttl': 60,  # 自动 TTL
        'proxied': False  # 是否开启 CF 代理（按需修改）
    }

    try:
        response = requests.put(url, headers=HEADERS, json=data, timeout=DEFAULT_TIMEOUT)
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        if response.status_code == 200:
            print(f"✅ 更新成功 | {current_time} | IP：{cf_ip}")
            return f"IP:{cf_ip} 解析 {name} 成功"
        else:
            print(f"❌ 更新失败 | {current_time} | 错误：{response.text}")
            return f"IP:{cf_ip} 解析 {name} 失败"
    except Exception as e:
        traceback.print_exc()
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"❌ 更新异常 | {current_time} | 错误：{str(e)}")
        return f"IP:{cf_ip} 解析 {name} 失败"


def push_plus(content):
    """
    PushPlus 微信推送
    """
    if not PUSHPLUS_TOKEN:
        return

    url = 'http://www.pushplus.plus/send'
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": "Cloudflare DNS 自动更新",
        "content": content,
        "template": "markdown",
        "channel": "wechat"
    }

    try:
        requests.post(url, json=data, timeout=DEFAULT_TIMEOUT)
        print("\n📱 推送消息已发送")
    except Exception as e:
        print(f"\n❌ 推送失败：{str(e)}")


def main():
    print("=" * 60)
    print(" Cloudflare DNS 自动更新脚本 启动 ".center(60, "="))
    print("=" * 60)

    # 检查环境变量
    if not all([CF_API_TOKEN, CF_ZONE_ID, CF_DNS_NAME]):
        print("\n❌ 错误：缺少必要环境变量")
        print("请配置：CF_API_TOKEN、CF_ZONE_ID、CF_DNS_NAME")
        return

    # 获取优选 IP
    print("\n正在获取 Cloudflare 优选 IP...")
    ip_text = get_cf_speed_test_ip()
    if not ip_text:
        print("\n❌ 错误：无法获取优选 IP 列表")
        return

    # 解析并过滤合法 IP
    ip_list = [ip.strip() for ip in ip_text.split(',') if ip.strip() and IP_REGEX.match(ip.strip())]
    if not ip_list:
        print("\n❌ 错误：未获取到任何合法 IPv4 地址")
        return

    print(f"\n✅ 获取到 {len(ip_list)} 个合法优选 IP")
    for idx, ip in enumerate(ip_list, 1):
        print(f"   {idx}. {ip}")

    # 获取 DNS 记录
    print(f"\n正在查询域名：{CF_DNS_NAME} 的 DNS 记录...")
    dns_records = get_dns_records(CF_DNS_NAME)
    if not dns_records:
        print(f"\n❌ 错误：未找到 {CF_DNS_NAME} 的 A 记录")
        return

    print(f"✅ 找到 {len(dns_records)} 条可更新的 A 记录")

    # 匹配数量
    if len(ip_list) > len(dns_records):
        print(f"\n⚠️  警告：IP 数量({len(ip_list)}) > 记录数({len(dns_records)})")
        ip_list = ip_list[:len(dns_records)]
        print(f"将只更新前 {len(ip_list)} 个 IP")

    # 开始更新
    print("\n" + "-" * 60)
    print("开始更新 DNS 记录...".center(60))
    print("-" * 60)

    push_msg = []
    for i, ip in enumerate(ip_list):
        res = update_dns_record(dns_records[i], CF_DNS_NAME, ip)
        push_msg.append(res)

    # 推送结果
    if push_msg:
        push_plus("\n".join(push_msg))

    print("\n" + "=" * 60)
    print(" 脚本执行完成 ".center(60, "="))
    print("=" * 60)


if __name__ == '__main__':
    main()
