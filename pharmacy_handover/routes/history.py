# -*- coding: utf-8 -*-
"""历史记录查询 / 详情 / 看板。"""
from flask import Blueprint, request, render_template

from config import DEPARTMENTS, IP_DEPARTMENT_MAP
from models import handover as hv_model
from models import log as log_model
from routes.auth import login_required, current_user, ok, fail, get_ip

history_bp = Blueprint('history', __name__)


def _scope():
    """普通药师只看本人记录，管理员看全部。"""
    cur = current_user()
    return None if cur['role'] == 'admin' else cur['id']


@history_bp.route('/')
@login_required
def dashboard_page():
    return render_template('dashboard.html', departments=DEPARTMENTS)


@history_bp.route('/api/dashboard/stats')
@login_required
def dashboard_stats():
    data = hv_model.stats()
    return ok(data)


@history_bp.route('/history')
@login_required
def history_page():
    return render_template('history.html', departments=DEPARTMENTS)


@history_bp.route('/api/handover/list')
@login_required
def handover_list():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
    except Exception:
        page, per_page = 1, 20
    filters = {
        'start_date': request.args.get('start_date', ''),
        'end_date': request.args.get('end_date', ''),
        'department': request.args.get('department', ''),
        'keyword': request.args.get('keyword', ''),
    }
    result = hv_model.list_records(filters, scope_user_id=_scope(), page=page, per_page=per_page)
    return ok(result)


@history_bp.route('/detail/<int:record_id>')
@login_required
def detail_page(record_id):
    rec = hv_model.get_record(record_id)
    if not rec:
        return render_template('detail.html', record=None, error='记录不存在')
    return render_template('detail.html', record=rec, error=None)


@history_bp.route('/api/handover/detail/<int:record_id>')
@login_required
def handover_detail(record_id):
    rec = hv_model.get_record(record_id)
    if not rec:
        return fail('记录不存在', 404, 404)
    cur = current_user()
    if cur['role'] != 'admin' and cur['id'] not in (rec.get('handover_id'), rec.get('receive_id')):
        return fail('无权查看他人交接班记录', 403, 403)
    log_model.add_log(cur['id'], 'view', '查看交接班记录 No%s' % record_id, get_ip())
    return ok({'record': rec})
