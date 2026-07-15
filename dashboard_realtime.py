"""
dashboard_realtime.py — Network Congestion Detection · Real-Time Dashboard
Run:  streamlit run dashboard_realtime.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import threading, queue, time, os
from collections import deque

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CongestionNet · Live",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL SHARED STATE  (survives st.rerun — lives at module level)
# ══════════════════════════════════════════════════════════════════════════════

MAXLEN = 150

class LiveState:
    def __init__(self):
        self.lock        = threading.Lock()
        self.running     = False
        self.mode        = "simulate"
        self.probs       = deque(maxlen=MAXLEN)
        self.labels      = deque(maxlen=MAXLEN)
        self.packets     = deque(maxlen=MAXLEN)
        self.timestamps  = deque(maxlen=MAXLEN)
        self.total       = 0
        self.total_cong  = 0
        self.thread      = None
        self.pkt_queue   = queue.Queue()
        self._proc       = None

    def reset(self):
        with self.lock:
            self.probs.clear()
            self.labels.clear()
            self.packets.clear()
            self.timestamps.clear()
            self.total      = 0
            self.total_cong = 0
            self.pkt_queue  = queue.Queue()

# Single global instance — shared across all reruns
if "_LIVE" not in st.session_state:
    st.session_state["_LIVE"] = LiveState()
G = st.session_state["_LIVE"]

# ══════════════════════════════════════════════════════════════════════════════
# TRAIN MODEL  (cached — only runs once)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_resource
def build_model():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    from sklearn.metrics import roc_auc_score, accuracy_score

    np.random.seed(42)
    n = 6000

    packet_size = np.random.randint(60, 1500, n).astype(float)
    rto         = np.random.uniform(50, 400, n)
    retrans     = np.random.poisson(0.3, n).astype(float)
    window_size = np.random.randint(8000, 65535, n).astype(float)
    packet_rate = np.random.randint(100, 1000, n).astype(float)
    rtt         = np.random.uniform(10, 200, n)

    score = (
        (packet_rate / 1000)        * 0.30 +
        (rto / 400)                 * 0.25 +
        (retrans / 5)               * 0.20 +
        (1 - window_size / 65535)   * 0.15 +
        (rtt / 200)                 * 0.10
    )
    y = ((score + np.random.normal(0, 0.06, n)) > 0.50).astype(int)

    # Make congested samples realistic
    rto[y==1]         *= np.random.uniform(2, 5, y.sum())
    window_size[y==1] *= np.random.uniform(0.1, 0.4, y.sum())
    retrans[y==1]     += np.random.randint(3, 10, y.sum())

    X = pd.DataFrame({
        'packet_size':    packet_size,
        'rto':            rto,
        'retransmission': retrans,
        'window_size':    window_size,
        'packet_rate':    packet_rate,
        'rtt':            rtt,
    })

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    pipe = Pipeline([
        ('scaler', StandardScaler()),
        ('clf',    RandomForestClassifier(
            n_estimators=100, class_weight='balanced',
            random_state=42, n_jobs=-1))
    ])
    pipe.fit(X_train, y_train)

    y_prob = pipe.predict_proba(X_test)[:, 1]
    auc    = roc_auc_score(y_test, y_prob)
    acc    = accuracy_score(y_test, (y_prob >= 0.5).astype(int))

    return pipe, list(X.columns), round(auc, 4), round(acc, 4)

MODEL, FEATURES, ROC_AUC, ACCURACY = build_model()

def predict(pkt: dict) -> float:
    row = pd.DataFrame([{f: pkt.get(f, 0.0) for f in FEATURES}])
    return float(MODEL.predict_proba(row)[0][1])

# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND THREADS
# ══════════════════════════════════════════════════════════════════════════════

def simulate_thread():
    rng = np.random.default_rng(int(time.time()))
    t   = 0
    while G.running and G.mode == "simulate":
        phase = (t // 25) % 3      # 0=normal  1=congested  2=recovery
        if phase == 0:
            pkt = dict(
                packet_size   = float(rng.integers(400, 1460)),
                rto           = float(rng.uniform(40, 160)),
                retransmission= float(rng.poisson(0.05)),
                window_size   = float(rng.integers(45000, 65535)),
                packet_rate   = float(rng.integers(80,  400)),
                rtt           = float(rng.uniform(8,   55)),
            )
        elif phase == 1:
            pkt = dict(
                packet_size   = float(rng.integers(60,  400)),
                rto           = float(rng.uniform(900, 2800)),
                retransmission= float(rng.poisson(5) + 3),
                window_size   = float(rng.integers(3000, 12000)),
                packet_rate   = float(rng.integers(750, 1000)),
                rtt           = float(rng.uniform(160, 290)),
            )
        else:
            pkt = dict(
                packet_size   = float(rng.integers(200, 1200)),
                rto           = float(rng.uniform(200, 700)),
                retransmission= float(rng.poisson(1)),
                window_size   = float(rng.integers(18000, 48000)),
                packet_rate   = float(rng.integers(200, 600)),
                rtt           = float(rng.uniform(40,  130)),
            )
        G.pkt_queue.put(pkt)
        t  += 1
        time.sleep(0.2)            # 5 packets/sec


def tshark_thread(tshark_path: str, iface: str):
    cmd = [
        tshark_path, '-i', iface,
        '-T', 'fields',
        '-e', 'frame.len',
        '-e', 'tcp.analysis.rto',
        '-e', 'tcp.analysis.retransmission',
        '-e', 'tcp.window_size',
        '-e', 'tcp.len',
        '-e', 'frame.time_delta',
        '-E', 'separator=,',
        '-l',
    ]
    try:
        import subprocess
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, bufsize=1)
        G._proc = proc
        for line in proc.stdout:
            if not G.running:
                proc.terminate(); break
            parts = line.strip().split(',')
            if len(parts) < 6: continue
            def sf(v, d=0.0):
                try: return float(v) if v.strip() else d
                except: return d
            time_delta = sf(parts[5], 0.01)
            pkt = dict(
                packet_size   = sf(parts[0]),
                rto           = sf(parts[1]) * 1000,
                retransmission= sf(parts[2]),
                window_size   = sf(parts[3]),
                packet_rate   = 1.0 / time_delta if time_delta > 0 else 100.0,
                rtt           = sf(parts[5]) * 1000,
            )
            G.pkt_queue.put(pkt)
    except Exception as e:
        G.pkt_queue.put({'_error': str(e)})
        G.running = False


# ══════════════════════════════════════════════════════════════════════════════
# DRAIN QUEUE  (called every rerun — this is where data flows in)
# ══════════════════════════════════════════════════════════════════════════════

error_msg = None
drained   = 0
while not G.pkt_queue.empty() and drained < 25:
    pkt = G.pkt_queue.get_nowait()
    if '_error' in pkt:
        error_msg = pkt['_error']
        G.running = False
        break
    prob  = predict(pkt)
    label = 1 if prob >= st.session_state.get("threshold", 0.5) else 0
    with G.lock:
        G.probs.append(prob)
        G.labels.append(label)
        G.packets.append(pkt)
        G.timestamps.append(time.strftime("%H:%M:%S"))
        G.total      += 1
        G.total_cong += label
    drained += 1

# Snapshot for rendering (avoid holding lock during chart drawing)
with G.lock:
    probs_arr  = np.array(G.probs)   if G.probs   else np.array([0.0])
    labels_arr = np.array(G.labels)  if G.labels  else np.array([0])
    pkts_list  = list(G.packets)
    ts_list    = list(G.timestamps)
    total      = G.total
    total_cong = G.total_cong

cong_rate  = float(labels_arr.mean())
avg_prob   = float(probs_arr.mean())
last_prob  = float(probs_arr[-1])
latest_pkt = pkts_list[-1] if pkts_list else {}

# ══════════════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: #060A10;
    color: #E2E8F0;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 1.4rem 2rem; max-width: 1500px; }

section[data-testid="stSidebar"] {
    background: #0A1120;
    border-right: 1px solid #1A2840;
}

.hero {
    background: linear-gradient(135deg,#0A1628 0%,#060E1C 100%);
    border: 1px solid #1A2840;
    border-radius: 14px;
    padding: 1.2rem 2rem;
    margin-bottom: 1rem;
    display: flex; align-items: center; justify-content: space-between;
}
.hero-title {
    font-family: 'Space Mono', monospace;
    font-size: 1.5rem; font-weight: 700;
    color: #00C8FF; letter-spacing: -0.5px;
    text-shadow: 0 0 30px rgba(0,200,255,0.4);
}
.hero-sub { color: #475569; font-size: 0.8rem; margin-top: 3px; }

@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(1.3)} }
.dot {
    display:inline-block; width:9px; height:9px; border-radius:50%;
    margin-right:5px; animation: pulse 1.2s infinite;
}
.dot-green  { background:#00E676; box-shadow:0 0 8px #00E676; }
.dot-red    { background:#FF4444; box-shadow:0 0 8px #FF4444; }
.dot-amber  { background:#FFB300; box-shadow:0 0 8px #FFB300; }
.dot-grey   { background:#475569; }

.stat-row { display:grid; grid-template-columns:repeat(6,1fr); gap:.7rem; margin-bottom:1rem; }
.stat-card {
    background:#0A1120; border:1px solid #1A2840;
    border-radius:10px; padding:.9rem 1.1rem;
    position:relative; overflow:hidden;
}
.stat-card::after {
    content:''; position:absolute; top:0;left:0;right:0; height:2px;
}
.c-blue::after   { background:linear-gradient(90deg,#00C8FF,#0066FF); }
.c-green::after  { background:linear-gradient(90deg,#00E676,#00BFA5); }
.c-red::after    { background:linear-gradient(90deg,#FF4444,#CC0000); }
.c-amber::after  { background:linear-gradient(90deg,#FFB300,#FF6F00); }
.c-purple::after { background:linear-gradient(90deg,#A855F7,#7C3AED); }
.c-teal::after   { background:linear-gradient(90deg,#2DD4BF,#0D9488); }

.stat-label {
    font-family:'Space Mono',monospace; font-size:.57rem;
    letter-spacing:.14em; color:#3D5A80; text-transform:uppercase; margin-bottom:.35rem;
}
.stat-value {
    font-family:'Space Mono',monospace; font-size:1.8rem;
    font-weight:700; color:#E2E8F0; line-height:1;
}
.stat-sub { font-size:.67rem; color:#475569; margin-top:.25rem; }

.alert-ok   { background:rgba(0,230,118,.06); border:1px solid rgba(0,230,118,.25); border-radius:10px; padding:.7rem 1.1rem; font-family:'Space Mono',monospace; font-size:.8rem; color:#00E676; margin-bottom:.8rem; }
.alert-warn { background:rgba(255,179,0,.07); border:1px solid rgba(255,179,0,.28); border-radius:10px; padding:.7rem 1.1rem; font-family:'Space Mono',monospace; font-size:.8rem; color:#FFB300; margin-bottom:.8rem; }
.alert-bad  { background:rgba(255,68,68,.1);  border:1px solid rgba(255,68,68,.4);  border-radius:10px; padding:.7rem 1.1rem; font-family:'Space Mono',monospace; font-size:.8rem; color:#FF4444; margin-bottom:.8rem; }
.alert-idle { background:#0A1120; border:1px solid #1A2840; border-radius:10px; padding:.7rem 1.1rem; font-family:'Space Mono',monospace; font-size:.8rem; color:#475569; margin-bottom:.8rem; }

.sec-hdr {
    font-family:'Space Mono',monospace; font-size:.6rem;
    letter-spacing:.18em; text-transform:uppercase;
    color:#00C8FF; border-left:3px solid #00C8FF;
    padding-left:.7rem; margin:.9rem 0 .5rem 0;
}
.feed-box {
    background:#060A10; border:1px solid #1A2840;
    border-radius:10px; padding:.7rem; height:240px;
    overflow-y:auto; font-family:'Space Mono',monospace; font-size:.68rem;
}
.fn { color:#2E6B50; padding:2px 0; border-bottom:1px solid #0A1628; }
.fc { color:#FF6B6B; padding:2px 0; border-bottom:1px solid #0A1628; font-weight:bold; }
.sidebar-label {
    font-family:'Space Mono',monospace; font-size:.6rem;
    letter-spacing:.12em; color:#3D5A80; text-transform:uppercase; margin-bottom:.3rem;
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

THEME = dict(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family='DM Sans', color='#4A6080', size=11),
    margin=dict(t=30, b=30, l=50, r=20),
    xaxis=dict(gridcolor='#0F1E33', zerolinecolor='#0F1E33'),
    yaxis=dict(gridcolor='#0F1E33', zerolinecolor='#0F1E33'),
)

with st.sidebar:
    st.markdown('<div style="font-family:Space Mono;font-size:1.05rem;color:#00C8FF;font-weight:700;margin-bottom:.2rem;">📡 CongestionNet</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#475569;font-size:.75rem;margin-bottom:1rem;">Real-Time Detection</div>', unsafe_allow_html=True)
    st.divider()

    st.markdown('<div class="sidebar-label">Capture Mode</div>', unsafe_allow_html=True)
    mode_choice = st.radio("Capture Mode", ["🎲  Simulate (Demo)", "📡  Live tshark"],
                           label_visibility="collapsed")
    G.mode = "simulate" if "Simulate" in mode_choice else "live"

    if G.mode == "live":
        st.divider()
        st.markdown('<div class="sidebar-label">tshark Path</div>', unsafe_allow_html=True)
        tshark_path = st.text_input("tshark Path", value=r'C:\Program Files\Wireshark\tshark.exe',
                                    label_visibility="collapsed")
        st.markdown('<div class="sidebar-label">Interface</div>', unsafe_allow_html=True)
        iface = st.text_input("Interface", value="", placeholder='e.g. Wi-Fi',
                               label_visibility="collapsed")


    st.divider()
    st.markdown('<div class="sidebar-label">Detection Threshold</div>', unsafe_allow_html=True)
    threshold = st.slider("Detection Threshold", 0.10, 0.90, 0.50, 0.05, label_visibility="collapsed")
    st.session_state["threshold"] = threshold

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        start_btn = st.button("▶ Start", width='stretch', type="primary",
                              disabled=G.running)
    with col_b:
        stop_btn  = st.button("■ Stop",  width='stretch',
                              disabled=not G.running)

    st.divider()
    st.markdown('<div class="sidebar-label">Model Info</div>', unsafe_allow_html=True)
    st.caption(f"ROC-AUC  : {ROC_AUC}")
    st.caption(f"Accuracy : {ACCURACY}")
    st.caption("Random Forest · 100 trees")
    st.caption("StandardScaler · balanced")

# ── Start / Stop ──────────────────────────────────────────────────────────────
if start_btn:
    G.reset()
    G.running = True
    if G.mode == "simulate":
        t = threading.Thread(target=simulate_thread, daemon=True)
    else:
        t = threading.Thread(target=tshark_thread,
                             args=(tshark_path, iface), daemon=True)
    t.start()
    G.thread = t

if stop_btn:
    G.running = False
    if G._proc:
        try: G._proc.terminate()
        except: pass

# ══════════════════════════════════════════════════════════════════════════════
# HERO + ALERT
# ══════════════════════════════════════════════════════════════════════════════

mode_label  = "SIMULATION" if G.mode == "simulate" else "LIVE CAPTURE"
dot_cls     = "dot-green" if G.running and cong_rate < 0.35 \
         else "dot-red"   if G.running and cong_rate > 0.6  \
         else "dot-amber" if G.running \
         else "dot-grey"
status_txt  = "RUNNING" if G.running else "STOPPED"
status_col  = "#00E676" if G.running else "#475569"

st.markdown(f"""
<div class="hero">
  <div>
    <div class="hero-title">📡 CongestionNet · Real-Time</div>
    <div class="hero-sub">
      <span class="dot {dot_cls}"></span>{mode_label} &nbsp;·&nbsp;
      <span style="color:{status_col};font-family:Space Mono;font-size:.73rem;">{status_txt}</span>
      &nbsp;·&nbsp; threshold={threshold:.2f} &nbsp;·&nbsp; window={MAXLEN} pkts
    </div>
  </div>
  <div style="font-family:Space Mono;font-size:.67rem;color:#1E3050;">
    ROC-AUC {ROC_AUC} &nbsp;|&nbsp; RF·100 trees
  </div>
