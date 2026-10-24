# -*- coding: utf-8 -*-
"""登录 / 登出 / 注册 / 权限校验。"""
import io
import random
import base64
import time
from functools import wraps

from flask import (Blueprint, request, session, jsonify, render_template,
                   redirect, url_for, current_app)

from models import user as user_model
from models import log as log_model
from models.db import now_str
from config import SESSION_TIMEOUT_MINUTES

auth_bp = Blueprint('auth', __name__)


# ---------------- 通用响应 ----------------

def ok(data=None, msg='ok'):
    return jsonify({'code': 0, 'msg': msg, 'data': data if data is not None else {}})


def fail(msg='操作失败', code=1, http_status=400):
    return jsonify({'code': code, 'msg': msg, 'data': {}}), http_status


def get_ip():
    return request.headers.get('X-Real-IP', request.remote_addr or '')


def current_user():
    if session.get('user_id'):
        return {
            'id': session.get('user_id'),
            'work_no': session.get('work_no'),
            'name': session.get('name'),
            'role': session.get('role'),
            'department': session.get('department'),
        }
    return None


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            if request.path.startswith('/api/'):
                return fail('未登录或登录已超时', 401, 401)
            return redirect(url_for('auth.login_page'))
        # 30 分钟无操作自动退出
        last = session.get('last_active', 0)
        if time.time() - last > SESSION_TIMEOUT_MINUTES * 60:
            session.clear()
            if request.path.startswith('/api/'):
                return fail('长时间无操作，已自动退出', 401, 401)
            return redirect(url_for('auth.login_page'))
        session['last_active'] = time.time()
        session.permanent = True
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if session.get('role') != 'admin':
            if request.path.startswith('/api/'):
                return fail('需要管理员权限', 403, 403)
            return redirect(url_for('history.dashboard_page'))
        return f(*args, **kwargs)
    return wrapper


# ---------------- 验证码 ----------------

@auth_bp.route('/api/captcha')
def captcha():
    from PIL import Image, ImageDraw
    code = ''.join(random.choice('23456789ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(4))
    session['captcha'] = code.upper()
    img = Image.new('RGB', (110, 40), (240, 247, 255))
    draw = ImageDraw.Draw(img)
    try:
        from PIL import ImageFont
        font = ImageFont.load_default(size=26)
    except Exception:
        font = None
    for i, ch in enumerate(code):
        draw.text((12 + i * 24, 7), ch, fill=(random.randint(0, 120), random.randint(0, 120), random.randint(80, 200)),
                  font=font)
    for _ in range(4):
        draw.line((random.randint(0, 110), random.randint(0, 40), random.randint(0, 110), random.randint(0, 40)),
                  fill=(180, 200, 220))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return ok({'image': 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')})


# ---------------- 登录 / 登出 ----------------

@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    work_no = str(data.get('work_no', '')).strip()
    password = str(data.get('password', '')).strip()
    captcha_input = str(data.get('captcha', '')).strip().upper()
    if not work_no or not password:
        return fail('工号和密码不能为空')
    if current_app.config.get('CAPTCHA_ENABLED', True):
        expect = session.get('captcha')
        if expect and captcha_input != expect:
            return fail('验证码错误')
    row, err = user_model.check_login(work_no, password)
    if err:
        log_model.add_log(None, 'login_fail', '工号:%s 原因:%s' % (work_no, err), get_ip())
        return fail(err)
    session.clear()
    session.permanent = True
    session['user_id'] = row['id']
    session['work_no'] = row['work_no']
    session['name'] = row['name']
    session['role'] = row['role']
    session['department'] = row['department']
    session['last_active'] = time.time()
    session.pop('captcha', None)
    log_model.add_log(row['id'], 'login', '%s 登录成功' % row['name'], get_ip())
    return ok({'user': row}, '登录成功')


@auth_bp.route('/api/logout', methods=['POST'])
@login_required
def logout():
    log_model.add_log(session.get('user_id'), 'logout', '%s 退出登录' % session.get('name'), get_ip())
    session.clear()
    return ok(msg='已退出登录')


@auth_bp.route('/api/me')
@login_required
def me():
    return ok({'user': current_user()})


@auth_bp.route('/api/register', methods=['POST'])
def register():
    """药师注册：提交后状态为待审核，需管理员开通。"""
    data = request.get_json(silent=True) or {}
    work_no = str(data.get('work_no', '')).strip()
    name = str(data.get('name', '')).strip()
    password = str(data.get('password', '')).strip()
    department = str(data.get('department', '')).strip()
    phone = str(data.get('phone', '')).strip()
    if not work_no or not name or not password:
        return fail('工号、姓名、密码不能为空')
    if len(password) < 6:
        return fail('密码长度至少 6 位')
    uid, err = user_model.create_user(work_no, name, password, 'pharmacist', department, phone, status=0)
    if err:
        return fail(err)
    log_model.add_log(uid, 'register', '%s(%s) 提交注册申请' % (name, work_no), get_ip())
    return ok({'id': uid}, '注册成功，请等待管理员审核开通')


# ---------------- 页面 ----------------

@auth_bp.route('/login')
def login_page():
    if session.get('user_id'):
        return redirect(url_for('history.dashboard_page'))
    return render_template('login.html')
