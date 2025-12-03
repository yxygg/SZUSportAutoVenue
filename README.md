# 🏸 SzuVenueBooker - 深大场馆自动抢票助手

**SzuVenueBooker** 是一个基于 LangBot 框架的深大体育场馆自动预约插件。它集成了 CAS 统一身份认证自动登录、Session 自动续期、断线重连以及多线程并发抢票功能，专为解决“定场难”问题而生。
基于https://github.com/Matt-Dong123/tools4szu/tree/main/venue-helper修改

## ✨ 核心功能

*   **全自动登录**：使用 Selenium 模拟真实浏览器登录，支持“七天免登录”勾选，有效规避验证码。
*   **智能续期 (Keep-Alive)**：
    *   每 30 分钟自动检查 Cookie 有效性并静默续期。
    *   **赛前预热**：每天 12:20（抢票前10分钟）强制预检，确保抢票时刻状态满血。
*   **浏览器指纹持久化**：保存浏览器 User Data Profile，实现长期免密登录，大幅降低触发多因素认证（MFA/滑块）的概率。
*   **高并发抢票**：支持同时配置多个场馆、多个时间段，到达 12:30 秒级并发请求。
*   **智能防冲突**：如果目标场地被抢，自动切换到下一个可用场地。
*   **管理员指令**：支持通过 QQ 指令查询场地、重载配置、手动触发任务。

## 📂 目录结构

```text
SzuVenueBooker/
├── src/
│   ├── api.py          # 核心 API 请求封装
│   ├── booker.py       # 抢票业务逻辑与调度
│   └── login.py        # Selenium 自动登录模块
├── scripts/
│   ├── browser_data/   # [自动生成] Chrome 用户配置文件缓存
│   └── init_login.py   # 初始化登录工具（首次使用必跑）
├── config.json         # 配置文件
├── main.py             # 插件入口与定时任务调度
└── README.md           # 说明文档
```

## 🛠️ 环境依赖

### 1. Python 库
请在 LangBot 运行环境中安装以下依赖：
```bash
pip install selenium webdriver_manager apscheduler requests
```

### 2. Google Chrome 浏览器
插件依赖 Chrome 浏览器进行模拟登录。
*   **Windows/Mac**: 确保已安装最新版 Google Chrome。
*   **Ubuntu/Linux 服务器** (必须安装，否则无法运行):
    ```bash
    # 下载安装包
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    # 安装
    sudo apt update
    sudo apt install ./google-chrome-stable_current_amd64.deb
    # 验证安装
    google-chrome --version
    ```

## 🚀 安装与初始化 (SOP)

### 第零步：安装并配置好Langbot
Langbot版本：4.0.8.1，如果使用其他版本可能本插件无法兼容
消息平台：推荐NapCat（OneBot协议）
具体配置方法参考Langbot文档
配置好后在Langbot/plugins文件夹克隆本项目

### 第一步：配置 `config.json`
在插件根目录下编辑 `config.json`：

```json
{
  "admin_qq": "123456789",          // 管理员QQ，接收抢票结果和异常通知
  "stuid": "2020000000",            // 真实学号
  "password": "your_password",      // 统一身份认证密码
  "stuname": "张三",                // 真实姓名
  "cookie": "",                     // 留空，脚本会自动填充
  "request_delay_ms": 300,          // 抢票请求间隔(毫秒)
  "max_duration_minutes": 6,        // 抢票持续时间(分钟)
  "targets": [                      // 抢票目标列表
    {
      "comment": "周三羽毛球19-20",
      "CGDM": "008",                // 场馆代码 (用 #venue list 查询)
      "XMDM": "002",                // 项目代码 (用 #venue list 查询)
      "XQWID": "1",                 // 校区代码 (1:粤海, 2:丽湖)
      "KYYSJD": "19:00-20:00",      // 时间段
      "YYLX": "1.0",                // 预约类型 (1.0：包场, 2.0: 散场)
      "priority": 1
    }
  ]
}
```
具体场馆代码、项目代码、预约类型对应表请查看https://github.com/Matt-Dong123/tools4szu/tree/main/venue-helper/data
### 第二步：初始化登录凭证 
为了避免在服务器上触发验证码，建议首次运行时进行人工引导登录，生成浏览器记忆。

1.  **在有图形界面的环境**（如 Windows 本地或 VNC）运行初始化脚本：
    ```bash
    python scripts/init_login.py
    ```
2.  **操作流程**：
    *   脚本会弹出一个 Chrome 窗口。
    *   它会自动输入账号密码并勾选“七天免登录”。
    *   **如果弹出滑块或短信验证码，请手动完成验证！**
    *   验证成功并跳转进系统后，脚本会自动保存 Cookie 和 Profile，并关闭窗口。
3.  **部署到服务器**：
    *   将生成的 `scripts/browser_data` 文件夹连同代码一起上传到服务器。
    *   服务器端的插件即可利用这份缓存实现无头（Headless）自动登录。

---

## 🎮 指令说明

仅限配置文件中设置的 `admin_qq` 使用。

| 指令 | 说明 |
| :--- | :--- |
| **`#venue help`** | 显示帮助菜单 |
| **`#venue config`** | 重载配置文件（更新抢票目标），不强制检查网络 |
| **`#venue list`** | 列出所有可用的 **场馆代码(CGDM)** 和 **项目代码(XMDM)** |
| **`#venue check`** | 测试连接，查询**明天**粤海校区羽毛球场地的占用情况 |
| **`#venue refresh`** | 手动触发一次 Cookie 强制刷新与维护 |
| **`#venue run`** | **【慎用】** 立即手动触发一次抢票任务（用于测试或捡漏） |

## ⏰ 定时任务逻辑

插件内置了自动调度器，无需人工干预：

1.  **00:00 - 23:59 (每30分钟)**：执行 `Interval` 任务，检查 Cookie 是否存活。若失效，后台静默启动浏览器自动续期。
2.  **12:20:00 (赛前预热)**：强制执行一次登录状态检查，确保 10 分钟后的抢票万无一失。
3.  **12:29:55 (抢票开始)**：
    *   提前 5 秒启动任务线程。
    *   根据 `config.json` 的目标列表轮询。
    *   锁定场地 -> 提交订单 -> 推送结果给管理员。
    *   任务持续 `max_duration_minutes` 分钟后自动停止。

### 第三步：启动Langbot

1.  在配置文件中将`cookie`字段设置为空字符串
2.  启动Langbot
3.  向机器人发送#venue list
4.  如果机器人能够列出场馆代码和项目代码，那么整个流程已经跑通
5.  在每天12:30等待机器人的好消息，去“我的预约”中支付即可。如果不想要可以不管，过期自动作废。


## ⚠️ 常见问题与免责声明

### 关于多因素认证 (MFA)
如果学校 CAS 系统风控升级，强制要求短信验证：
1.  后台自动登录会失败，机器人会向管理员发送报警消息：`⚠️ Cookie 维护失败...触发多因素认证`。
2.  此时请尽快在本地重新运行 `scripts/init_login.py`，手动过一次验证，然后将新的 `browser_data` 更新到服务器即可。
