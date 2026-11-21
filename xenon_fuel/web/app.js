/* ==========================================================================
   xenon_fuel – NUI aplikace
   Autor: XenonD3VS
   Vanilla JS, bez závislostí. Veškeré ceny a výpočty jsou pouze náhled –
   finální hodnoty vždy počítá a ověřuje server.
   ========================================================================== */
'use strict';

const RESOURCE = typeof GetParentResourceName === 'function' ? GetParentResourceName() : 'xenon_fuel';

const S = {
    locale: {},
    cfg: {
        currency: { symbol: '$', position: 'before', thousands: ' ', decimal: ',' },
        fuelTypes: {},
        fuelOrder: [],
        hud: { Position: 'bottom-right', Offset: { x: 28, y: 28 }, LowThreshold: 20 },
        hudEnabled: true,
        sounds: { enabled: true, volume: 0.35, pumpLoop: true, clicks: true, warning: true },
        permissions: [],
        ranks: [],
        cancelKey: 'X',
        payroll: 30,
    },
};

/* ------------------------------------------------------------------ Pomocné funkce */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function esc(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/** Formátovací řetězce ve stylu Lua (%s, %d, %.2f, %%) */
function luaFormat(fmt, args) {
    let i = 0;
    return fmt.replace(/%(%|s|d|i|(?:\.(\d+))?f)/g, (m, type, dec) => {
        if (type === '%') return '%';
        const v = args[i++];
        if (type === 's') return v === undefined ? '' : String(v);
        if (type === 'd' || type === 'i') return String(Math.floor(Number(v) || 0));
        return (Number(v) || 0).toFixed(dec !== undefined ? Number(dec) : 6);
    });
}

function t(key, ...args) {
    const str = S.locale[key];
    if (str === undefined) return key;
    return args.length ? luaFormat(str, args) : str;
}

function fmtNum(value, decimals = 0) {
    const c = S.cfg.currency;
    const n = Number(value) || 0;
    const neg = n < 0;
    const fixed = Math.abs(n).toFixed(decimals);
    let [int, frac] = fixed.split('.');
    int = int.replace(/\B(?=(\d{3})+(?!\d))/g, c.thousands);
    return (neg ? '-' : '') + int + (frac ? c.decimal + frac : '');
}

function fmtMoney(value, decimals = 0) {
    const c = S.cfg.currency;
    const n = Number(value) || 0;
    const num = fmtNum(Math.abs(n), decimals);
    const sign = n < 0 && Number(num.replace(/[^0-9]/g, '')) > 0 ? '-' : '';
    return c.position === 'after' ? `${sign}${num} ${c.symbol}` : `${sign}${c.symbol}${num}`;
}

function fmtCompactMoney(value) {
    const n = Math.abs(value);
    let s;
    if (n >= 1e6) s = (value / 1e6).toFixed(n >= 1e7 ? 0 : 1) + 'M';
    else if (n >= 1e3) s = (value / 1e3).toFixed(n >= 1e4 ? 0 : 1) + 'k';
    else s = String(Math.round(value));
    s = s.replace('.', S.cfg.currency.decimal);
    return S.cfg.currency.position === 'after' ? `${s} ${S.cfg.currency.symbol}` : `${S.cfg.currency.symbol}${s}`;
}

function unitLabel(unit) {
    return unit === 'kwh' ? 'kWh' : 'l';
}

function pad(n) { return String(n).padStart(2, '0'); }

function fmtDate(seconds, withTime = true) {
    if (!seconds) return '—';
    const d = new Date(Number(seconds) * 1000);
    const date = `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
    return withTime ? `${date} ${pad(d.getHours())}:${pad(d.getMinutes())}` : date;
}

function fmtDuration(seconds) {
    seconds = Math.max(0, Math.floor(seconds || 0));
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 0) return t('duration_hm', h, m);
    return t('duration_m', m);
}

function fmtClock(seconds) {
    seconds = Math.max(0, Math.floor(seconds || 0));
    return `${pad(Math.floor(seconds / 3600))}:${pad(Math.floor((seconds % 3600) / 60))}:${pad(seconds % 60)}`;
}

function hexToRgba(hex, alpha) {
    const h = String(hex || '#f0a23b').replace('#', '');
    const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
    const n = parseInt(full, 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

function fuelVars(color) {
    return `--c:${esc(color)};--cs:${hexToRgba(color, 0.09)};--cp:${hexToRgba(color, 0.55)}`;
}

function gradeChip(fuel, cls = '') {
    return `<span class="grade ${cls}" style="--c:${esc(fuel.color)}">${esc(fuel.short)}</span>`;
}

function initials(name) {
    return String(name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('');
}

function clamp(v, min, max) { return Math.min(max, Math.max(min, v)); }
function floor2(v) { return Math.floor(v * 100 + 1e-9) / 100; }

async function post(name, data) {
    try {
        const res = await fetch(`https://${RESOURCE}/${name}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json; charset=UTF-8' },
            body: JSON.stringify(data || {}),
        });
        const text = await res.text();
        try { return JSON.parse(text); } catch { return text; }
    } catch (e) {
        return null;
    }
}

/* ------------------------------------------------------------------ Zvuky (Web Audio API) */
const Sound = {
    ctx: null,
    pump: null,

    ensure() {
        if (!S.cfg.sounds.enabled) return null;
        if (!this.ctx) {
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx) return null;
            this.ctx = new Ctx();
        }
        if (this.ctx.state === 'suspended') this.ctx.resume();
        return this.ctx;
    },

    volume() { return clamp(Number(S.cfg.sounds.volume) || 0, 0, 1); },

    noiseBuffer(ctx, seconds, brown) {
        const length = Math.floor(ctx.sampleRate * seconds);
        const buffer = ctx.createBuffer(1, length, ctx.sampleRate);
        const data = buffer.getChannelData(0);
        let last = 0;
        for (let i = 0; i < length; i++) {
            const white = Math.random() * 2 - 1;
            if (brown) {
                last = (last + 0.02 * white) / 1.02;
                data[i] = last * 3.5;
            } else {
                data[i] = white;
            }
        }
        return buffer;
    },

    /** Kovové cvaknutí pistole */
    click(pitch = 1) {
        const ctx = this.ensure();
        if (!ctx || !S.cfg.sounds.clicks) return;
        const now = ctx.currentTime;
        const src = ctx.createBufferSource();
        src.buffer = this.noiseBuffer(ctx, 0.08, false);
        const bp = ctx.createBiquadFilter();
        bp.type = 'bandpass';
        bp.frequency.value = 2600 * pitch;
        bp.Q.value = 3;
        const g = ctx.createGain();
        g.gain.setValueAtTime(0.0001, now);
        g.gain.exponentialRampToValueAtTime(0.5 * this.volume(), now + 0.004);
        g.gain.exponentialRampToValueAtTime(0.0001, now + 0.07);
        src.connect(bp).connect(g).connect(ctx.destination);
        src.start(now);
        src.stop(now + 0.09);

        const osc = ctx.createOscillator();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(1400 * pitch, now);
        osc.frequency.exponentialRampToValueAtTime(500 * pitch, now + 0.05);
        const og = ctx.createGain();
        og.gain.setValueAtTime(0.18 * this.volume(), now);
        og.gain.exponentialRampToValueAtTime(0.0001, now + 0.06);
        osc.connect(og).connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.07);
    },

    tone(freq, start, duration, type = 'sine', gain = 0.25) {
        const ctx = this.ctx;
        const osc = ctx.createOscillator();
        osc.type = type;
        osc.frequency.value = freq;
        const g = ctx.createGain();
        g.gain.setValueAtTime(0.0001, start);
        g.gain.exponentialRampToValueAtTime(gain * this.volume(), start + 0.012);
        g.gain.exponentialRampToValueAtTime(0.0001, start + duration);
        osc.connect(g).connect(ctx.destination);
        osc.start(start);
        osc.stop(start + duration + 0.02);
    },

    warning() {
        const ctx = this.ensure();
        if (!ctx || !S.cfg.sounds.warning) return;
        const now = ctx.currentTime;
        this.tone(880, now, 0.14, 'square', 0.08);
        this.tone(660, now + 0.18, 0.22, 'square', 0.08);
    },

    complete() {
        const ctx = this.ensure();
        if (!ctx) return;
        const now = ctx.currentTime;
        this.tone(988, now, 0.18, 'sine', 0.2);
        this.tone(1319, now + 0.12, 0.32, 'sine', 0.18);
    },

    /** Čerpadlo: hnědý šum přes pásmovou propust + nízký motorový brum s modulací průtoku */
    startPump() {
        const ctx = this.ensure();
        if (!ctx || !S.cfg.sounds.pumpLoop || this.pump) return;
        const now = ctx.currentTime;
        const master = ctx.createGain();
        master.gain.setValueAtTime(0.0001, now);
        master.gain.exponentialRampToValueAtTime(0.32 * this.volume(), now + 0.5);
        master.connect(ctx.destination);

        const noise = ctx.createBufferSource();
        noise.buffer = this.noiseBuffer(ctx, 2.5, true);
        noise.loop = true;
        const bp = ctx.createBiquadFilter();
        bp.type = 'bandpass';
        bp.frequency.value = 520;
        bp.Q.value = 0.8;
        const ng = ctx.createGain();
        ng.gain.value = 0.9;

        const lfo = ctx.createOscillator();
        lfo.frequency.value = 5.5;
        const lfoGain = ctx.createGain();
        lfoGain.gain.value = 0.18;
        lfo.connect(lfoGain).connect(ng.gain);

        const hum = ctx.createOscillator();
        hum.type = 'sawtooth';
        hum.frequency.value = 58;
        const lp = ctx.createBiquadFilter();
        lp.type = 'lowpass';
        lp.frequency.value = 240;
        const hg = ctx.createGain();
        hg.gain.value = 0.22;

        noise.connect(bp).connect(ng).connect(master);
        hum.connect(lp).connect(hg).connect(master);
        noise.start(now);
        hum.start(now);
        lfo.start(now);
        this.pump = { master, nodes: [noise, hum, lfo] };
    },

    stopPump() {
        if (!this.pump || !this.ctx) return;
        const { master, nodes } = this.pump;
        const now = this.ctx.currentTime;
        master.gain.cancelScheduledValues(now);
        master.gain.setValueAtTime(master.gain.value || 0.0001, now);
        master.gain.exponentialRampToValueAtTime(0.0001, now + 0.35);
        nodes.forEach((n) => { try { n.stop(now + 0.4); } catch { /* již zastaveno */ } });
        setTimeout(() => { try { master.disconnect(); } catch { /* ignorovat */ } }, 600);
        this.pump = null;
    },

    play(name) {
        switch (name) {
            case 'nozzle_take': this.click(1); break;
            case 'nozzle_return': this.click(0.75); break;
            case 'pump_start': this.click(1.1); setTimeout(() => this.startPump(), 120); break;
            case 'pump_stop': this.stopPump(); this.click(0.9); break;
            case 'warning': this.warning(); break;
            case 'complete': this.complete(); break;
            default: break;
        }
    },
};

/* ------------------------------------------------------------------ Notifikace */
const Toasts = {
    show(message, type = 'info') {
        const root = $('#toasts');
        const icons = { success: 'circle-check', error: 'circle-x', warning: 'triangle-alert', info: 'info' };
        const el = document.createElement('div');
        const duration = type === 'error' ? 5500 : 4500;
        el.className = `toast ${type}`;
        el.innerHTML = `${icon(icons[type] || 'info')}<div>${esc(message)}</div><span class="t-bar" style="animation-duration:${duration}ms"></span>`;
        root.appendChild(el);
        while (root.children.length > 5) root.firstElementChild.remove();
        setTimeout(() => {
            el.classList.add('out');
            setTimeout(() => el.remove(), 260);
        }, duration);
    },
};

/* ------------------------------------------------------------------ HUD paliva */
const Hud = {
    update(d) {
        const el = $('#hud');
        if (!S.cfg.hudEnabled || !d || !d.show) {
            el.hidden = true;
            return;
        }
        const pos = String(S.cfg.hud.Position || 'bottom-right');
        const off = S.cfg.hud.Offset || { x: 28, y: 28 };
        el.style.top = pos.startsWith('top') ? `${off.y}px` : '';
        el.style.bottom = pos.startsWith('bottom') ? `${off.y}px` : '';
        el.style.left = pos.endsWith('left') ? `${off.x}px` : '';
        el.style.right = pos.endsWith('right') ? `${off.x}px` : '';

        const fuel = clamp(Number(d.fuel) || 0, 0, 100);
        const on = Math.ceil(fuel / 5);
        let segs = '';
        for (let i = 1; i <= 20; i++) segs += `<i class="${i <= on ? 'on' : ''}"></i>`;
        el.className = `hud${d.low ? ' low' : ''}${fuel <= 5 ? ' critical' : ''}`;
        el.innerHTML = `
            <div class="h-top">${icon(d.electric ? 'zap' : 'fuel')}<span class="eyebrow">${esc(t(d.electric ? 'hud_battery' : 'hud_fuel'))}</span>
                <span class="h-val num">${fmtNum(fuel, 1)}<small>%</small></span></div>
            <div class="h-seg">${segs}</div>
            <div class="h-sub"><span>${fmtNum(d.amount, 1)} ${unitLabel(d.unit)}</span><span>${d.low ? esc(t('hud_low')) : ''}</span></div>`;
        el.hidden = false;
    },
};

/* ------------------------------------------------------------------ Průběh tankování */
const Progress = {
    data: null,
    update(d) {
        const el = $('#progress');
        if (d.show === false) {
            el.hidden = true;
            this.data = null;
            return;
        }
        if (d.update) {
            if (!this.data) return;
            const p = this.data;
            const pct = p.amount > 0 ? clamp(d.delivered / p.amount * 100, 0, 100) : 100;
            $('#pd-liters').innerHTML = `${fmtNum(d.delivered, 2)}<small>${unitLabel(p.fuel.unit)}</small>`;
            $('#pd-cost').textContent = fmtMoney(d.cost, 2);
            $('#pd-bar').style.width = `${pct}%`;
            $('#pd-tank').textContent = t('progress_tank', fmtNum(d.fuel, 1));
            return;
        }
        this.data = d;
        el.innerHTML = `
            <div class="pd-head">${gradeChip(d.fuel)}<span class="name">${esc(d.fuel.label)}</span><span class="pd-live">${esc(t('progress_live'))}</span></div>
            <div class="pd-screens">
                <div class="pd-screen"><div class="eyebrow">${esc(t('progress_amount'))}</div>
                    <div class="v num" id="pd-liters">0,00<small>${unitLabel(d.fuel.unit)}</small></div>
                    <div class="of">${esc(t('progress_of', fmtNum(d.amount, 2), unitLabel(d.fuel.unit)))}</div></div>
                <div class="pd-screen"><div class="eyebrow">${esc(t('progress_price'))}</div>
                    <div class="v num" id="pd-cost">${fmtMoney(0, 2)}</div>
                    <div class="of">${esc(t('progress_deposit', fmtMoney(d.total)))}</div></div>
            </div>
            <div class="pd-bar"><span id="pd-bar" style="width:0%"></span></div>
            <div class="pd-foot"><span id="pd-tank">${esc(t('progress_tank', fmtNum(d.startFuel, 1)))}</span>
                <span><kbd>${esc(d.key || S.cfg.cancelKey)}</kbd> ${esc(t('progress_cancel'))}</span></div>`;
        el.hidden = false;
    },
};

/* ------------------------------------------------------------------ Akční průběh (nakládka / vykládka) */
const ActionBar = {
    update(d) {
        const el = $('#action');
        if (!d.show) {
            el.hidden = true;
            return;
        }
        el.innerHTML = `<div class="row"><span>${esc(d.label)}</span><span><kbd>${esc(d.key || 'X')}</kbd> ${esc(t('action_cancel'))}</span></div>
            <div class="track"><span id="action-fill"></span></div>`;
        el.hidden = false;
        const fill = $('#action-fill');
        fill.animate([{ width: '0%' }, { width: '100%' }], { duration: d.duration, fill: 'forwards', easing: 'linear' });
    },
};

/* ------------------------------------------------------------------ HUD rozvozu */
const JobHud = {
    update(d) {
        const el = $('#jobhud');
        if (!d.show) {
            el.hidden = true;
            return;
        }
        const steps = ['assigned', 'loaded', 'delivered'];
        const idx = steps.indexOf(d.status);
        el.innerHTML = `
            <div class="j-head">${icon('truck')}<span class="eyebrow">${esc(t('job_title', d.orderId))}</span>${d.fuel ? gradeChip(d.fuel) : ''}</div>
            <div class="j-step">${esc(d.step)}</div>
            <div class="j-steps">${steps.map((s, i) => `<i class="${i <= idx ? 'done' : ''}"></i>`).join('')}<i class="${idx >= 2 ? 'done' : ''}"></i></div>
            <div class="j-meta"><span>${esc(d.station || '')}</span><span><b class="num">${fmtNum(d.liters)}</b> ${d.fuel ? unitLabel(d.fuel.unit) : 'l'} · <b>${fmtMoney(d.reward)}</b></span></div>`;
        el.hidden = false;
    },
};

