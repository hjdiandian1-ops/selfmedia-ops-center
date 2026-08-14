#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全工具模块（发布前安全审查落地项）
====================================
统一提供三类防护：
1. job_id / 主题 白名单校验（防路径穿越与命令参数注入）
2. URL 安全校验（防 SSRF：仅 http/https、拒绝内网/环回/链路本地/云元数据地址）
3. xlsx 压缩包安全校验（防 zip 炸弹与异常结构）

用法：
    from security_utils import valid_job_id, safe_http_url, safe_xlsx_zip
"""
import ipaddress
import os
import re
import socket
import zipfile

# 允许中英文、数字、下划线、连字符（Job 命名与命令行参数共用）
JOB_ID_RE = re.compile(r"^[A-Za-z0-9_\-\u4e00-\u9fa5]{1,80}$")
THEME_RE = re.compile(r"^[\u4e00-\u9fa5A-Za-z0-9_，。、：:；;！!？?（）()「」【】《》\s·—-]{1,200}$")

# 默认限制：单文件 50MB、条目数 300、单成员解压 200MB、总解压 600MB、压缩比 1000:1
XLSX_MAX_FILE_BYTES = 50 * 1024 * 1024
XLSX_MAX_MEMBERS = 300
XLSX_MAX_MEMBER_BYTES = 200 * 1024 * 1024
XLSX_MAX_TOTAL_BYTES = 600 * 1024 * 1024
XLSX_MAX_RATIO = 1000


def valid_job_id(job_id):
    """job_id 是否合法（白名单正则）。"""
    return bool(job_id) and bool(JOB_ID_RE.fullmatch(job_id or ""))


def require_job_id(job_id, label="job_id"):
    """不合法即抛 ValueError（服务端转 400）。"""
    if not valid_job_id(job_id):
        raise ValueError(f"{label} 含非法字符（仅允许中英文、数字、_ 与 -）: {job_id!r}")
    return job_id


def require_theme(theme, label="theme"):
    if not theme:
        return theme
    if not THEME_RE.fullmatch(theme):
        raise ValueError(f"{label} 含非法字符: {theme!r}")
    return theme


def _is_private_ipv4(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if ip.version == 4:
        return (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified
                or str(ip) == "169.254.169.254")
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified


def safe_http_url(url, resolve_dns=True):
    """URL 是否可安全发起 HTTP 请求。
    规则：仅 http/https；禁止 userinfo；主机不得为内网/环回/链路本地/云元数据；
    若主机为域名且 resolve_dns=True，解析后任一地址命中私网即拒绝。
    """
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if len(url) > 2048 or "://" not in url:
        return False
    scheme, _, rest = url.partition("://")
    if scheme.lower() not in ("http", "https"):
        return False
    host = rest.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if "@" in host:  # userinfo 禁止
        return False
    hostname = host.rsplit(":", 1)[0] if ":" in host and not host.startswith("[") else host.strip("[]")
    if not hostname:
        return False
    if _is_private_ipv4(hostname):
        return False
    if resolve_dns:
        try:
            addrs = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        except OSError:
            return False
        for item in addrs:
            ip = item[4][0]
            if _is_private_ipv4(ip):
                return False
    return True


def safe_xlsx_zip(path):
    """校验 xlsx 压缩包结构，异常抛 ValueError。返回 zipfile.ZipFile 供调用方使用。"""
    if not os.path.isfile(path):
        raise ValueError("xlsx 文件不存在")
    size = os.path.getsize(path)
    if size > XLSX_MAX_FILE_BYTES:
        raise ValueError(f"xlsx 文件过大（{size} 字节 > {XLSX_MAX_FILE_BYTES}）")
    zf = zipfile.ZipFile(path)
    infos = zf.infolist()
    if len(infos) > XLSX_MAX_MEMBERS:
        zf.close()
        raise ValueError(f"xlsx 条目过多（{len(infos)} > {XLSX_MAX_MEMBERS}）")
    total = 0
    for info in infos:
        total += info.file_size
        if info.file_size > XLSX_MAX_MEMBER_BYTES:
            zf.close()
            raise ValueError(f"xlsx 单成员解压过大: {info.filename}")
        if info.file_size > 0 and info.compress_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > XLSX_MAX_RATIO:
                zf.close()
                raise ValueError(f"xlsx 疑似 zip 炸弹（压缩比异常）: {info.filename}")
    if total > XLSX_MAX_TOTAL_BYTES:
        zf.close()
        raise ValueError(f"xlsx 总解压体积过大（{total} 字节）")
    return zf
