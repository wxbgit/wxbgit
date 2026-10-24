# -*- coding: utf-8 -*-
"""交接班记录模型（handover_records + drug_inventory 表）。"""
import json
from datetime import datetime, timedelta

from models.db import query, execute, now_str
from utils.crypto import new_token

JSON_FIELDS = (
    'fridge_data', 'narcotic_info', 'normaldruginfo', 'highalertdrugs',
    'machine_status', 'pending_items', 'abnormal_events',
)


def json_loads(value, default=None):
    if default is None:
        default = {}
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _row_to_dict(row):
    if row is None:
        return None
    d = dict(row)
    for f in JSON_FIELDS:
        d[f] = json_loads(d.get(f), {} if f != 'abnormal_events' else {})
    return d


# ---------------- 写入 ----------------

DRAFT_FIELDS = (
    'handover_time', 'temperature', 'humidity', 'fridge_data', 'narcotic_info',
    'normaldruginfo', 'highalertdrugs', 'machine_status', 'pending_items',
    'abnormal_events', 'handover_note', 'handover_sign',
)


def create_draft(handover_id, department, payload=None, handover_time=None):
    """生成扫码交接用的草稿记录（可携带交班药师已填写的内容），返回 (record_id, token)。"""
    token = new_token()
    data = {
        'handover_id': handover_id,
        'department': department,
        'handover_time': handover_time or (payload or {}).get('handover_time') or now_str(),
        'status': 'draft',
        'qr_token': token,
    }
    for f in DRAFT_FIELDS:
        v = (payload or {}).get(f)
        if v not in (None, '', {}, []):
            data[f] = v
    rid = create_record(data)
    return rid, token


def get_by_token(token):
    return _row_to_dict(query('SELECT * FROM handover_records WHERE qr_token=?', (token,), one=True))


def create_record(payload):
    """新建交接班记录（提交时调用）。"""
    cols = [
        'handover_time', 'handover_id', 'receive_id', 'department',
        'temperature', 'humidity', 'fridge_data', 'narcotic_info',
        'normaldruginfo', 'highalertdrugs', 'machine_status', 'pending_items',
        'abnormal_events', 'handover_note', 'handover_sign', 'receive_sign',
        'status', 'qr_token',
    ]
    cols = cols + ['created_at']
    values = []
    for c in cols:
        v = now_str() if c == 'created_at' else payload.get(c)
        if c in JSON_FIELDS and not isinstance(v, str):
            v = json.dumps(v or {}, ensure_ascii=False)
        values.append(v)
    sql = 'INSERT INTO handover_records(%s) VALUES(%s)' % (','.join(cols), ','.join(['?'] * len(cols)))
    return execute(sql, values)


def update_record(record_id, payload):
    sets, args = [], []
    for c in (
        'handover_time', 'handover_id', 'receive_id', 'department', 'temperature', 'humidity',
        'fridge_data', 'narcotic_info', 'normaldruginfo', 'highalertdrugs', 'machine_status',
        'pending_items', 'abnormal_events', 'handover_note', 'handover_sign', 'receive_sign',
        'status', 'excel_path', 'pdf_path', 'pdf_hash', 'content_hash',
    ):
        if c in payload:
            v = payload[c]
            if c in JSON_FIELDS and not isinstance(v, str):
                v = json.dumps(v or {}, ensure_ascii=False)
            sets.append('%s=?' % c)
            args.append(v)
    if not sets:
        return record_id
    args.append(record_id)
    execute('UPDATE handover_records SET %s WHERE id=?' % ','.join(sets), args)
    return record_id


def set_paths(record_id, excel_path=None, pdf_path=None, pdf_hash=None):
    sets, args = [], []
    if excel_path is not None:
        sets.append('excel_path=?')
        args.append(excel_path)
    if pdf_path is not None:
        sets.append('pdf_path=?')
        args.append(pdf_path)
    if pdf_hash is not None:
        sets.append('pdf_hash=?')
        args.append(pdf_hash)
    if not sets:
        return
    args.append(record_id)
    execute('UPDATE handover_records SET %s WHERE id=?' % ','.join(sets), args)


# ---------------- 查询 ----------------

def get_record(record_id):
    row = query('SELECT * FROM handover_records WHERE id=?', (record_id,), one=True)
    rec = _row_to_dict(row)
    if rec:
        rec['handover_name'] = _user_name(rec.get('handover_id'))
        rec['receive_name'] = _user_name(rec.get('receive_id'))
        rec['items'] = get_inventory(record_id)
    return rec