/* ------------------------------------------------------------------ Účtenka */
const Receipt = {
    timer: null,
    show(r, fromItem) {
        if (!r) return;
        const layer = $('#receipt-layer');
        clearTimeout(this.timer);
        const el = document.createElement('div');
        el.className = 'receipt';
        el.innerHTML = `
            <button class="r-close" data-close>${icon('x')}</button>
            <div class="r-brand">${icon('fuel')}${esc(r.station)}</div>
            <div class="r-center">${esc(t('receipt_title'))}</div>
            <div class="r-sep"></div>
            <div class="r-row"><span>${esc(t('receipt_date'))}</span><span>${esc(r.date)} ${esc(r.time)}</span></div>
            <div class="r-row"><span>${esc(t('receipt_number'))}</span><span>${esc(r.number)}</span></div>
            ${r.plate ? `<div class="r-row"><span>${esc(t('receipt_plate'))}</span><span>${esc(r.plate)}</span></div>` : ''}
            <div class="r-sep"></div>
            <div class="r-row"><span><span class="r-grade" style="background:${esc(r.color)}">${esc(r.fuelShort)}</span>${esc(r.fuel)}</span><span></span></div>
            <div class="r-row"><span>${esc(t('receipt_amount'))}</span><span>${fmtNum(r.liters, 2)} ${unitLabel(r.unit)}</span></div>
            <div class="r-row"><span>${esc(t('receipt_unit_price'))}</span><span>${fmtMoney(r.price, 2)}/${unitLabel(r.unit)}</span></div>
            <div class="r-sep"></div>
            <div class="r-total"><span>${esc(t('receipt_total'))}</span><span>${fmtMoney(r.total)}</span></div>
            <div class="r-row" style="margin-top:6px"><span>${esc(t('receipt_payment'))}</span><span>${esc(t('payment_' + r.method))}</span></div>
            <div class="r-foot">${esc(t('receipt_thanks'))}</div>`;
        layer.innerHTML = '';
        layer.appendChild(el);
        const hide = () => {
            el.classList.add('out');
            setTimeout(() => el.remove(), 320);
        };
        el.querySelector('[data-close]').addEventListener('click', hide);
        this.timer = setTimeout(hide, fromItem ? 15000 : 9000);
    },
};

/* ------------------------------------------------------------------ Načítání (čekání na server) */
const Loader = {
    timer: null,
    show(label) {
        clearTimeout(this.timer);
        // krátké odpovědi nezobrazují nic (bez probliknutí)
        this.timer = setTimeout(() => {
            const el = $('#loader');
            el.innerHTML = `<div class="loader-ring">${icon('fuel')}</div>
                <div><div class="l-title">${esc(label || t('loading'))}</div><div class="l-sub"><span class="dots">${esc(t('loading_sub'))}</span></div></div>`;
            el.className = 'loader';
            el.hidden = false;
        }, 140);
    },
    hide() {
        clearTimeout(this.timer);
        $('#loader').hidden = true;
    },
};

/** Řádky skeletonu pro tabulky během načítání */
function skeletonRows(cols, rows = 6) {
    let html = '';
    for (let r = 0; r < rows; r++) {
        html += `<tr class="skel-row">${Array.from({ length: cols }, (_, c) => `<td><span class="skel" style="width:${[70, 55, 85, 45, 60, 75, 50][(r + c) % 7]}%"></span></td>`).join('')}</tr>`;
    }
    return html;
}

/* ------------------------------------------------------------------ Modální okna */
const Modals = {
    stack: [],

    open(view, className, html) {
        const existing = $(`#modals .backdrop[data-view="${view}"]`);
        if (existing) existing.remove();
        this.stack = this.stack.filter((v) => v !== view);
        const backdrop = document.createElement('div');
        backdrop.className = 'backdrop';
        backdrop.dataset.view = view;
        backdrop.innerHTML = `<div class="window ${className}">${html}</div>`;
        $('#modals').appendChild(backdrop);
        this.stack.push(view);
        return backdrop.firstElementChild;
    },

    get(view) {
        const el = $(`#modals .backdrop[data-view="${view}"]`);
        return el ? el.firstElementChild : null;
    },

    /** @param notify informovat Lua (zavřeno uživatelem) */
    close(view, notify, instant) {
        const el = $(`#modals .backdrop[data-view="${view}"]`);
        this.stack = this.stack.filter((v) => v !== view);
        if (!el) return;
        if (instant) {
            el.remove();
        } else {
            el.classList.add('closing');
            setTimeout(() => el.remove(), 170);
        }
        if (notify) post('close', { view });
        const ctrl = Views[view];
        if (ctrl && ctrl.onClose) ctrl.onClose();
    },

    closeAll() {
        [...this.stack].forEach((v) => this.close(v, false, true));
    },

    top() { return this.stack[this.stack.length - 1]; },
};

function closeButton(view) {
    return `<button class="icon-btn" data-close-view="${view}" title="Esc">${icon('x')}</button>`;
}

document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-close-view]');
    if (btn) {
        const view = btn.dataset.closeView;
        if (view === 'offer') Views.offer.respond(false);
        else Modals.close(view, true);
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    const view = Modals.top();
    if (!view) return;
    if (view === 'offer') Views.offer.respond(false);
    else Modals.close(view, true);
});

/* ==========================================================================
   OKNO: Tankování
   ========================================================================== */
const Views = {};

Views.refuel = {
    q: null,
    st: null,

    open(data) {
        const q = data;
        const fuel = q.defaultFuel || (q.fuels.find((f) => f.compatible) || {}).id;
        this.q = q;
        this.st = { fuel, full: true, amount: q.maxAmount, method: q.payment.default, busy: false, error: '' };
        const win = Modals.open('refuel', 'refuel', this.html());
        this.bind(win);
        this.refresh();
    },

    onClose() { this.q = null; },

    fuel() { return this.q.fuels.find((f) => f.id === this.st.fuel); },

    maxFor(fuel) {
        let max = this.q.maxAmount;
        if (fuel && fuel.available >= 0) max = Math.min(max, fuel.available);
        return floor2(Math.max(0, max));
    },

    amount() {
        const max = this.maxFor(this.fuel());
        if (this.st.full) return max;
        return floor2(clamp(this.st.amount, 0, max));
    },

    html() {
        const q = this.q;
        const v = q.vehicle;
        const grades = q.fuels.map((f) => {
            const out = f.available >= 0 && f.available < q.minAmount;
            const disabled = !f.compatible || out;
            const note = !f.compatible ? t('refuel_incompatible') : (out ? t('refuel_out_of_stock') : '');
            return `<button class="grade-tile" data-fuel="${esc(f.id)}" style="${fuelVars(f.color)}" ${disabled ? 'disabled' : ''}>
                ${gradeChip(f, 'lg')}
                <div><div class="g-label">${esc(f.label)}</div>
                ${note ? `<div class="g-note">${esc(note)}</div>` : `<div class="g-price num">${fmtMoney(f.price, 2)} / ${unitLabel(f.unit)}</div>`}</div>
            </button>`;
        }).join('');

        const methods = q.payment.methods.map((m) => `
            <button class="pay-option" data-pay="${m}">
                ${icon(m === 'cash' ? 'banknote' : 'landmark')}
                <div><div class="p-label">${esc(t('payment_' + m))}</div><div class="p-bal num">${fmtMoney(q.payment.balances[m] || 0)}</div></div>
            </button>`).join('');

        return `
            <div class="win-head">
                <div class="win-mark">${icon('fuel')}</div>
                <div><div class="title">${esc(q.station.label)}</div><div class="sub">${esc(t('refuel_subtitle'))}</div></div>
                <div class="spacer"></div>${closeButton('refuel')}
            </div>
            <div class="win-body">
                <div class="col">
                    <div class="veh">
                        <div><div class="veh-name">${esc(v.label)}</div><div class="veh-cat">${esc(v.categoryLabel)} · ${esc(t('refuel_tank', fmtNum(v.capacity), unitLabel(this.fuel() ? this.fuel().unit : 'l')))}</div></div>
                        ${v.plate ? `<span class="plate">${esc(v.plate)}</span>` : ''}
                    </div>
                    <div class="tank">
                        <div class="tank-row"><span class="eyebrow">${esc(t('refuel_tank_state'))}</span><span class="val" id="rf-tankval"></span></div>
                        <div class="tank-bar"><div class="cur" style="width:${clamp(v.fuel, 0, 100)}%"></div><div class="add" id="rf-add"></div><div class="ticks"></div></div>
                        <div class="tank-legend"><span><i style="background:#d9d6cf"></i>${esc(t('refuel_current'))}</span><span><i style="background:var(--accent)"></i>${esc(t('refuel_added'))}</span></div>
                    </div>
                    <div class="section-label" style="margin-top:22px"><span class="eyebrow">${esc(t('refuel_fuel_type'))}</span></div>
                    <div class="grades">${grades}</div>
                    <div class="notice refuel-note">${icon('info')}<span>${esc(t('refuel_note', S.cfg.cancelKey))}</span></div>
                </div>
                <div class="col">
                    <div class="section-label"><span class="eyebrow">${esc(t('refuel_amount'))}</span><span class="muted" style="font-size:12px" id="rf-max"></span></div>
                    <div class="amount-display">
                        <button class="step-btn" data-step="-1">${icon('minus')}</button>
                        <div class="digits num" id="rf-digits"></div>
                        <button class="step-btn" data-step="1">${icon('plus')}</button>
                    </div>
                    <input type="range" id="rf-range" min="0" step="0.5">
                    <div class="presets">
                        <button class="preset" data-preset="5">5</button>
                        <button class="preset" data-preset="10">10</button>
                        <button class="preset" data-preset="20">20</button>
                        <button class="preset" data-preset="full">${esc(t('refuel_full'))}</button>
                    </div>
                    <div class="custom-row">
                        <div class="input-group"><input class="input num" id="rf-custom" type="number" min="0" step="0.1" placeholder="${esc(t('refuel_custom'))}"><span class="suffix" id="rf-unit"></span></div>
                        <button class="btn" id="rf-apply">${esc(t('refuel_apply'))}</button>
                    </div>

                    <div class="section-label"><span class="eyebrow">${esc(t('refuel_payment'))}</span></div>
                    <div class="pay-options">${methods}</div>

                    <div class="summary">
                        <div class="sum-row"><span>${esc(t('refuel_unit_price'))}</span><b class="num" id="rf-price"></b></div>
                        <div class="sum-row"><span>${esc(t('refuel_quantity'))}</span><b class="num" id="rf-qty"></b></div>
                        <div class="sum-row"><span>${esc(t('refuel_duration'))}</span><b class="num" id="rf-dur"></b></div>
                        <div class="sum-total"><span class="eyebrow">${esc(t('refuel_total'))}</span><span class="t-val num" id="rf-total"></span></div>
                    </div>
                    <div class="error-line" id="rf-error" style="margin-top:12px"></div>
                    <button class="btn btn-primary btn-lg btn-block" id="rf-confirm" style="margin-top:12px"></button>
                </div>
            </div>`;
    },

    bind(win) {
        win.addEventListener('click', (e) => {
            const fuelBtn = e.target.closest('[data-fuel]');
            if (fuelBtn && !fuelBtn.disabled) {
                this.st.fuel = fuelBtn.dataset.fuel;
                this.st.error = '';
                this.refresh();
                return;
            }
            const step = e.target.closest('[data-step]');
            if (step) {
                const max = this.maxFor(this.fuel());
                const cur = this.amount();
                this.st.full = false;
                this.st.amount = clamp(Math.round(cur + Number(step.dataset.step)), 0, max);
                if (this.st.amount >= max) this.st.full = true;
                this.refresh();
                return;
            }
            const preset = e.target.closest('[data-preset]');
            if (preset) {
                if (preset.dataset.preset === 'full') {
                    this.st.full = true;
                } else {
                    this.st.full = false;
                    this.st.amount = Number(preset.dataset.preset);
                }
                this.refresh();
                return;
            }
            const pay = e.target.closest('[data-pay]');
            if (pay) {
                this.st.method = pay.dataset.pay;
                this.st.error = '';
                this.refresh();
                return;
            }
            if (e.target.closest('#rf-apply')) {
                this.applyCustom(win);
                return;
            }
            if (e.target.closest('#rf-confirm')) this.confirm();
        });

        $('#rf-range', win).addEventListener('input', (e) => {
            const max = this.maxFor(this.fuel());
            const val = Number(e.target.value);
            this.st.full = val >= max;
            this.st.amount = val;
            this.refresh(true);
        });

        $('#rf-custom', win).addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.applyCustom(win);
        });
    },

    applyCustom(win) {
        const input = $('#rf-custom', win);
        const val = Number(String(input.value).replace(',', '.'));
        if (!val || val <= 0) return;
        const max = this.maxFor(this.fuel());
        this.st.amount = floor2(clamp(val, 0, max));
        this.st.full = this.st.amount >= max;
        input.value = '';
        this.refresh();
    },

    /** Aktualizace dynamických částí bez překreslení (zachová tah posuvníku) */
    refresh(fromRange) {
        const win = Modals.get('refuel');
        if (!win || !this.q) return;
        const q = this.q;
        const fuel = this.fuel();
        const unit = unitLabel(fuel ? fuel.unit : 'l');
        const max = this.maxFor(fuel);
        const amount = this.amount();
        const price = fuel ? fuel.price : 0;
        const total = amount > 0 ? Math.max(1, Math.ceil(amount * price - 1e-9)) : 0;
        const addPct = q.vehicle.capacity > 0 ? amount / q.vehicle.capacity * 100 : 0;
        const after = clamp(q.vehicle.fuel + addPct, 0, 100);
        const balance = q.payment.balances[this.st.method] || 0;
        const enough = balance >= total;

        $$('[data-fuel]', win).forEach((b) => b.classList.toggle('active', b.dataset.fuel === this.st.fuel));
        $$('[data-pay]', win).forEach((b) => {
            b.classList.toggle('active', b.dataset.pay === this.st.method);
            b.classList.toggle('short', (q.payment.balances[b.dataset.pay] || 0) < total);
        });
        $$('[data-preset]', win).forEach((b) => {
            const p = b.dataset.preset;
            b.classList.toggle('active', p === 'full' ? this.st.full : (!this.st.full && Number(p) === amount));
            if (p !== 'full') b.disabled = Number(p) > max;
            if (p !== 'full') b.textContent = `${p} ${unit}`;
        });

        $('#rf-digits', win).innerHTML = `${fmtNum(amount, 2)}<small>${unit}</small>`;
        $('#rf-max', win).textContent = t('refuel_max', fmtNum(max, 2), unit);
        $('#rf-unit', win).textContent = unit;
        $('#rf-tankval', win).innerHTML = `<b>${fmtNum(q.vehicle.fuel, 0)} %</b> → <b>${fmtNum(after, 0)} %</b>`;
        const add = $('#rf-add', win);
        add.style.left = `${clamp(q.vehicle.fuel, 0, 100)}%`;
        add.style.width = `${Math.max(0, after - q.vehicle.fuel)}%`;

        const range = $('#rf-range', win);
        range.max = String(max);
        if (!fromRange) range.value = String(amount);
        range.style.setProperty('--fill', `${max > 0 ? amount / max * 100 : 0}%`);
        range.disabled = max <= 0;

        $('#rf-price', win).textContent = `${fmtMoney(price, 2)} / ${unit}`;
        $('#rf-qty', win).textContent = `${fmtNum(amount, 2)} ${unit}`;
        $('#rf-dur', win).textContent = t('refuel_seconds', Math.ceil(amount / (q.vehicle.rate || 1)));
        $('#rf-total', win).textContent = fmtMoney(total);

        let error = this.st.error;
        if (!error && !enough && total > 0) error = t('error_insufficient_funds', fmtMoney(total));
        if (!error && max < q.minAmount) error = t('error_tank_full');
        $('#rf-error', win).innerHTML = error ? `${icon('triangle-alert')}<span>${esc(error)}</span>` : '';

        const confirm = $('#rf-confirm', win);
        confirm.disabled = !this.st.busy && (!fuel || amount < q.minAmount || !enough);
        confirm.classList.toggle('is-loading', this.st.busy);
        confirm.innerHTML = this.st.busy
            ? `${icon('fuel')} ${esc(t('refuel_processing'))}`
            : `${icon('fuel')} ${esc(t('refuel_confirm', fmtMoney(total)))}`;
    },

    async confirm() {
        if (this.st.busy) return;
        const fuel = this.fuel();
        if (!fuel) return;
        this.st.busy = true;
        this.st.error = '';
        this.refresh();
        const res = await post('refuel:confirm', {
            fuelType: fuel.id,
            amount: this.amount(),
            full: this.st.full,
            method: this.st.method,
        });
        if (!this.q) return;
        this.st.busy = false;
        if (!res || !res.ok) {
            this.st.error = (res && res.message) || t('error_internal');
            this.refresh();
        }
    },
};

/* ==========================================================================
   OKNO: Management benzinky
   ========================================================================== */
