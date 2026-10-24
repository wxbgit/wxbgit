/* 通用工具：请求封装、提示、退出、会话超时、导航高亮 */
(function () {
    const TIMEOUT_MINUTES = parseInt(document.body.dataset.timeout || '30', 10);

    window.api = function (url, options) {
        options = options || {};
        const opts = {
            method: options.method || 'GET',
            headers: {},
            credentials: 'same-origin'
        };
        if (options.body) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(options.body);
        }
        return fetch(url, opts)
            .then(function (r) {
                if (r.status === 401 || r.status === 403) {
                    return r.json().then(function (j) {
                        toast(j.msg || '登录已过期');
                        setTimeout(function () { location.href = '/login'; }, 800);
                        throw new Error(j.msg);
                    });
                }
                return r.json();
            })
            .then(function (j) {
                if (j.code !== 0) {
                    toast(j.msg || '操作失败');
                    throw new Error(j.msg || '操作失败');
                }
                return j.data;
            });
    };

    window.toast = function (msg, duration) {
        let el = document.getElementById('toast');
        if (!el) {
            el = document.createElement('div');
            el.id = 'toast';
            document.body.appendChild(el);
        }
        el.textContent = msg;
        el.classList.add('show');
        clearTimeout(el._t);
        el._t = setTimeout(function () { el.classList.remove('show'); }, duration || 2200);
    };

    window.logout = function () {
        fetch('/api/logout', { method: 'POST', credentials: 'same-origin' })
            .then(function () { location.href = '/login'; });
    };

    window.confirmBox = function (msg, onOk) {
        if (window.confirm(msg)) { onOk(); }
    };

    window.modal = function (html, opts) {
        opts = opts || {};
        const mask = document.createElement('div');
        mask.className = 'modal-mask';
        mask.innerHTML = '<div class="modal">' + html + '</div>';
        mask.addEventListener('click', function (e) {
            if (e.target === mask && opts.closeOnMask !== false) { mask.remove(); }
        });
        document.body.appendChild(mask);
        if (opts.onMount) { opts.onMount(mask); }
        return mask;
    };

    window.closeModal = function (el) {
        const mask = el || document.querySelector('.modal-mask');
        if (mask) { mask.remove(); }
    };

    window.fmt = function (v) {
        if (v === null || v === undefined || v === '') { return '-'; }
        return v;
    };

    // 导航高亮
    document.addEventListener('DOMContentLoaded', function () {
        const path = location.pathname;
        document.querySelectorAll('.tabbar a').forEach(function (a) {
            const href = a.getAttribute('href');
            if (href === '/' ? path === '/' : path.indexOf(href) === 0) {
                a.classList.add('active');
            }
        });
        // 会话超时（30 分钟无操作自动退出）
        if (TIMEOUT_MINUTES > 0) {
            let timer;
            const reset = function () {
                clearTimeout(timer);
                timer = setTimeout(function () {
                    toast('长时间无操作，已自动退出');
                    fetch('/api/logout', { method: 'POST', credentials: 'same-origin' })
                        .then(function () { location.href = '/login'; });
                }, TIMEOUT_MINUTES * 60 * 1000);
            };
            ['click', 'keydown', 'touchstart', 'scroll'].forEach(function (ev) {
                window.addEventListener(ev, reset, { passive: true });
            });
            reset();
        }
    });
})();
