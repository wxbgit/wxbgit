# -*- coding: utf-8 -*-
"""用户模型（users 表）。"""
from models.db import query, execute, now_str
from utils.crypto import hash_password, verify_password


def _row_to_dict(row):
    if row is None:
        return None
    d = dict(row)
    d.pop('password_hash', None)
    return d


def get_by_work_no(work_no):
    return query('SELECT * FROM users WHERE work_no=?', (work_no,), one=True)


def get_by_id(user_id):
    return query('SELECT * FROM users WHERE id=?', (user_id,), one=True)


def create_user(work_no, name, password, role='pharmacist', department='', phone='', status=1):
    if get_by_work_no(work_no):
        return None, '工号已存在'
    if role not in ('admin', 'pharmacist'):
        return None, '角色非法'
    uid = execute(
        'INSERT INTO users(work_no,name,password_hash,role,department,phone,created_at,status) '
        'VALUES(?,?,?,?,?,?,?,?)',
        (work_no, name, hash_password(password), role, department, phone, now_str(), status)
    )
    return uid, ''


def check_login(work_no, password):
    row = get_by_work_no(work_no)
    if row is None:
        return None, '工号不存在'
    if row['status'] != 1:
        return None, '账号已停用，请联系管理员'
    if not verify_password(password, row['password_hash']):
        return None, '密码错误'
    return _row_to_dict(row), ''


def list_users(keyword=''):
    sql = 'SELECT * FROM users WHERE 1=1'
    args = []
    if keyword:
        sql += ' AND (work_no LIKE ? OR name LIKE ? OR department LIKE ?)'
        args += ['%%%s%%' % keyword] * 3
    sql += ' ORDER BY status DESC, id ASC'
    rows = query(sql, args)
    return [_row_to_dict(r) for r in rows]


def update_user(user_id, **fields):
    allowed = ('name', 'role', 'department', 'phone', 'status')
    sets, args = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append('%s=?' % k)
            args.append(v)
    if not sets:
        return False, '没有可更新字段'
    args.append(user_id)
    execute('UPDATE users SET %s WHERE id=?' % ','.join(sets), args)
    return True, ''


def reset_password(user_id, new_password):
    execute('UPDATE users SET password_hash=? WHERE id=?', (hash_password(new_password), user_id))
    return True, ''


def count_users():
    row = query('SELECT COUNT(*) AS c FROM users', one=True)
    return row['c'] if row else 0