Views.management = {
    d: null,
    st: null,

    open(data) {
        this.d = data;
        this.st = {
            tab: null, busy: false, salesPage: 1, financePage: 1,
            hireOpen: false, players: null, hireRank: null,
            expanded: null, permDraft: {}, confirmFire: null, confirmSell: false, confirmQuit: false,
            order: { fuel: null, liters: null, method: null },
        };
        this.st.tab = this.tabs()[0] ? this.tabs()[0].id : 'shift';
        this.st.enter = true;
        const win = Modals.open('management', 'mgmt', '<div class="mgmt-side"></div><div class="mgmt-main"></div>');
        this.bind(win);
        this.render();
        this.startClock();
    },

    onClose() {
        clearInterval(this.clock);
        this.d = null;
    },

    perms() { return (this.d.viewer && this.d.viewer.perms) || {}; },
    feat() { return (this.d.viewer && this.d.viewer.features) || {}; },

    tabs() {
        const p = this.perms();
        const f = this.feat();
        const v = this.d.viewer || {};
        const list = [];
        if (p.view_overview) list.push({ id: 'overview', icon: 'layout-dashboard', label: t('tab_overview') });
        if (p.manage_prices || p.view_overview) list.push({ id: 'prices', icon: 'tag', label: t('tab_prices') });
        if (p.view_stock && f.stock) list.push({ id: 'stock', icon: 'warehouse', label: t('tab_stock'), badge: this.d.orders ? this.d.orders.filter((o) => ['pending', 'assigned', 'loaded'].includes(o.status)).length : 0 });
        if (f.employees && p.manage_employees) list.push({ id: 'employees', icon: 'users', label: t('tab_employees') });
        if (v.isEmployee) list.push({ id: 'shift', icon: 'clock', label: t('tab_shift') });
        if (p.view_finances || p.deposit || p.withdraw) list.push({ id: 'finance', icon: 'wallet', label: t('tab_finance') });
        if (p.view_transactions) list.push({ id: 'sales', icon: 'scroll-text', label: t('tab_sales') });
        if (v.isOwner) list.push({ id: 'settings', icon: 'settings', label: t('tab_settings') });
        return list;
    },

    startClock() {
        clearInterval(this.clock);
        this.clock = setInterval(() => {
            if (!this.d || !this.d.viewer || !this.d.viewer.onDuty) return;
            this.d.viewer.shiftSeconds = (this.d.viewer.shiftSeconds || 0) + 1;
            const el = $('#shift-clock');
            if (el) el.textContent = fmtClock(this.d.viewer.shiftSeconds);
        }, 1000);
    },

    async action(name, payload = {}, opts = {}) {
        if (this.st.busy && !opts.parallel) return null;
        if (!opts.parallel) this.st.busy = true;
        this.setBusy(true, opts.button);
        const res = await post('mgmt:action', { action: name, payload });
        if (!this.d) return res;
        if (!opts.parallel) this.st.busy = false;
        this.setBusy(false);
        if (res && res.update) Object.assign(this.d, res.update);
        if (!opts.noRender) this.render();
        return res;
    },

    /** Indikátor probíhající akce: pruh v horní části panelu + spinner v tlačítku */
    setBusy(on, button) {
        const win = Modals.get('management');
        if (!win) return;
        const main = $('.mgmt-main', win);
        const bar = $('.win-progress', main);
        if (on && !bar) main.insertAdjacentHTML('afterbegin', '<div class="win-progress"></div>');
        if (!on && bar) bar.remove();
        const content = $('.mgmt-content', win);
        if (content) content.classList.toggle('is-busy', on && !button);
        if (button) button.classList.add('is-loading');
        if (!on) $$('.is-loading', win).forEach((el) => el.classList.remove('is-loading'));
    },

    /* --------------------------------------------- vykreslení */
    render() {
        const win = Modals.get('management');
        if (!win || !this.d) return;
        const tabs = this.tabs();
        if (!tabs.find((x) => x.id === this.st.tab)) this.st.tab = tabs[0] ? tabs[0].id : null;
        const s = this.d.station;
        const v = this.d.viewer;
        const p = this.perms();
        const role = v.isOwner ? t('role_owner') : (v.rankLabel || t('role_employee'));

        $('.mgmt-side', win).innerHTML = `
            <div class="mgmt-brand">
                <div class="win-mark">${icon('store')}</div>
                <div class="s-name">${esc(s.label)}</div>
                <div class="s-type">${esc(s.typeLabel)}${s.label !== s.defaultLabel ? ' · ' + esc(s.defaultLabel) : ''}</div>
                <div class="status-toggle">
                    ${p.toggle_station
                        ? `<button class="pill ${s.open ? 'ok' : 'err'}" data-act="toggleOpen" title="${esc(t('toggle_hint'))}">${esc(s.open ? t('status_open') : t('status_closed'))}</button>`
                        : `<span class="pill ${s.open ? 'ok' : 'err'}">${esc(s.open ? t('status_open') : t('status_closed'))}</span>`}
                </div>
            </div>
            <div class="nav">${tabs.map((x) => `<button class="${x.id === this.st.tab ? 'active' : ''}" data-tab="${x.id}">${icon(x.icon)}<span>${esc(x.label)}</span>${x.badge ? `<span class="badge">${x.badge}</span>` : ''}</button>`).join('')}</div>
            <div class="viewer">
                <div class="avatar">${esc(initials(v.name))}</div>
                <div><div class="v-name">${esc(v.name)}</div><div class="v-role">${esc(role)}${v.onDuty ? ' · ' + esc(t('on_duty')) : ''}</div></div>
            </div>`;

        const current = tabs.find((x) => x.id === this.st.tab);
        $('.mgmt-main', win).innerHTML = `
            <div class="win-head">
                <div><div class="title">${esc(current ? current.label : '')}</div><div class="sub">${esc(this.tabSubtitle())}</div></div>
                <div class="spacer"></div>
                <button class="icon-btn" data-act="refresh" title="${esc(t('refresh'))}">${icon('refresh-cw')}</button>
                ${closeButton('management')}
            </div>
            <div class="mgmt-content${this.st.enter ? ' tab-enter' : ''}">${this.renderTab()}</div>`;
        this.st.enter = false;
    },

    tabSubtitle() {
        const s = this.d.station;
        switch (this.st.tab) {
            case 'overview': return s.ownerName ? t('sub_owner', s.ownerName) : '';
            case 'prices': return t('sub_prices');
            case 'stock': return t('sub_stock');
            case 'employees': return t('sub_employees', (this.d.employees || []).length, this.d.maxEmployees || 0);
            case 'shift': return t('sub_shift');
            case 'finance': return t('sub_finance');
            case 'sales': return t('sub_sales');
            case 'settings': return t('sub_settings');
            default: return '';
        }
    },

    renderTab() {
        switch (this.st.tab) {
            case 'overview': return this.tabOverview();
            case 'prices': return this.tabPrices();
            case 'stock': return this.tabStock();
            case 'employees': return this.tabEmployees();
            case 'shift': return this.tabShift();
            case 'finance': return this.tabFinance();
            case 'sales': return this.tabSales();
            case 'settings': return this.tabSettings();
            default: return `<div class="empty">${icon('lock')}<div>${esc(t('no_access'))}</div></div>`;
        }
    },

    /* --------------------------------------------- Přehled */
    tabOverview() {
        const s = this.d.station;
        const st = this.d.stats || {};
        const tiles = [];
        if (s.balance !== undefined && s.balance !== null) {
            tiles.push(`<div class="card kpi highlight"><div class="k-label">${icon('wallet')}${esc(t('kpi_balance'))}</div><div class="k-val num">${fmtMoney(s.balance)}</div><div class="k-sub">${esc(t('kpi_balance_sub'))}</div></div>`);
        }
        tiles.push(`<div class="card kpi"><div class="k-label">${icon('chart-line')}${esc(t('kpi_revenue'))}</div><div class="k-val num">${fmtMoney(st.revenue || 0)}</div><div class="k-sub">${esc(t('kpi_profit', fmtMoney(st.profit || 0)))}</div></div>`);
        tiles.push(`<div class="card kpi"><div class="k-label">${icon('users')}${esc(t('kpi_customers'))}</div><div class="k-val num">${fmtNum(st.customers || 0)}</div><div class="k-sub">${esc(t('kpi_employees', st.employees || 0))}</div></div>`);
        tiles.push(`<div class="card kpi"><div class="k-label">${icon('droplet')}${esc(t('kpi_liters'))}</div><div class="k-val num">${fmtNum(st.liters || 0)}</div><div class="k-sub">${esc(t('kpi_orders', st.activeOrders || 0))}</div></div>`);

        const sales = this.d.sales && this.d.sales.rows ? this.d.sales.rows.slice(0, 6) : null;
        return `
            <div class="grid g-4">${tiles.join('')}</div>
            <div class="grid g-main" style="margin-top:14px">
                <div class="card chart-card">
                    <div class="card-head"><h3>${esc(t('chart_title', (this.d.chart || []).length))}</h3>
                        <div class="chart-legend"><span><i style="background:var(--chart-1)"></i>${esc(t('chart_revenue'))}</span><span><i style="background:var(--chart-2)"></i>${esc(t('chart_costs'))}</span></div></div>
                    <div class="card-body">${this.chart(this.d.chart || [])}</div>
                </div>
                <div class="card">
                    <div class="card-head"><h3>${esc(t('stock_title'))}</h3></div>
                    <div class="card-body">${this.stockList(false)}</div>
                </div>
            </div>
            ${sales ? `<div class="card" style="margin-top:14px"><div class="card-head"><h3>${esc(t('recent_sales'))}</h3>
                <button class="btn btn-ghost btn-sm" data-tab="sales">${esc(t('show_all'))}${icon('chevron-right')}</button></div>
                <div class="card-body">${this.salesTable(sales, true)}</div></div>` : ''}`;
    },

    chart(data) {
        if (!data.length) return `<div class="empty">${icon('chart-line')}<div>${esc(t('chart_empty'))}</div></div>`;
        const W = 470, H = 290, padL = 46, padR = 6, padT = 12, padB = 26;
        const innerW = W - padL - padR, innerH = H - padT - padB;
        const maxVal = Math.max(1, ...data.map((d) => Math.max(d.revenue, d.costs)));
        const niceStep = (() => {
            const raw = maxVal / 4;
            const mag = Math.pow(10, Math.floor(Math.log10(raw)));
            const n = raw / mag;
            return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag;
        })();
        const top = niceStep * 4;
        const y = (v) => padT + innerH - (v / top) * innerH;
        const band = innerW / data.length;
        const barW = Math.min(18, band * 0.3);
        const days = (t('weekdays_short') || 'Ne,Po,Út,St,Čt,Pá,So').split(',');
        let barIndex = 0;
        const bar = (x, v, color) => {
            if (v <= 0) return '';
            const yTop = y(v);
            const h = padT + innerH - yTop;
            const r = Math.min(4, h, barW / 2);
            return `<path class="chart-bar" style="animation-delay:${(0.12 + barIndex++ * 0.035).toFixed(3)}s" d="M${x},${padT + innerH} L${x},${yTop + r} Q${x},${yTop} ${x + r},${yTop} L${x + barW - r},${yTop} Q${x + barW},${yTop} ${x + barW},${yTop + r} L${x + barW},${padT + innerH} Z" fill="${color}"/>`;
        };
        let grid = '';
        for (let i = 0; i <= 4; i++) {
            const val = niceStep * i;
            const yy = y(val);
            grid += `<line x1="${padL}" x2="${W - padR}" y1="${yy}" y2="${yy}" stroke="rgba(255,255,255,${i === 0 ? 0.14 : 0.06})" stroke-width="1"/>`;
            grid += `<text x="${padL - 8}" y="${yy + 4}" text-anchor="end" fill="#82878e" font-size="11" font-family="Barlow">${esc(fmtCompactMoney(val))}</text>`;
        }
        let bars = '', labels = '', hits = '';
        data.forEach((d, i) => {
            const cx = padL + band * i + band / 2;
            bars += bar(cx - barW - 1, d.revenue, 'var(--chart-1)');
            bars += bar(cx + 1, d.costs, 'var(--chart-2)');
            const date = new Date(d.date * 1000);
            labels += `<text x="${cx}" y="${H - 8}" text-anchor="middle" fill="#82878e" font-size="11" font-family="Barlow">${esc(days[date.getDay()] || '')} ${date.getDate()}.</text>`;
            hits += `<rect class="chart-hit" data-i="${i}" x="${padL + band * i}" y="${padT}" width="${band}" height="${innerH}" fill="transparent"/>`;
        });
        this.chartData = data;
        return `<div class="chart-wrap" id="chart"><svg viewBox="0 0 ${W} ${H}" style="height:auto">${grid}<g id="chart-hl"></g>${bars}${labels}${hits}</svg><div class="chart-tip" id="chart-tip" hidden></div></div>`;
    },

    stockList(withPending) {
        const fuels = this.d.fuels || [];
        if (!fuels.length) return '';
        return `<div class="stock-list">${fuels.map((f) => {
            const stock = f.stock || 0;
            const pct = f.capacity > 0 ? clamp(stock / f.capacity * 100, 0, 100) : 0;
            const pend = withPending && f.pending ? clamp(f.pending / f.capacity * 100, 0, 100 - pct) : 0;
            const low = pct < 15;
            return `<div class="stock-item" style="${fuelVars(f.color)}">
                <div class="s-top">${gradeChip(f)}<span class="s-name">${esc(f.label)}</span><span class="s-amt num"><b>${fmtNum(stock)}</b> / ${fmtNum(f.capacity)} ${unitLabel(f.unit)}</span></div>
                <div class="stock-bar"><div class="fill" style="width:${pct}%"></div>${pend ? `<div class="pend" style="left:${pct}%;width:${pend}%"></div>` : ''}</div>
                <div class="s-meta"><span>${low ? `<span style="color:var(--warn)">${esc(t('stock_low'))}</span>` : esc(t('stock_pct', fmtNum(pct, 0)))}</span><span>${withPending && f.pending ? esc(t('stock_pending', fmtNum(f.pending), unitLabel(f.unit))) : ''}</span></div>
            </div>`;
        }).join('')}</div>`;
    },

    /* --------------------------------------------- Ceny */
    tabPrices() {
        const can = !!this.perms().manage_prices;
        const rows = (this.d.fuels || []).map((f) => `
            <div class="price-row">
                ${gradeChip(f, 'lg')}
                <div><div class="p-name">${esc(f.label)}</div>
                    <div class="p-meta">${esc(t('price_meta', fmtMoney(f.minPrice, 2), fmtMoney(f.maxPrice, 2), fmtMoney(f.defaultPrice, 2), fmtMoney(f.wholesale, 2)))}</div></div>
                <div class="input-group"><input class="input num" type="number" step="0.01" min="${f.minPrice}" max="${f.maxPrice}" value="${Number(f.price).toFixed(2)}" data-price-input="${esc(f.id)}" ${can ? '' : 'disabled'}><span class="suffix">/${unitLabel(f.unit)}</span></div>
                ${can ? `<button class="btn btn-sm" data-save-price="${esc(f.id)}">${icon('check')}${esc(t('save'))}</button>` : `<span class="muted num">${fmtMoney(f.price, 2)}</span>`}
            </div>`).join('');
        return `${can ? '' : `<div class="notice" style="margin-bottom:14px">${icon('lock')}<span>${esc(t('prices_readonly'))}</span></div>`}
            <div class="card">${rows}</div>
            <div class="notice" style="margin-top:14px">${icon('info')}<span>${esc(t('prices_hint'))}</span></div>`;
    },

    /* --------------------------------------------- Sklad a objednávky */
    tabStock() {
        const p = this.perms();
        const f = this.feat();
        const cfg = this.d.orderConfig;
        const canOrder = p.order_fuel && f.orders && cfg && (cfg.supplier || cfg.tanker);
        return `
            <div class="grid ${canOrder ? 'g-2' : ''}">
                <div class="card"><div class="card-head"><h3>${esc(t('stock_title'))}</h3></div><div class="card-body">${this.stockList(true)}</div></div>
                ${canOrder ? `<div class="card"><div class="card-head"><h3>${esc(t('order_title'))}</h3></div><div class="card-body" id="order-form">${this.orderForm()}</div></div>` : ''}
            </div>
            ${f.orders && this.d.orders ? `<div class="card" style="margin-top:14px"><div class="card-head"><h3>${esc(t('orders_title'))}</h3></div><div class="card-body">${this.ordersTable()}</div></div>` : ''}`;
    },

    orderState() {
        const cfg = this.d.orderConfig;
        const o = this.st.order;
        const fuels = this.d.fuels || [];
        if (!o.fuel || !fuels.find((x) => x.id === o.fuel)) o.fuel = fuels[0] && fuels[0].id;
        if (!o.method) o.method = cfg.tanker ? 'tanker' : 'supplier';
        if (o.method === 'tanker' && !cfg.tanker) o.method = 'supplier';
        if (o.method === 'supplier' && !cfg.supplier) o.method = 'tanker';
        const fuel = fuels.find((x) => x.id === o.fuel);
        const free = fuel ? Math.max(0, Math.floor(fuel.capacity - (fuel.stock || 0) - (fuel.pending || 0))) : 0;
        const max = Math.min(cfg.max, free);
        if (o.liters === null) o.liters = Math.min(max, Math.max(cfg.min, Math.round(max / 2 / 100) * 100));
        o.liters = clamp(o.liters, Math.min(cfg.min, max), max);
        return { cfg, o, fuel, free, max };
    },

    orderQuote(fuel, liters, method) {
        const cfg = this.d.orderConfig;
        if (!fuel) return { cost: 0, reward: 0 };
        if (method === 'supplier') return { cost: Math.ceil(liters * (fuel.wholesale + cfg.supplier.fee) - 1e-9), reward: 0 };
        const r = cfg.tanker.reward;
        const reward = Math.floor(Math.min(r.max, r.base + liters * r.perLiter));
        return { cost: Math.ceil(liters * fuel.wholesale - 1e-9) + reward, reward };
    },

    orderForm() {
        const { cfg, o, fuel, free, max } = this.orderState();
        const q = this.orderQuote(fuel, o.liters, o.method);
        const canSubmit = fuel && max >= cfg.min;
        const balance = this.d.station.balance;
        return `
            <div class="field"><label>${esc(t('order_fuel'))}</label>
                <div class="chip-select">${(this.d.fuels || []).map((x) => `<button class="${x.id === o.fuel ? 'active' : ''}" data-order-fuel="${esc(x.id)}" style="${fuelVars(x.color)}">${gradeChip(x)}${esc(x.label)}</button>`).join('')}</div></div>
            <div class="field" style="margin-top:14px"><label>${esc(t('order_amount'))} <span class="faint">· ${esc(t('order_free', fmtNum(free), unitLabel(fuel ? fuel.unit : 'l')))}</span></label>
                <div class="custom-row" style="margin-top:0;grid-template-columns:1fr 130px">
                    <input type="range" id="order-range" min="${Math.min(cfg.min, max)}" max="${max}" step="100" value="${o.liters}" style="--fill:${max > 0 ? (o.liters - Math.min(cfg.min, max)) / Math.max(1, max - Math.min(cfg.min, max)) * 100 : 0}%" ${canSubmit ? '' : 'disabled'}>
                    <div class="input-group"><input class="input num" id="order-liters" type="number" step="100" value="${o.liters}" ${canSubmit ? '' : 'disabled'}><span class="suffix">${unitLabel(fuel ? fuel.unit : 'l')}</span></div>
                </div></div>
            <div class="field" style="margin-top:14px"><label>${esc(t('order_method'))}</label>
                <div class="method-cards">
                    ${cfg.supplier ? `<button class="method-card ${o.method === 'supplier' ? 'active' : ''}" data-order-method="supplier"><div class="m-title">${icon('package')}${esc(t('order_method_supplier'))}</div><div class="m-desc">${esc(t('order_supplier_desc', cfg.supplier.delay, fmtMoney(cfg.supplier.fee, 2)))}</div></button>` : ''}
                    ${cfg.tanker ? `<button class="method-card ${o.method === 'tanker' ? 'active' : ''}" data-order-method="tanker"><div class="m-title">${icon('truck')}${esc(t('order_method_tanker'))}</div><div class="m-desc">${esc(t('order_tanker_desc'))}</div></button>` : ''}
                </div></div>
            <div class="summary" style="margin-top:14px">
                <div class="sum-row"><span>${esc(t('order_wholesale'))}</span><b class="num">${fuel ? fmtMoney(fuel.wholesale, 2) : '—'} / ${unitLabel(fuel ? fuel.unit : 'l')}</b></div>
                ${q.reward ? `<div class="sum-row"><span>${esc(t('order_reward'))}</span><b class="num">${fmtMoney(q.reward)}</b></div>` : ''}
                <div class="sum-total"><span class="eyebrow">${esc(t('order_total'))}</span><span class="t-val num" style="font-size:24px">${fmtMoney(q.cost)}</span></div>
                ${balance !== undefined && balance !== null && balance < q.cost ? `<div class="error-line" style="margin-top:8px">${icon('triangle-alert')}<span>${esc(t('error_company_funds', fmtMoney(q.cost)))}</span></div>` : ''}
            </div>
            <button class="btn btn-primary btn-block" style="margin-top:14px" data-act="orderFuel" ${canSubmit ? '' : 'disabled'}>${icon('truck')}${esc(canSubmit ? t('order_submit') : t('order_no_space'))}</button>`;
    },

    orderStatus(o) {
        const map = {
            pending: o.method === 'supplier' ? ['info', t('order_status_transit')] : ['warn', t('order_status_waiting')],
            assigned: ['info', t('order_status_assigned')],
            loaded: ['accent', t('order_status_loaded')],
            delivered: ['ok', t('order_status_delivered')],
            cancelled: ['err', t('order_status_cancelled')],
        };
        const [cls, label] = map[o.status] || ['', o.status];
        return `<span class="pill ${cls}">${esc(label)}</span>`;
    },

    ordersTable() {
        const orders = this.d.orders || [];
        if (!orders.length) return `<div class="empty">${icon('package')}<div>${esc(t('orders_empty'))}</div></div>`;
        const now = Date.now() / 1000;
        const canCancel = this.perms().cancel_orders;
        const fuelMap = {};
        (this.d.fuels || []).forEach((f) => { fuelMap[f.id] = f; });
        return `<table class="table"><thead><tr><th>#</th><th>${esc(t('col_fuel'))}</th><th class="right">${esc(t('col_amount'))}</th><th>${esc(t('col_method'))}</th><th>${esc(t('col_status'))}</th><th>${esc(t('col_info'))}</th><th class="right">${esc(t('col_cost'))}</th><th></th></tr></thead><tbody>
            ${orders.map((o) => {
                const f = fuelMap[o.fuelType] || S.cfg.fuelTypes[o.fuelType] || { short: '?', color: '#888', unit: 'l', label: o.fuelType };
                let info = '';
                if (o.status === 'delivered') info = fmtDate(o.deliveredAt);
                else if (o.status === 'cancelled') info = fmtDate(o.createdAt);
                else if (o.driverName) info = t('order_driver', o.driverName);
                else if (o.deliverAt > 0) info = o.deliverAt > now ? t('order_eta', Math.max(1, Math.ceil((o.deliverAt - now) / 60))) : t('order_eta_soon');
                else info = fmtDate(o.createdAt);
                return `<tr><td class="num">${o.id}</td><td>${gradeChip(f)}</td><td class="right num strong">${fmtNum(o.liters)} ${unitLabel(f.unit)}</td>
                    <td>${esc(t('order_method_' + o.method))}</td><td>${this.orderStatus(o)}</td><td>${esc(info)}</td>
                    <td class="right num">${fmtMoney(o.cost)}</td>
                    <td class="right">${canCancel && o.status === 'pending' ? `<button class="btn btn-ghost btn-sm" data-cancel-order="${o.id}">${esc(t('cancel'))}</button>` : ''}</td></tr>`;
            }).join('')}</tbody></table>`;
    },

    /* --------------------------------------------- Zaměstnanci */
    rankOptions(selected) {
        const v = this.d.viewer;
        return (this.d.ranks || []).filter((r) => v.isOwner || r.grade < v.grade)
            .map((r) => `<option value="${esc(r.id)}" ${r.id === selected ? 'selected' : ''}>${esc(r.label)}</option>`).join('');
    },

    tabEmployees() {
        const list = this.d.employees || [];
        const v = this.d.viewer;
        const max = this.d.maxEmployees || 0;
        let hire = '';
        if (this.st.hireOpen) {
            const players = this.st.players;
            let body;
            if (players === null) body = `<div class="hire-list">${[0, 1, 2].map(() => `<div class="skel-item"><span class="skel round" style="width:30px;height:30px"></span><span><span class="skel" style="width:55%"></span><span class="skel" style="width:30%;margin-top:7px;height:9px"></span></span><span class="skel" style="height:32px;border-radius:10px"></span><span class="skel" style="height:30px;border-radius:999px"></span></div>`).join('')}</div>`;
            else if (!players.length) body = `<div class="empty">${icon('user-x')}<div>${esc(t('hire_none'))}</div></div>`;
            else body = `<div class="hire-list">${players.map((pl) => `
                <div class="hire-item"><div class="emp-name"><div class="avatar">${esc(initials(pl.name))}</div><div><div class="n">${esc(pl.name)}</div><div class="s">ID ${pl.id}</div></div></div>
                    <select class="select" data-hire-rank="${pl.id}">${this.rankOptions(this.st.hireRank)}</select>
                    <button class="btn btn-primary btn-sm" data-hire="${pl.id}">${icon('user-plus')}${esc(t('hire_send'))}</button></div>`).join('')}</div>`;
            hire = `<div class="card" style="margin-bottom:14px"><div class="card-head"><h3>${esc(t('hire_title'))}</h3>
                <button class="btn btn-ghost btn-sm" data-act="nearbyPlayers">${icon('refresh-cw')}${esc(t('refresh'))}</button></div>
                <div class="card-body"><p class="muted" style="font-size:13px;margin-bottom:12px">${esc(t('hire_hint'))}</p>${body}</div></div>`;
        }

        const rows = list.map((e) => {
            const expanded = this.st.expanded === e.identifier;
            const fire = this.st.confirmFire === e.identifier;
            return `<tr class="emp-row">
                <td><div class="emp-name"><div class="avatar">${esc(initials(e.name))}</div><div><div class="n"><span class="online-dot ${e.online ? 'on' : ''}"></span>${esc(e.name)}${e.isMe ? ` <span class="faint">(${esc(t('you'))})</span>` : ''}</div><div class="s">${esc(t('emp_hired', fmtDate(e.hiredAt, false)))}</div></div></div></td>
                <td>${e.manageable ? `<select class="select" style="height:32px;min-width:136px" data-rank-select="${esc(e.identifier)}">${this.rankOptions(e.rank)}${!v.isOwner && e.grade >= v.grade ? `<option selected>${esc(e.rankLabel)}</option>` : ''}</select>` : `<span class="strong">${esc(e.rankLabel)}</span>`}</td>
                <td class="right num">${fmtMoney(e.salary)}</td>
                <td class="right num">${esc(fmtDuration(e.weekSeconds))}</td>
                <td class="right num">${esc(fmtDuration(e.secondsWorked))}</td>
                <td>${e.onDuty ? `<span class="pill ok">${esc(t('on_duty'))}</span>` : `<span class="pill">${esc(t('off_duty'))}</span>`}</td>
                <td class="right" style="white-space:nowrap">${e.manageable ? `
                    <button class="icon-btn ${expanded ? 'active' : ''}" data-perms="${esc(e.identifier)}" title="${esc(t('emp_permissions'))}">${icon('shield')}</button>
                    ${fire ? `<button class="btn btn-danger btn-sm" data-fire="${esc(e.identifier)}">${esc(t('emp_fire_confirm'))}</button>` : `<button class="icon-btn danger" data-fire-ask="${esc(e.identifier)}" title="${esc(t('emp_fire'))}">${icon('user-x')}</button>`}` : ''}</td>
            </tr>${expanded ? `<tr class="perm-panel"><td colspan="7">${this.permEditor(e)}</td></tr>` : ''}`;
        }).join('');

        return `${hire}
            <div class="card"><div class="card-head"><h3>${esc(t('emp_title'))} <span class="faint num">${list.length}/${max}</span></h3>
                ${!this.st.hireOpen ? `<button class="btn btn-sm" data-act="openHire" ${list.length >= max ? 'disabled' : ''}>${icon('user-plus')}${esc(t('hire_open'))}</button>` : `<button class="btn btn-ghost btn-sm" data-act="closeHire">${esc(t('close'))}</button>`}</div>
                <div class="card-body table-scroll">${list.length ? `<table class="table emp-table"><thead><tr><th>${esc(t('col_name'))}</th><th>${esc(t('col_rank'))}</th><th class="right">${esc(t('col_salary', S.cfg.payroll))}</th><th class="right">${esc(t('col_week'))}</th><th class="right">${esc(t('col_total'))}</th><th>${esc(t('col_status'))}</th><th></th></tr></thead><tbody>${rows}</tbody></table>`
                    : `<div class="empty">${icon('users')}<div>${esc(t('emp_empty'))}</div></div>`}</div></div>`;
    },

    permEditor(e) {
        const draft = this.st.permDraft;
        const rank = (this.d.ranks || []).find((r) => r.id === e.rank) || { permissions: {} };
        const items = (this.d.permissionList || []).map((perm) => {
            const state = draft[perm] === true ? 'allow' : draft[perm] === false ? 'deny' : 'inherit';
            const inherited = !!(rank.permissions && rank.permissions[perm]);
            return `<div class="perm-item"><span>${esc(t('perm_' + perm))}${state === 'inherit' ? ` <span class="faint">(${esc(inherited ? t('perm_yes') : t('perm_no'))})</span>` : ''}</span>
                <span class="tri">
                    <button class="${state === 'inherit' ? 'on-inherit' : ''}" data-perm="${perm}" data-val="inherit" title="${esc(t('perm_inherit'))}">${icon('minus')}</button>
                    <button class="${state === 'allow' ? 'on-allow' : ''}" data-perm="${perm}" data-val="allow" title="${esc(t('perm_allow'))}">${icon('check')}</button>
                    <button class="${state === 'deny' ? 'on-deny' : ''}" data-perm="${perm}" data-val="deny" title="${esc(t('perm_deny'))}">${icon('x')}</button>
                </span></div>`;
        }).join('');
        return `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <span class="muted" style="font-size:13px">${esc(t('perm_hint', e.rankLabel))}</span>
                <div style="display:flex;gap:8px"><button class="btn btn-ghost btn-sm" data-perms="${esc(e.identifier)}">${esc(t('cancel'))}</button>
                <button class="btn btn-primary btn-sm" data-save-perms="${esc(e.identifier)}">${icon('check')}${esc(t('save'))}</button></div></div>
            <div class="perm-grid">${items}</div>`;
    },

    /* --------------------------------------------- Moje směna */
    tabShift() {
        const v = this.d.viewer;
        const me = (this.d.employees || []).find((e) => e.isMe) || {};
        const rank = (S.cfg.ranks || []).find((r) => r.id === v.rank) || {};
        return `
            <div class="card shift-card">
                <div class="win-mark" style="width:52px;height:52px">${icon(v.onDuty ? 'timer' : 'clock')}</div>
                <div style="flex:1">
                    <div class="eyebrow">${esc(v.onDuty ? t('shift_running') : t('shift_inactive'))}</div>
                    <div class="shift-clock num" id="shift-clock">${fmtClock(v.onDuty ? v.shiftSeconds : 0)}</div>
                    <div class="muted" style="font-size:13px">${esc(t('shift_earned', fmtMoney(v.shiftEarned || 0)))}</div>
                </div>
                <button class="btn ${v.onDuty ? 'btn-danger' : 'btn-primary'} btn-lg" data-act="duty">${icon(v.onDuty ? 'log-out' : 'power')}${esc(v.onDuty ? t('duty_end') : t('duty_start'))}</button>
            </div>
            <div class="grid g-3" style="margin-top:14px">
                <div class="card kpi"><div class="k-label">${icon('briefcase')}${esc(t('shift_rank'))}</div><div class="k-val" style="font-size:20px">${esc(v.rankLabel || '')}</div><div class="k-sub">${esc(t('shift_salary', fmtMoney(rank.salary || 0), S.cfg.payroll))}</div></div>
                <div class="card kpi"><div class="k-label">${icon('history')}${esc(t('col_week'))}</div><div class="k-val num" style="font-size:20px">${esc(fmtDuration(me.weekSeconds))}</div><div class="k-sub">${esc(t('shift_total', fmtDuration(me.secondsWorked)))}</div></div>
                <div class="card kpi"><div class="k-label">${icon('wallet')}${esc(t('shift_paid'))}</div><div class="k-val num" style="font-size:20px">${fmtMoney(me.totalPaid || 0)}</div><div class="k-sub">${esc(t('emp_hired', fmtDate(me.hiredAt, false)))}</div></div>
            </div>
            <div class="notice" style="margin-top:14px">${icon('info')}<span>${esc(t('shift_hint', S.cfg.payroll))}</span></div>
            <div class="card danger-zone" style="margin-top:14px"><div class="card-body" style="display:flex;align-items:center;gap:14px">
                <div style="flex:1"><div style="font-weight:600">${esc(t('quit_title'))}</div><div class="muted" style="font-size:13px">${esc(t('quit_desc'))}</div></div>
                ${this.st.confirmQuit ? `<div class="confirm-inline"><button class="btn btn-ghost btn-sm" data-act="quitCancel">${esc(t('cancel'))}</button><button class="btn btn-danger btn-sm" data-act="quit">${esc(t('confirm'))}</button></div>`
                    : `<button class="btn btn-danger btn-sm" data-act="quitAsk">${icon('log-out')}${esc(t('quit_btn'))}</button>`}
            </div></div>`;
    },

    /* --------------------------------------------- Finance */
    tabFinance() {
        const p = this.perms();
        const s = this.d.station;
        const sum = this.d.financeSummary;
        const fin = this.d.finance;
        const moneyCard = (kind) => `
            <div class="card"><div class="card-head"><h3>${esc(t(kind === 'deposit' ? 'fin_deposit' : 'fin_withdraw'))}</h3>${icon(kind === 'deposit' ? 'arrow-down-to-line' : 'arrow-up-from-line', 'muted')}</div>
                <div class="card-body">
                    <div class="seg" data-seg="${kind}"><button class="active" data-m="bank">${icon('landmark')}${esc(t('payment_bank'))}</button><button data-m="cash">${icon('banknote')}${esc(t('payment_cash'))}</button></div>
                    <div class="money-form"><div class="input-group"><input class="input num" type="number" min="1" step="1" placeholder="0" data-amount="${kind}"><span class="suffix">${esc(S.cfg.currency.symbol)}</span></div>
                    <button class="btn ${kind === 'deposit' ? 'btn-primary' : ''}" data-money="${kind}">${esc(t(kind === 'deposit' ? 'fin_deposit_btn' : 'fin_withdraw_btn'))}</button></div>
                </div></div>`;

        const types = sum ? Object.keys(sum.byType || {}) : [];
        return `
            <div class="grid ${p.deposit || p.withdraw ? 'g-3' : ''}">
                <div class="card kpi highlight"><div class="k-label">${icon('wallet')}${esc(t('kpi_balance'))}</div><div class="big-balance num">${s.balance !== undefined && s.balance !== null ? fmtMoney(s.balance) : '—'}</div><div class="k-sub">${esc(t('fin_balance_sub'))}</div></div>
                ${p.deposit ? moneyCard('deposit') : ''}
                ${p.withdraw ? moneyCard('withdraw') : ''}
            </div>
            ${sum ? `<div class="grid g-3" style="margin-top:14px">
                <div class="card kpi"><div class="k-label">${icon('arrow-down-to-line')}${esc(t('fin_income'))}</div><div class="k-val num amount-pos">${fmtMoney(sum.income)}</div><div class="k-sub">${esc(t('fin_since_purchase'))}</div></div>
                <div class="card kpi"><div class="k-label">${icon('arrow-up-from-line')}${esc(t('fin_expenses'))}</div><div class="k-val num amount-neg">${fmtMoney(sum.expenses)}</div><div class="k-sub">${esc(t('fin_expenses_sub'))}</div></div>
                <div class="card kpi"><div class="k-label">${icon('chart-line')}${esc(t('fin_profit'))}</div><div class="k-val num ${sum.profit >= 0 ? 'amount-pos' : 'amount-neg'}">${fmtMoney(sum.profit)}</div><div class="k-sub">${esc(types.map((x) => `${t('fin_type_' + x)} ${sum.byType[x].count}×`).slice(0, 3).join(' · '))}</div></div>
            </div>` : ''}
            ${fin ? `<div class="card" style="margin-top:14px"><div class="card-head"><h3>${esc(t('fin_history'))}</h3></div><div class="card-body">${this.financeTable(fin)}</div></div>` : ''}`;
    },

    financeTable(fin) {
        if (this.st.loadingTable === 'finance') {
            return `<table class="table"><thead><tr><th>${esc(t('col_date'))}</th><th>${esc(t('col_type'))}</th><th>${esc(t('col_note'))}</th><th>${esc(t('col_actor'))}</th><th class="right">${esc(t('col_amount_money'))}</th><th class="right">${esc(t('col_balance'))}</th></tr></thead><tbody>${skeletonRows(6, 7)}</tbody></table>`;
        }
        if (!fin.rows.length) return `<div class="empty">${icon('scroll-text')}<div>${esc(t('fin_empty'))}</div></div>`;
        return `<table class="table"><thead><tr><th>${esc(t('col_date'))}</th><th>${esc(t('col_type'))}</th><th>${esc(t('col_note'))}</th><th>${esc(t('col_actor'))}</th><th class="right">${esc(t('col_amount_money'))}</th><th class="right">${esc(t('col_balance'))}</th></tr></thead><tbody>
            ${fin.rows.map((r) => `<tr><td class="num">${fmtDate(r.created_at)}</td><td class="strong">${esc(t('fin_type_' + r.type))}</td><td>${esc(r.note || '')}</td><td>${esc(r.actor_name || '—')}</td>
                <td class="right num ${r.amount > 0 ? 'amount-pos' : r.amount < 0 ? 'amount-neg' : ''}">${r.amount > 0 ? '+' : ''}${fmtMoney(r.amount)}</td><td class="right num">${fmtMoney(r.balance)}</td></tr>`).join('')}
            </tbody></table>${this.pager('finance', fin)}`;
    },

    pager(kind, data) {
        if (!data || data.pages <= 1) return '';
        return `<div class="pager"><span>${esc(t('page', data.page, data.pages))}</span>
            <button class="icon-btn" data-page="${kind}" data-dir="-1" ${data.page <= 1 ? 'disabled' : ''}>${icon('chevron-left')}</button>
            <button class="icon-btn" data-page="${kind}" data-dir="1" ${data.page >= data.pages ? 'disabled' : ''}>${icon('chevron-right')}</button></div>`;
    },

    /* --------------------------------------------- Prodeje */
    tabSales() {
        const sales = this.d.sales;
        if (!sales) return '';
        if (this.st.loadingTable === 'sales') {
            return `<div class="card"><div class="card-body"><table class="table"><thead><tr><th>${esc(t('col_date'))}</th><th>${esc(t('col_receipt'))}</th><th>${esc(t('col_customer'))}</th><th>${esc(t('col_plate'))}</th><th>${esc(t('col_fuel'))}</th><th class="right">${esc(t('col_amount'))}</th><th class="right">${esc(t('col_unit_price'))}</th><th>${esc(t('col_payment'))}</th><th class="right">${esc(t('col_total_price'))}</th></tr></thead><tbody>${skeletonRows(9, 8)}</tbody></table></div></div>`;
        }
        return `<div class="card"><div class="card-body">${sales.rows.length ? this.salesTable(sales.rows, false) + this.pager('sales', sales) : `<div class="empty">${icon('receipt')}<div>${esc(t('sales_empty'))}</div></div>`}</div></div>`;
    },

    salesTable(rows, compact) {
        if (!rows.length) return `<div class="empty">${icon('receipt')}<div>${esc(t('sales_empty'))}</div></div>`;
        return `<table class="table"><thead><tr><th>${esc(t('col_date'))}</th>${compact ? '' : `<th>${esc(t('col_receipt'))}</th>`}<th>${esc(t('col_customer'))}</th><th>${esc(t('col_plate'))}</th><th>${esc(t('col_fuel'))}</th><th class="right">${esc(t('col_amount'))}</th>${compact ? '' : `<th class="right">${esc(t('col_unit_price'))}</th><th>${esc(t('col_payment'))}</th>`}<th class="right">${esc(t('col_total_price'))}</th></tr></thead><tbody>
            ${rows.map((r) => {
                const f = S.cfg.fuelTypes[r.fuel_type] || { short: '?', color: '#888', unit: 'l' };
                return `<tr><td class="num">${fmtDate(r.created_at)}</td>${compact ? '' : `<td class="mono" style="font-size:12px">${esc(r.receipt)}</td>`}<td class="strong">${esc(r.player_name || '—')}</td><td>${r.plate ? `<span class="plate" style="height:20px;font-size:11px">${esc(r.plate)}</span>` : '—'}</td>
                    <td>${gradeChip(f)}</td><td class="right num">${fmtNum(r.liters, 2)} ${unitLabel(f.unit)}</td>
                    ${compact ? '' : `<td class="right num">${fmtMoney(r.price_per_liter, 2)}</td><td>${esc(t('payment_' + r.payment_method))}</td>`}
                    <td class="right num strong">${fmtMoney(r.total)}</td></tr>`;
            }).join('')}</tbody></table>`;
    },

    /* --------------------------------------------- Nastavení */
    tabSettings() {
        const s = this.d.station;
        const len = s.renameLength || { min: 3, max: 32 };
        return `
            <div class="grid g-2">
                <div class="card"><div class="card-head"><h3>${esc(t('set_rename'))}</h3></div><div class="card-body">
                    ${s.canRename ? `<div class="field"><label>${esc(t('set_rename_label', len.min, len.max))}</label>
                        <div class="money-form" style="margin-top:0"><input class="input" id="rename-input" maxlength="${len.max}" value="${esc(s.label !== s.defaultLabel ? s.label : '')}" placeholder="${esc(s.defaultLabel)}">
                        <button class="btn btn-primary" data-act="rename">${esc(t('save'))}</button></div></div>
                        <p class="muted" style="font-size:12px;margin-top:8px">${esc(t('set_rename_hint'))}</p>` : `<div class="notice">${icon('lock')}<span>${esc(t('set_rename_disabled'))}</span></div>`}
                </div></div>
                <div class="card"><div class="card-head"><h3>${esc(t('set_info'))}</h3></div><div class="card-body"><div class="kv">
                    <span>${esc(t('set_type'))}</span><span>${esc(s.typeLabel)}</span>
                    <span>${esc(t('set_purchase_price'))}</span><span class="num">${fmtMoney(s.purchasePrice || 0)}</span>
                    <span>${esc(t('set_purchased_at'))}</span><span class="num">${fmtDate(s.purchasedAt)}</span>
                    <span>${esc(t('set_status'))}</span><span>${esc(s.open ? t('status_open') : t('status_closed'))}</span>
                </div>
                <button class="btn btn-block" style="margin-top:14px" data-act="toggleOpen">${icon('power')}${esc(s.open ? t('set_close') : t('set_open'))}</button></div></div>
            </div>
            <div class="card danger-zone" style="margin-top:14px"><div class="card-body" style="display:flex;align-items:center;gap:16px">
                <div style="flex:1"><div style="font-weight:600">${esc(t('sell_title'))}</div>
                    <div class="muted" style="font-size:13px;margin-top:3px">${esc(t('sell_desc', fmtMoney(s.sellValue || 0), s.balance !== undefined && s.balance !== null ? fmtMoney(s.balance) : '—'))}</div></div>
                ${this.st.confirmSell ? `<div class="confirm-inline"><button class="btn btn-ghost btn-sm" data-act="sellCancel">${esc(t('cancel'))}</button><button class="btn btn-danger btn-sm" data-act="sell">${icon('trash-2')}${esc(t('sell_confirm'))}</button></div>`
                    : `<button class="btn btn-danger" data-act="sellAsk">${esc(t('sell_btn', fmtMoney((s.sellValue || 0) + Math.max(0, s.balance || 0))))}</button>`}
            </div></div>`;
    },

    /* --------------------------------------------- události */
    bind(win) {
        win.addEventListener('click', (e) => this.onClick(e));
        win.addEventListener('input', (e) => this.onInput(e));
        win.addEventListener('change', (e) => this.onChange(e));
        win.addEventListener('mousemove', (e) => this.onChartHover(e));
        win.addEventListener('mouseleave', () => this.hideTip());
    },

    hideTip() {
        const tip = $('#chart-tip');
        if (tip) tip.hidden = true;
        const hl = $('#chart-hl');
        if (hl) hl.innerHTML = '';
    },

    onChartHover(e) {
        const hit = e.target.closest && e.target.closest('.chart-hit');
        if (!hit) return this.hideTip();
        const d = this.chartData && this.chartData[Number(hit.dataset.i)];
        const wrap = $('#chart');
        const tip = $('#chart-tip');
        if (!d || !wrap || !tip) return;
        const rect = wrap.getBoundingClientRect();
        const hr = hit.getBoundingClientRect();
        $('#chart-hl').innerHTML = `<rect x="${hit.getAttribute('x')}" y="${hit.getAttribute('y')}" width="${hit.getAttribute('width')}" height="${hit.getAttribute('height')}" fill="rgba(255,255,255,.035)" rx="4"/>`;
        tip.innerHTML = `<div class="tt-date">${fmtDate(d.date, false)}</div>
            <div class="tt-row"><span><i style="background:var(--chart-1)"></i>${esc(t('chart_revenue'))}</span><b class="num">${fmtMoney(d.revenue)}</b></div>
            <div class="tt-row"><span><i style="background:var(--chart-2)"></i>${esc(t('chart_costs'))}</span><b class="num">${fmtMoney(d.costs)}</b></div>`;
        tip.style.left = `${hr.left - rect.left + hr.width / 2}px`;
        tip.style.top = `${Math.max(56, e.clientY - rect.top - 12)}px`;
        tip.hidden = false;
    },

    onInput(e) {
        if (e.target.id === 'order-range' || e.target.id === 'order-liters') {
            const val = Math.round(Number(e.target.value) || 0);
            this.st.order.liters = val;
            if (e.target.id === 'order-range') {
                this.rerenderOrder(true);
            }
        }
    },

    onChange(e) {
        const rankSel = e.target.closest('[data-rank-select]');
        if (rankSel) {
            this.action('setRank', { identifier: rankSel.dataset.rankSelect, rank: rankSel.value });
            return;
        }
        const hireRank = e.target.closest('[data-hire-rank]');
        if (hireRank) this.st.hireRank = hireRank.value;
        if (e.target.id === 'order-liters') this.rerenderOrder(false);
    },

    rerenderOrder(fromRange) {
        const form = $('#order-form');
        if (!form) return;
        if (fromRange) {
            const { o, fuel } = this.orderState();
            const q = this.orderQuote(fuel, o.liters, o.method);
            const input = $('#order-liters', form);
            if (input) input.value = o.liters;
            const range = $('#order-range', form);
            const min = Number(range.min), max = Number(range.max);
            range.style.setProperty('--fill', `${max > min ? (o.liters - min) / (max - min) * 100 : 0}%`);
            const totals = $$('.t-val', form);
            if (totals[0]) totals[0].textContent = fmtMoney(q.cost);
            return;
        }
        form.innerHTML = this.orderForm();
    },

    async onClick(e) {
        const el = e.target.closest('button, [data-tab]');
        if (!el || el.disabled) return;
        const ds = el.dataset;

        if (ds.tab) {
            this.st.enter = this.st.tab !== ds.tab;
            this.st.tab = ds.tab;
            this.st.confirmSell = false;
            this.st.confirmQuit = false;
            this.st.confirmFire = null;
            this.render();
            return;
        }

        if (ds.act) return this.onAct(ds.act, el);
        const btnOpts = { button: el.classList.contains('btn') || el.classList.contains('icon-btn') ? el : null };

        if (ds.savePrice) {
            const input = $(`[data-price-input="${ds.savePrice}"]`);
            this.action('setPrice', { fuelType: ds.savePrice, price: Number(String(input.value).replace(',', '.')) }, btnOpts);
            return;
        }
        if (ds.orderFuel) {
            this.st.order.fuel = ds.orderFuel;
            this.st.order.liters = null;
            this.rerenderOrder(false);
            return;
        }
        if (ds.orderMethod) {
            this.st.order.method = ds.orderMethod;
            this.rerenderOrder(false);
            return;
        }
        if (ds.cancelOrder) {
            this.action('cancelOrder', { orderId: Number(ds.cancelOrder) }, btnOpts);
            return;
        }
        if (ds.hire) {
            const sel = $(`[data-hire-rank="${ds.hire}"]`);
            const res = await this.action('hire', { target: Number(ds.hire), rank: sel ? sel.value : null }, { noRender: true, button: el });
            if (res && res.ok && this.st.players) {
                this.st.players = this.st.players.filter((p) => String(p.id) !== ds.hire);
                this.render();
            }
            return;
        }
        if (ds.perms) {
            if (this.st.expanded === ds.perms) {
                this.st.expanded = null;
            } else {
                const emp = (this.d.employees || []).find((x) => x.identifier === ds.perms);
                this.st.expanded = ds.perms;
                this.st.permDraft = Object.assign({}, (emp && emp.overrides) || {});
            }
            this.render();
            return;
        }
        if (ds.perm) {
            if (ds.val === 'inherit') delete this.st.permDraft[ds.perm];
            else this.st.permDraft[ds.perm] = ds.val === 'allow';
            this.render();
            return;
        }
        if (ds.savePerms) {
            const res = await this.action('setPermissions', { identifier: ds.savePerms, permissions: this.st.permDraft }, btnOpts);
            if (res && res.ok) {
                this.st.expanded = null;
                this.render();
            }
            return;
        }
        if (ds.fireAsk) {
            this.st.confirmFire = ds.fireAsk;
            this.render();
            return;
        }
        if (ds.fire) {
            this.st.confirmFire = null;
            this.action('fire', { identifier: ds.fire }, btnOpts);
            return;
        }
        if (ds.m) {
            const seg = el.closest('[data-seg]');
            $$('button', seg).forEach((b) => b.classList.toggle('active', b === el));
            return;
        }
        if (ds.money) {
            const kind = ds.money;
            const input = $(`[data-amount="${kind}"]`);
            const seg = $(`[data-seg="${kind}"] .active`);
            const amount = Math.floor(Number(input.value) || 0);
            if (amount <= 0) return;
            this.action(kind, { amount, method: seg ? seg.dataset.m : 'bank' }, btnOpts);
            return;
        }
        if (ds.page) {
            const kind = ds.page;
            const current = kind === 'sales' ? this.d.sales : this.d.finance;
            const page = current.page + Number(ds.dir);
            this.st.loadingTable = kind;
            this.render();
            const res = await this.action(kind === 'sales' ? 'salesPage' : 'financePage', { page }, { noRender: true });
            if (!this.d) return;
            this.st.loadingTable = null;
            if (res && res.ok) {
                if (kind === 'sales') this.d.sales = res.data;
                else this.d.finance = res.data;
            }
            this.render();
        }
    },

    async onAct(act, el) {
        const opts = { button: el && (el.classList.contains('btn') || el.classList.contains('icon-btn')) ? el : null };
        switch (act) {
            case 'refresh': return this.action('refresh', {}, opts);
            case 'toggleOpen': return this.action('toggleOpen', {}, opts);
            case 'duty': return this.action('duty', {}, opts);
            case 'orderFuel': {
                const { o } = this.orderState();
                const res = await this.action('orderFuel', { fuelType: o.fuel, liters: o.liters, method: o.method }, opts);
                if (res && res.ok) {
                    this.st.order.liters = null;
                    this.render();
                }
                return res;
            }
            case 'openHire':
                this.st.hireOpen = true;
                this.st.players = null;
                this.render();
                return this.onAct('nearbyPlayers');
            case 'closeHire':
                this.st.hireOpen = false;
                return this.render();
            case 'nearbyPlayers': {
                this.st.players = null;
                this.render();
                const res = await this.action('nearbyPlayers', {}, { noRender: true });
                this.st.players = res && res.ok ? res.data || [] : [];
                return this.render();
            }
            case 'rename': {
                const input = $('#rename-input');
                return this.action('rename', { label: input ? input.value : '' }, opts);
            }
            case 'sellAsk': this.st.confirmSell = true; return this.render();
            case 'sellCancel': this.st.confirmSell = false; return this.render();
            case 'sell': return this.action('sell', { confirm: this.d.station.id }, opts);
            case 'quitAsk': this.st.confirmQuit = true; return this.render();
            case 'quitCancel': this.st.confirmQuit = false; return this.render();
            case 'quit': return this.action('quit', {}, opts);
            default: return null;
        }
    },
};

