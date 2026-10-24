# -*- coding: utf-8 -*-
"""交接班核心路由：二维码、预填、提交。"""
from flask import Blueprint, request, render_template

from config import (DEPARTMENTS, FRIDGES, HIGH_ALERT_DRUGS, ABNORMAL_EVENTS,
                    SAFE_STATUS, EXPIRY_WARNING_DAYS, IP_DEPARTMENT_MAP)
from models import handover as hv_model
from models import user as user_model
from models import log as log_model
from models.db import now_str
from utils.excel import build_excel
from utils.pdf import build_pdf
from utils.qrcode import make_qr_base64
from routes.auth import login_required, current_user, ok, fail, get_ip

handover_bp = Blueprint('handover', __name__)


def department_by_ip():
    ip = get_ip()
    return IP_DEPARTMENT_MAP.get(ip, '')


@handover_bp.route('/handover')
@login_required
def handover_page():
    return render_template('handover.html',
                           departments=DEPARTMENTS,
                           fridges=FRIDGES,
                           high_alert_drugs=HIGH_ALERT_DRUGS,
                           abnormal_events=ABNORMAL_EVENTS,
                           safe_status=SAFE_STATUS,
                           expiry_days=EXPIRY_WARNING_DAYS,
                           default_department=current_user().get('department') or department_by_ip())


@handover_bp.route('/api/handover/config')
@login_required
def handover_config():
    return ok({
        'departments': DEPARTMENTS,
        'fridges': FRIDGES,
        'high_alert_drugs': HIGH_ALERT_DRUGS,
        'abnormal_events': ABNORMAL_EVENTS,
        'safe_status': SAFE_STATUS,
        'expiry_days': EXPIRY_WARNING_DAYS,
        'ip_department': department_by_ip(),
        'server_time': now_str(),
    })


@handover_bp.route('/api/handover/prefill')
@login_required
def prefill():
    """自动采集：取上一班次数据作为本班初始值。"""
    department = request.args.get('department') or department_by_ip()
    last = hv_model.last_record(department) or hv_model.last_record()
    if not last:
        return ok({'found': False, 'department': department, 'server_time': now_str()})
    return ok({
        'found': True,
        'department': department,
        'server_time': now_str(),
        'last': {
            'id': last['id'],
            'handover_time': last.get('handover_time'),
            'department': last.get('department'),
            'temperature': last.get('temperature'),
            'humidity': last.get('humidity'),
            'fridge_data': last.get('fridge_data'),
            'narcotic_info': last.get('narcotic_info'),
            'normaldruginfo': last.get('normaldruginfo'),
            'highalertdrugs': last.get('highalertdrugs'),
            'machine_status': last.get('machine_status'),
            'pending_items': last.get('pending_items'),
        },
        'items': hv_model.get_inventory(last['id']),
    })


@handover_bp.route('/api/handover/qrcode', methods=['POST'])
@login_required
def create_qrcode():
    """交班药师生成交接二维码（草稿记录）。"""
    data = request.get_json(silent=True) or {}
    form = data.get('form') or {}
    department = data.get('department') or form.get('department') or current_user().get('department') or department_by_ip()
    rid, token = hv_model.create_draft(current_user()['id'], department, form)
    if form.get('items'):
        hv_model.save_inventory(rid, form['items'])
    url = request.host_url.rstrip('/') + '/handover?token=' + token
    log_model.add_log(current_user()['id'], 'qrcode', '生成交接二维码 No%s' % rid, get_ip())
    return ok({
        'record_id': rid,
        'token': token,
        'url': url,
        'qrcode': make_qr_base64(url),
        'department': department,
    }, '二维码已生成，请接班药师扫码')


