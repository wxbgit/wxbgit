# -*- coding: utf-8 -*-
"""全局配置：路径、密钥、科室字典、冰箱与高危药品模板等。"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
EXPORT_DIR = os.path.join(BASE_DIR, 'exports')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
DB_PATH = os.path.join(DATA_DIR, 'pharmacy.db')
LOG_FILE = os.path.join(LOG_DIR, 'app.log')

SECRET_KEY = 'pharmacy-handover-intranet-secret-key'
SESSION_TIMEOUT_MINUTES = 30      # 30 分钟无操作自动退出
PERMANENT_SESSION = True

HOST = os.environ.get('PH_HOST', '0.0.0.0')
PORT = int(os.environ.get('PH_PORT', '5000'))
DEBUG = os.environ.get('PH_DEBUG', '1') == '1'
# 登录图形验证码开关（内网部署默认开启；自动化测试可通过 PH_CAPTCHA=0 关闭）
CAPTCHA_ENABLED = os.environ.get('PH_CAPTCHA', '1') == '1'

# 药房/科室列表（可在 config 中手动维护）
DEPARTMENTS = ['门诊药房', '急诊药房', '住院药房', '中药房', '静配中心']

# 冰箱模板：name 名称，range 正常范围提示
FRIDGES = [
    {'key': 'fridge_2_8', 'name': '2~8℃冷藏冰箱', 'min': 2, 'max': 8},
    {'key': 'fridge_neg20', 'name': '-20℃冷冻冰箱', 'min': -25, 'max': -15},
    {'key': 'fridge_neg80', 'name': '-80℃超低温冰箱', 'min': -90, 'max': -70},
]

# 高警示药品模板
HIGH_ALERT_DRUGS = [
    '10%氯化钾注射液', '10%氯化钠注射液', '胰岛素（各类）',
    '肝素钠注射液', '化疗药物', '高浓度电解质',
]

# 服务器 IP -> 科室（位置信息自动采集；未命中则药师手动选择）
IP_DEPARTMENT_MAP = {
    '127.0.0.1': '门诊药房',
    '::1': '门诊药房',
}

EXPIRY_WARNING_DAYS = 90           # 近效期判定阈值（天）
MACHINE_LOW_THRESHOLD = 30         # 发药机余量低于该百分比提示补货

# 异常事件选项
ABNORMAL_EVENTS = ['药品报损', '患者投诉', '系统故障', '停电', '设备故障', '其他']

# 保险柜状态选项
SAFE_STATUS = ['正常', '异常', '已维修']


class Config:
    SECRET_KEY = SECRET_KEY
    DEBUG = DEBUG
    JSON_AS_ASCII = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024


def ensure_dirs():
    for d in (DATA_DIR, EXPORT_DIR, LOG_DIR):
        os.makedirs(d, exist_ok=True)