/* ==========================================================================
   OKNO: Nákup benzinky
   ========================================================================== */
Views.purchase = {
    d: null,
    method: null,
    busy: false,

    open(data) {
        this.d = data;
        const methods = Object.keys(data.accounts || {});
        this.method = methods.includes('bank') ? 'bank' : methods[0];
        this.busy = false;
        const win = Modals.open('purchase', 'purchase', '');
        win.addEventListener('click', (e) => this.onClick(e));
        this.render();
    },

    onClose() { this.d = null; },

    render(error) {
        const win = Modals.get('purchase');
        if (!win || !this.d) return;
        const d = this.d;
        const balance = d.accounts[this.method] || 0;
        const limit = d.owned >= d.maxOwned;
        win.innerHTML = `
            <div class="win-head"><div class="win-mark">${icon('store')}</div>
                <div><div class="title">${esc(d.label)}</div><div class="sub">${esc(d.typeLabel)}</div></div><div class="spacer"></div>${closeButton('purchase')}</div>
            <div class="win-body">
                <div class="price-hero"><div><div class="eyebrow">${esc(t('buy_price'))}</div><div class="v num" style="margin-top:8px">${fmtMoney(d.price)}</div></div>
                    <div style="text-align:right"><div class="eyebrow">${esc(t('buy_owned'))}</div><div class="num" style="font-size:18px;font-weight:600;margin-top:8px">${d.owned} / ${d.maxOwned}</div></div></div>
                <div class="section-label" style="margin-top:20px"><span class="eyebrow">${esc(t('buy_fuels'))}</span></div>
                <div class="fuel-caps">${d.fuels.map((f) => `<div class="fuel-cap">${gradeChip(f)}<span class="fc-name">${esc(f.label)}</span><span class="fc-val num">${esc(t('buy_capacity', fmtNum(f.capacity), unitLabel(f.unit)))}</span><span class="muted num">${fmtMoney(f.price, 2)}</span></div>`).join('')}</div>
                <div class="notice" style="margin-top:14px">${icon('info')}<span>${esc(t('buy_info', Math.round(d.startingStock * 100), Math.round(d.sellBack * 100)))}</span></div>
                <div class="section-label" style="margin-top:20px"><span class="eyebrow">${esc(t('refuel_payment'))}</span></div>
                <div class="pay-options">${Object.keys(d.accounts).map((m) => `<button class="pay-option ${m === this.method ? 'active' : ''} ${(d.accounts[m] || 0) < d.price ? 'short' : ''}" data-pay="${m}">${icon(m === 'cash' ? 'banknote' : 'landmark')}<div><div class="p-label">${esc(t('payment_' + m))}</div><div class="p-bal num">${fmtMoney(d.accounts[m] || 0)}</div></div></button>`).join('')}</div>
                <div class="error-line" style="margin-top:12px">${error ? `${icon('triangle-alert')}<span>${esc(error)}</span>` : (limit ? `${icon('triangle-alert')}<span>${esc(t('error_max_owned', d.maxOwned))}</span>` : (balance < d.price ? `${icon('triangle-alert')}<span>${esc(t('error_insufficient_funds', fmtMoney(d.price)))}</span>` : ''))}</div>
            </div>
            <div class="win-foot"><span class="muted" style="flex:1;font-size:13px">${esc(t('buy_terms'))}</span>
                <button class="btn btn-ghost" data-close-view="purchase">${esc(t('cancel'))}</button>
                <button class="btn btn-primary ${this.busy ? 'is-loading' : ''}" data-buy ${!this.busy && (limit || balance < d.price) ? 'disabled' : ''}>${icon('check')}${esc(this.busy ? t('buy_processing') : t('buy_confirm'))}</button></div>`;
    },

    async onClick(e) {
        const pay = e.target.closest('[data-pay]');
        if (pay) {
            this.method = pay.dataset.pay;
            this.render();
            return;
        }
        const buy = e.target.closest('[data-buy]');
        if (buy && !buy.disabled && !this.busy) {
            this.busy = true;
            this.render();
            const res = await post('purchase:confirm', { method: this.method });
            this.busy = false;
            if (!res || !res.ok) this.render((res && res.message) || t('error_internal'));
        }
    },
};

