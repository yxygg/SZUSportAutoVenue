# src/api.py
# -*- coding: utf-8 -*-
import json
import logging
import requests
import os

# 保持原脚本的环境设置
os.environ['NO_PROXY'] = 'ehall.szu.edu.cn'

logger = logging.getLogger(__name__)

# 基础请求头
BASE_HEADERS = {
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'https://ehall.szu.edu.cn',
    'Pragma': 'no-cache',
    'Referer': 'https://ehall.szu.edu.cn/qljfwapp/sys/lwSzuCgyy/index.do',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest',
}

def parse_cookie_str(cookie_str):
    """解析Cookie字符串为字典"""
    cookies = {}
    if not cookie_str:
        return cookies
    for item in cookie_str.split(';'):
        item = item.strip()
        if not item: continue
        try:
            k, v = item.split('=', 1)
            cookies[k] = v
        except ValueError:
            continue
    return cookies

def safe_json_loads(content):
    """
    安全解析JSON，处理BOM和非JSON情况
    """
    if not content:
        raise ValueError("返回内容为空")

    # 1. 尝试检测 HTML (通常意味着 Cookie 失效)
    # 将 bytes 转为字符串预览
    try:
        preview = content[:100].decode('utf-8', errors='ignore').lower()
    except:
        preview = ""
    
    if "<html" in preview or "<!doctype" in preview or "cas" in preview:
        raise ValueError("Cookie已失效或未登录 (服务器返回了HTML页面)")

    # 2. 尝试 JSON 解码
    try:
        if isinstance(content, bytes):
            text = content.decode('utf-8-sig') # 自动去除 BOM
        else:
            text = content
            if text.startswith('\ufeff'):
                text = text[1:]
        
        return json.loads(text)
    except json.JSONDecodeError as e:
        # 记录具体的错误内容以便调试
        logger.error(f"JSON解析失败: {e}, 内容预览: {preview}")
        raise e

class SzuApi:
    def __init__(self, cookie_str, stuid, stuname):
        self.cookies = parse_cookie_str(cookie_str)
        self.stuid = str(stuid)
        self.stuname = str(stuname)
        self.headers = BASE_HEADERS.copy()

    def get_sys_config(self):
        """获取系统配置(场馆/项目信息)"""
        try:
            ret = requests.post(
                "https://ehall.szu.edu.cn/qljfwapp/sys/lwSzuCgyy/sportVenue/getSportVenueData.do",
                cookies=self.cookies,
                headers=self.headers,
                timeout=10,
                allow_redirects=True 
            )
            
            if ret.status_code != 200:
                return False, f"服务器错误 HTTP {ret.status_code}"

            data = safe_json_loads(ret.content)
            return True, data
        except ValueError as ve:
            # 捕获我们自定义的 Cookie 失效错误
            logger.warning(f"获取配置失败: {ve}")
            return False, str(ve)
        except Exception as e:
            logger.error(f"获取系统配置未知异常: {e}")
            return False, f"请求异常: {str(e)}"

    def get_time_list(self, XQ, YYRQ, YYLX, XMDM):
        """获取时间列表"""
        try:
            data = {'XQ': XQ, 'YYRQ': YYRQ, 'YYLX': YYLX, 'XMDM': XMDM}
            ret = requests.post(
                "https://ehall.szu.edu.cn/qljfwapp/sys/lwSzuCgyy/sportVenue/getTimeList.do",
                cookies=self.cookies,
                headers=self.headers,
                data=data,
                timeout=5
            )
            return safe_json_loads(ret.content)
        except Exception as e:
            logger.error(f"获取时间列表失败: {e}")
            return None

    def get_room(self, XMDM, YYRQ, YYLX, KSSJ, JSSJ, XQDM):
        """获取场地列表"""
        try:
            data = {
                'XMDM': XMDM, 'YYRQ': YYRQ, 'YYLX': YYLX,
                'KSSJ': KSSJ, 'JSSJ': JSSJ, 'XQDM': XQDM,
            }
            ret = requests.post(
                "https://ehall.szu.edu.cn/qljfwapp/sys/lwSzuCgyy/modules/sportVenue/getOpeningRoom.do",
                cookies=self.cookies,
                headers=self.headers,
                data=data,
                timeout=5
            )
            res = safe_json_loads(ret.content)
            if "datas" in res and "getOpeningRoom" in res["datas"]:
                return res["datas"]["getOpeningRoom"]["rows"]
            return []
        except Exception as e:
            logger.error(f"获取场地列表失败: {e}")
            return None

    def post_book(self, CGDM, CDWID, XMDM, XQWID, KYYSJD, YYRQ, YYLX):
        """提交预约"""
        try:
            times = KYYSJD.split('-')
            data = {
                'DHID': '', 'CYRS': '',
                'YYRGH': self.stuid,
                'YYRXM': self.stuname,
                'CGDM': CGDM, 'CDWID': CDWID,
                'XMDM': XMDM, 'XQWID': XQWID,
                'KYYSJD': KYYSJD, 'YYRQ': YYRQ, 'YYLX': YYLX,
                'PC_OR_PHONE': 'pc',
                'YYKS': f"{YYRQ} {times[0]}",
                'YYJS': f"{YYRQ} {times[1]}"
            }
            ret = requests.post(
                "https://ehall.szu.edu.cn/qljfwapp/sys/lwSzuCgyy/sportVenue/insertVenueBookingInfo.do",
                cookies=self.cookies,
                headers=self.headers,
                data=data,
                timeout=5
            )
            return safe_json_loads(ret.content)
        except Exception as e:
            logger.error(f"预约请求异常: {e}")
            return {"msg": str(e)}