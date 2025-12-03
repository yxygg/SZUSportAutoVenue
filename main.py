# main.py
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
from datetime import datetime

# 引入调度触发器
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import PersonNormalMessageReceived

from .src.booker import VenueBooker


@register(name="SzuVenueBooker", description="深大体育场馆自动抢票助手", version="1.1", author="SzuHelper")
class SzuVenueBookerPlugin(BasePlugin):

  def __init__(self, host: APIHost):
    super().__init__(host)
    self.host = host
    self.logger = logging.getLogger("SzuVenueBooker")

    # 路径配置
    self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
    self.config_path = os.path.join(self.plugin_dir, "config.json")

    # 初始化业务逻辑
    self.booker = VenueBooker(self.config_path)

    # 初始化调度器
    self.scheduler = AsyncIOScheduler()

  async def initialize(self):
    """插件初始化"""
    self.logger.info("SzuVenueBooker 正在初始化...")

    # 1. 【核心任务】每日抢票：12:29:30 启动
    self.scheduler.add_job(
      self.scheduled_booking_task,
      trigger=CronTrigger(hour=12, minute=29, second=30),
      id="daily_venue_booking",
      replace_existing=True
    )

    # 2. 【新增】赛前预热：每天 12:20 (抢票前10分钟) 强制检查一次 Cookie
    self.scheduler.add_job(
      self.scheduled_cookie_refresh,
      trigger=CronTrigger(hour=12, minute=20, second=0),
      id="pre_booking_cookie_check",
      replace_existing=True,
      args=["赛前预热"]  # 传入参数用于日志区分
    )

    # 3. 【新增】日常维护：每 30 分钟检查一次 Cookie 状态
    self.scheduler.add_job(
      self.scheduled_cookie_refresh,
      trigger=IntervalTrigger(minutes=30),
      id="interval_cookie_check",
      replace_existing=True,
      args=["日常维护"]
    )

    self.scheduler.start()
    self.logger.info("SzuVenueBooker 调度器已启动: [抢票: 12:29:30] [预热: 12:20] [日常: 每30分]")

  async def scheduled_cookie_refresh(self, source="未知"):
    """
    定时 Cookie 维护任务
    source: 触发来源说明
    """
    self.logger.info(f"🔄 触发 Cookie 自动维护任务 ({source})...")

    # 定义在线程中运行的函数
    def run_check():
      # force_check=True 会调用 API 测试 Cookie，如果失效则自动启动浏览器续期
      # 返回值: (bool:是否成功, str:错误信息或None)
      return self.booker.reload_config(force_check=True)

    # 使用 to_thread 避免阻塞主线程
    success, msg = await asyncio.to_thread(run_check)

    if success:
      self.logger.info(f"✅ Cookie 状态良好 ({source})")
    else:
      # 如果是因为 MFA 失败，需要通知管理员
      if msg and "多因素认证" in msg:
        admin_qq = self.booker.config.get("admin_qq")
        if admin_qq:
          await self.send_private_msg(admin_qq, f"⚠️ **Cookie 维护失败** ({source})\n{msg}")
      self.logger.warning(f"Cookie 维护结束，状态可能有异: {msg}")

  async def scheduled_booking_task(self):
    """定时抢票任务回调"""
    self.logger.info("🔥 触发每日抢票任务！")
    admin_qq = self.booker.config.get("admin_qq")

    async def send_notify(msg):
      if admin_qq:
        await self.send_private_msg(admin_qq, msg)
      else:
        self.logger.warning(f"未配置 admin_qq，无法发送通知: {msg}")

    # 执行抢票逻辑
    await self.booker.run_booking_cycle(send_notify)

  async def send_private_msg(self, user_id, text):
    """发送私聊消息辅助函数"""
    import pkg.platform.types as platform_types
    adapters = self.host.get_platform_adapters()
    if not adapters:
      self.logger.error("无可用适配器，发送消息失败")
      return
    try:
      await self.host.send_active_message(
        adapter=adapters[0],
        target_type="person",
        target_id=str(user_id),
        message=platform_types.MessageChain([platform_types.Plain(text)])
      )
    except Exception as e:
      self.logger.error(f"发送消息失败: {e}")

  @handler(PersonNormalMessageReceived)
  async def handle_admin_msg(self, ctx: EventContext):
    """处理管理员指令"""
    msg = ctx.event.text_message.strip()
    sender = str(ctx.event.sender_id)

    # 简单权限检查
    # 注意：reload_config 会更新内存中的 config，所以这里直接读内存的
    admin_qq = self.booker.config.get("admin_qq")
    if sender != str(admin_qq):
      return

    if msg == "#venue help":
      reply = (
        "🏸 **深大场馆助手指令**\n"
        "#venue config : 重载配置并检查Cookie\n"
        "#venue list : 列出场馆/项目\n"
        "#venue check : 检查明天场地情况\n"
        "#venue refresh : 手动强制刷新一次Cookie\n"
        "#venue run : 立即触发抢票"
      )
      ctx.add_return("reply", [reply])
      ctx.prevent_default()

    elif msg == "#venue config":
      # 这是一个轻量级重载，不强制网络检查
      self.booker.reload_config(force_check=False)
      ctx.add_return("reply", ["✅ 配置已重载 (内存更新)。"])
      ctx.prevent_default()

    elif msg == "#venue refresh":
      # 手动触发维护
      ctx.add_return("reply", ["🔄 正在后台执行强制刷新，请稍候..."])
      await self.scheduled_cookie_refresh(source="管理员指令")
      ctx.prevent_default()

    elif msg == "#venue list":
      res = await asyncio.to_thread(self.booker.format_venue_list)
      ctx.add_return("reply", [res])
      ctx.prevent_default()

    elif msg == "#venue check":
      ctx.add_return("reply", ["🔍 正在获取场地信息..."])
      res = await asyncio.to_thread(self.booker.test_room_list)
      await self.send_private_msg(sender, res)
      ctx.prevent_default()

    elif msg == "#venue run":
      ctx.add_return("reply", ["🚀 手动触发抢票任务！"])
      asyncio.create_task(self.scheduled_booking_task())
      ctx.prevent_default()

  def __del__(self):
    if self.scheduler.running:
      self.scheduler.shutdown()