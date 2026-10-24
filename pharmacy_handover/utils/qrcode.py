# -*- coding: utf-8 -*-
"""二维码生成工具（qrcode + Pillow，纯离线）。"""
import base64
import io

import qrcode

from utils.crypto import decode_data_url


def make_qr_base64(data, box_size=8, border=2):
    """生成二维码 PNG 的 base64（带 data URL 前缀）。"""
    qr = qrcode.QRCode(version=None, box_size=box_size, border=border,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def make_qr_bytes(data):
    raw = decode_data_url(make_qr_base64(data))
    return raw