</div>
""", unsafe_allow_html=True)

if error_msg:
    st.error(f"tshark error: {error_msg}")

# Alert banner
if not G.running and total == 0:
    st.markdown('<div class="alert-idle">⬛ IDLE — Press ▶ Start in the sidebar to begin monitoring</div>', unsafe_allow_html=True)
elif cong_rate > 0.6:
    st.markdown('<div class="alert-bad">🔴  CONGESTION DETECTED — High congestion probability across rolling window</div>', unsafe_allow_html=True)
elif cong_rate > 0.3:
    st.markdown('<div class="alert-warn">🟡  WARNING — Elevated congestion probability detected</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="alert-ok">🟢  NETWORK HEALTHY — No significant congestion in rolling window</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# STAT CARDS
# ══════════════════════════════════════════════════════════════════════════════

cr_color  = "c-red" if cong_rate > 0.5 else "c-green"
lp_color  = "c-red" if last_prob >= threshold else "c-green"
lp_status = "CONGESTED" if last_prob >= threshold else "NORMAL"

st.markdown(f"""
<div class="stat-row">
  <div class="stat-card c-blue">
    <div class="stat-label">Packets Analyzed</div>
    <div class="stat-value">{total:,}</div>
    <div class="stat-sub">total seen</div>
  </div>
  <div class="stat-card {cr_color}">
    <div class="stat-label">Congestion Rate</div>
    <div class="stat-value">{cong_rate*100:.1f}%</div>
    <div class="stat-sub">{total_cong:,} flagged</div>
  </div>
  <div class="stat-card c-amber">
    <div class="stat-label">Avg Probability</div>
    <div class="stat-value">{avg_prob:.3f}</div>
    <div class="stat-sub">rolling {MAXLEN}-pkt window</div>
  </div>
  <div class="stat-card {lp_color}">
    <div class="stat-label">Last Packet</div>
    <div class="stat-value">{last_prob:.3f}</div>
    <div class="stat-sub">{lp_status}</div>
  </div>
  <div class="stat-card c-teal">
    <div class="stat-label">Current RTO</div>
    <div class="stat-value">{latest_pkt.get('rto', 0):.0f}</div>
    <div class="stat-sub">ms</div>
  </div>
  <div class="stat-card c-purple">
    <div class="stat-label">Window Size</div>
    <div class="stat-value">{int(latest_pkt.get('window_size', 0)):,}</div>
    <div class="stat-sub">bytes</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CHARTS — Row 1
