import sys
import os

# Windows 终端 UTF-8（必须在任何中文日志输出之前执行）
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import logging
import logging.config
import time
import schedule
import json
import random
from error_watcher import ErrorWatcher
from sensor_updator import SensorUpdator
from datetime import datetime,timedelta
from const import *
from data_fetcher import DataFetcher

def main():
    global RETRY_TIMES_LIMIT
    if 'PYTHON_IN_DOCKER' not in os.environ:
        load_project_env()
    if os.path.isfile('/data/options.json'):
        with open('/data/options.json') as f:
            options = json.load(f)
        try:
            for key, value in options.items():
                os.environ[key] = str(value)
            logging.info("当前以 Home Assistant Add-on 形式运行")
        except Exception as e:
            logging.error(f"读取 options.json 失败，程序退出: {e}")
            sys.exit()

    try:
        PHONE_NUMBER = os.getenv("PHONE_NUMBER")
        PASSWORD = os.getenv("PASSWORD")
        HASS_URL = os.getenv("HASS_URL")
        JOB_START_TIME = os.getenv("JOB_START_TIME", "09:30")
        RUN_ON_STARTUP = os.getenv("RUN_ON_STARTUP", "false").strip().strip('"').strip("'").lower() in ("true", "1", "yes")
        LOG_LEVEL = os.getenv("LOG_LEVEL","INFO")
        VERSION = os.getenv("VERSION")
        RETRY_TIMES_LIMIT = int(os.getenv("RETRY_TIMES_LIMIT", 5))
        
        logger_init(LOG_LEVEL)
        if 'PYTHON_IN_DOCKER' in os.environ:
            logging.info("当前运行在 Docker 容器中")
        else:
            logging.info("当前运行在本地环境")
        logging.info(f"登录账号: {PHONE_NUMBER}")
        logging.info(f"RUN_ON_STARTUP={os.getenv('RUN_ON_STARTUP', 'false')} (生效: {'是' if RUN_ON_STARTUP else '否'})")
    except Exception as e:
        logging.error(f"读取环境变量失败，程序退出: {e}")
        sys.exit()

    logging.info(f"当前版本: {VERSION}，仓库地址: {REPO_URL}")
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"当前时间: {current_datetime}")

    logging.info("正在初始化 ErrorWatcher...")
    error_dir = os.path.join(get_data_dir(), 'errors')
    ErrorWatcher.init(root_dir=error_dir)
    logging.info("ErrorWatcher 初始化完成")
    fetcher = DataFetcher(PHONE_NUMBER, PASSWORD)
    updator = SensorUpdator()

    # 生成随机延迟时间（-10分钟到+10分钟）
    random_delay_minutes = random.randint(-10, 10)
    parsed_time = datetime.strptime(JOB_START_TIME, "%H:%M") + timedelta(minutes=random_delay_minutes)
    logging.info(f"登录账号: {PHONE_NUMBER}，Home Assistant 地址: {HASS_URL}，每天 {parsed_time.strftime('%H:%M')} 定时同步")

    # 添加随机延迟
    next_run_time = parsed_time + timedelta(hours=12)

    logging.info(f"定时任务已注册，每天 {parsed_time.strftime('%H:%M')} 和 {next_run_time.strftime('%H:%M')} 各执行一次")
    schedule.every().day.at(parsed_time.strftime("%H:%M")).do(run_task, fetcher)
    schedule.every().day.at(next_run_time.strftime("%H:%M")).do(run_task, fetcher)
    
    # 每5分钟重发一次数据，防止HA重启后数据丢失
    schedule.every(5).minutes.do(updator.republish)
    
    # 启动时抓取策略：
    # RUN_ON_STARTUP=true  → 立即登录抓取（Docker 调试/首次部署推荐）
    # 否则先尝试缓存恢复，无缓存才抓取（有缓存则等到定时任务，避免频繁重启封号）
    if RUN_ON_STARTUP:
        logging.info("RUN_ON_STARTUP 已启用，启动后立即执行登录与数据抓取...")
        run_task(fetcher)
    elif not updator.republish():
        logging.info("未找到有效缓存，立即从国家电网抓取数据...")
        run_task(fetcher)
    else:
        logging.info("已从缓存恢复数据，跳过启动时抓取，等待定时任务执行。")
    
    while True:
        schedule.run_pending()
        time.sleep(1)


def run_task(data_fetcher: DataFetcher):
    for retry_times in range(1, RETRY_TIMES_LIMIT + 1):
        try:
            data_fetcher.fetch()
            return
        except Exception as e:
            logging.error(f"数据同步任务失败: [{e}]，剩余重试次数 {RETRY_TIMES_LIMIT - retry_times}")
            continue

def logger_init(level: str):
    logger = logging.getLogger()
    logger.setLevel(level)
    # 移除所有默认 handler，避免重复输出（解决 INFO:root: 乱码问题）
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)
    fmt = logging.Formatter("%(asctime)s  [%(levelname)-8s] ---- %(message)s", "%Y-%m-%d %H:%M:%S")
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)


if __name__ == "__main__":
    main()
