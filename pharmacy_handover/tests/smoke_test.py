# -*- coding: utf-8 -*-
"""本地冒烟测试：启动服务 → 登录 → 交接班提交 → 导出 → 验证 → 权限校验。

用法： python tests/smoke_test.py
"""
import io
import os
import sys
import json
import time
import base64
import http.cookiejar
import subprocess
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = os.environ.get('SMOKE_PORT', '5099')
BASE = 'http://127.0.0.1:%s' % PORT

PASSED, FAILED = [], []


def check(name, cond, extra=''):
    if cond:
        PASSED.append(name)
        print('  [OK] %s' % name)
    else:
        FAILED.append('%s %s' % (name, extra))
        print('  [FAIL] %s %s' % (name, extra))


class Client(object):
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _open(self, req):
        try:
            resp = self.opener.open(req, timeout=30)
            return resp.getcode(), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def get(self, path):
        return self._open(urllib.request.Request(BASE + path))

    def post_json(self, path, body):
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(BASE + path, data=data, method='POST',
                                     headers={'Content-Type': 'application/json'})
        return self._open(req)

    def post_file(self, path, filename, raw):
        boundary = '----smokeboundary1234'
        body = io.BytesIO()
        body.write(('--%s\r\n' % boundary).encode())
        body.write(('Content-Disposition: form-data; name="file"; filename="%s"\r\n' % filename).encode())
        body.write(b'Content-Type: application/pdf\r\n\r\n')
        body.write(raw)
        body.write(('\r\n--%s--\r\n' % boundary).encode())
        req = urllib.request.Request(BASE + path, data=body.getvalue(), method='POST',
                                     headers={'Content-Type': 'multipart/form-data; boundary=' + boundary})
        return self._open(req)


def jget(client, path, expect=200):
    code, raw = client.get(path)
    try:
        j = json.loads(raw.decode('utf-8'))
    except Exception:
        j = {'code': -1, 'msg': raw[:200].decode('utf-8', 'ignore')}
    return code, j


def jpost(client, path, body):
    code, raw = client.post_json(path, body)
    try:
        j = json.loads(raw.decode('utf-8'))
    except Exception:
        j = {'code': -1, 'msg': raw[:300].decode('utf-8', 'ignore')}
    return code, j


def make_sign_base64(text='签名'):
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (240, 90), 'white')
    d = ImageDraw.Draw(img)
    d.line((20, 60, 80, 25, 140, 70, 210, 30), fill=(20, 40, 60), width=3)
    d.text((95, 70), text, fill=(20, 40, 60))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def wait_server(timeout=40):
    for _ in range(timeout * 2):
        try:
            with urllib.request.urlopen(BASE + '/login', timeout=2) as r:
                if r.getcode() == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    env = dict(os.environ)
    env.update({'PH_PORT': PORT, 'PH_DEBUG': '0', 'PH_CAPTCHA': '0', 'PYTHONIOENCODING': 'utf-8'})
    print('启动服务 ...')
    # 注意：不要使用 PIPE 且不读取，否则管道缓冲区写满会阻塞服务进程
    log_path = os.path.join(BASE_DIR, 'logs', 'smoke_server.log')
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logf = open(log_path, 'w', encoding='utf-8')
    proc = subprocess.Popen([sys.executable, os.path.join(BASE_DIR, 'app.py')],
                            cwd=BASE_DIR, env=env, stdout=logf, stderr=subprocess.STDOUT)
    try:
        if not wait_server():
            logf.flush()
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                print('服务启动失败，日志尾部：\n' + ''.join(f.readlines()[-30:]))
            return 1
        run_tests()
    finally:
        try:
            logf.close()
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    print('\n========== 汇总 ==========')
    print('通过 %d 项，失败 %d 项' % (len(PASSED), len(FAILED)))
    for f in FAILED:
        print('  × ' + f)
    return 0 if not FAILED else 2


