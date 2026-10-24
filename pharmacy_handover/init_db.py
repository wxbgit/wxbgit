# -*- coding: utf-8 -*-
"""数据库初始化脚本：创建 4 张表并写入默认管理员。

用法： python init_db.py
"""
import os
import sqlite3

from config import DB_PATH, ensure_dirs
from models.db import get_conn

SCHEMA = [
    '''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        work_no TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'pharmacist',
        department TEXT,
        phone TEXT,
        face_code TEXT,
        fingerprint_code TEXT,
        created_at TEXT,
        status INTEGER DEFAULT 1
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS handover_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        handover_time TEXT,
        handover_id INTEGER,
        receive_id INTEGER,
        department TEXT,
        temperature TEXT,
        humidity TEXT,
        fridge_data TEXT,
        narcotic_info TEXT,
        normaldruginfo TEXT,
        highalertdrugs TEXT,
        machine_status TEXT,
        pending_items TEXT,
        abnormal_events TEXT,
        handover_note TEXT,
        handover_sign TEXT,
        receive_sign TEXT,
        excel_path TEXT,
        pdf_path TEXT,
        pdf_hash TEXT,
        content_hash TEXT,
        status TEXT DEFAULT 'completed',
        qr_token TEXT,
        created_at TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS drug_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recordid INTEGER,
        drug_name TEXT,
        spec TEXT,
        batch_no TEXT,
        expiry_date TEXT,
        stock_qty INTEGER,
        unit TEXT,
        drug_type TEXT,
        location TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS system_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        detail TEXT,
        ip_address TEXT,
        created_at TEXT
    )
    ''',
    'CREATE INDEX IF NOT EXISTS idx_handover_time ON handover_records(handover_time)',
    'CREATE INDEX IF NOT EXISTS idx_handover_dept ON handover_records(department)',
    'CREATE INDEX IF NOT EXISTS idx_inventory_record ON drug_inventory(recordid)',
    'CREATE INDEX IF NOT EXISTS idx_logs_created ON system_logs(created_at)',
]


def init_db():
    ensure_dirs()
    conn = get_conn()
    try:
        for sql in SCHEMA:
            conn.execute(sql)
        conn.commit()
    finally:
        conn.close()
    print('数据库表创建完成：%s' % DB_PATH)
    seed_default_users()


def seed_default_users():
    from models import user as user_model
    defaults = [
        ('admin', '系统管理员', 'admin123', 'admin', '门诊药房', '13800000000'),
        ('1001', '张药师', '123456', 'pharmacist', '门诊药房', '13800000001'),
        ('1002', '李药师', '123456', 'pharmacist', '门诊药房', '13800000002'),
    ]
    for work_no, name, pwd, role, dept, phone in defaults:
        if user_model.get_by_work_no(work_no) is None:
            user_model.create_user(work_no, name, pwd, role, dept, phone, status=1)
            print('已创建默认账号：%s / %s（%s）' % (work_no, name, role))
        else:
            print('账号已存在，跳过：%s' % work_no)


if __name__ == '__main__':
    init_db()