@handover_bp.route('/api/handover/token/<token>')
@login_required
def token_info(token):
    rec = hv_model.get_by_token(token)
    if not rec:
        return fail('二维码无效或已失效')
    return ok({
        'record_id': rec['id'],
        'department': rec.get('department'),
        'handover_time': rec.get('handover_time'),
        'handover_name': hv_model._user_name(rec.get('handover_id')),
        'status': rec.get('status'),
        'temperature': rec.get('temperature'),
        'humidity': rec.get('humidity'),
        'fridge_data': rec.get('fridge_data'),
        'narcotic_info': rec.get('narcotic_info'),
        'normaldruginfo': rec.get('normaldruginfo'),
        'highalertdrugs': rec.get('highalertdrugs'),
        'machine_status': rec.get('machine_status'),
        'pending_items': rec.get('pending_items'),
        'abnormal_events': rec.get('abnormal_events'),
        'handover_note': rec.get('handover_note'),
        'handover_sign': rec.get('handover_sign'),
        'items': rec.get('items') or [],
    })


@handover_bp.route('/api/handover/submit', methods=['POST'])
@login_required
def submit():
    data = request.get_json(silent=True) or {}
    cur = current_user()

    department = str(data.get('department') or '').strip() or cur.get('department') or department_by_ip()
    if not department:
        return fail('请填写所在药房')

    handover_sign = data.get('handover_sign') or ''
    receive_sign = data.get('receive_sign') or ''
    if not handover_sign or not receive_sign:
        return fail('交班药师与接班药师必须完成手写签名')

    # 接班药师身份确认：扫码（token）或工号+密码
    token = str(data.get('token') or '').strip()
    receive_id = None
    handover_id = cur['id']
    if token:
        draft = hv_model.get_by_token(token)
        if not draft:
            return fail('交接二维码无效')
        if draft.get('handover_id') == cur['id']:
            return fail('接班药师不能与交班药师为同一人，请将二维码交由接班药师扫码')
        handover_id = draft.get('handover_id') or cur['id']
        receive_id = cur['id']

    work_no = str(data.get('receive_work_no') or '').strip()
    password = str(data.get('receive_password') or '').strip()
    if work_no:
        if not password:
            return fail('请输入接班药师密码')
        rrow, err = user_model.check_login(work_no, password)
        if err:
            return fail('接班药师身份验证失败：%s' % err)
        if rrow['id'] == handover_id:
            return fail('交班人与接班人不能为同一人')
        receive_id = rrow['id']
    if not receive_id:
        return fail('请通过扫码或工号密码完成接班人确认')

    payload = {
        'handover_time': data.get('handover_time') or now_str(),
        'handover_id': handover_id,
        'receive_id': receive_id,
        'department': department,
        'temperature': data.get('temperature'),
        'humidity': data.get('humidity'),
        'fridge_data': data.get('fridge_data') or {},
        'narcotic_info': data.get('narcotic_info') or {},
        'normaldruginfo': data.get('normaldruginfo') or {},
        'highalertdrugs': data.get('highalertdrugs') or {},
        'machine_status': data.get('machine_status') or {},
        'pending_items': data.get('pending_items') or {},
        'abnormal_events': data.get('abnormal_events') or {},
        'handover_note': data.get('handover_note') or '',
        'handover_sign': handover_sign,
        'receive_sign': receive_sign,
        'status': 'completed',
    }

    draft = hv_model.get_by_token(token) if token else None
    if draft:
        # 扫码交接：以交班药师填写的内容为底稿，接班药师的填写覆盖之
        for f in hv_model.DRAFT_FIELDS:
            if not payload.get(f) and draft.get(f):
                payload[f] = draft[f]
        record_id = hv_model.update_record(draft['id'], payload)
    else:
        record_id = hv_model.create_record(payload)

    items = data.get('items') or []
    if items or not draft:
        hv_model.save_inventory(record_id, items)

    # 生成 Excel 备份 + PDF（含哈希）
    record = hv_model.get_record(record_id)
    excel_path = build_excel(record)
    pdf_path, file_hash, chash = build_pdf(record)
    hv_model.set_paths(record_id, excel_path=excel_path, pdf_path=pdf_path, pdf_hash=file_hash)
    hv_model.update_record(record_id, {'content_hash': chash})

    log_model.add_log(cur['id'], 'submit', '提交交接班记录 No%s（%s）' % (record_id, department), get_ip())
    return ok({
        'id': record_id,
        'excel_path': excel_path,
        'pdf_path': pdf_path,
        'pdf_hash': file_hash,
        'content_hash': chash,
    }, '交接班提交成功')
