# -*- coding: utf-8 -*-
"""药师工作台 · Flask 主入口。"""
import os
import logging
from datetime import timedelta

from flask import Flask, session, jsonify, render_template, request

from config import (Config, HOST, PORT, DEBUG, SESSION_TIMEOUT_MINUTES,
                    DB_PATH, ensure_dirs)
from models import log as log_model
from routes import auth_bp, handover_bp, history_bp, export_bp, admin_bp


def setup_logging():
    ensure_dirs()
    from config import LOG_FILE
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h, logging.FileHandler) for h in root.handlers):
        root.addHandler(handler)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(Config)
    app.permanent_session_lifetime = timedelta(minutes=SESSION_TIMEOUT_MINUTES)

    app.register_blueprint(auth_bp)
    app.register_blueprint(handover_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def inject_user():
        is_admin = session.get('role') == 'admin'
        return {
            'current_user': {
                'id': session.get('user_id'),
                'name': session.get('name'),
                'work_no': session.get('work_no'),
                'role': session.get('role'),
                'department': session.get('department'),
            } if session.get('user_id') else None,
            'is_admin': is_admin,
            'session_timeout': SESSION_TIMEOUT_MINUTES,
        }

    @app.before_request
    def refresh_session():
        # 页面访问也刷新活跃时间，避免 30 分钟误踢
        if session.get('user_id'):
            import time
            session['last_active'] = time.time()
            session.permanent = True

    @app.errorhandler(404)
    def page_not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({'code': 404, 'msg': '接口不存在', 'data': {}}), 404
        return render_template('base.html', error='页面不存在'), 404

    @app.errorhandler(500)
    def server_error(e):
        logging.exception('服务器内部错误')
        if request.path.startswith('/api/'):
            return jsonify({'code': 500, 'msg': '服务器内部错误', 'data': {}}), 500
        return render_template('base.html', error='服务器内部错误'), 500

    return app


def ensure_db():
    if not os.path.exists(DB_PATH):
        import init_db
        init_db.init_db()


app = create_app()


if __name__ == '__main__':
    setup_logging()
    ensure_db()
    print('=' * 60)
    print('药师工作台启动： http://127.0.0.1:%d' % PORT)
    print('默认账号：admin / admin123（管理员），1001 / 123456（药师）')
    print('=' * 60)
    app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True)