/* ==========================================================================
   OKNO: Rozvoz paliva – nabídka zakázek
   ========================================================================== */
Views.board = {
    d: null,
    busy: false,

    open(data) {
        this.d = data;
        this.busy = false;
        const win = Modals.open('board', 'board', '');
        win.addEventListener('click', (e) => this.onClick(e));
        this.render();
    },

    onClose() { this.d = null; },

    render(error) {
        const win = Modals.get('board');
        if (!win || !this.d) return;
        const d = this.d;
        const job = d.job;
        let content = '';
        if (job) {
            content += `<div class="active-job">${icon('truck')}<div style="flex:1"><div style="font-weight:600">${esc(t('board_active', job.orderId))}</div>
                <div class="muted" style="font-size:13px">${esc(job.station ? job.station.label : '')} · ${fmtNum(job.liters)} ${job.fuel ? unitLabel(job.fuel.unit) : 'l'} · ${fmtMoney(job.reward)}</div></div>
                ${job.status !== 'delivered' ? `<button class="btn btn-danger btn-sm" data-cancel-job>${esc(t('board_cancel_job'))}</button>` : ''}</div>`;
        }
        if (!d.canWork) content += `<div class="notice warn" style="margin-bottom:14px">${icon('lock')}<span>${esc(t('error_wrong_job'))}</span></div>`;
        if (!d.orders.length) {
            content += `<div class="empty">${icon('package')}<div>${esc(t('board_empty'))}</div></div>`;
        } else {
            content += d.orders.map((o) => `
                <div class="order-card">
                    ${gradeChip(o.fuel, 'lg')}
                    <div><div class="o-station">${esc(o.station)}</div>
                        <div class="o-meta"><span>${icon('droplet')}${fmtNum(o.liters)} ${unitLabel(o.fuel.unit)} ${esc(o.fuel.label)}</span><span>${icon('route')}${fmtNum(o.distance / 1000, 1)} km</span><span>#${o.id}</span></div></div>
                    <div class="o-reward"><div class="eyebrow">${esc(t('board_reward'))}</div><div class="v num">${fmtMoney(o.reward)}</div></div>
                    <button class="btn btn-primary ${this.pending === o.id ? 'is-loading' : ''}" data-accept="${o.id}" ${job || !d.canWork || (this.busy && this.pending !== o.id) ? 'disabled' : ''}>${icon('truck')}${esc(this.pending === o.id ? t('board_accepting') : t('board_accept'))}</button>
                </div>`).join('');
        }
        win.innerHTML = `
            <div class="win-head"><div class="win-mark">${icon('truck')}</div>
                <div><div class="title">${esc(d.depot)}</div><div class="sub">${esc(t('board_subtitle', d.orders.length))}</div></div><div class="spacer"></div>${closeButton('board')}</div>
            <div class="win-body">${content}<div class="error-line" style="margin-top:12px">${error ? `${icon('triangle-alert')}<span>${esc(error)}</span>` : ''}</div></div>`;
    },

    async onClick(e) {
        const accept = e.target.closest('[data-accept]');
        if (accept && !accept.disabled && !this.busy) {
            this.busy = true;
            this.pending = Number(accept.dataset.accept);
            this.render();
            const res = await post('board:accept', { orderId: this.pending });
            this.busy = false;
            this.pending = null;
            if (!res || !res.ok) this.render((res && res.message) || t('error_internal'));
            return;
        }
        if (e.target.closest('[data-cancel-job]')) post('board:cancel', {});
    },
};

