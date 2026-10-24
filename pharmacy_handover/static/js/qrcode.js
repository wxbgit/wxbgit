/* 扫码交接：生成二维码 / 解析 URL 中的 token */
(function () {
    window.QRHandover = {
        token: '',
        /**
         * 生成交接二维码
         * @param {string} department 药房
         * @param {function} cb 回调(token)
         */
        generate: function (department, cb) {
            if (!department) {
                toast('请先选择所在药房');
                return;
            }
            const form = (window.Handover && window.Handover.collect) ? window.Handover.collect() : {};
            api('/api/handover/qrcode', {
                method: 'POST', body: { department: department, form: form }
            }).then(function (d) {
                QRHandover.token = d.token;
                modal(`
                    <h3>扫码交接</h3>
                    <div style="text-align:center">
                        <img src="${d.qrcode}" style="width:220px;height:220px;border:1px solid #dfe7ee;border-radius:8px">
                    </div>
                    <div style="margin-top:10px;font-size:12.5px;color:#7d8b96;text-align:center;line-height:1.7">
                        请接班药师使用手机扫一扫，核对信息并完成签名提交<br>
                        药房：${d.department}
                    </div>
                    <div class="hash-text" style="margin-top:8px">${d.url}</div>
                    <div class="modal-footer">
                        <button class="btn btn-outline" id="qrCopy">复制链接</button>
                        <button class="btn" onclick="closeModal(this.closest('.modal-mask'))">我知道了</button>
                    </div>`, {
                    onMount: function (mask) {
                        mask.querySelector('#qrCopy').addEventListener('click', function () {
                            const ta = document.createElement('textarea');
                            ta.value = d.url;
                            document.body.appendChild(ta);
                            ta.select();
                            try { document.execCommand('copy'); toast('链接已复制'); } catch (e) { toast('请手动复制'); }
                            ta.remove();
                        });
                    }
                });
                if (cb) cb(d.token);
            }).catch(function () { });
        },

        /** 页面带 ?token= 时，加载交班人信息 */
        initFromUrl: function (cb) {
            const m = location.search.match(/token=([0-9a-fA-F]+)/);
            if (!m) { if (cb) cb(null); return; }
            QRHandover.token = m[1];
            api('/api/handover/token/' + m[1]).then(function (d) {
                const box = document.getElementById('qrInfo');
                if (box) {
                    box.innerHTML = `<div class="tip-item" style="background:#eaf3fb;border-left-color:#1f6fb2">
                        已通过扫码确认交接单：由 <b>${d.handover_name || '-'}</b> 于 ${d.handover_time || '-'} 发起（${d.department || '-'}），
                        您（当前登录人）将作为接班药师完成本次交接。
                    </div>`;
                }
                if (cb) cb(d);
            }).catch(function () {
                const box = document.getElementById('qrInfo');
                if (box) box.innerHTML = '<div class="tip-item high">二维码无效或已失效，请改用工号密码交接</div>';
                if (cb) cb(null);
            });
        }
    };
})();