def _user_name(user_id):
    if not user_id:
        return ''
    row = query('SELECT name FROM users WHERE id=?', (user_id,), one=True)
    return row['name'] if row else ''


def list_records(filters=None, scope_user_id=None, page=1, per_page=20):
    filters = filters or {}
    sql = ('SELECT r.*, a.name AS handover_name, b.name AS receive_name '
           'FROM handover_records r '
           'LEFT JOIN users a ON a.id=r.handover_id '
           'LEFT JOIN users b ON b.id=r.receive_id '
           "WHERE r.status='completed'")
    args = []
    if filters.get('start_date'):
        sql += ' AND date(r.handover_time) >= date(?)'
        args.append(filters['start_date'])
    if filters.get('end_date'):
        sql += ' AND date(r.handover_time) <= date(?)'
        args.append(filters['end_date'])
    if filters.get('department'):
        sql += ' AND r.department=?'
        args.append(filters['department'])
    if filters.get('keyword'):
        sql += ' AND (a.name LIKE ? OR b.name LIKE ? OR a.work_no LIKE ? OR b.work_no LIKE ?)'
        args += ['%%%s%%' % filters['keyword']] * 4
    if scope_user_id:
        sql += ' AND (r.handover_id=? OR r.receive_id=?)'
        args += [scope_user_id, scope_user_id]
    total = query('SELECT COUNT(*) AS c FROM (%s) t' % sql, args, one=True)['c']
    sql += ' ORDER BY r.id DESC LIMIT ? OFFSET ?'
    args += [per_page, (page - 1) * per_page]
    rows = query(sql, args)
    return {
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
        'list': [dict(r) for r in rows],
    }


def last_record(department=None):
    sql = "SELECT * FROM handover_records WHERE status='completed'"
    args = []
    if department:
        sql += ' AND department=?'
        args.append(department)
    sql += ' ORDER BY id DESC LIMIT 1'
    return _row_to_dict(query(sql, args, one=True))


def find_by_hash(pdf_hash):
    if not pdf_hash:
        return None
    row = query('SELECT * FROM handover_records WHERE pdf_hash=?', (pdf_hash,), one=True)
    return _row_to_dict(row)


# ---------------- 库存快照 ----------------

def save_inventory(record_id, items):
    execute('DELETE FROM drug_inventory WHERE recordid=?', (record_id,))
    for it in items or []:
        execute(
            'INSERT INTO drug_inventory(recordid,drug_name,spec,batch_no,expiry_date,stock_qty,unit,drug_type,location) '
            'VALUES(?,?,?,?,?,?,?,?,?)',
            (record_id, it.get('drug_name', ''), it.get('spec', ''), it.get('batch_no', ''),
             it.get('expiry_date', ''), int(it.get('stock_qty') or 0), it.get('unit', ''),
             it.get('drug_type', '普通'), it.get('location', ''))
        )


def get_inventory(record_id):
    rows = query('SELECT * FROM drug_inventory WHERE recordid=? ORDER BY id ASC', (record_id,))
    result = []
    for r in rows:
        d = dict(r)
        d['near_expiry'] = is_near_expiry(d.get('expiry_date'))
        result.append(d)
    return result


def is_near_expiry(expiry_date, days=90):
    if not expiry_date:
        return False
    try:
        d = datetime.strptime(str(expiry_date)[:10], '%Y-%m-%d')
    except Exception:
        return False
    return 0 <= (d - datetime.now()).days <= days


def near_expiry_items(record_id=None, limit=20):
    if record_id:
        rows = query('SELECT * FROM drug_inventory WHERE recordid=?', (record_id,))
    else:
        rows = query('SELECT * FROM drug_inventory WHERE recordid=(SELECT MAX(id) FROM handover_records)')
    result = []
    for r in rows:
        d = dict(r)
        if is_near_expiry(d.get('expiry_date')):
            result.append(d)
    return result[:limit]


# ---------------- 规则引擎（二期 5.x 轻量版） ----------------