/* ==========================================================================
   OKNO: Historie tankování hráče
   ========================================================================== */
Views.history = {
    rows: [],
    open(data) {
        this.rows = data.rows || [];
        const rows = this.rows;
        const body = rows.length ? `<table class="table clickable"><thead><tr><th>${esc(t('col_date'))}</th><th>${esc(t('col_station'))}</th><th>${esc(t('col_plate'))}</th><th>${esc(t('col_fuel'))}</th><th class="right">${esc(t('col_amount'))}</th><th class="right">${esc(t('col_unit_price'))}</th><th>${esc(t('col_payment'))}</th><th class="right">${esc(t('col_total_price'))}</th></tr></thead><tbody>
            ${rows.map((r, i) => {
                const f = S.cfg.fuelTypes[r.fuel_type] || { short: '?', color: '#888', unit: 'l' };
                return `<tr data-row="${i}"><td class="num">${fmtDate(r.created_at)}</td><td class="strong">${esc(r.station_label)}</td><td>${r.plate ? `<span class="plate" style="height:20px;font-size:11px">${esc(r.plate)}</span>` : '—'}</td><td>${gradeChip(f)}</td>
                    <td class="right num">${fmtNum(r.liters, 2)} ${unitLabel(f.unit)}</td><td class="right num">${fmtMoney(r.price_per_liter, 2)}</td><td>${esc(t('payment_' + r.payment_method))}</td><td class="right num strong">${fmtMoney(r.total)}</td></tr>`;
            }).join('')}</tbody></table>` : `<div class="empty">${icon('history')}<div>${esc(t('history_empty'))}</div></div>`;
        const win = Modals.open('history', 'history', `
            <div class="win-head"><div class="win-mark">${icon('history')}</div><div><div class="title">${esc(t('history_title'))}</div><div class="sub">${esc(t('history_sub', rows.length))}</div></div><div class="spacer"></div>${closeButton('history')}</div>
            <div class="win-body">${body}</div>`);
        win.addEventListener('click', (e) => {
            const row = e.target.closest('[data-row]');
            if (!row) return;
            const r = this.rows[Number(row.dataset.row)];
            const f = S.cfg.fuelTypes[r.fuel_type] || { label: r.fuel_type, short: '?', color: '#888', unit: 'l' };
            const d = new Date(r.created_at * 1000);
            Receipt.show({
                number: r.receipt, station: r.station_label, date: fmtDate(r.created_at, false), time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
                fuel: f.label, fuelShort: f.short, color: f.color, unit: f.unit, liters: Number(r.liters), price: Number(r.price_per_liter),
                total: Number(r.total), method: r.payment_method, plate: r.plate,
            }, true);
        });
    },
};

/* ==========================================================================
   OKNO: Nabídka práce
   ========================================================================== */
Views.offer = {
    open(d) {
        Modals.open('offer', 'offer', `
            <div class="win-body">
                <div class="o-hero">${icon('briefcase')}<h2>${esc(t('offer_title'))}</h2>
                    <p>${esc(t('offer_text', d.from, d.station))}</p></div>
                <div class="kv" style="margin-top:18px">
                    <span>${esc(t('offer_rank'))}</span><span>${esc(d.rank)}</span>
                    <span>${esc(t('offer_salary'))}</span><span class="num">${esc(t('shift_salary', fmtMoney(d.salary), d.interval))}</span>
                </div>
                <div class="o-timer"><span style="animation-duration:${(d.timeout || 45) * 1000}ms"></span></div>
            </div>
            <div class="win-foot"><button class="btn btn-ghost" style="flex:1" data-offer="0">${esc(t('offer_decline'))}</button>
                <button class="btn btn-primary" style="flex:1" data-offer="1">${icon('check')}${esc(t('offer_accept'))}</button></div>`)
            .addEventListener('click', (e) => {
                const b = e.target.closest('[data-offer]');
                if (b) this.respond(b.dataset.offer === '1');
            });
    },
    respond(accepted) {
        Modals.close('offer', false);
        post('offer:respond', { accepted });
    },
};

/* ==========================================================================
   OKNO: Admin panel
   ========================================================================== */