def run_tests():
    sign = make_sign_base64('张药师')
    sign2 = make_sign_base64('李药师')

    print('\n[1] 页面可访问性')
    anon = Client()
    for path in ('/login',):
        code, _ = anon.get(path)
        check('GET %s' % path, code == 200, 'code=%s' % code)
    code, _ = anon.get('/')
    check('未登录访问 / 跳转登录', code in (200, 302), 'code=%s' % code)
    code, j = jget(anon, '/api/handover/list')
    check('未登录调用接口返回 401', code == 401 or j.get('code') == 401, 'code=%s' % code)

    print('\n[2] 登录 / 登出')
    cli = Client()
    code, j = jpost(cli, '/api/login', {'work_no': '1001', 'password': '123456'})
    check('药师 1001 登录', j.get('code') == 0, j.get('msg'))
    code, j = jpost(Client(), '/api/login', {'work_no': '1001', 'password': 'wrong'})
    check('错误密码被拒绝', j.get('code') != 0)

    print('\n[3] 配置与自动预填')
    code, j = jget(cli, '/api/handover/config')
    check('获取交接班配置', j.get('code') == 0 and 'departments' in j.get('data', {}), j.get('msg'))
    code, j = jget(cli, '/api/handover/prefill')
    check('自动预填接口', j.get('code') == 0, j.get('msg'))

    print('\n[4] 扫码交接二维码')
    code, j = jpost(cli, '/api/handover/qrcode', {'department': '门诊药房'})
    check('生成交接二维码', j.get('code') == 0, j.get('msg'))
    token = j.get('data', {}).get('token', '')
    check('二维码包含 token', bool(token))
    if token:
        code, j = jget(cli, '/api/handover/token/' + token)
        check('解析二维码 token', j.get('code') == 0, j.get('msg'))

    print('\n[5] 提交交接班（工号密码方式）')
    payload = {
        'department': '门诊药房',
        'handover_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'temperature': '23.5', 'humidity': '55',
        'fridge_data': {'list': [
            {'name': '2~8℃冷藏冰箱', 'temperature': '5.2', 'humidity': '60', 'normal': '正常'},
            {'name': '-20℃冷冻冰箱', 'temperature': '-18', 'humidity': '', 'normal': '异常'}
        ]},
        'narcotic_info': {'variety_count': '12', 'stock_qty': '320', 'empty_ampoule': '18',
                          'safe_status': '正常', 'remark': '账物相符'},
        'normaldruginfo': {'variety_total': '860', 'stock_total': '12400'},
        'highalertdrugs': {'list': [{'name': '10%氯化钾注射液', 'spec': '10ml', 'qty': '60',
                                     'unit': '支', 'location': '保险柜'}]},
        'machine_status': {'fast_machine': '45', 'smart_shelf': '38', 'remark': ''},
        'pending_items': {'unreviewed_rx': '6', 'undispensed_rx': '3', 'return_orders': '1',
                          'pending_advice': '2'},
        'abnormal_events': {'events': ['药品报损'], 'detail': '破损 2 支已登记'},
        'handover_note': '3床患者明天出院需备药',
        'handover_sign': sign, 'receive_sign': sign2,
        'receive_work_no': '1002', 'receive_password': '123456',
        'items': [
            {'drug_name': '阿莫西林胶囊', 'spec': '0.25g*24', 'batch_no': 'A202501',
             'expiry_date': time.strftime('%Y-%m-%d', time.localtime(time.time() + 30 * 86400)),
             'stock_qty': 120, 'unit': '盒', 'drug_type': '普通', 'location': '药架A'},
            {'drug_name': '胰岛素注射液', 'spec': '400IU', 'batch_no': 'B202402',
             'expiry_date': '2024-05-01', 'stock_qty': 15, 'unit': '支',
             'drug_type': '高警示', 'location': '冰箱'}
        ]
    }
    code, j = jpost(cli, '/api/handover/submit', payload)
    check('提交交接班记录', j.get('code') == 0, j.get('msg'))
    data = j.get('data', {})
    rid = data.get('id')
    check('返回记录编号', bool(rid), str(data))
    check('生成 PDF 哈希', bool(data.get('pdf_hash')))
    check('Excel 文件已落地', bool(data.get('excel_path')) and os.path.exists(data.get('excel_path', '')))
    check('PDF 文件已落地', bool(data.get('pdf_path')) and os.path.exists(data.get('pdf_path', '')))

    print('\n[6] 查询与详情')
    code, j = jget(cli, '/api/handover/list?page=1&per_page=10')
    check('历史列表查询', j.get('code') == 0 and j['data']['total'] >= 1, j.get('msg'))
    code, j = jget(cli, '/api/handover/detail/%s' % rid)
    check('记录详情', j.get('code') == 0, j.get('msg'))
    rec = j.get('data', {}).get('record', {})
    check('详情含库存快照', len(rec.get('items', [])) == 2, str(len(rec.get('items', []))))
    check('近效期自动标记', any(i.get('near_expiry') for i in rec.get('items', [])), '未标记近效期')

    print('\n[7] 看板统计')
    code, j = jget(cli, '/api/dashboard/stats')
    check('看板统计接口', j.get('code') == 0, j.get('msg'))
    check('统计包含建议', 'suggestions' in j.get('data', {}))

    print('\n[8] 导出与防篡改验证')
    code, raw = cli.get('/api/handover/export_excel/%s' % rid)
    check('导出 Excel', code == 200 and raw[:2] == b'PK', 'code=%s' % code)
    code, pdf_bytes = cli.get('/api/handover/export_pdf/%s' % rid)
    check('导出 PDF', code == 200 and pdf_bytes[:4] == b'%PDF', 'code=%s' % code)
    code, j = jget(cli, '/api/handover/verify/%s' % rid)
    check('记录完整性校验通过', j.get('data', {}).get('valid') is True, str(j.get('data')))
    code, j = jpost(cli, '/api/verify/upload', {})
    # 上传原始 PDF（应通过）
    resp = cli.post_file('/api/verify/upload', 'rec.pdf', pdf_bytes)
    up = json.loads(resp[1].decode('utf-8'))
    check('上传原始 PDF 校验通过', up.get('data', {}).get('valid') is True, up.get('msg'))
    resp = cli.post_file('/api/verify/upload', 'rec_modified.pdf', pdf_bytes + b'\n% tampered')
    up2 = json.loads(resp[1].decode('utf-8'))
    check('上传被篡改 PDF 校验失败', up2.get('data', {}).get('valid') is False, up2.get('msg'))

    print('\n[9] 权限控制')
    admin = Client()
    code, j = jpost(admin, '/api/login', {'work_no': 'admin', 'password': 'admin123'})
    check('管理员登录', j.get('code') == 0, j.get('msg'))
    test_no = '9' + time.strftime('%H%M%S')
    code, j = jpost(admin, '/api/users', {'work_no': test_no, 'name': '王药师', 'password': '123456',
                                          'role': 'pharmacist', 'department': '急诊药房'})
    check('管理员新增用户', j.get('code') == 0, j.get('msg'))
    other = Client()
    code, j = jpost(other, '/api/login', {'work_no': test_no, 'password': '123456'})
    check('新用户登录', j.get('code') == 0, j.get('msg'))
    code, j = jget(other, '/api/handover/detail/%s' % rid)
    check('无关药师无权查看他人记录', j.get('code') == 403, 'code=%s' % code)
    code, j = jget(other, '/api/users')
    check('普通药师不能访问用户管理接口', j.get('code') == 403, 'code=%s' % code)
    code, j = jget(admin, '/api/logs?limit=5')
    check('管理员查看操作日志', j.get('code') == 0 and len(j['data']['list']) > 0, j.get('msg'))

    print('\n[10] 页面渲染（登录态）')
    for path in ('/', '/handover', '/history', '/verify', '/users', '/detail/%s' % rid):
        code, raw = admin.get(path)
        check('GET %s' % path, code == 200, 'code=%s' % code)
    code, raw = admin.get('/handover?token=%s' % token if token else '/handover')
    check('扫码进入交接页', code == 200, 'code=%s' % code)

    print('\n[12] 扫码交接全流程（交班人生成 → 接班人扫码提交）')
    a = Client()
    jpost(a, '/api/login', {'work_no': '1001', 'password': '123456'})
    code, j = jpost(a, '/api/handover/qrcode', {'department': '住院药房'})
    qr_token = j.get('data', {}).get('token', '')
    check('交班人生成二维码', bool(qr_token), j.get('msg'))
    b = Client()
    jpost(b, '/api/login', {'work_no': '1002', 'password': '123456'})
    qr_payload = dict(payload)
    qr_payload.update({'token': qr_token, 'department': '住院药房',
                       'receive_work_no': '', 'receive_password': '',
                       'handover_sign': sign, 'receive_sign': sign2, 'items': []})
    code, j = jpost(b, '/api/handover/submit', qr_payload)
    check('扫码方式提交成功', j.get('code') == 0, j.get('msg'))
    if j.get('code') == 0:
        code, j2 = jget(a, '/api/handover/detail/%s' % j['data']['id'])
        rec = j2.get('data', {}).get('record', {})
        check('扫码提交记录交班人为 1001', rec.get('handover_name') == '张药师', str(rec.get('handover_name')))
        check('扫码提交记录接班人为 1002', rec.get('receive_name') == '李药师', str(rec.get('receive_name')))

    print('\n[11] 登出')
    code, j = jpost(cli, '/api/logout', {})
    check('登出成功', j.get('code') == 0, j.get('msg'))
    code, j = jget(cli, '/api/handover/list')
    check('登出后接口不可访问', j.get('code') == 401, 'code=%s' % code)


if __name__ == '__main__':
    sys.exit(main())