def suggestions(department=None):
    """基于上一班次数据生成接班建议（库存预警 / 近效期 / 麻精审计）。"""
    from config import MACHINE_LOW_THRESHOLD
    tips = []
    last = last_record(department) or last_record()
    if not last:
        return tips

    mach = json_loads(last.get('machine_status'), {})
    try:
        fast = float(mach.get('fast_machine') or 0)
    except Exception:
        fast = 0
    try:
        shelf = float(mach.get('smart_shelf') or 0)
    except Exception:
        shelf = 0
    if fast and fast < MACHINE_LOW_THRESHOLD:
        tips.append({'level': 'high', 'type': '库存预警',
                     'text': '快速发药机余量仅 %.0f%%，低于 %d%%，建议立即补货' % (fast, MACHINE_LOW_THRESHOLD)})
    if shelf and shelf < MACHINE_LOW_THRESHOLD:
        tips.append({'level': 'high', 'type': '库存预警',
                     'text': '智能药架余量仅 %.0f%%，建议补货' % shelf})

    near = near_expiry_items(last['id'])
    if near:
        names = '、'.join([n['drug_name'] for n in near[:5]])
        tips.append({'level': 'mid', 'type': '近效期提醒',
                     'text': '近效期（≤90天）药品 %d 个：%s，建议优先调配' % (len(near), names)})

    prev = query("SELECT * FROM handover_records WHERE status='completed' AND id<? ORDER BY id DESC LIMIT 1",
                 (last['id'],), one=True)
    if prev:
        prev_nar = json_loads(prev['narcotic_info'] if 'narcotic_info' in prev.keys() else None, {})
        cur_nar = json_loads(last.get('narcotic_info'), {})
        try:
            p = float(prev_nar.get('stock_qty') or 0)
            c = float(cur_nar.get('stock_qty') or 0)
            if p > 0 and abs(c - p) / p > 0.3:
                tips.append({'level': 'high', 'type': '麻精审计',
                             'text': '麻精药品在库数量较上班次波动 %.0f%%，请核对账册' % (abs(c - p) / p * 100)})
        except Exception:
            pass

    pend = json_loads(last.get('pending_items'), {})
    total_pending = 0
    for v in pend.values():
        try:
            total_pending += int(v or 0)
        except Exception:
            pass
    if total_pending > 0:
        tips.append({'level': 'mid', 'type': '待办提醒',
                     'text': '上班次遗留待办 %d 项，接班后请优先处理' % total_pending})

    abn = json_loads(last.get('abnormal_events'), {})
    if abn.get('events'):
        tips.append({'level': 'high', 'type': '异常跟踪',
                     'text': '上班次发生异常：%s，请跟进处理' % '、'.join(abn.get('events', []))})
    return tips


# ---------------- 统计 ----------------

def stats(scope_user_id=None):
    today = datetime.now().strftime('%Y-%m-%d')
    total = query("SELECT COUNT(*) AS c FROM handover_records WHERE status='completed'", one=True)['c']
    today_cnt = query(
        "SELECT COUNT(*) AS c FROM handover_records WHERE status='completed' AND date(handover_time)=date(?)",
        (today,), one=True)['c']
    month_cnt = query(
        "SELECT COUNT(*) AS c FROM handover_records WHERE status='completed' "
        "AND strftime('%Y-%m', handover_time)=strftime('%Y-%m','now')", one=True)['c']
    abnormal = 0
    rows = query("SELECT abnormal_events FROM handover_records WHERE status='completed' "
                 "ORDER BY id DESC LIMIT 50")
    pending_sum = {}
    for r in rows:
        ev = json_loads(r['abnormal_events'], {})
        if ev.get('events'):
            abnormal += 1
    last = last_record()
    pending = {}
    if last:
        pending = json_loads(last.get('pending_items'), {})
        for k, v in pending.items():
            try:
                pending_sum[k] = int(v or 0)
            except Exception:
                pending_sum[k] = 0
    near = len(near_expiry_items(last['id'] if last else None)) if last else 0
    dept_rows = query("SELECT department, COUNT(*) AS c FROM handover_records WHERE status='completed' "
                      "GROUP BY department ORDER BY c DESC LIMIT 10")
    return {
        'total_records': total,
        'today_records': today_cnt,
        'month_records': month_cnt,
        'user_count': query('SELECT COUNT(*) AS c FROM users', one=True)['c'],
        'abnormal_recent': abnormal,
        'near_expiry_count': near,
        'pending_items': pending_sum,
        'last_record': {
            'id': last['id'], 'handover_time': last.get('handover_time'),
            'department': last.get('department'),
        } if last else None,
        'department_stats': [dict(r) for r in dept_rows],
        'suggestions': suggestions(),
        'expiry_warning_days': 90,
        'generated_at': now_str(),
    }
