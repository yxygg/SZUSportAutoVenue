# src/login.py
# -*- coding: utf-8 -*-
import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


def get_new_cookie(username, password, headless=False):
  """
  启动浏览器登录。
  """
  logger.info(f"启动自动登录 (Headless={headless})...")

  base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  user_data_dir = os.path.join(base_dir, "scripts", "browser_data")
  if not os.path.exists(user_data_dir):
    os.makedirs(user_data_dir)

  chrome_options = Options()
  chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
  chrome_options.add_argument("--profile-directory=SzuBotProfile")

  if headless:
    chrome_options.add_argument("--headless")

  chrome_options.add_argument("--no-sandbox")
  chrome_options.add_argument("--disable-gpu")
  chrome_options.add_argument(
    'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

  driver = None
  try:
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    target_url = "https://ehall.szu.edu.cn/qljfwapp/sys/lwSzuCgyy/index.do"
    driver.get(target_url)

    wait = WebDriverWait(driver, 10)

    # 等待 URL 稳定
    time.sleep(2)
    current_url = driver.current_url
    logger.info(f"当前页面URL: {current_url}")

    # ================== 核心逻辑修正 ==================

    # 判定优先级 1: 只要包含 authserver，就是没登录，必须输入账号密码
    if "authserver" in current_url:
      logger.info("处于登录页面，开始自动操作...")

      # 等待元素加载
      user_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
      pwd_input = driver.find_element(By.ID, "password")
      submit_btn = driver.find_element(By.ID, "login_submit")

      # 1. 勾选“七天免登录”
      try:
        # 有些时候 checkbox 加载慢，尝试显式等待
        remember_me = wait.until(EC.presence_of_element_located((By.ID, "rememberMe")))
        if not remember_me.is_selected():
          remember_me.click()
          logger.info("✅ 已勾选'七天免登录'")
      except Exception as e:
        logger.warning(f"勾选七天免登录失败(不影响后续): {e}")

      # 2. 输入账号密码
      if not user_input.get_attribute('value'):
        user_input.clear()
        user_input.send_keys(username)

      # 密码框总是清空重输比较稳妥
      pwd_input.clear()
      pwd_input.send_keys(password)

      time.sleep(0.5)
      submit_btn.click()
      logger.info("点击登录，等待跳转...")

    # 判定优先级 2: 不含 authserver 且含 ehall，才是真的登录了
    elif "ehall.szu.edu.cn" in current_url and "authserver" not in current_url:
      logger.info("检测到已登录状态(Profile生效)，无需输入密码。")

    # =================================================

    # --- 循环检测跳转结果 ---
    # Headless模式给60秒，有界面模式(手动Init)给600秒等待人工操作
    max_retries = 60 if headless else 600

    for i in range(max_retries):
      current_url = driver.current_url

      # 1. 成功: URL 是 ehall 且不含 authserver
      if "ehall.szu.edu.cn" in current_url and "authserver" not in current_url:
        logger.info("🎉 成功跳转至 ehall 系统！")
        time.sleep(1)  # 等待Cookie写入
        cookies_list = driver.get_cookies()
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies_list])
        return "SUCCESS", cookie_str

      # 2. 失败/风控: 仍在 authserver 且 URL 出现 MFA 特征
      if "authserver" in current_url:
        if "reAuthCheck" in current_url or "isMultifactor=true" in current_url:
          if headless:
            err_msg = "触发多因素认证(短信/验证码)，无法自动处理。"
            logger.error(err_msg)
            return "MFA_REQUIRED", err_msg
          else:
            if i % 5 == 0:
              logger.warning("⚠️ 处于多因素认证页面！请手动操作...")

      time.sleep(1)

    return "ERROR", "登录超时或未跳转到目标页面"

  except Exception as e:
    logger.error(f"Selenium 运行异常: {e}")
    return "ERROR", str(e)
  finally:
    if driver:
      driver.quit()