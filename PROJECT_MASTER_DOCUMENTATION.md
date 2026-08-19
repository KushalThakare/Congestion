# 📘 CongestionNet — Master Technical Manual & Architectural Documentation

> **Project Title:** CongestionNet — Real-Time ML Network Telemetry & Congestion Detection System  
> **Repository:** [https://github.com/KushalThakare/Congestion](https://github.com/KushalThakare/Congestion)  
> **Document Purpose:** Comprehensive end-to-end technical reference for group members, project evaluators, and system operators.

---

## 📄 Table of Contents
1. [Executive Summary & Core Mission](#1-executive-summary--core-mission)
2. [The Problem Statement & Why It Matters](#2-the-problem-statement--why-it-matters)
3. [Target Audience & Who This Project Helps](#3-target-audience--who-this-project-helps)
4. [Tech Stack Breakdown & Component Roles](#4-tech-stack-breakdown--component-roles)
5. [System Architecture & 4-Phase Engineering Pipeline](#5-system-architecture--4-phase-engineering-pipeline)
6. [Feature Engineering & Mathematical Formulas](#6-feature-engineering--mathematical-formulas)
7. [Machine Learning Model & Training Methodology](#7-machine-learning-model--training-methodology)
8. [API & WebSocket Protocol Reference](#8-api--websocket-protocol-reference)
9. [Operator & Execution Manual (How to Run Everything)](#9-operator--execution-manual-how-to-run-everything)
10. [Project Defense & Interview Q&A Guide for Group Members](#10-project-defense--interview-qa-guide-for-group-members)

---

## 1. Executive Summary & Core Mission

**CongestionNet** is a production-grade, full-stack Machine Learning and network telemetry application. It monitors live TCP packet streams directly from physical network interfaces (Wi-Fi, Ethernet), eliminates packet-level jitter using a **1.5-second sliding window aggregator**, and predicts network congestion risks in real time using a retrained **Random Forest Classifier** achieving **98.39% Accuracy** and **0.9989 ROC-AUC**.

The project features:
- **Zero-Dependency Native OS Capture**: Reads live packet metrics directly from kernel network adapters without requiring external tools.
- **Organic PCAP Model Training**: Trained on 4,980 real-world network packet samples recorded under normal, high-speed, and artificial congestion conditions.
- **Production Containerization & CI/CD**: Containerized via Docker (`network_mode: "host"`) and automated via GitHub Actions.

---

## 2. The Problem Statement & Why It Matters

### The Core Problem: Network Congestion & Bufferbloat
In modern computer networks, when network traffic bursts exceed link capacity, routers buffer excess packets in memory queues. If queues remain full for too long:
1. **Latency Spikes (Bufferbloat)**: Round-Trip Times (RTT) jump from 15ms to 300ms+, causing lag in video calls and online gaming.
2. **Packet Loss & Retransmissions**: Routers drop incoming packets when buffers overflow, triggering TCP retransmission storms and slowing down file transfers.
3. **Volatile Raw Packet Noise**: Individual network packets jump rapidly between 60 Bytes and 1500 Bytes, and TCP Round-Trip Times (RTT) are only present on ACK packets. Running ML predictions on isolated raw packets leads to high jitter and false alarm congestion warnings.

### How CongestionNet Solves It
CongestionNet continuously samples network metrics, feeds them through an **in-memory 1.5-second sliding window aggregator** to smooth out noise, and runs a Machine Learning model every 50-80ms to predict congestion **before severe packet loss occurs**.

---

## 3. Target Audience & Who This Project Helps

1. **Network Engineers & System Administrators**:
   - Helps monitor router/switch queue health and detect link saturation early without manual packet inspection.
2. **DevOps & Site Reliability Engineers (SREs)**:
   - Provides real-time telemetry metrics for cloud microservices to detect network bottlenecking between servers.
3. **Internet Service Providers (ISPs) & Network Operators**:
   - Assists in automated Quality of Service (QoS) management and dynamic bandwidth throttling detection.
4. **Gamers, VoIP Users & Video Conferencing Platforms (Zoom/Teams)**:
   - Helps diagnose whether latency spikes are caused by home network queueing or remote server lag.

---

## 4. Tech Stack Breakdown & Component Roles

Every technology in this project was selected for a specific engineering purpose:

| Technology | Role in Project | Why We Used It |
|---|---|---|
| **Python 3.11** | Core Language | Primary language for Machine Learning data science, network socket telemetry, and backend APIs. |
| **FastAPI** | Web Framework | High-performance Python async REST API framework; serves static frontend files and manages WebSockets. |
| **Uvicorn** | ASGI Server | Lightning-fast asynchronous server gateway that keeps persistent WebSockets open 24/7. |
| **Scikit-Learn** | Machine Learning | Implements `RandomForestClassifier`, `StandardScaler`, and evaluation metrics (`roc_auc_score`, `f1_score`). |
| **Pandas & NumPy** | Data Processing | Handles numerical array operations, dataframe feature scaling, and CSV dataset management. |
| **Psutil** | Native Network Sniffing | Interrogates OS kernel network adapters (`Wi-Fi`, `Ethernet`) to retrieve real-time byte and packet counts without third-party dependencies. |
| **TShark / Wireshark** | PCAP Telemetry Capture | CLI tool used to record `.pcap` traffic sessions and parse deep TCP header fields (`tcp.analysis.rto`, `tcp.window_size`, `tcp.analysis.ack_rtt`). |
| **Chart.js** | Live UI Visualizations | Renders responsive real-time line charts, gauge meters, and dynamic feature bar charts on the web UI. |
| **Vanilla HTML5 / CSS3 / ES6 JS** | Frontend Interface | Lightweight, zero-framework web dashboard adhering to a clean Nordic Minimalist dark design. |
| **Docker & Docker Compose** | Containerization | Packages the application into an isolated container that runs with `--network host` privileges on any server. |
| **GitHub Actions** | CI/CD Automation | Automatically lints code, tests API endpoints, validates ML pipelines, and builds Docker images on every `git push`. |

---

## 5. System Architecture & 4-Phase Engineering Pipeline

```
  ┌─────────────────────────────────────────────────────────────┐
  │              PHYSICAL NETWORK INTERFACE                     │
  │              (Wi-Fi / Ethernet / Local Adapter)             │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ Live Packet Telemetry
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │               SLIDING WINDOW AGGREGATOR                     │
  │     (1.5-Second In-Memory Buffer in src/aggregator.py)      │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ 6 Windowed Rolling Features
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │              RANDOM FOREST ML MODEL INFERENCE               │
  │         (models/random_forest_congestion.pkl)               │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ Prediction Probability + Label
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                 FASTAPI WEBSOCKET SERVER                    │
  │                 (Real-Time Async Push /ws)                  │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ JSON Data Stream
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                 LIVE DASHBOARD UI (Chart.js)                │
  │       (Real-Time Line Chart, Gauge Meter, Bar Graphs)       │
  └─────────────────────────────────────────────────────────────┘
```

### Phase 1: Real-Time Feature Engineering & Smoothing
- Built `SlidingWindowAggregator` (`src/aggregator.py`) to buffer 1.5 seconds of packet history in RAM.
- Replaced volatile raw packet fields with 6 rolling window statistical metrics to achieve 100% training-inference parity.

### Phase 2: Autoconfiguration & Interface Auto-Discovery
- Built `find_tshark_path()` for system-wide binary discovery.
- Created `GET /api/interfaces` REST endpoint to list system network cards dynamically.
- Replaced text inputs with dynamic UI dropdown menus.

### Phase 3: Real-World Training Data Collection
- Developed `src/record_traffic.py` CLI recorder and `src/pcap_processor.py` telemetry parser.
- Recorded organic Wi-Fi traffic sessions (`normal.pcap`, `high_throughput.pcap`, `congested.pcap`).
- Extracted 4,980 real-world telemetry samples and retrained the Random Forest model (**98.39% Accuracy**).

### Phase 4: Native Capture, Containerization & CI/CD
- Implemented `native_live_loop` in `app.py` for zero-dependency OS network scanning.
- Created production `Dockerfile` and `docker-compose.yml` (`network_mode: "host"`).
- Established GitHub Actions CI/CD workflow (`.github/workflows/ci-cd.yml`).

---

## 6. Feature Engineering & Mathematical Formulas

The model uses 6 engineered rolling window statistics computed over a **1.5-second time window** ($W = 1.5\text{s}$):

1. **`average_rtt` (ms)**: Rolling mean of valid Round-Trip Times:
   $$\text{average\_rtt} = \frac{1}{N_{\text{valid}}} \sum_{i \in \text{valid RTTs}} \text{RTT}_i$$

2. **`retransmission_rate` (ratio)**: Ratio of retransmitted TCP packets to total packets:
   $$\text{retransmission\_rate} = \frac{\text{Count}(\text{retransmission} > 0)}{N_{\text{total\_packets\_in\_window}}}$$

3. **`throughput_mbps` (Mbps)**: Total data transferred per second in Megabits:
   $$\text{throughput\_mbps} = \frac{(\sum \text{packet\_bytes}) \times 8}{\text{duration\_seconds} \times 1,000,000}$$

4. **`window_size_trend` (Bytes/sec)**: Rate of change of TCP window size:
   $$\text{window\_size\_trend} = \frac{\text{window\_size}_{\text{latest}} - \text{window\_size}_{\text{oldest}}}{\text{duration\_seconds}}$$

5. **`average_rto` (ms)**: Rolling mean of Retransmission Timeout limits:
   $$\text{average\_rto} = \frac{1}{N} \sum_{i=1}^{N} \text{RTO}_i$$

6. **`current_window_size` (Bytes)**: The latest advertised TCP window size in the window.

---

## 7. Machine Learning Model & Training Methodology

### Algorithm Choice: Random Forest Classifier
- **Why Random Forest?** Non-linear decision boundaries, handles feature scaling gracefully, highly resistant to overfitting, and provides fast inference times (<1ms per prediction).
- **Hyperparameters**: `n_estimators=100`, `max_depth=15`, `class_weight='balanced'`, `random_state=42`.

### Evaluation Results

```
=======================================================
         NETWORK CONGESTION DETECTION — RESULTS
=======================================================
  Accuracy  : 0.9839 (98.39%)
  ROC-AUC   : 0.9989

Classification Report:
               precision    recall  f1-score   support

   Normal (0)       0.99      0.99      0.99       732
Congested (1)       0.97      0.97      0.97       264

     accuracy                           0.98       996
    macro avg       0.98      0.98      0.98       996
 weighted avg       0.98      0.98      0.98       996
```

---

## 8. API & WebSocket Protocol Reference

### REST Endpoints
- **`GET /api/interfaces`**: Discovers active network cards and binary paths.
- **`GET /`**: Serves static HTML dashboard.

### WebSocket Endpoint (`/ws`)
- **Action Messages Sent by Client**:
  - `{"action": "start", "mode": "live", "interface": "Wi-Fi", "threshold": 0.50}`
  - `{"action": "stop"}`
  - `{"action": "set_threshold", "threshold": 0.65}`
- **Payload Broadcast by Server**:
  ```json
  {
    "type": "packet",
    "data": { "packet_size": 1420, "rtt": 22.4, "window_size": 64240 },
    "windowed_features": {
      "average_rtt": 24.1,
      "retransmission_rate": 0.0,
      "throughput_mbps": 4.52,
      "window_size_trend": 120.0,
      "average_rto": 80.0,
      "current_window_size": 64240
    },
    "probability": 0.08,
    "label": 0,
    "timestamp": "23:45:12"
  }
  ```

---

## 9. Operator & Execution Manual (How to Run Everything)

### A. Run Dashboard Locally
```bash
cd "e:\Out Study\congestion control\Congestion"
python -m uvicorn app:app --port 8000
```
Open **`http://localhost:8000`** and click **Start Analysis**.

### B. Record Wi-Fi Traffic Sessions
```bash
python src/record_traffic.py --label normal --duration 180 --interface "Wi-Fi"
python src/record_traffic.py --label high_throughput --duration 180 --interface "Wi-Fi"
python src/record_traffic.py --label congested --duration 180 --interface "Wi-Fi"
```

### C. Retrain Model on Real PCAPs
```bash
python main.py --real-pcap
```

---

## 10. Project Defense & Interview Q&A Guide for Group Members

### Q1: What is the main objective of CongestionNet?
**Answer:** CongestionNet monitors live network packet traffic in real time and uses Machine Learning to predict network congestion and bufferbloat before severe packet drops occur.

### Q2: Why did we use a Sliding Window Aggregator instead of predicting on raw single packets?
**Answer:** Raw single packets are extremely noisy and volatile (e.g., RTT is only present on TCP ACK packets, packet sizes jump between 60B and 1500B instantly). The 1.5-second sliding window smooths out packet jitter and computes rolling metrics, ensuring stable ML predictions.

### Q3: What Machine Learning algorithm was used and why?
**Answer:** We used a **Random Forest Classifier** (100 decision trees). It handles non-linear feature relationships well, executes sub-millisecond predictions, and achieved **98.39% accuracy** and a **0.9989 ROC-AUC score** on organic network traffic.

### Q4: How does the application capture live traffic without Wireshark/TShark?
**Answer:** We built a Native OS Kernel Capture Engine (`app.py`) that uses Python's `psutil` library to read live byte counts, packet rates, error rates, and drop counts directly from operating system network adapters (`Wi-Fi`, `Ethernet`) without requiring third-party tools.

### Q5: How is the application deployed?
**Answer:** It is containerized using **Docker** with `--network host` mode to access physical interfaces, and configured with a **GitHub Actions CI/CD pipeline** for automated testing and deployment on cloud hosts like **Render** or **Railway**.
