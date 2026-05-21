import os

# 国网电力官网
LOGIN_URL = "https://95598.cn/osgweb/login"
ELECTRIC_USAGE_URL = "https://95598.cn/osgweb/electricityCharge"
BALANCE_URL = "https://95598.cn/osgweb/userAcc"
BILL_SUMMARY_URL = "https://95598.cn/osgweb/electricityCharge"
STEP_ELECTRICITY_URL = "https://95598.cn/osgweb/stepElectricityConsumption"
ELECTRIC_BILL_SUMMARY_URL = (
    "https://95598.cn/osgweb01/electricityChargeQuery/queryElectricBillSummary"
)

# Home Assistant
SUPERVISOR_URL = "http://supervisor/core"
API_PATH = "/api/states/"

BALANCE_SENSOR_NAME = "sensor.electricity_charge_balance"
DAILY_USAGE_SENSOR_NAME = "sensor.last_electricity_usage"
YEARLY_USAGE_SENSOR_NAME = "sensor.yearly_electricity_usage"
YEARLY_CHARGE_SENSOR_NAME = "sensor.yearly_electricity_charge"
MONTH_USAGE_SENSOR_NAME = "sensor.month_electricity_usage"
MONTH_CHARGE_SENSOR_NAME = "sensor.month_electricity_charge"
MONTH_VALLEY_SENSOR_NAME = "sensor.month_valley_usage"
MONTH_FLAT_SENSOR_NAME = "sensor.month_flat_usage"
MONTH_PEAK_SENSOR_NAME = "sensor.month_peak_usage"
MONTH_TIP_SENSOR_NAME = "sensor.month_tip_usage"
PREPAY_BALANCE_SENSOR_NAME = "sensor.prepay_balance"
BALANCE_UNIT = "CNY"
USAGE_UNIT = "KWH"

# 项目仓库
REPO_URL = "https://github.com/Poiig/ha_sgcc_electricity"


def get_data_dir() -> str:
    """获取数据存储目录：Docker 用 /data，本地用项目下的 data/"""
    if 'PYTHON_IN_DOCKER' in os.environ:
        return '/data'
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def load_project_env() -> None:
    """加载项目根目录 .env（本地开发时 cwd 可能在 scripts/）。"""
    if 'PYTHON_IN_DOCKER' in os.environ:
        return
    import dotenv
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
    dotenv.load_dotenv(env_path, verbose=True, override=True)

