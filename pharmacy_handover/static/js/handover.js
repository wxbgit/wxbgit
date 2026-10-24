/* 交接班表单逻辑：动态表格、自动预填、签名、预览确认、提交 */
window.Handover = (function () {
    const $ = function (id) { return document.getElementById(id); };
    let cfg = {};
    let padH = null, padR = null, me = null, lastItems = [];
    let mode = 'pwd';
    let draftSign = '';   // 扫码交接时交班药师已完成的签名

    /* ---------------- 动态表格 ---------------- */

    function daysToExpiry(dateStr) {
        if (!dateStr) return null;
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return null;
        return Math.ceil((d - new Date()) / 86400000);
    }

    function isNearExpiry(dateStr) {
        const d = daysToExpiry(dateStr);
        return d !== null && d >= 0 && d <= (cfg.expiryDays || 90);
    }

    function fridgeRows() {
        const rows = [];
        document.querySelectorAll('#fridgeBody tr').forEach(function (tr) {
            const name = tr.querySelector('.f-name').value.trim();
            if (!name) return;
            const t = tr.querySelector('.f-temp').value.trim();
            const h = tr.querySelector('.f-humi').value.trim();
            const min = parseFloat(tr.dataset.min), max = parseFloat(tr.dataset.max);
            let normal = '正常';
            if (t !== '' && !isNaN(min) && !isNaN(max)) {
                const tv = parseFloat(t);
                normal = (tv >= min && tv <= max) ? '正常' : '异常';
            }
            rows.push({ name: name, temperature: t, humidity: h, normal: normal });
        });
        return rows;
    }

    function addFridgeRow(data) {
        const tbody = $('fridgeBody');
        const tr = document.createElement('tr');
        const min = data && data.min !== undefined ? data.min : '';
        const max = data && data.max !== undefined ? data.max : '';
        tr.dataset.min = min;
        tr.dataset.max = max;
        tr.innerHTML = `
            <td><input type="text" class="f-name" value="${(data && data.name) || ''}" placeholder="冰箱名称"></td>
            <td><input type="number" step="0.1" class="f-temp" value="${(data && data.temperature) || ''}"></td>
            <td><input type="number" step="0.1" class="f-humi" value="${(data && data.humidity) || ''}"></td>
            <td><span class="f-status tag tag-ok">正常</span></td>
            <td><button type="button" class="btn btn-sm btn-danger" onclick="this.closest('tr').remove()">删除</button></td>`;
        tbody.appendChild(tr);
        const updater = function () {
            const t = tr.querySelector('.f-temp').value.trim();
            const badge = tr.querySelector('.f-status');
            if (t !== '' && min !== '' && max !== '') {
                const tv = parseFloat(t);
                const ok = tv >= parseFloat(min) && tv <= parseFloat(max);
                badge.textContent = ok ? '正常' : '异常';
                badge.className = 'f-status tag ' + (ok ? 'tag-ok' : 'tag-danger');
            } else {
                badge.textContent = '正常';
                badge.className = 'f-status tag tag-ok';
            }
        };
        tr.querySelector('.f-temp').addEventListener('input', updater);
        updater();
        return tr;
    }

    function invRows() {
        const rows = [];
        document.querySelectorAll('#invBody tr').forEach(function (tr) {
            const name = tr.querySelector('.i-name').value.trim();
            if (!name) return;
            const expiry = tr.querySelector('.i-expiry').value;
            rows.push({
                drug_name: name,
                spec: tr.querySelector('.i-spec').value.trim(),
                batch_no: tr.querySelector('.i-batch').value.trim(),
                expiry_date: expiry,
                stock_qty: parseInt(tr.querySelector('.i-qty').value || '0', 10),
                unit: tr.querySelector('.i-unit').value.trim(),
                drug_type: tr.querySelector('.i-type').value,
                location: tr.querySelector('.i-loc').value.trim(),
                near_expiry: isNearExpiry(expiry)
            });
        });
        return rows;
    }

    function addInvRow(data) {
        const tbody = $('invBody');
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><input type="text" class="i-name" value="${(data && data.drug_name) || ''}" placeholder="药品名称"></td>
            <td><input type="text" class="i-spec" style="width:70px" value="${(data && data.spec) || ''}"></td>
            <td><input type="text" class="i-batch" style="width:80px" value="${(data && data.batch_no) || ''}"></td>
            <td><input type="date" class="i-expiry" value="${(data && data.expiry_date) || ''}"></td>
            <td><input type="number" class="i-qty" style="width:60px" value="${(data && data.stock_qty) !== undefined ? data.stock_qty : ''}"></td>
            <td><input type="text" class="i-unit" style="width:46px" value="${(data && data.unit) || ''}"></td>
            <td><select class="i-type" style="width:70px">
                <option>普通</option><option>麻精</option><option>高警示</option></select></td>
            <td><input type="text" class="i-loc" style="width:76px" value="${(data && data.location) || ''}"></td>
            <td><button type="button" class="btn btn-sm btn-danger" onclick="this.closest('tr').remove()">删除</button></td>`;
        tbody.appendChild(tr);
        if (data && data.drug_type) { tr.querySelector('.i-type').value = data.drug_type; }
        const mark = function () {
            const near = isNearExpiry(tr.querySelector('.i-expiry').value);
            tr.classList.toggle('near-expiry', near);
        };
        tr.querySelector('.i-expiry').addEventListener('change', mark);
        mark();
        return tr;
    }

    function haRows() {
        const rows = [];
        document.querySelectorAll('#haBody tr').forEach(function (tr) {
            const name = tr.querySelector('.h-name').value.trim();
            if (!name) return;
            rows.push({
                name: name,
                spec: tr.querySelector('.h-spec').value.trim(),
                qty: tr.querySelector('.h-qty').value.trim(),
                unit: tr.querySelector('.h-unit').value.trim(),
                location: tr.querySelector('.h-loc').value.trim()
            });
        });
        return rows;
    }

    function addHaRow(data) {
        const tbody = $('haBody');
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><input type="text" class="h-name" list="haList" value="${(data && data.name) || ''}" placeholder="药品名称"></td>
            <td><input type="text" class="h-spec" style="width:80px" value="${(data && data.spec) || ''}"></td>
            <td><input type="number" class="h-qty" style="width:64px" value="${(data && data.qty) !== undefined ? data.qty : ''}"></td>
            <td><input type="text" class="h-unit" style="width:50px" value="${(data && data.unit) || ''}"></td>
            <td><input type="text" class="h-loc" style="width:80px" value="${(data && data.location) || ''}"></td>
            <td><button type="button" class="btn btn-sm btn-danger" onclick="this.closest('tr').remove()">删除</button></td>`;
        tbody.appendChild(tr);
        return tr;
    }

    /* ---------------- 预填 ---------------- */

    function applyPrefill(d) {
        if (!d || !d.found) { 
            if (d && d.server_time) $('handoverTime').value = d.server_time;
            return; 
        }
        const last = d.last || {};
        $('temperature').value = last.temperature || '';
        $('humidity').value = last.humidity || '';
        const nar = last.narcotic_info || {};
        $('narVariety').value = nar.variety_count || '';
        $('narQty').value = nar.stock_qty || '';
        $('narAmpoule').value = nar.empty_ampoule || '';
        if (nar.safe_status) $('narSafe').value = nar.safe_status;
        $('narRemark').value = nar.remark || '';
        const nor = last.normaldruginfo || {};
        $('norVariety').value = nor.variety_total || '';
        $('norQty').value = nor.stock_total || '';
        const m = last.machine_status || {};
        $('fastMachine').value = m.fast_machine || '';
        $('smartShelf').value = m.smart_shelf || '';
        $('machineRemark').value = m.remark || '';
        const p = last.pending_items || {};
        $('pUnreviewed').value = p.unreviewed_rx || 0;
        $('pUndispensed').value = p.undispensed_rx || 0;
        $('pReturn').value = p.return_orders || 0;
        $('pAdvice').value = p.pending_advice || 0;
        // 冰箱
        const fr = (last.fridge_data || {}).list || [];
        if (fr.length) {
            $('fridgeBody').innerHTML = '';
            fr.forEach(function (f) { addFridgeRow(f); });
        }
        // 高警示
        const ha = (last.highalertdrugs || {}).list || [];
        if (ha.length) {
            $('haBody').innerHTML = '';
            ha.forEach(function (h) { addHaRow(h); });
        }
        lastItems = d.items || [];
        if (d.server_time) $('handoverTime').value = d.server_time;
        toast('已自动带入上一班次数据（No.' + last.id + '），请核对修改');
    }

    function loadPrefill() {
        const dept = $('department').value;
        api('/api/handover/prefill?department=' + encodeURIComponent(dept)).then(applyPrefill)
            .catch(function () { });
    }

    function importLastInventory() {
        if (!lastItems.length) { toast('上一班次没有库存快照数据'); return; }
        $('invBody').innerHTML = '';
        lastItems.forEach(function (it) { addInvRow(it); });
        syncNormalTotal();
        toast('已导入 ' + lastItems.length + ' 条库存明细');
    }

    function syncNormalTotal() {
        const rows = invRows();
        if (!$('norVariety').value) {
            $('norVariety').value = rows.length;
        }
        if (!$('norQty').value) {
            const total = rows.reduce(function (s, r) { return s + (r.stock_qty || 0); }, 0);
            $('norQty').value = total;
        }
    }

    /** 扫码进入：载入交班药师已填写的内容 */
    function applyDraft(d) {
        if (!d) return;
        draftSign = d.handover_sign || '';
        setMode('qr');
        if (d.department) { $('department').value = d.department; $('deptSource').value = '扫码交接单带入'; }
        applyPrefill({
            found: true,
            server_time: d.handover_time,
            last: {
                id: d.record_id, temperature: d.temperature, humidity: d.humidity,
                fridge_data: d.fridge_data, narcotic_info: d.narcotic_info,
                normaldruginfo: d.normaldruginfo, highalertdrugs: d.highalertdrugs,
                machine_status: d.machine_status, pending_items: d.pending_items,
                abnormal_events: d.abnormal_events
            },
            items: d.items || []
        });
        if (d.abnormal_events && d.abnormal_events.events) {
            document.querySelectorAll('#abnormalBox input').forEach(function (c) {
                c.checked = d.abnormal_events.events.indexOf(c.value) >= 0;
            });
            $('abnormalDetail').value = d.abnormal_events.detail || '';
        }
        if (d.handover_note) $('handoverNote').value = d.handover_note;
        if (d.items && d.items.length) {
            $('invBody').innerHTML = '';
            d.items.forEach(function (it) { addInvRow(it); });
        }
        toast('已载入交班药师填写的内容，请核对后签名提交');
    }

    /* ---------------- 采集与校验 ---------------- */

    function collectPayload() {
        const events = [];
        document.querySelectorAll('#abnormalBox input:checked').forEach(function (c) { events.push(c.value); });
        return {
            token: QRHandover.token || '',
            department: $('department').value,
            handover_time: $('handoverTime').value,
            temperature: $('temperature').value,
            humidity: $('humidity').value,
            fridge_data: { list: fridgeRows() },
            narcotic_info: {
                variety_count: $('narVariety').value,
                stock_qty: $('narQty').value,
                empty_ampoule: $('narAmpoule').value,
                safe_status: $('narSafe').value,
                remark: $('narRemark').value
            },
            normaldruginfo: {
                variety_total: $('norVariety').value,
                stock_total: $('norQty').value
            },
            highalertdrugs: { list: haRows() },
            machine_status: {
                fast_machine: $('fastMachine').value,
                smart_shelf: $('smartShelf').value,
                remark: $('machineRemark').value
            },
            pending_items: {
                unreviewed_rx: $('pUnreviewed').value,
                undispensed_rx: $('pUndispensed').value,
                return_orders: $('pReturn').value,
                pending_advice: $('pAdvice').value
            },
            abnormal_events: { events: events, detail: $('abnormalDetail').value },
            handover_note: $('handoverNote').value,
            handover_sign: padH.toDataURL() || draftSign,
            receive_sign: padR.toDataURL(),
            receive_work_no: mode === 'pwd' ? $('receiveWorkNo').value.trim() : '',
            receive_password: mode === 'pwd' ? $('receivePwd').value.trim() : '',
            items: invRows()
        };
    }

    function validate(p) {
        if (!p.department) { toast('请选择所在药房'); return false; }
        if (mode === 'pwd') {
            if (!p.receive_work_no || !p.receive_password) { toast('请输入接班药师工号与密码'); return false; }
        } else if (!p.token) {
            toast('请先生成交接二维码或让接班药师扫码进入'); return false;
        }
        if (!p.handover_sign) { toast('请完成交班药师签名'); return false; }
        if (!p.receive_sign) { toast('请完成接班药师签名'); return false; }
        return true;
    }

    /* ---------------- 预览 ---------------- */

    function row(k, v) {
        return '<tr><th>' + k + '</th><td>' + (v === '' || v === null || v === undefined ? '-' : v) + '</td></tr>';
    }

    function buildPreviewHtml(p) {
        let html = '<div class="preview-section">基础信息</div><table class="preview-table">';
        html += row('交班药师', me ? me.name + '（' + me.work_no + '）' : '-');
        html += row('接班药师', mode === 'pwd' ? $('receiveWorkNo').value.trim() : '扫码接班（当前登录人）');
        html += row('交接时间', p.handover_time);
        html += row('所在药房', p.department);
        html += '</table>';

        html += '<div class="preview-section">药房环境</div><table class="preview-table">';
        html += row('温度', p.temperature + ' ℃');
        html += row('湿度', p.humidity + ' %');
        p.fridge_data.list.forEach(function (f) {
            html += row('冰箱·' + f.name, f.temperature + '℃ / ' + f.humidity + '%（' + f.normal + '）');
        });
        html += '</table>';

        html += '<div class="preview-section">麻精药品</div><table class="preview-table">';
        html += row('在库品种数', p.narcotic_info.variety_count);
        html += row('在库数量', p.narcotic_info.stock_qty);
        html += row('空安瓿回收数', p.narcotic_info.empty_ampoule);
        html += row('保险柜状态', p.narcotic_info.safe_status);
        html += '</table>';

        html += '<div class="preview-section">普通药品</div><table class="preview-table">';
        html += row('在库品种总数', p.normaldruginfo.variety_total);
        html += row('在库总数量', p.normaldruginfo.stock_total);
        html += '</table>';

        if (p.highalertdrugs.list.length) {
            html += '<div class="preview-section">高警示药品</div><table class="preview-table">';
            p.highalertdrugs.list.forEach(function (d) {
                html += row(d.name, (d.qty || '-') + (d.unit || '') + '　规格：' + (d.spec || '-'));
            });
            html += '</table>';
        }

        html += '<div class="preview-section">发药机 / 待办</div><table class="preview-table">';
        html += row('快速发药机余量', p.machine_status.fast_machine + ' %');
        html += row('智能药架余量', p.machine_status.smart_shelf + ' %');
        html += row('未审核处方', p.pending_items.unreviewed_rx);
        html += row('未调配处方', p.pending_items.undispensed_rx);
        html += row('待退药单', p.pending_items.return_orders);
        html += row('待处理医嘱', p.pending_items.pending_advice);
        html += '</table>';

        html += '<div class="preview-section">异常事件 / 留言</div><table class="preview-table">';
        html += row('异常事件', p.abnormal_events.events.length ? p.abnormal_events.events.join('、') : '无');
        html += row('异常描述', p.abnormal_events.detail);
        html += row('交接留言', p.handover_note);
        html += '</table>';

        if (p.items.length) {
            html += '<div class="preview-section">库存快照（近效期≤' + cfg.expiryDays + '天标红）</div>';
            html += '<div class="table-wrap"><table class="grid"><tr><th>名称</th><th>有效期</th><th>数量</th><th>类型</th></tr>';
            p.items.forEach(function (it) {
                html += '<tr class="' + (it.near_expiry ? 'near-expiry' : '') + '"><td>' + it.drug_name +
                    (it.near_expiry ? ' <span class="badge-near">近效期</span>' : '') + '</td><td>' + (it.expiry_date || '-') +
                    '</td><td>' + it.stock_qty + '</td><td>' + it.drug_type + '</td></tr>';
            });
            html += '</table></div>';
        }

        html += '<div class="preview-section">双方签名</div><div style="display:flex;gap:10px">';
        html += '<div style="flex:1"><div style="font-size:12px;color:#7d8b96">交班药师</div><img src="' + p.handover_sign + '" style="width:100%;border:1px solid #dfe7ee;border-radius:6px;background:#fff"></div>';
        html += '<div style="flex:1"><div style="font-size:12px;color:#7d8b96">接班药师</div><img src="' + p.receive_sign + '" style="width:100%;border:1px solid #dfe7ee;border-radius:6px;background:#fff"></div>';
        html += '</div>';
        return html;
    }

    function preview() {
        const p = collectPayload();
        if (!validate(p)) return;
        modal('<h3>提交前确认</h3>' + buildPreviewHtml(p) + `
            <div class="modal-footer">
                <button class="btn btn-outline" onclick="closeModal(this.closest('.modal-mask'))">返回修改</button>
                <button class="btn btn-success" id="btnSubmit">确认无误，提交</button>
            </div>`, {
            closeOnMask: false,
            onMount: function (mask) {
                mask.querySelector('#btnSubmit').addEventListener('click', function () {
                    mask.querySelector('#btnSubmit').disabled = true;
                    mask.querySelector('#btnSubmit').textContent = '提交中...';
                    doSubmit(p, mask);
                });
            }
        });
    }

    function doSubmit(p, mask) {
        api('/api/handover/submit', { method: 'POST', body: p }).then(function (d) {
            closeModal(mask);
            modal(`
                <h3>交接成功</h3>
                <div style="text-align:center;font-size:15px;margin-bottom:10px">
                    记录编号：<b>No.${d.id}</b>
                </div>
                <div class="tip-item">Excel 备份与 PDF 存证已生成，PDF 哈希已写入数据库。</div>
                <div class="hash-text">PDF哈希：${d.pdf_hash}</div>
                <div class="hash-text" style="margin-top:4px">内容指纹：${d.content_hash}</div>
                <div class="modal-footer">
                    <button class="btn btn-outline" onclick="location.href='/'">返回首页</button>
                    <button class="btn" onclick="location.href='/detail/${d.id}'">查看详情</button>
                </div>`, { closeOnMask: false });
        }).catch(function () {
            const btn = mask && mask.querySelector('#btnSubmit');
            if (btn) { btn.disabled = false; btn.textContent = '确认无误，提交'; }
        });
    }

    /* ---------------- 初始化 ---------------- */

    function setMode(m) {
        mode = m;
        $('modePwd').classList.toggle('active', m === 'pwd');
        $('modeQr').classList.toggle('active', m === 'qr');
        $('pwdBox').style.display = m === 'pwd' ? '' : 'none';
        $('qrBox').style.display = m === 'qr' ? '' : 'none';
    }

    function init(options) {
        cfg = options || {};
        padH = new SignaturePad('signHandover', {
            onStart: function () { hidePlaceholder('signHandover'); }
        });
        padR = new SignaturePad('signReceive', {
            onStart: function () { hidePlaceholder('signReceive'); }
        });

        function hidePlaceholder(id) {
            const box = document.getElementById(id).parentNode.querySelector('.placeholder');
            if (box) box.style.display = 'none';
        }

        $('clearSign1').addEventListener('click', function () { padH.clear(); showPh('signHandover'); });
        $('clearSign2').addEventListener('click', function () { padR.clear(); showPh('signReceive'); });
        function showPh(id) {
            const box = document.getElementById(id).parentNode.querySelector('.placeholder');
            if (box) box.style.display = '';
        }

        $('modePwd').addEventListener('click', function () { setMode('pwd'); });
        $('modeQr').addEventListener('click', function () { setMode('qr'); });
        $('btnAddFridge').addEventListener('click', function () { addFridgeRow(null); });
        $('btnAddInv').addEventListener('click', function () { addInvRow(null); });
        $('btnAddHa').addEventListener('click', function () { addHaRow(null); });
        $('btnImportLast').addEventListener('click', importLastInventory);
        $('btnPreview').addEventListener('click', preview);

        api('/api/me').then(function (d) {
            me = d.user;
            $('handoverUser').value = me.name + '（' + me.work_no + '）';
            if (me.department) {
                $('department').value = me.department;
                $('deptSource').value = '账号所属药房';
            }
        }).catch(function () { });

        api('/api/handover/config').then(function (d) {
            $('handoverTime').value = d.server_time;
            if (!me || !me.department) {
                if (d.ip_department) {
                    $('department').value = d.ip_department;
                    $('deptSource').value = '服务器IP自动识别';
                }
            }
        }).catch(function () { });

        // 默认行
        (cfg.fridges || []).forEach(function (f) { addFridgeRow(f); });
        (cfg.highAlertDrugs || []).slice(0, 3).forEach(function (name) { addHaRow({ name: name }); });
        addInvRow(null);

        $('department').addEventListener('change', function () {
            $('deptSource').value = '手动选择';
            loadPrefill();
        });

        // 扫码模式
        QRHandover.initFromUrl(applyDraft);

        setTimeout(loadPrefill, 300);
    }

    return {
        init: init, collect: collectPayload, applyDraft: applyDraft,
        addInvRow: addInvRow, addHaRow: addHaRow, addFridgeRow: addFridgeRow
    };
})();
