# src/booker.py
# -*- coding: utf-8 -*-
import json
import os
import time
import logging
import asyncio
import copy
from datetime import datetime, timedelta
from .api import SzuApi

# 尝试导入自动登录模块
try:
  from .login import get_new_cookie
except ImportError:
  get_new_cookie = None

logger = logging.getLogger(__name__)


class VenueBooker:
  def __init__(self, config_path):
    self.config_path = config_path
    self.config = {}
    self.api = None
    # 初始化时不强制检查网络，避免阻塞
    self.reload_config(force_check=False)

  def save_config(self):
    """保存当前配置到文件"""
    try:
      with open(self.config_path, 'w', encoding='utf-8') as f:
        json.dump(self.config, f, indent=2, ensure_ascii=False)
      logger.info("配置(Cookie)已保存到本地。")
    except Exception as e:
      logger.error(f"保存配置文件失败: {e}")

  def reload_config(self, force_check=False):
    """
    加载配置文件并检查Cookie有效性
    :param force_check: 是否验证Cookie并尝试自动续期
    :return: (bool: success, str: message/error)
    """
    if os.path.exists(self.config_path):
      # 读取配置
      with open(self.config_path, 'r', encoding='utf-8-sig') as f:
        try:
          self.config = json.load(f)
        except json.JSONDecodeError as e:
          err = f"配置文件 JSON 格式错误: {e}"
          logger.error(err)
          return False, err

      # 初始化API
      self.api = SzuApi(
        self.config.get("cookie", ""),
        self.config.get("stuid", ""),
        self.config.get("stuname", "")
      )

      # 如果不需要检查，直接返回成功
      if not force_check:
        return True, None

      # 检查密码是否存在，否则无法自动登录
      if not self.config.get("password"):
        return True, "未配置密码，跳过自动续期检查"

      # --- 开始检查 Cookie 有效性 ---
      # 发送一个轻量级请求 (获取系统配置)
      status, _ = self.api.get_sys_config()

      if status:
        # API请求成功，说明 Cookie 还是活的
        # 此时不需要启动浏览器，节省资源
        return True, "Cookie 依然有效"

      else:
        logger.info("检测到 Cookie 失效，启动浏览器进行自动续期...")

        if get_new_cookie:
          # 调用 login.py (强制 headless 模式)
          code, result = get_new_cookie(
            self.config.get("stuid"),
            self.config.get("password"),
            headless=True
          )

          if code == "SUCCESS":
            logger.info("自动续期成功！")
            self.config["cookie"] = result
            self.save_config()
            # 重新初始化 API
            self.api = SzuApi(result, self.config["stuid"], self.config["stuname"])
            return True, "自动续期成功"

          elif code == "MFA_REQUIRED":
            # 这是最需要关注的错误
            err_msg = "自动登录失败：触发多因素认证(MFA)，请管理员手动运行 init_login.py"
            logger.error(err_msg)
            return False, err_msg
          else:
            err_msg = f"自动登录出错: {result}"
            logger.error(err_msg)
            return False, err_msg
        else:
          return False, "缺少 login 模块，无法自动登录"

    return False, "配置文件不存在"

  def get_next_day_date(self):
    """获取明天日期的字符串 YYYY-MM-DD"""
    next_day = datetime.now() + timedelta(days=1)
    return next_day.strftime("%Y-%m-%d")

  def format_venue_list(self):
    """管理员指令：获取场馆列表"""
    # 获取列表前先确保连接正常，这里轻度检查
    self.reload_config(force_check=True)
    status, data = self.api.get_sys_config()

    if not status:
      return f"获取失败 (Cookie失效且自动修复失败): {data}"

    msg = "📋 **场馆与项目列表**\n"
    msg += "--- 场馆 (CGDM) ---\n"
    for v in data.get("packageVenueList", []) + data.get("dismissalVenueList", []):
      msg += f"[{v.get('CGBM', '?')}] {v.get('CGMC', '?')} (校区:{v.get('SSXQ', '?')})\n"

    msg += "\n--- 项目 (XMDM) ---\n"
    for xm in data.get("xmList", []):
      msg += f"[{xm.get('XMDM', '?')}] {xm.get('XMMC', '?')} (类型:{xm.get('DCFS', '?')})\n"

    return msg

  def test_room_list(self):
    """管理员指令：测试获取场地"""
    # 强制检查，确保测试结果准确
    success, msg = self.reload_config(force_check=True)
    if not success:
      return f"无法执行查询：{msg}"

    target_date = self.get_next_day_date()
    # 默认测试参数，可根据需要调整
    # 002:羽毛球, 1:粤海校区, 19:00-20:00
    rooms = self.api.get_room(
      XMDM="002",
      YYRQ=target_date,
      YYLX="1.0",
      KSSJ="19:00",
      JSSJ="20:00",
      XQDM="1"
    )

    if rooms is None:
      return f"获取 {target_date} 场地列表失败，API无响应。"

    msg = f"🏸 **{target_date} 19:00-20:00 粤海羽毛球测试**\n"
    available_count = 0
    for r in rooms:
      status = "❌占用" if r.get('disabled') else "✅空闲"
      if not r.get('disabled'): available_count += 1
      msg += f"- {r.get('CDMC')} ({status})\n"

    msg += f"\n共 {len(rooms)} 个场地，可用: {available_count}"
    return msg

  async def run_booking_cycle(self, host_api_sender):
    """执行抢票循环"""
    await host_api_sender("⏳ 正在进行赛前最终检查...")

    # 1. 再次强制刷新配置（双保险）
    def run_check():
      return self.reload_config(force_check=True)

    success, msg = await asyncio.to_thread(run_check)

    if not success:
      # 如果登录都失败了，任务直接没法跑
      await host_api_sender(f"⛔ **任务终止**: {msg}")
      return

    if not self.config.get("targets"):
      await host_api_sender("⚠️ 没有配置抢票目标，停止任务。")
      return

    target_date = self.get_next_day_date()
    delay_sec = self.config.get("request_delay_ms", 500) / 1000.0
    max_minutes = self.config.get("max_duration_minutes", 6)

    end_time = datetime.now() + timedelta(minutes=max_minutes)

    await host_api_sender(f"🚀 开始执行 {target_date} 的抢票任务...\n将在 {max_minutes} 分钟后停止。")

    # 准备任务队列
    pending_courses = []
    for t in self.config["targets"]:
      course = copy.deepcopy(t)
      course["YYRQ"] = target_date
      pending_courses.append(course)

    success_list = []

    # 循环直到超时或全部完成
    while datetime.now() < end_time and len(pending_courses) > 0:

      # 遍历副本
      for course in pending_courses[:]:

        # --- 阶段 1: 寻找场地 (如果还未锁定 CDWID) ---
        if "CDWID" not in course:
          try:
            kssj, jssj = course["KYYSJD"].split("-")
            rooms = self.api.get_room(
              course["XMDM"], course["YYRQ"], course["YYLX"],
              kssj, jssj, course["XQWID"]
            )

            if rooms:
              # 找到第一个非disabled的场地
              valid_room = next((r for r in rooms if not r['disabled']), None)

              if valid_room:
                course["CDWID"] = valid_room["WID"]
                course["CDMC"] = valid_room["CDMC"]
                logger.info(f"锁定场地: {course['comment']} -> {valid_room['CDMC']}")
              else:
                pass  # 没场，跳过
            else:
              pass  # API 返回 None
          except Exception as e:
            logger.error(f"获取场地列表异常: {e}")
            continue

        # --- 阶段 2: 执行预约 (如果已锁定 CDWID) ---
        if "CDWID" in course:
          logger.info(f"发起预约: {course['comment']} ({course.get('CDMC')})")

          res = self.api.post_book(
            course["CGDM"], course["CDWID"], course["XMDM"],
            course["XQWID"], course["KYYSJD"], course["YYRQ"], course["YYLX"]
          )

          res_str = json.dumps(res, ensure_ascii=False) if res else ""

          if res and "成功" in res_str:
            msg = f"🎉 抢票成功: {course.get('CDMC')} ({course['comment']})"
            logger.info(msg)
            success_list.append(msg)
            await host_api_sender(msg)
            pending_courses.remove(course)

          elif "冲突" in res_str or "已被" in res_str:
            logger.warning(f"预约冲突，场地可能已被抢: {course.get('CDMC')}")
            # 清除锁定，下一轮重新找
            del course["CDWID"]

          else:
            logger.warning(f"预约返回未知: {res_str}")
            # 如果是 Cookie 突然失效，这里会不断失败直到任务超时
            # 改进：如果检测到 "登录" 关键字，可能需要紧急续期，但实战中几分钟的抢票期通常来不及

      await asyncio.sleep(delay_sec)

    summary = f"🏁 抢票任务结束。\n目标数: {len(self.config['targets'])}\n成功数: {len(success_list)}"
    await host_api_sender(summary)