Views.admin = {
    d: null,
    st: null,

    open(data) {
        this.d = data;
        this.st = {
            tab: 'overview', enter: true, busy: false, expanded: null, search: '', filter: 'all',
            confirmReset: null, fuelAmount: 100, radius: 25, plate: null,
        };
        const win = Modals.open('admin', 'mgmt admin', '<div class="mgmt-side"></div><div class="mgmt-main"></div>');
        win.addEventListener('click', (e) => this.onClick(e));
        win.addEventListener('input', (e) => this.onInput(e));
        win.addEventListener('mousemove', (e) => this.onHover(e));
        win.addEventListener('mouseleave', () => this.hideTip());
        this.render();
    },

    onClose() { this.d = null; },

    tabs() {
        const live = this.d.live || { sessions: [], jobs: [], duty: [] };
        const liveCount = live.sessions.length + live.jobs.length + live.duty.length;
        return [
            { id: 'overview', icon: 'layout-dashboard', label: t('admin_tab_overview') },
            { id: 'stations', icon: 'store', label: t('admin_tab_stations'), badge: (this.d.stations || []).filter((x) => x.owned).length },
            { id: 'orders', icon: 'package', label: t('admin_tab_orders'), badge: (this.d.orders || []).length },
            { id: 'live', icon: 'timer', label: t('admin_tab_live'), badge: liveCount },
            { id: 'fuel', icon: 'fuel', label: t('admin_tab_fuel') },
            { id: 'logs', icon: 'scroll-text', label: t('admin_tab_logs') },
        ];
    },

    async action(name, payload = {}, opts = {}) {
        if (this.st.busy) return null;
        this.st.busy = true;
        this.setBusy(true, opts.button);
        const res = await post('admin:action', { action: name, payload });
        if (!this.d) return res;
        this.st.busy = false;
        this.setBusy(false);
        if (res && res.update) Object.assign(this.d, res.update);
        if (!opts.noRender) this.render();
        return res;
    },

    setBusy(on, button) {
        const win = Modals.get('admin');
        if (!win) return;
        const main = $('.mgmt-main', win);
        const bar = $('.win-progress', main);
        if (on && !bar) main.insertAdjacentHTML('afterbegin', '<div class="win-progress"></div>');
        if (!on && bar) bar.remove();
        if (button) button.classList.add('is-loading');
        if (!on) $$('.is-loading', win).forEach((el) => el.classList.remove('is-loading'));
    },

    render() {
        const win = Modals.get('admin');
        if (!win || !this.d) return;
        const tabs = this.tabs();
        const current = tabs.find((x) => x.id === this.st.tab) || tabs[0];
        const subs = { overview: t('admin_sub_overview'), stations: t('admin_sub_stations', (this.d.stations || []).length), orders: t('admin_sub_orders'), live: t('admin_sub_live'), fuel: t('admin_sub_fuel'), logs: t('admin_sub_logs', S.cfg.adminLogLimit || 100) };
        $('.mgmt-side', win).innerHTML = `
            <div class="mgmt-brand">
                <div class="win-mark">${icon('shield')}</div>
                <div class="s-name">${esc(t('admin_title'))}</div>
                <div class="s-type">xenon_fuel</div>
                <div class="status-toggle"><span class="pill accent">${esc(t('admin_badge'))}</span></div>
            </div>
            <div class="nav">${tabs.map((x) => `<button class="${x.id === current.id ? 'active' : ''}" data-tab="${x.id}">${icon(x.icon)}<span>${esc(x.label)}</span>${x.badge ? `<span class="badge">${x.badge}</span>` : ''}</button>`).join('')}</div>
            <div class="viewer"><div class="avatar">${esc(initials(this.d.admin && this.d.admin.name))}</div>
                <div><div class="v-name">${esc(this.d.admin ? this.d.admin.name : '')}</div><div class="v-role">${esc(t('admin_role'))}</div></div></div>`;
        $('.mgmt-main', win).innerHTML = `
            <div class="win-head">
                <div><div class="title">${esc(current.label)}</div><div class="sub">${esc(subs[current.id] || '')}</div></div>
                <div class="spacer"></div>
                <button class="icon-btn" data-act="refresh" title="${esc(t('refresh'))}">${icon('refresh-cw')}</button>
                ${closeButton('admin')}
            </div>
            <div class="mgmt-content${this.st.enter ? ' tab-enter' : ''}">${this.renderTab(current.id)}</div>`;
        this.st.enter = false;
    },

    renderTab(tab) {
        switch (tab) {
            case 'overview': return this.tabOverview();
            case 'stations': return this.tabStations();
            case 'orders': return this.tabOrders();
            case 'live': return this.tabLive();
            case 'fuel': return this.tabFuel();
            case 'logs': return this.tabLogs();
            default: return '';
        }
    },

    /* --------------------------------------------- Přehled */
    tabOverview() {
        const o = this.d.overview || {};
        const top = o.top || [];
        const maxTop = Math.max(1, ...top.map((x) => x.revenue));
        return `
            <div class="grid g-4">
                <div class="card kpi highlight"><div class="k-label">${icon('store')}${esc(t('admin_kpi_stations'))}</div><div class="k-val num">${o.owned || 0} <span class="faint" style="font-size:16px">/ ${o.stations || 0}</span></div><div class="k-sub">${esc(t('admin_kpi_stations_sub', o.closed || 0))}</div></div>
                <div class="card kpi"><div class="k-label">${icon('wallet')}${esc(t('admin_kpi_balances'))}</div><div class="k-val num">${fmtMoney(o.balances || 0)}</div><div class="k-sub">${esc(t('admin_kpi_balances_sub'))}</div></div>
                <div class="card kpi"><div class="k-label">${icon('chart-line')}${esc(t('kpi_revenue'))}</div><div class="k-val num">${fmtMoney(o.revenue || 0)}</div><div class="k-sub">${esc(t('admin_kpi_revenue_sub', fmtNum(o.customers || 0), fmtNum(o.liters || 0)))}</div></div>
                <div class="card kpi"><div class="k-label">${icon('users')}${esc(t('admin_kpi_online'))}</div><div class="k-val num">${o.players || 0}</div><div class="k-sub">${esc(t('admin_kpi_online_sub', o.sessions || 0, o.jobs || 0, o.onDuty || 0))}</div></div>
            </div>
            <div class="grid g-main" style="margin-top:14px">
                <div class="card chart-card"><div class="card-head"><h3>${esc(t('admin_chart_title', (o.chart || []).length))}</h3></div>
                    <div class="card-body">${this.chart(o.chart || [])}</div></div>
                <div class="card"><div class="card-head"><h3>${esc(t('admin_top_title'))}</h3></div>
                    <div class="card-body"><div class="top-list">${top.length ? top.map((x, i) => `
                        <div class="top-item"><span class="top-rank num">${i + 1}</span>
                            <div style="flex:1;min-width:0"><div class="top-row"><span class="top-name">${esc(x.label)}</span><span class="num strong">${fmtMoney(x.revenue)}</span></div>
                            <div class="stock-bar" style="--c:var(--accent)"><div class="fill" style="width:${x.revenue / maxTop * 100}%"></div></div>
                            <div class="s-meta"><span>${esc(x.owned ? t('admin_owned') : t('public'))}</span></div></div></div>`).join('') : `<div class="empty">${icon('chart-line')}<div>${esc(t('chart_empty'))}</div></div>`}</div></div></div>
            </div>
            <div class="grid g-3" style="margin-top:14px">
                <button class="card quick" data-tab="live">${icon('timer')}<div><b class="num">${o.sessions || 0}</b><span>${esc(t('admin_quick_sessions'))}</span></div>${icon('chevron-right')}</button>
                <button class="card quick" data-tab="orders">${icon('package')}<div><b class="num">${o.orders || 0}</b><span>${esc(t('admin_quick_orders'))}</span></div>${icon('chevron-right')}</button>
                <button class="card quick" data-tab="live">${icon('truck')}<div><b class="num">${o.jobs || 0}</b><span>${esc(t('admin_quick_jobs'))}</span></div>${icon('chevron-right')}</button>
            </div>`;
    },

    chart(data) {
        if (!data.length) return `<div class="empty">${icon('chart-line')}<div>${esc(t('chart_empty'))}</div></div>`;
        const W = 470, H = 270, padL = 46, padR = 6, padT = 12, padB = 26;
        const innerW = W - padL - padR, innerH = H - padT - padB;
        const maxVal = Math.max(1, ...data.map((d) => d.revenue));
        const raw = maxVal / 4;
        const mag = Math.pow(10, Math.floor(Math.log10(raw)));
        const n = raw / mag;
        const step = (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag;
        const top = step * 4;
        const y = (v) => padT + innerH - (v / top) * innerH;
        const band = innerW / data.length;
        const barW = Math.min(24, band * 0.42);
        const days = (t('weekdays_short') || 'Ne,Po,Út,St,Čt,Pá,So').split(',');
        let grid = '', bars = '', labels = '', hits = '';
        for (let i = 0; i <= 4; i++) {
            const yy = y(step * i);
            grid += `<line x1="${padL}" x2="${W - padR}" y1="${yy}" y2="${yy}" stroke="rgba(255,255,255,${i === 0 ? 0.14 : 0.06})" stroke-width="1"/>`;
            grid += `<text x="${padL - 8}" y="${yy + 4}" text-anchor="end" fill="#82878e" font-size="11" font-family="Barlow">${esc(fmtCompactMoney(step * i))}</text>`;
        }
        data.forEach((d, i) => {
            const cx = padL + band * i + band / 2;
            const x = cx - barW / 2;
            if (d.revenue > 0) {
                const yTop = y(d.revenue);
                const h = padT + innerH - yTop;
                const r = Math.min(4, h, barW / 2);
                bars += `<path class="chart-bar" style="animation-delay:${(0.12 + i * 0.05).toFixed(2)}s" d="M${x},${padT + innerH} L${x},${yTop + r} Q${x},${yTop} ${x + r},${yTop} L${x + barW - r},${yTop} Q${x + barW},${yTop} ${x + barW},${yTop + r} L${x + barW},${padT + innerH} Z" fill="var(--chart-1)"/>`;
            }
            const date = new Date(d.date * 1000);
            labels += `<text x="${cx}" y="${H - 8}" text-anchor="middle" fill="#82878e" font-size="11" font-family="Barlow">${esc(days[date.getDay()] || '')} ${date.getDate()}.</text>`;
            hits += `<rect class="chart-hit" data-i="${i}" x="${padL + band * i}" y="${padT}" width="${band}" height="${innerH}" fill="transparent"/>`;
        });
        this.chartData = data;
        return `<div class="chart-wrap" id="adm-chart"><svg viewBox="0 0 ${W} ${H}" style="height:auto">${grid}<g id="adm-chart-hl"></g>${bars}${labels}${hits}</svg><div class="chart-tip" id="adm-chart-tip" hidden></div></div>`;
    },

    hideTip() {
        const tip = $('#adm-chart-tip');
        if (tip) tip.hidden = true;
        const hl = $('#adm-chart-hl');
        if (hl) hl.innerHTML = '';
    },

    onHover(e) {
        const hit = e.target.closest && e.target.closest('#adm-chart .chart-hit');
        if (!hit) return this.hideTip();
        const d = this.chartData && this.chartData[Number(hit.dataset.i)];
        const wrap = $('#adm-chart');
        const tip = $('#adm-chart-tip');
        if (!d || !wrap || !tip) return;
        const rect = wrap.getBoundingClientRect();
        const hr = hit.getBoundingClientRect();
        $('#adm-chart-hl').innerHTML = `<rect x="${hit.getAttribute('x')}" y="${hit.getAttribute('y')}" width="${hit.getAttribute('width')}" height="${hit.getAttribute('height')}" fill="rgba(255,255,255,.035)" rx="4"/>`;
        tip.innerHTML = `<div class="tt-date">${fmtDate(d.date, false)}</div>
            <div class="tt-row"><span><i style="background:var(--chart-1)"></i>${esc(t('chart_revenue'))}</span><b class="num">${fmtMoney(d.revenue)}</b></div>
            <div class="tt-row"><span>${esc(t('admin_chart_refuels'))}</span><b class="num">${fmtNum(d.refuels)}</b></div>
            <div class="tt-row"><span>${esc(t('admin_chart_liters'))}</span><b class="num">${fmtNum(d.liters, 1)}</b></div>`;
        tip.style.left = `${hr.left - rect.left + hr.width / 2}px`;
        tip.style.top = `${Math.max(70, e.clientY - rect.top - 12)}px`;
        tip.hidden = false;
    },

    /* --------------------------------------------- Benzinky */
    filteredStations() {
        const q = this.st.search.trim().toLowerCase();
        return (this.d.stations || []).filter((x) => {
            if (this.st.filter === 'owned' && !x.owned) return false;
            if (this.st.filter === 'public' && x.owned) return false;
            if (this.st.filter === 'closed' && x.open) return false;
            if (!q) return true;
            return [x.label, x.id, x.ownerName || '', x.defaultLabel].some((v) => String(v).toLowerCase().includes(q));
        });
    },

    tabStations() {
        const filters = ['all', 'owned', 'public', 'closed'];
        return `
            <div class="toolbar">
                <div class="input-group search">${icon('store')}<input class="input" id="adm-search" placeholder="${esc(t('admin_search'))}" value="${esc(this.st.search)}"></div>
                <div class="seg">${filters.map((f) => `<button class="${this.st.filter === f ? 'active' : ''}" data-filter="${f}">${esc(t('admin_filter_' + f))}</button>`).join('')}</div>
            </div>
            <div class="card" style="margin-top:14px"><div class="card-body table-scroll"><table class="table adm-table">
                <thead><tr><th>${esc(t('col_station'))}</th><th>${esc(t('admin_col_owner'))}</th><th class="right">${esc(t('kpi_balance'))}</th><th>${esc(t('stock_title'))}</th><th class="right">${esc(t('kpi_revenue'))}</th><th>${esc(t('col_status'))}</th><th></th></tr></thead>
                <tbody id="adm-stations-body">${this.stationRows()}</tbody></table></div></div>`;
    },

    stationRows() {
        const list = this.filteredStations();
        if (!list.length) return `<tr><td colspan="7"><div class="empty">${icon('store')}<div>${esc(t('admin_no_results'))}</div></div></td></tr>`;
        return list.map((x) => {
            const expanded = this.st.expanded === x.id;
            return `<tr class="adm-row ${expanded ? 'expanded' : ''}" data-expand="${esc(x.id)}">
                <td><div class="st-name" title="${esc(x.typeLabel)}"><span class="n">${esc(x.label)}</span><span class="mono s">${esc(x.id)}</span></div></td>
                <td>${x.owned ? `<span class="strong">${esc(x.ownerName || '—')}</span>` : `<span class="faint">${esc(t('public'))}</span>`}</td>
                <td class="right num">${x.owned ? fmtMoney(x.balance) : '—'}</td>
                <td>${x.unlimited ? `<span class="faint">${esc(t('admin_unlimited'))}</span>` : `<div class="mini-bar"><span style="width:${Math.min(100, x.stockPct)}%;${x.stockPct < 15 ? 'background:var(--warn)' : ''}"></span></div><span class="mini-val num">${fmtNum(x.stockPct, 0)} %</span>`}</td>
                <td class="right num">${fmtMoney(x.revenue)}</td>
                <td><span class="pill ${x.open ? 'ok' : 'err'}">${esc(x.open ? t('status_open') : t('status_closed'))}</span></td>
                <td class="right"><span class="chev ${expanded ? 'open' : ''}">${icon('chevron-right')}</span></td>
            </tr>${expanded ? `<tr class="perm-panel"><td colspan="7">${this.stationDetail(x)}</td></tr>` : ''}`;
        }).join('');
    },

    stationDetail(x) {
        const players = this.d.players || [];
        const confirm = this.st.confirmReset === x.id;
        return `
            <div class="adm-actions">
                <button class="btn btn-sm" data-act="teleport" data-id="${esc(x.id)}">${icon('map-pin')}${esc(t('admin_teleport'))}</button>
                <button class="btn btn-sm" data-act="toggleStation" data-id="${esc(x.id)}">${icon('power')}${esc(x.open ? t('set_close') : t('set_open'))}</button>
                <button class="btn btn-sm" data-act="fillStock" data-id="${esc(x.id)}">${icon('droplet')}${esc(t('admin_fill_stock'))}</button>
                <button class="btn btn-sm" data-act="resetPrices" data-id="${esc(x.id)}" ${x.customPrices ? '' : 'disabled'}>${icon('tag')}${esc(t('admin_reset_prices'))}</button>
                <span class="spacer"></span>
                ${x.owned ? (confirm
                    ? `<button class="btn btn-ghost btn-sm" data-act="resetCancel">${esc(t('cancel'))}</button><button class="btn btn-danger btn-sm" data-act="resetStation" data-id="${esc(x.id)}">${icon('trash-2')}${esc(t('admin_reset_confirm'))}</button>`
                    : `<button class="btn btn-danger btn-sm" data-act="resetAsk" data-id="${esc(x.id)}">${icon('trash-2')}${esc(t('admin_reset'))}</button>`) : ''}
            </div>
            <div class="grid adm-detail">
                <div class="card"><div class="card-head"><h3>${esc(t('admin_ownership'))}</h3></div><div class="card-body">
                    <div class="kv"><span>${esc(t('set_type'))}</span><span>${esc(x.typeLabel)}</span>
                        <span>${esc(t('admin_col_owner'))}</span><span>${esc(x.owned ? x.ownerName : t('public'))}</span>
                        <span>${esc(t('tab_employees'))}</span><span class="num">${x.employees}</span>
                        <span>${esc(t('kpi_customers'))}</span><span class="num">${fmtNum(x.customers)}</span>
                        <span>${esc(t('buy_price'))}</span><span class="num">${x.purchasable ? fmtMoney(x.price) : '—'}</span></div>
                    <div class="field" style="margin-top:14px"><label>${esc(t('admin_transfer_label'))}</label>
                        <div class="money-form" style="margin-top:0"><select class="select" data-transfer-select="${esc(x.id)}">${players.map((p) => `<option value="${p.id}">[${p.id}] ${esc(p.name)}</option>`).join('')}</select>
                        <button class="btn btn-primary" data-act="transfer" data-id="${esc(x.id)}" ${players.length ? '' : 'disabled'}>${esc(t('admin_transfer'))}</button></div></div>
                </div></div>
                <div class="card"><div class="card-head"><h3>${esc(t('admin_finance_name'))}</h3></div><div class="card-body">
                    <div class="field"><label>${esc(t('kpi_balance'))}</label>
                        <div class="money-form" style="margin-top:0"><div class="input-group"><input class="input num" type="number" min="0" step="1" value="${x.balance}" data-balance="${esc(x.id)}" ${x.owned ? '' : 'disabled'}><span class="suffix">${esc(S.cfg.currency.symbol)}</span></div>
                        <button class="btn" data-act="setBalance" data-id="${esc(x.id)}" ${x.owned ? '' : 'disabled'}>${esc(t('admin_set'))}</button></div></div>
                    <div class="field" style="margin-top:14px"><label>${esc(t('set_rename'))}</label>
                        <div class="money-form" style="margin-top:0"><input class="input" maxlength="32" placeholder="${esc(x.defaultLabel)}" value="${esc(x.label !== x.defaultLabel ? x.label : '')}" data-rename="${esc(x.id)}">
                        <button class="btn" data-act="rename" data-id="${esc(x.id)}">${esc(t('save'))}</button></div></div>
                </div></div>
                <div class="card adm-stock-card"><div class="card-head"><h3>${esc(t('stock_title'))}</h3>${x.unlimited ? `<span class="pill info no-dot">${esc(t('admin_unlimited'))}</span>` : ''}</div><div class="card-body"><div class="adm-stock">
                    ${x.fuels.map((f) => `<div class="adm-stock-row">${gradeChip(f)}
                        <div class="input-group"><input class="input num" type="number" min="0" max="${f.capacity}" step="100" value="${Math.round(f.stock)}" data-stock="${esc(x.id)}:${esc(f.id)}"><span class="suffix">/ ${fmtNum(f.capacity)}</span></div>
                        <button class="icon-btn" data-act="setStock" data-id="${esc(x.id)}" data-fuel="${esc(f.id)}" title="${esc(t('admin_set'))}">${icon('check')}</button></div>`).join('')}
                </div></div></div>
            </div>`;
    },

    /* --------------------------------------------- Objednávky */
    tabOrders() {
        const orders = this.d.orders || [];
        if (!orders.length) return `<div class="card"><div class="card-body"><div class="empty">${icon('package')}<div>${esc(t('admin_orders_empty'))}</div></div></div></div>`;
        const now = Date.now() / 1000;
        return `<div class="card"><div class="card-body table-scroll"><table class="table adm-table"><thead><tr><th>#</th><th>${esc(t('col_station'))}</th><th>${esc(t('col_fuel'))}</th><th class="right">${esc(t('col_amount'))}</th><th>${esc(t('col_method'))}</th><th>${esc(t('col_status'))}</th><th>${esc(t('col_info'))}</th><th class="right">${esc(t('col_cost'))}</th><th></th></tr></thead><tbody>
            ${orders.map((o) => {
                const f = S.cfg.fuelTypes[o.fuelType] || { short: '?', color: '#888', unit: 'l' };
                let info = o.driverName ? t('order_driver', o.driverName) : (o.deliverAt > 0 ? (o.deliverAt > now ? t('order_eta', Math.max(1, Math.ceil((o.deliverAt - now) / 60))) : t('order_eta_soon')) : fmtDate(o.createdAt));
                return `<tr><td class="num">${o.id}</td><td class="strong">${esc(o.station)}</td><td>${gradeChip(f)}</td><td class="right num">${fmtNum(o.liters)} ${unitLabel(f.unit)}</td>
                    <td>${esc(t('order_method_' + o.method))}</td><td>${Views.management.orderStatus(o)}</td><td>${esc(info)}</td><td class="right num">${fmtMoney(o.cost)}</td>
                    <td class="right" style="white-space:nowrap"><button class="btn btn-sm" data-act="deliverOrder" data-order="${o.id}">${icon('check')}${esc(t('admin_deliver'))}</button>
                    <button class="btn btn-ghost btn-sm" data-act="cancelOrder" data-order="${o.id}">${esc(t('cancel'))}</button></td></tr>`;
            }).join('')}</tbody></table></div></div>
            <div class="notice" style="margin-top:14px">${icon('info')}<span>${esc(t('admin_orders_hint'))}</span></div>`;
    },

    /* --------------------------------------------- Živě */
    tabLive() {
        const live = this.d.live || { sessions: [], jobs: [], duty: [] };
        const empty = (key, ic) => `<div class="empty">${icon(ic)}<div>${esc(t(key))}</div></div>`;
        const sessions = live.sessions.length ? `<table class="table adm-table"><thead><tr><th>${esc(t('admin_col_player'))}</th><th>${esc(t('col_station'))}</th><th>${esc(t('col_plate'))}</th><th>${esc(t('col_fuel'))}</th><th>${esc(t('admin_col_progress'))}</th><th class="right">${esc(t('admin_col_deposit'))}</th><th></th></tr></thead><tbody>
            ${live.sessions.map((x) => {
                const f = S.cfg.fuelTypes[x.fuelType] || { short: '?', color: '#888', unit: 'l' };
                const pct = x.amount > 0 ? Math.min(100, x.delivered / x.amount * 100) : 0;
                return `<tr><td class="strong">${esc(x.player)} <span class="faint">[${x.source}]</span></td><td>${esc(x.station)}</td><td>${x.plate ? `<span class="plate" style="height:20px;font-size:11px">${esc(x.plate)}</span>` : '—'}</td><td>${gradeChip(f)}</td>
                    <td><div class="mini-bar flow"><span style="width:${pct}%"></span></div><span class="mini-val num">${fmtNum(x.delivered, 1)} / ${fmtNum(x.amount, 1)} ${unitLabel(f.unit)}</span></td>
                    <td class="right num">${fmtMoney(x.paid)}</td><td class="right"><button class="btn btn-danger btn-sm" data-act="stopSession" data-session="${x.id}">${esc(t('admin_stop'))}</button></td></tr>`;
            }).join('')}</tbody></table>` : empty('admin_live_no_sessions', 'fuel');
        const jobs = live.jobs.length ? `<table class="table adm-table"><thead><tr><th>${esc(t('admin_col_driver'))}</th><th>#</th><th>${esc(t('col_station'))}</th><th>${esc(t('col_status'))}</th><th class="right">${esc(t('admin_col_time'))}</th><th class="right">${esc(t('board_reward'))}</th><th></th></tr></thead><tbody>
            ${live.jobs.map((x) => `<tr><td class="strong">${esc(x.driver)} <span class="faint">[${x.source}]</span></td><td class="num">${x.orderId}</td><td>${esc(x.station)}</td><td>${Views.management.orderStatus({ status: x.status === 'delivered' ? 'delivered' : x.status, method: 'tanker' })}</td>
                <td class="right num">${esc(t('duration_m', x.minutes))}</td><td class="right num">${fmtMoney(x.reward)}</td><td class="right"><button class="btn btn-ghost btn-sm" data-act="cancelJob" data-source="${x.source}">${esc(t('cancel'))}</button></td></tr>`).join('')}</tbody></table>` : empty('admin_live_no_jobs', 'truck');
        const duty = live.duty.length ? `<table class="table adm-table"><thead><tr><th>${esc(t('admin_col_employee'))}</th><th>${esc(t('col_station'))}</th><th>${esc(t('col_rank'))}</th><th class="right">${esc(t('admin_col_shift'))}</th><th class="right">${esc(t('admin_col_earned'))}</th><th></th></tr></thead><tbody>
            ${live.duty.map((x) => `<tr><td class="strong">${esc(x.name)} <span class="faint">[${x.source}]</span></td><td>${esc(x.station)}</td><td>${esc(x.rank)}</td><td class="right num">${fmtClock(x.seconds)}</td><td class="right num">${fmtMoney(x.earned)}</td>
                <td class="right"><button class="btn btn-ghost btn-sm" data-act="clockOut" data-source="${x.source}">${esc(t('admin_clock_out'))}</button></td></tr>`).join('')}</tbody></table>` : empty('admin_live_no_duty', 'clock');
        return `
            <div class="card"><div class="card-head"><h3>${icon('fuel', 'muted')} ${esc(t('admin_live_sessions'))} <span class="faint num">${live.sessions.length}</span></h3></div><div class="card-body table-scroll">${sessions}</div></div>
            <div class="card" style="margin-top:14px"><div class="card-head"><h3>${icon('truck', 'muted')} ${esc(t('admin_live_jobs'))} <span class="faint num">${live.jobs.length}</span></h3></div><div class="card-body table-scroll">${jobs}</div></div>
            <div class="card" style="margin-top:14px"><div class="card-head"><h3>${icon('clock', 'muted')} ${esc(t('admin_live_duty'))} <span class="faint num">${live.duty.length}</span></h3></div><div class="card-body table-scroll">${duty}</div></div>`;
    },

    /* --------------------------------------------- Palivo vozidel */
    tabFuel() {
        const radii = [10, 25, 50, 100].filter((r) => r <= ((this.d.admin && this.d.admin.areaMax) || 100));
        const plate = this.st.plate;
        return `
            <div class="grid g-3">
                <div class="card"><div class="card-head"><h3>${esc(t('admin_fuel_vehicle'))}</h3>${icon('gauge', 'muted')}</div><div class="card-body">
                    <div class="amount-display" style="margin-top:0"><div class="digits num" id="adm-fuel-val">${fmtNum(this.st.fuelAmount)}<small>%</small></div></div>
                    <input type="range" id="adm-fuel-range" min="0" max="100" step="1" value="${this.st.fuelAmount}" style="--fill:${this.st.fuelAmount}%">
                    <div class="presets">${[0, 25, 50, 100].map((v) => `<button class="preset ${this.st.fuelAmount === v ? 'active' : ''}" data-fuel-preset="${v}">${v} %</button>`).join('')}</div>
                    <div class="grid g-2" style="margin-top:12px;gap:8px">
                        <button class="btn btn-primary" data-act="vehicleFuel" data-target="current">${icon('fuel')}${esc(t('admin_current_vehicle'))}</button>
                        <button class="btn" data-act="vehicleFuel" data-target="nearest">${icon('map-pin')}${esc(t('admin_nearest_vehicle'))}</button>
                    </div>
                </div></div>
                <div class="card"><div class="card-head"><h3>${esc(t('admin_area_title'))}</h3>${icon('route', 'muted')}</div><div class="card-body">
                    <p class="muted" style="font-size:13px;line-height:1.45">${esc(t('admin_area_desc'))}</p>
                    <div class="field" style="margin-top:14px"><label>${esc(t('admin_area_radius'))}</label>
                        <div class="seg">${radii.map((r) => `<button class="${this.st.radius === r ? 'active' : ''}" data-radius="${r}">${r} m</button>`).join('')}</div></div>
                    <button class="btn btn-primary btn-block" style="margin-top:16px" data-act="areaRefuel">${icon('droplet')}${esc(t('admin_area_btn', this.st.radius))}</button>
                </div></div>
                <div class="card"><div class="card-head"><h3>${esc(t('admin_plate_title'))}</h3>${icon('receipt', 'muted')}</div><div class="card-body">
                    <div class="field"><label>${esc(t('col_plate'))}</label>
                        <div class="money-form" style="margin-top:0"><input class="input mono" id="adm-plate" maxlength="8" placeholder="ABC 123" value="${esc(plate ? plate.plate : '')}" style="text-transform:uppercase">
                        <button class="btn" data-act="plateLookup">${esc(t('admin_lookup'))}</button></div></div>
                    ${plate ? `<div class="plate-result"><span class="plate">${esc(plate.plate)}</span><span class="num">${plate.fuel === null || plate.fuel === undefined ? esc(t('admin_plate_unknown')) : fmtNum(plate.fuel, 1) + ' %'}</span></div>` : `<p class="muted" style="font-size:12px;margin-top:10px">${esc(t('admin_plate_hint'))}</p>`}
                    <div class="field" style="margin-top:14px"><label>${esc(t('admin_plate_set'))}</label>
                        <div class="money-form" style="margin-top:0"><div class="input-group"><input class="input num" id="adm-plate-amount" type="number" min="0" max="100" step="1" value="100"><span class="suffix">%</span></div>
                        <button class="btn" data-act="plateSet">${esc(t('admin_set'))}</button></div></div>
                </div></div>
            </div>
            <div class="notice" style="margin-top:14px">${icon('info')}<span>${esc(t('admin_fuel_hint'))}</span></div>`;
    },

    /* --------------------------------------------- Audit log */
    tabLogs() {
        const logs = this.d.logs || [];
        if (!logs.length) return `<div class="card"><div class="card-body"><div class="empty">${icon('scroll-text')}<div>${esc(t('admin_logs_empty'))}</div></div></div></div>`;
        return `<div class="card"><div class="card-body table-scroll"><table class="table adm-table"><thead><tr><th>${esc(t('col_date'))}</th><th>${esc(t('admin_col_admin'))}</th><th>${esc(t('admin_col_action'))}</th><th>${esc(t('admin_col_target'))}</th><th>${esc(t('admin_col_details'))}</th></tr></thead><tbody>
            ${logs.map((l) => `<tr><td class="num">${fmtDate(l.created_at)}</td><td class="strong">${esc(l.admin_name || '—')}</td><td><span class="pill info no-dot">${esc(S.locale['admin_log_' + l.action] || l.action)}</span></td><td class="mono" style="font-size:12px">${esc(l.target || '—')}</td><td>${esc(l.details || '')}</td></tr>`).join('')}
            </tbody></table></div></div>`;
    },

    /* --------------------------------------------- události */
    onInput(e) {
        if (e.target.id === 'adm-search') {
            this.st.search = e.target.value;
            const body = $('#adm-stations-body');
            if (body) body.innerHTML = this.stationRows();
            return;
        }
        if (e.target.id === 'adm-fuel-range') {
            this.st.fuelAmount = Number(e.target.value);
            e.target.style.setProperty('--fill', `${this.st.fuelAmount}%`);
            const v = $('#adm-fuel-val');
            if (v) v.innerHTML = `${fmtNum(this.st.fuelAmount)}<small>%</small>`;
            $$('[data-fuel-preset]').forEach((b) => b.classList.toggle('active', Number(b.dataset.fuelPreset) === this.st.fuelAmount));
        }
    },

    async onClick(e) {
        const el = e.target.closest('button, [data-tab], [data-expand]');
        if (!el || el.disabled) return;
        const ds = el.dataset;
        if (e.target.closest('input, select')) return;

        if (ds.tab) {
            this.st.enter = this.st.tab !== ds.tab;
            this.st.tab = ds.tab;
            this.render();
            return;
        }
        if (ds.filter) { this.st.filter = ds.filter; this.render(); return; }
        if (ds.radius) { this.st.radius = Number(ds.radius); this.render(); return; }
        if (ds.fuelPreset) {
            this.st.fuelAmount = Number(ds.fuelPreset);
            this.render();
            return;
        }
        if (ds.expand && !e.target.closest('.perm-panel')) {
            this.st.expanded = this.st.expanded === ds.expand ? null : ds.expand;
            this.st.confirmReset = null;
            const body = $('#adm-stations-body');
            if (body) body.innerHTML = this.stationRows();
            return;
        }
        if (!ds.act) return;
        const opts = { button: el.classList.contains('btn') || el.classList.contains('icon-btn') ? el : null };
        const id = ds.id;
        switch (ds.act) {
            case 'refresh': return this.action('refresh', {}, opts);
            case 'teleport': return this.action('teleport', { stationId: id }, opts);
            case 'toggleStation': return this.action('toggleStation', { stationId: id }, opts);
            case 'fillStock': return this.action('fillStock', { stationId: id }, opts);
            case 'resetPrices': return this.action('resetPrices', { stationId: id }, opts);
            case 'resetAsk': this.st.confirmReset = id; return this.render();
            case 'resetCancel': this.st.confirmReset = null; return this.render();
            case 'resetStation': this.st.confirmReset = null; return this.action('resetStation', { stationId: id, confirm: id }, opts);
            case 'transfer': {
                const sel = $(`[data-transfer-select="${id}"]`);
                return this.action('transfer', { stationId: id, target: sel ? Number(sel.value) : null }, opts);
            }
            case 'setBalance': {
                const input = $(`[data-balance="${id}"]`);
                return this.action('setBalance', { stationId: id, balance: Math.floor(Number(input.value) || 0) }, opts);
            }
            case 'rename': {
                const input = $(`[data-rename="${id}"]`);
                return this.action('rename', { stationId: id, label: input ? input.value : '' }, opts);
            }
            case 'setStock': {
                const input = $(`[data-stock="${id}:${ds.fuel}"]`);
                return this.action('setStock', { stationId: id, fuelType: ds.fuel, liters: Number(input.value) || 0 }, opts);
            }
            case 'deliverOrder': return this.action('deliverOrder', { orderId: Number(ds.order) }, opts);
            case 'cancelOrder': return this.action('cancelOrder', { orderId: Number(ds.order) }, opts);
            case 'stopSession': return this.action('stopSession', { sessionId: Number(ds.session) }, opts);
            case 'cancelJob': return this.action('cancelJob', { source: Number(ds.source) }, opts);
            case 'clockOut': return this.action('clockOut', { source: Number(ds.source) }, opts);
            case 'vehicleFuel': return this.action('vehicleFuel', { amount: this.st.fuelAmount, target: ds.target }, opts);
            case 'areaRefuel': return this.action('areaRefuel', { radius: this.st.radius }, opts);
            case 'plateLookup': {
                const plate = ($('#adm-plate').value || '').trim().toUpperCase();
                if (!plate) return null;
                const res = await this.action('plateLookup', { plate }, Object.assign(opts, { noRender: true }));
                if (res && res.ok && this.d) { this.st.plate = res.data; this.render(); }
                return res;
            }
            case 'plateSet': {
                const plate = ($('#adm-plate').value || '').trim().toUpperCase();
                if (!plate) return null;
                const res = await this.action('plateSet', { plate, amount: Number($('#adm-plate-amount').value) }, Object.assign(opts, { noRender: true }));
                if (res && res.ok && this.d) { this.st.plate = res.data; this.render(); }
                return res;
            }
            default: return null;
        }
    },
};

/* ------------------------------------------------------------------ Zprávy z Lua */
function init(data) {
    if (data.locale) S.locale = data.locale;
    if (data.config) Object.assign(S.cfg, data.config);
}

window.addEventListener('message', (event) => {
    const msg = event.data || {};
    const data = msg.data || {};
    switch (msg.action) {
        case 'init': init(data); break;
        case 'open': Loader.hide(); if (Views[data.view]) Views[data.view].open(data.data || {}); break;
        case 'loading': if (data.show) Loader.show(data.label); else Loader.hide(); break;
        case 'close': Modals.close(data.view, false); break;
        case 'closeAll': Modals.closeAll(); break;
        case 'notify': Toasts.show(data.message, data.type); break;
        case 'hud': Hud.update(data); break;
        case 'progress': Progress.update(data); break;
        case 'receipt': Receipt.show(data.receipt, data.fromItem); break;
        case 'sound': Sound.play(data.name); break;
        case 'jobhud': JobHud.update(data); break;
        case 'action': ActionBar.update(data); break;
        default: break;
    }
});

post('ready', {});
