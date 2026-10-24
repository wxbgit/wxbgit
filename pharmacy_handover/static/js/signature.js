/* 手写签名 Canvas（支持手机触摸与鼠标，导出白底 PNG base64） */
(function () {
    function SignaturePad(canvas, options) {
        this.canvas = typeof canvas === 'string' ? document.getElementById(canvas) : canvas;
        this.options = options || {};
        this.ctx = this.canvas.getContext('2d');
        this.hasStroke = false;
        this._initSize();
        this._bind();
    }

    SignaturePad.prototype._initSize = function () {
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.getBoundingClientRect();
        const w = rect.width || this.canvas.clientWidth || 300;
        const h = rect.height || this.canvas.clientHeight || 140;
        this.canvas.width = Math.round(w * dpr);
        this.canvas.height = Math.round(h * dpr);
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.ctx.lineWidth = 2.4;
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
        this.ctx.strokeStyle = '#17293a';
    };

    SignaturePad.prototype._pos = function (e) {
        const rect = this.canvas.getBoundingClientRect();
        const src = e.touches && e.touches[0] ? e.touches[0] : e;
        return { x: src.clientX - rect.left, y: src.clientY - rect.top };
    };

    SignaturePad.prototype._bind = function () {
        const self = this;
        let drawing = false;
        let last = null;

        const start = function (e) {
            e.preventDefault();
            drawing = true;
            self.hasStroke = true;
            last = self._pos(e);
            self.ctx.beginPath();
            self.ctx.moveTo(last.x, last.y);
            // 点一下也要留下痕迹
            self.ctx.lineTo(last.x + 0.1, last.y + 0.1);
            self.ctx.stroke();
            if (self.options.onStart) self.options.onStart();
        };
        const move = function (e) {
            if (!drawing) return;
            e.preventDefault();
            const p = self._pos(e);
            self.ctx.lineTo(p.x, p.y);
            self.ctx.stroke();
            last = p;
        };
        const end = function () { drawing = false; last = null; };

        if (window.PointerEvent) {
            this.canvas.addEventListener('pointerdown', start);
            this.canvas.addEventListener('pointermove', move);
            window.addEventListener('pointerup', end);
            this.canvas.addEventListener('pointerleave', end);
        } else {
            this.canvas.addEventListener('touchstart', start, { passive: false });
            this.canvas.addEventListener('touchmove', move, { passive: false });
            this.canvas.addEventListener('touchend', end);
            this.canvas.addEventListener('mousedown', start);
            this.canvas.addEventListener('mousemove', move);
            window.addEventListener('mouseup', end);
        }
    };

    SignaturePad.prototype.clear = function () {
        const w = this.canvas.width, h = this.canvas.height;
        this.ctx.clearRect(0, 0, w, h);
        this.hasStroke = false;
    };

    SignaturePad.prototype.isEmpty = function () {
        return !this.hasStroke;
    };

    SignaturePad.prototype.toDataURL = function () {
        if (!this.hasStroke) return '';
        const tmp = document.createElement('canvas');
        tmp.width = this.canvas.width;
        tmp.height = this.canvas.height;
        const c = tmp.getContext('2d');
        c.fillStyle = '#ffffff';
        c.fillRect(0, 0, tmp.width, tmp.height);
        c.drawImage(this.canvas, 0, 0);
        c.strokeStyle = '#17293a';
        return tmp.toDataURL('image/png');
    };

    window.SignaturePad = SignaturePad;
})();
