# -*- coding: utf-8 -*-
"""管理员路由：用户管理、日志、批量导出。"""
import os
from datetime import datetime

from flask import Blueprint, request, send_file, render_template

from config import DEPARTMENTS
from models import user as user_model
from models import handover as hv_model
from models import log as log_model
from utils.excel import build_history_excel
from routes.auth import login_required, admin_required, current_user, ok, fail, get_ip

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/users')
@login_required
@admin_required
def users_page():
    return render_template('users.html', departments=DEPARTMENTS)


@admin_bp.route('/api/users', methods=['GET', 'POST'])
@login_required
@admin_required
def users_api():
    if request.method == 'GET':
        return ok({'list': user_model.list_users(request.args.get('keyword', ''))})
    data = request.get_json(silent=True) or {}
    work_no = str(data.get('work_no', '')).strip()
    name = str(data.get('name', '')).strip()
    password = str(data.get('password', '')).strip() or '123456'
    role = data.get('role', 'pharmacist')
    if not work_no or not name:
        return fail('工号和姓名不能为空')
    uid, err = user_model.create_user(work_no, name, password, role,
                                      data.get('department', ''), data.get('phone', ''),
                                      status=int(data.get('status', 1)))
    if err:
        return fail(err)
    log_model.add_log(current_user()['id'], 'user_add', '新增用户 %s(%s)' % (name, work_no), get_ip())
    return ok({'id': uid}, '用户创建成功')


@admin_bp.route('/api/users/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    fields = {}
    for k in ('name', 'role', 'department', 'phone'):
        if k in data:
            fields[k] = data[k]
    if 'status' in data:
        fields['status'] = int(data['status'])
    flag, err = user_model.update_user(user_id, **fields)
    if err:
        return fail(err)
    log_model.add_log(current_user()['id'], 'user_update', '修改用户 %s：%s' % (user_id, fields), get_ip())
    return ok(msg='已保存')


@admin_bp.route('/api/users/<int:user_id>/reset_password', methods=['POST'])
@login_required
@admin_required
def reset_password(user_id):
    data = request.get_json(silent=True) or {}
    pwd = str(data.get('password', '')).strip() or '123456'
    user_model.reset_password(user_id, pwd)
    log_model.add_log(current_user()['id'], 'user_reset_pwd', '重置用户 %s 密码' % user_id, get_ip())
    return ok(msg='密码已重置为：%s' % pwd)


@admin_bp.route('/api/logs')
@login_required
@admin_required
def logs_api():
    return ok({'list': log_model.list_logs(limit=int(request.args.get('limit', 100)),
                                           action=request.args.get('action', ''))})


@admin_bp.route('/api/handover/export_batch')
@login_required
@admin_required
def export_batch():
    """按条件批量导出历史记录 Excel。"""
    filters = {
        'start_date': request.args.get('start_date', ''),
        'end_date': request.args.get('end_date', ''),
        'department': request.args.get('department', ''),
        'keyword': request.args.get('keyword', ''),
    }
    result = hv_model.list_records(filters, page=1, per_page=2000)
    fname = '交接班历史_%s.xlsx' % datetime.now().strftime('%Y%m%d%H%M%S')
    path = build_history_excel(result['list'], fname)
    log_model.add_log(current_user()['id'], 'export', '批量导出历史记录 %d 条' % len(result['list']), get_ip())
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))
