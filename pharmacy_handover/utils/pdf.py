# -*- coding: utf-8 -*-
"""PDF 生成工具（reportlab，含签名图片嵌入 + 哈希计算）。"""
import os
import io
import json
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table, TableStyle,
                                Spacer, Image, KeepTogether)

from config import EXPORT_DIR
from utils.crypto import sha256_hex, sha256_file, decode_data_url

FONT_NAME = 'STSong-Light'
_registered = False


def _ensure_font():
    global _registered
    if not _registered:
        pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))
        _registered = True
    return FONT_NAME


def _safe(text):
    return re.sub(r'[\\/:*?"<>|]', '_', str(text or ''))


# ---------------- 哈希 ----------------

CANONICAL_FIELDS = (
    'id', 'handover_time', 'handover_id', 'receive_id', 'department', 'temperature',
    'humidity', 'fridge_data', 'narcotic_info', 'normaldruginfo', 'highalertdrugs',
    'machine_status', 'pending_items', 'abnormal_events', 'handover_note',
    'handover_sign', 'receive_sign',
)


def content_hash(record):
    """根据记录内容计算确定性指纹（用于 DB 防篡改校验）。"""
    data = {}
    for f in CANONICAL_FIELDS:
        v = record.get(f)
        data[f] = v if isinstance(v, (str, int, float)) else json.dumps(v, ensure_ascii=False, sort_keys=True)
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return sha256_hex(canonical.encode('utf-8'))


# ---------------- 排版辅助 ----------------

def _styles():
    _ensure_font()
    return {
        'title': ParagraphStyle('title', fontName=FONT_NAME, fontSize=17, leading=22,
                                alignment=1, textColor=colors.HexColor('#1F6FB2')),
        'h': ParagraphStyle('h', fontName=FONT_NAME, fontSize=11.5, leading=16,
                            textColor=colors.HexColor('#1F6FB2')),
        'n': ParagraphStyle('n', fontName=FONT_NAME, fontSize=9, leading=13),
        'small': ParagraphStyle('small', fontName=FONT_NAME, fontSize=7.5, leading=10,
                                textColor=colors.HexColor('#666666')),
        'cell': ParagraphStyle('cell', fontName=FONT_NAME, fontSize=8.5, leading=12),
        'cellb': ParagraphStyle('cellb', fontName=FONT_NAME, fontSize=8.5, leading=12,
                                textColor=colors.HexColor('#1F6FB2')),
    }


def _kv_table(rows, st, col_widths=(38 * mm, 68 * mm, 38 * mm, 36 * mm)):
    data = []
    pairs = [rows[i:i + 2] for i in range(0, len(rows), 2)]
    for pair in pairs:
        line = []
        for k, v in pair:
            line.append(Paragraph(str(k), st['cellb']))
            line.append(Paragraph(str(v if v not in (None, '') else '-'), st['cell']))
        while len(line) < 4:
            line.extend([Paragraph('', st['cell']), Paragraph('', st['cell'])])
        data.append(line)
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#B7C7D8')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F2F7FC')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#F2F7FC')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return t


def _grid_table(header, rows, st, widths, warn_col=None):
    data = [[Paragraph(str(h), st['cell']) for h in header]]
    for r in rows:
        cells = r[:-1] if len(r) == len(header) + 1 else r
        data.append([Paragraph(str(c if c not in (None, '') else '-'), st['cell']) for c in cells])
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#B7C7D8')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DCE9F5')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]
    for i, r in enumerate(rows, start=1):
        if r and r[-1] is True:
            style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#FDE7E7')))
    t.setStyle(TableStyle(style))
    return t


def _sign_image(data_url, width=55 * mm):
    raw = decode_data_url(data_url)
    if not raw:
        return Paragraph('（未签名）', _styles()['cell'])
    try:
        from PIL import Image as PILImage
        im = PILImage.open(io.BytesIO(raw))
        w, h = im.size
        height = (h / w * width) if w else 18 * mm
        return Image(io.BytesIO(raw), width=width, height=height)
    except Exception:
        return Paragraph('（签名图片损坏）', _styles()['cell'])


# ---------------- 主函数 ----------------

