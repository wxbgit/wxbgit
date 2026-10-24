# -*- coding: utf-8 -*-
"""导出（Excel / PDF）与防篡改验证路由。"""
import os

from flask import Blueprint, request, send_file, render_template

from models import handover as hv_model
from models import log as log_model
from utils.excel import build_excel
from utils.pdf import build_pdf, content_hash
from utils.crypto import sha256_hex, sha256_file
from routes.auth import login_required, current_user, ok, fail, get_ip

export_bp = Blueprint('export', __name__)


def _check_permission(rec):
    cur = current_user()
    if cur['role'] == 'admin':
        return True
    return cur['id'] in (rec.get('handover_id'), rec.get('receive_id'))


def _ensure_pdf(rec):
    """PDF 文件缺失时重新生成并更新哈希。"""
    path = rec.get('pdf_path')
    if path and os.path.exists(path):
        return path
    fresh = hv_model.get_record(rec['id'])
    path, file_hash, chash = build_pdf(fresh)
    hv_model.set_paths(rec['id'], pdf_path=path, pdf_hash=file_hash)
    hv_model.update_record(rec['id'], {'content_hash': chash})
    return path


def _ensure_excel(rec):
    path = rec.get('excel_path')
    if path and os.path.exists(path):
        return path
    fresh = hv_model.get_record(rec['id'])
    path = build_excel(fresh)
    hv_model.set_paths(rec['id'], excel_path=path)
    return path


@export_bp.route('/api/handover/export_excel/<int:record_id>')
@login_required
def export_excel(record_id):
    rec = hv_model.get_record(record_id)
    if not rec:
        return fail('记录不存在', 404, 404)
    if not _check_permission(rec):
        return fail('无权导出该记录', 403, 403)
    path = _ensure_excel(rec)
    log_model.add_log(current_user()['id'], 'export', '导出Excel No%s' % record_id, get_ip())
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@export_bp.route('/api/handover/export_pdf/<int:record_id>')
@login_required
def export_pdf(record_id):
    rec = hv_model.get_record(record_id)
    if not rec:
        return fail('记录不存在', 404, 404)
    if not _check_permission(rec):
        return fail('无权导出该记录', 403, 403)
    path = _ensure_pdf(rec)
    inline = request.args.get('inline') == '1'
    log_model.add_log(current_user()['id'], 'export', '导出PDF No%s' % record_id, get_ip())
    return send_file(path, as_attachment=not inline, download_name=os.path.basename(path))


@export_bp.route('/api/handover/verify/<int:record_id>')
@login_required
def verify_by_id(record_id):
    rec = hv_model.get_record(record_id)
    if not rec:
        return fail('记录不存在', 404, 404)
    result = {
        'record_id': record_id,
        'stored_file_hash': rec.get('pdf_hash') or '',
        'stored_content_hash': rec.get('content_hash') or '',
        'current_file_hash': '',
        'current_content_hash': content_hash(rec),
        'file_exists': bool(rec.get('pdf_path') and os.path.exists(rec.get('pdf_path'))),
        'file_valid': False,
        'content_valid': (rec.get('content_hash') or '') == content_hash(rec),
        'valid': False,
    }
    if result['file_exists']:
        result['current_file_hash'] = sha256_file(rec['pdf_path'])
        result['file_valid'] = result['current_file_hash'] == (rec.get('pdf_hash') or '')
    result['valid'] = bool(result['file_valid'] and result['content_valid'])
    result['message'] = '校验通过，文件与记录均未被篡改' if result['valid'] else '校验失败：文件或记录已被修改'
    log_model.add_log(current_user()['id'], 'verify', '验证记录 No%s：%s' % (record_id, result['message']), get_ip())
    return ok(result, result['message'])


@export_bp.route('/api/verify/upload', methods=['POST'])
@login_required
def verify_upload():
    """上传 PDF，按 SHA256 比对数据库哈希，判断文件是否被篡改。"""
    file = request.files.get('file')
    if not file or not file.filename:
        return fail('请选择要验证的 PDF 文件')
    raw = file.read()
    if not raw:
        return fail('文件内容为空')
    file_hash = sha256_hex(raw)
    rec = hv_model.find_by_hash(file_hash)
    if rec:
        log_model.add_log(current_user()['id'], 'verify', '上传PDF校验通过 No%s' % rec['id'], get_ip())
        return ok({
            'valid': True,
            'record_id': rec['id'],
            'department': rec.get('department'),
            'handover_time': rec.get('handover_time'),
            'file_hash': file_hash,
            'message': '校验通过：该 PDF 与系统记录一致，未被篡改',
        }, '校验通过')
    log_model.add_log(current_user()['id'], 'verify', '上传PDF校验失败 hash=%s' % file_hash[:16], get_ip())
    return ok({
        'valid': False,
        'file_hash': file_hash,
        'message': '校验失败：未在系统中找到匹配的哈希值，文件可能已被修改或不属于本系统',
    }, '校验失败')


@export_bp.route('/verify')
@login_required
def verify_page():
    return render_template('verify.html')
