# -*- coding: utf-8 -*-
"""操作日志模型（system_logs 表）。"""
from models.db import query, execute, now_str


def add_log(user_id, action, detail='', ip_address=''):
    try:
        execute(
            'INSERT INTO system_logs(user_id,action,detail,ip_address,created_at) VALUES(?,?,?,?,?)',
            (user_id, action, detail, ip_address, now_str())
        )
    except Exception:
        pass


def list_logs(limit=100, action=''):
    sql = 'SELECT l.*, u.name AS user_name, u.work_no FROM system_logs l LEFT JOIN users u ON u.id=l.user_id'
    args = []
    if action:
        sql += ' WHERE l.action=?'
        args.append(action)
    sql += ' ORDER BY l.id DESC LIMIT ?'
    args.append(limit)
    return [dict(r) for r in query(sql, args)]