# ══════════════════════════════════════════════════════════════════════════════

col1, col2 = st.columns([2.2, 1])

with col1:
    st.markdown('<div class="sec-hdr">Congestion Probability · Live Timeline</div>', unsafe_allow_html=True)
    if len(probs_arr) > 2:
        xs = list(range(len(probs_arr)))
        fig = go.Figure()
        fig.add_hrect(y0=threshold, y1=1.0,
                      fillcolor='rgba(255,68,68,0.05)', line_width=0)
        fig.add_hline(y=threshold, line_dash='dot', line_color='#FF4444',
                      line_width=1, opacity=0.6,
                      annotation_text=f"threshold {threshold:.2f}",
                      annotation_font=dict(color='#FF4444', size=9, family='Space Mono'))
        fig.add_trace(go.Scatter(
            x=xs, y=list(probs_arr), mode='lines',
            line=dict(color='#00C8FF', width=2),
            fill='tozeroy', fillcolor='rgba(0,200,255,0.05)',
            hovertemplate='Pkt %{x}<br>P=%{y:.3f}<extra></extra>'
        ))
        # Red dots for congested packets
        cx = [i for i,p in enumerate(probs_arr) if p >= threshold]
        cy = [probs_arr[i] for i in cx]
        if cx:
            fig.add_trace(go.Scatter(
                x=cx, y=cy, mode='markers', name='Congested',
                marker=dict(color='#FF4444', size=5),
                hovertemplate='Pkt %{x}<br>P=%{y:.3f}<extra></extra>'
            ))
        layout = dict(THEME)
        layout['height'] = 270
        layout['yaxis'] = dict(**THEME['yaxis'], range=[0,1], title='P(congestion)')
        layout['xaxis'] = dict(**THEME['xaxis'], title='Packet Index')
        layout['showlegend'] = False
        fig.update_layout(**layout)
        st.plotly_chart(fig, width='stretch')
    else:
        st.markdown('<div style="height:270px;display:flex;align-items:center;'
                    'justify-content:center;color:#1A2840;font-family:Space Mono;'
                    'font-size:.8rem;border:1px solid #0F1E33;border-radius:10px;">'
                    '▶ Press Start to begin live monitoring...</div>',
                    unsafe_allow_html=True)