def build_pdf(record, content_hash_value=None):
    """生成不可修改 PDF，返回 (路径, 文件SHA256, 内容指纹SHA256)。"""
    _ensure_font()
    os.makedirs(EXPORT_DIR, exist_ok=True)
    date_str = str(record.get('handover_time') or '')[:10].replace('-', '')
    fname = _safe('%s_%s_No%s.pdf' % (date_str or 'nodate', record.get('department') or '药房', record.get('id')))
    path = os.path.join(EXPORT_DIR, fname)

    st = _styles()
    doc = SimpleDocTemplate(path, pagesize=A4, title='药师交接班记录 No%s' % record.get('id'),
                            author='药师工作台', leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm)
    story = []
    story.append(Paragraph('药师交接班记录表', st['title']))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph('记录编号：No%s　　药房：%s　　交接时间：%s' % (
        record.get('id'), record.get('department') or '-', record.get('handover_time') or '-'), st['small']))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('一、基础信息', st['h']))
    story.append(_kv_table([
        ('交班药师', record.get('handover_name') or '-'),
        ('接班药师', record.get('receive_name') or '-'),
        ('交接时间', record.get('handover_time') or '-'),
        ('所在药房', record.get('department') or '-'),
    ], st))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('二、环境信息', st['h']))
    fridges = record.get('fridge_data') or {}
    if isinstance(fridges, dict):
        fridges = fridges.get('list', [])
    rows = [[f.get('name', ''), f.get('temperature', ''), f.get('humidity', ''),
             f.get('normal', ''), str(f.get('normal', '')).strip() in ('异常', '否')] for f in fridges]
    story.append(_kv_table([
        ('药房温度(℃)', record.get('temperature') or '-'),
        ('药房湿度(%)', record.get('humidity') or '-'),
    ], st))
    story.append(Spacer(1, 2 * mm))
    if rows:
        story.append(_grid_table(['冰箱名称', '温度(℃)', '湿度(%)', '是否正常'], rows, st,
                                 widths=(48 * mm, 30 * mm, 30 * mm, 30 * mm)))
    else:
        story.append(Paragraph('无冰箱记录', st['cell']))
    story.append(Spacer(1, 3 * mm))

    nar = record.get('narcotic_info') or {}
    story.append(Paragraph('三、麻精药品', st['h']))
    story.append(_kv_table([
        ('在库品种数', nar.get('variety_count', '-')),
        ('在库数量', nar.get('stock_qty', '-')),
        ('空安瓿回收数', nar.get('empty_ampoule', '-')),
        ('保险柜状态', nar.get('safe_status', '-')),
    ], st))
    story.append(Spacer(1, 3 * mm))

    nor = record.get('normaldruginfo') or {}
    story.append(Paragraph('四、普通药品', st['h']))
    story.append(_kv_table([
        ('在库品种总数', nor.get('variety_total', '-')),
        ('在库总数量', nor.get('stock_total', '-')),
    ], st))
    story.append(Spacer(1, 3 * mm))

    drugs = record.get('highalertdrugs') or {}
    if isinstance(drugs, dict):
        drugs = drugs.get('list', [])
    story.append(Paragraph('五、高警示药品', st['h']))
    if drugs:
        story.append(_grid_table(['药品名称', '规格', '在库数量', '单位', '存放位置'],
                                 [[d.get('name', ''), d.get('spec', ''), d.get('qty', ''),
                                   d.get('unit', ''), d.get('location', '')] for d in drugs],
                                 st, widths=(45 * mm, 28 * mm, 25 * mm, 20 * mm, 30 * mm)))
    else:
        story.append(Paragraph('无记录', st['cell']))
    story.append(Spacer(1, 3 * mm))

    mach = record.get('machine_status') or {}
    story.append(Paragraph('六、发药机状态', st['h']))
    story.append(_kv_table([
        ('快速发药机余量(%)', mach.get('fast_machine', '-')),
        ('智能药架余量(%)', mach.get('smart_shelf', '-')),
        ('备注', mach.get('remark', '-')),
    ], st))
    story.append(Spacer(1, 3 * mm))

    pend = record.get('pending_items') or {}
    story.append(Paragraph('七、待办事项', st['h']))
    story.append(_kv_table([
        ('未审核处方数', pend.get('unreviewed_rx', '-')),
        ('未调配处方数', pend.get('undispensed_rx', '-')),
        ('待退药单数', pend.get('return_orders', '-')),
        ('待处理医嘱数', pend.get('pending_advice', '-')),
    ], st))
    story.append(Spacer(1, 3 * mm))

    abn = record.get('abnormal_events') or {}
    story.append(Paragraph('八、异常事件', st['h']))
    story.append(_kv_table([
        ('异常类型', '、'.join(abn.get('events', []) or []) or '无'),
        ('异常描述', abn.get('detail', '-') or '-'),
    ], st))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('九、交接留言', st['h']))
    story.append(Paragraph(str(record.get('handover_note') or '无').replace('\n', '<br/>'), st['cell']))
    story.append(Spacer(1, 3 * mm))

    items = record.get('items') or []
    if items:
        story.append(Paragraph('十、库存快照（近效期≤90天标红）', st['h']))
        rows = [[it.get('drug_name', ''), it.get('spec', ''), it.get('batch_no', ''),
                 it.get('expiry_date', ''), it.get('stock_qty', ''), it.get('unit', ''),
                 it.get('drug_type', ''), it.get('location', ''), bool(it.get('near_expiry'))]
                for it in items]
        story.append(_grid_table(['药品名称', '规格', '批号', '有效期', '数量', '单位', '类型', '位置'],
                                 rows, st,
                                 widths=(32 * mm, 20 * mm, 22 * mm, 22 * mm, 14 * mm, 12 * mm, 18 * mm, 22 * mm)))
        story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('十一、双方电子签名', st['h']))
    sign_tbl = Table([
        [Paragraph('交班药师签名', st['cellb']), Paragraph('接班药师签名', st['cellb'])],
        [_sign_image(record.get('handover_sign', '')), _sign_image(record.get('receive_sign', ''))],
    ], colWidths=(88 * mm, 88 * mm))
    sign_tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#B7C7D8')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(KeepTogether(sign_tbl))
    story.append(Spacer(1, 4 * mm))

    ch = content_hash_value or content_hash(record)
    story.append(Paragraph('十二、防篡改信息', st['h']))
    story.append(Paragraph('记录内容指纹（SHA256）：<br/>%s' % ch, st['small']))
    story.append(Paragraph('说明：本文件哈希值已存入系统数据库，可在系统「验证」页面上传本文件校验完整性，'
                           '文件被修改后校验将失败。', st['small']))

    doc.build(story)
    file_hash = sha256_file(path)
    return path, file_hash, ch
