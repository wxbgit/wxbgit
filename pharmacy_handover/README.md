# 药师工作台 · 交接班系统（内网离线版）

Python Flask + SQLite + 纯前端 HTML/JS，单台内网服务器部署，手机浏览器访问，全程不连外网。

## 一、快速启动

```bash
# 1. 安装依赖（Python 3.10+）
pip install -r requirements.txt

# 2. 初始化数据库（自动创建 4 张表 + 默认账号）
python init_db.py

# 3. 启动服务
python app.py
```

默认访问地址：`http://127.0.0.1:5000`（局域网内手机访问 `http://服务器内网IP:5000`）。

### 默认账号

| 工号 | 密码 | 角色 | 说明 |
|---|---|---|---|
| admin | admin123 | 管理员 | 用户管理、全部记录查看与导出 |
| 1001 | 123456 | 药师 | 交接班操作 |
| 1002 | 123456 | 药师 | 交接班操作 |

> 上线前请先在「用户管理」中修改默认密码。

### 常用环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| PH_HOST | 0.0.0.0 | 监听地址 |
| PH_PORT | 5000 | 端口 |
| PH_DEBUG | 1 | 生产部署建议设为 0 |
| PH_CAPTCHA | 1 | 登录验证码开关（自动化测试设 0） |

## 二、功能清单

- **用户管理**：工号+姓名+密码注册（需管理员审核开通）、登录登出、Session 30 分钟无操作自动退出、角色权限控制；用户表预留手机号、科室、人脸/指纹特征码字段（二期）。
- **交接班核心**：工号密码交接 / 扫码交接（二维码）、自动带入上一班次数据、手动补充、双方 Canvas 手写签名、提交前预览确认、提交即写库并生成 Excel 备份。
- **信息采集**：基础信息、位置信息（服务器 IP 映射科室）、药房温湿度、各冰箱温湿度、麻精药品、普通药品、高警示药品、发药机状态、待办事项、异常事件、交接留言、库存快照（近效期≤90 天自动标红）。
- **导出与防篡改**：提交自动生成标准 Excel；PDF 含双方签名 + 时间戳 + 哈希；PDF 生成时计算 SHA256 存入数据库，验证页上传 PDF 重新计算比对，文件被修改即校验失败。
- **规则引擎（轻量版）**：库存预警、近效期提醒、麻精数量波动审计、待办与异常跟踪，首页自动生成接班建议。

## 三、目录结构

```
pharmacy_handover/
├── app.py               # Flask 主入口
├── config.py            # 配置（路径/密钥/科室字典/IP映射）
├── init_db.py           # 数据库初始化脚本
├── requirements.txt
├── models/              # user / handover / log 模型
├── routes/              # auth / handover / history / export / admin
├── utils/               # crypto / excel / pdf / qrcode
├── static/              # css + js（main / handover / signature / qrcode）
├── templates/           # login / dashboard / handover / history / detail / users / verify
├── data/pharmacy.db     # SQLite（自动生成，已 gitignore）
├── exports/             # Excel / PDF 导出归档（按日期+药房命名）
├── logs/app.log         # 运行日志
└── tests/smoke_test.py  # 本地全流程冒烟测试
```

## 四、主要接口

| 接口 | 方法 | 说明 |
|---|---|---|
| /api/captcha | GET | 登录验证码 |
| /api/login / /api/logout | POST | 登录 / 登出 |
| /api/register | POST | 药师注册（待审核） |
| /api/users | GET/POST | 用户列表 / 新增 |
| /api/users/<id> | POST | 修改用户（角色/科室/状态等） |
| /api/users/<id>/reset_password | POST | 重置密码 |
| /api/handover/config | GET | 表单字典（科室/冰箱/高危药品） |
| /api/handover/prefill | GET | 自动带入上一班次数据 |
| /api/handover/qrcode | POST | 生成交接二维码（草稿） |
| /api/handover/token/<token> | GET | 解析二维码 |
| /api/handover/submit | POST | 提交交接班记录 |
| /api/handover/list | GET | 历史记录（分页+筛选） |
| /api/handover/detail/<id> | GET | 记录详情 |
| /api/handover/export_excel/<id> | GET | 导出 Excel |
| /api/handover/export_pdf/<id> | GET | 导出 PDF（?inline=1 预览） |
| /api/handover/verify/<id> | GET | 按记录编号校验完整性 |
| /api/verify/upload | POST | 上传 PDF 校验完整性 |
| /api/handover/export_batch | GET | 管理员批量导出历史 |
| /api/dashboard/stats | GET | 看板统计与建议 |
| /api/logs | GET | 操作日志（管理员） |

## 五、部署要点（内网）

1. 服务器设置固定内网 IP，关闭外网网关/公网出口；药师手机连同一 WiFi 访问 `http://内网IP:5000`。
2. 在 `config.py` 中按院区实际维护：
   - `DEPARTMENTS` 药房列表
   - `FRIDGES` 冰箱模板（名称与正常区间）
   - `HIGH_ALERT_DRUGS` 高警示药品模板
   - `IP_DEPARTMENT_MAP` 服务器 IP → 科室（用于自动定位药房）
3. Windows 开机自启：在计划任务中添加 `python app.py`（工作目录设为项目根目录）；Linux 可用 systemd 或 nohup。
4. 备份：定期拷贝 `data/pharmacy.db` 与 `exports/` 目录；PDF 哈希存于数据库，可用于事后审计。

## 六、测试

```bash
python tests/smoke_test.py    # 自动拉起服务并跑完全流程（登录→交接→签名→导出→验证→权限）
```

覆盖 45 项断言：页面可访问、登录鉴权、自动预填、二维码交接、提交与落库、Excel/PDF 生成、
防篡改校验（原始 PDF 通过 / 篡改 PDF 失败）、权限隔离、页面渲染、登出。

## 七、二期扩展预留

- `users.face_code` / `fingerprint_code`：人脸、指纹特征码字段已建好。
- 温湿度传感器、冰箱监控：对接后只需在 `/api/handover/prefill` 中返回实测值即可自动填入。
- AI 接班建议：`models/handover.py → suggestions()` 目前为规则引擎，可替换为 Ollama + DeepSeek-R1:1.5B 调用。