with col2:
    st.markdown('<div class="sec-hdr">Current P(Congestion)</div>', unsafe_allow_html=True)
    g_color = '#FF4444' if last_prob >= threshold else \
              '#FFB300'  if last_prob > 0.35 else '#00E676'
    fig_g = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(last_prob * 100, 1),
        number=dict(suffix="%", font=dict(family='Space Mono', size=34, color='#E2E8F0')),
        gauge=dict(
            axis=dict(range=[0,100],
                      tickfont=dict(color='#2A4060', family='Space Mono', size=9)),
            bar=dict(color=g_color, thickness=0.22),
            bgcolor='#060A10', bordercolor='#1A2840',
            steps=[
                dict(range=[0,35],   color='rgba(0,230,118,0.07)'),
                dict(range=[35,60],  color='rgba(255,179,0,0.07)'),
                dict(range=[60,100], color='rgba(255,68,68,0.07)'),
            ],
            threshold=dict(line=dict(color='#475569', width=1.5),
                           thickness=0.75, value=threshold*100)
        )
    ))
    fig_g.update_layout(**THEME, height=270)
    st.plotly_chart(fig_g, width='stretch')

# ══════════════════════════════════════════════════════════════════════════════
# CHARTS — Row 2
# ══════════════════════════════════════════════════════════════════════════════

