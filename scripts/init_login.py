# scripts/init_login.py
# -*- coding: utf-8 -*-
import logging
import sys
import os
import json

# 1. 路径计算
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from src.booker import VenueBooker
from src.login import get_new_cookie

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def debug_check_json(path):
  """单独检查 JSON 文件是否健康"""
  print(f"\n🔍 [调试] 正在检查配置文件路径:\n👉 {path}")

  if not os.path.exists(path):
    print("❌ [错误] 文件不存在！请检查路径是否正确。")
    return False

  try:
    with open(path, 'r', encoding='utf-8-sig') as f:
      content = f.read()
      print(f"📄 [调试] 文件内容预览 (前100字符): {content[:100]}...")
      json.loads(content)  # 尝试解析
      print("✅ [调试] JSON 格式验证通过。")
      return True
  except json.JSONDecodeError as e:
    print(f"❌ [错误] JSON 格式错误！请检查逗号、引号、括号。")
    print(f"错误详情: {e}")
    print("👉 提示：在添加 'password' 字段时，请检查上一行末尾是否加了逗号(,)。")
    return False
  except Exception as e:
    print(f"❌ [错误] 读取文件异常: {e}")
    return False


def main():
  print("========================================")
  print("      SzuVenueBooker 初始化工具 (调试版)")
  print("========================================")

  config_path = os.path.join(project_root, "config.json")

  # --- 第一步：先运行调试检查 ---
  if not debug_check_json(config_path):
    print("⛔ 由于配置文件无法读取，程序终止。")
    return
  # ---------------------------

  booker = VenueBooker(config_path)
  # 强制重新加载一次以确保同步
  booker.reload_config(force_check=False)

  stuid = booker.config.get("stuid")
  password = booker.config.get("password")

  print(f"\n🔑 读取到的配置信息:")
  print(f"   stuid: {stuid}")
  print(f"   password: {'******' if password else 'None'}")

  if not stuid or not password:
    print("\n❌ 错误：stuid 或 password 为空！")
    print("请打开 config.json 确认这两个字段有值。")
    return

  print(f"\n🚀 正在启动 Chrome 浏览器...")
  print("👉 如果触发'多因素认证'(验证码)，请手动在浏览器中操作！")

  code, result = get_new_cookie(stuid, password, headless=False)

  if code == "SUCCESS":
    print("\n✅ 登录成功！")
    booker.config["cookie"] = result
    booker.save_config()
    print("✅ 配置已更新。")
  else:
    print(f"\n❌ 登录失败: {code} - {result}")


if __name__ == "__main__":
  main()