col3, col4 = st.columns(2)

with col3:
    st.markdown('<div class="sec-hdr">Latest Packet Features</div>', unsafe_allow_html=True)
    if latest_pkt:
        MAXVALS = {'packet_size':1500,'rto':3000,'retransmission':10,
                   'window_size':65535,'packet_rate':1000,'rtt':300}
        feat_names = list(latest_pkt.keys())
        feat_vals  = [latest_pkt[f] for f in feat_names]
        norm       = [min(v / MAXVALS.get(k, max(abs(v),1)), 1.0)
                      for k,v in zip(feat_names, feat_vals)]
        bcolors    = ['#FF4444' if n > 0.65 else '#FFB300' if n > 0.35 else '#00C8FF'
                      for n in norm]
        fig3 = go.Figure(go.Bar(
            x=feat_vals, y=feat_names, orientation='h',
            marker=dict(color=bcolors, line=dict(width=0)),
            text=[f"{v:.1f}" for v in feat_vals],
            textposition='outside',
            textfont=dict(family='Space Mono', size=9, color='#4A6080'),
        ))
        layout = dict(THEME)
        layout['height'] = 240
        layout['xaxis'] = dict(**THEME['xaxis'], showticklabels=False)
        layout['bargap'] = 0.35
        fig3.update_layout(**layout)
        st.plotly_chart(fig3, width='stretch')
    else:
        st.markdown('<div style="height:240px;display:flex;align-items:center;'
                    'justify-content:center;color:#1A2840;font-family:Space Mono;'
                    'font-size:.8rem;border:1px solid #0F1E33;border-radius:10px;">'
                    'No packets yet</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="sec-hdr">Rolling Congestion Rate (10-pkt window)</div>', unsafe_allow_html=True)
    if len(labels_arr) > 5:
        rates = []
        for i in range(len(labels_arr)):
            s = max(0, i-9)
            rates.append(float(labels_arr[s:i+1].mean()))
        fig4 = go.Figure()
        fig4.add_hrect(y0=0.5, y1=1.0, fillcolor='rgba(255,68,68,0.05)', line_width=0)
        fig4.add_trace(go.Scatter(
            x=list(range(len(rates))), y=rates,
            mode='lines', fill='tozeroy',
            line=dict(color='#A855F7', width=2),
            fillcolor='rgba(168,85,247,0.07)',
        ))
        fig4.add_hline(y=0.5, line_dash='dot', line_color='#FF4444',
                       line_width=1, opacity=0.4)
        layout = dict(THEME)
        layout['height'] = 240
        layout['yaxis'] = dict(**THEME['yaxis'], range=[0,1], title='Rate')
        layout['xaxis'] = dict(**THEME['xaxis'], title='Packet Index')
        fig4.update_layout(**layout)
        st.plotly_chart(fig4, width='stretch')
    else:
        st.markdown('<div style="height:240px;display:flex;align-items:center;'
                    'justify-content:center;color:#1A2840;font-family:Space Mono;'
                    'font-size:.8rem;border:1px solid #0F1E33;border-radius:10px;">'
                    'Collecting data...</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PACKET FEED LOG
# ══════════════════════════════════════════════════════════════════════════════

st.markdown('<div class="sec-hdr">Packet Feed Log · Last 30 packets</div>', unsafe_allow_html=True)
if ts_list:
    rows = ""
    for i in range(min(30, len(pkts_list))):
        idx  = -(i+1)
        p    = pkts_list[idx]
        prob = float(probs_arr[idx]) if abs(idx) <= len(probs_arr) else 0.0
        lbl  = "CONGESTED" if prob >= threshold else "normal   "
        cls  = "fc" if prob >= threshold else "fn"
        dot  = "●" if prob >= threshold else "○"
        rows += (
            f'<div class="{cls}">{dot} [{ts_list[idx]}] {lbl} '
            f'P={prob:.3f} &nbsp;|&nbsp; '
            f'size={p.get("packet_size",0):.0f}B &nbsp; '
            f'rto={p.get("rto",0):.0f}ms &nbsp; '
            f'win={p.get("window_size",0):.0f} &nbsp; '
            f'retrans={p.get("retransmission",0):.0f} &nbsp; '
            f'rtt={p.get("rtt",0):.0f}ms'
            f'</div>'
        )
    st.markdown(f'<div class="feed-box">{rows}</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="feed-box"><span style="color:#1A2840;">'
                'Waiting for packets — press ▶ Start...</span></div>',
                unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# AUTO REFRESH — only when running
# ══════════════════════════════════════════════════════════════════════════════

if G.running:
    time.sleep(0.4)
    st.rerun()