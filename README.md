# 📡 CongestionNet — Real-Time ML Network Telemetry & Congestion Detection

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-1.2+-orange.svg)](https://scikit-learn.org/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-blue.svg)](https://www.docker.com/)
[![CI/CD Pipeline](https://github.com/KushalThakare/Congestion/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/KushalThakare/Congestion/actions)

**CongestionNet** is a production-grade, end-to-end Machine Learning network telemetry product. It analyzes live TCP packet streams, performs **sliding-window feature smoothing**, detects queueing delay & bufferbloat, and predicts network congestion risks in real time using **FastAPI WebSockets** and a trained **Random Forest Classifier**.

---

## 🗺️ Architectural Implementation Phases

### Phase 1: Real-Time Feature Engineering & Smoothing
- **Sliding Window Aggregator** (`src/aggregator.py`): Eliminates volatile single-packet noise via a 1.5-second time-bounded rolling window buffer.
- **6 Extracted Windowed Features**:
  1. `average_rtt`: Rolling mean of valid TCP Round-Trip Times (ms).
  2. `retransmission_rate`: Ratio of TCP retransmitted packets to total packets.
  3. `throughput_mbps`: Data throughput in Mbps calculated over the window duration.
  4. `window_size_trend`: Rate of change of `tcp.window_size` over time.
  5. `average_rto`: Rolling mean of TCP Retransmission Timeouts (ms).
  6. `current_window_size`: Latest TCP window size (bytes).

### Phase 2: Autoconfiguration & Interface Auto-Discovery
- **Path Autolocation**: `find_tshark_path()` automatically detects TShark binaries across system `PATH` and default OS installation directories.
- **REST Discovery API**: `GET /api/interfaces` scans physical system network adapters (`Wi-Fi`, `Ethernet`) via `psutil` kernel telemetry.
- **Dynamic Frontend Selector**: UI dynamically populates active network interfaces with zero hardcoded paths.

### Phase 3: Real-World Training Data Collection & Pipeline
- **Traffic Recorder CLI** (`src/record_traffic.py`): Records labeled `.pcap` sessions (`normal`, `high_throughput`, `congested`).
- **Telemetry Feature Extractor** (`src/pcap_processor.py`): Extracted **4,980 organic PCAP telemetry samples** from real Wi-Fi network captures.
- **Model Fine-Tuning**: Retrained Random Forest model on organic network behavior using `python main.py --real-pcap`.

### Phase 4: Native Capture, Containerization & CI/CD
- **Native OS Capture Engine**: Zero-dependency live network capture directly from OS kernel adapters.
- **Dockerization**: Production `Dockerfile` and `docker-compose.yml` (`network_mode: "host"`).
- **GitHub Actions CI/CD**: Continuous Integration workflow (`.github/workflows/ci-cd.yml`) for automated linting, testing, and Docker image validation on every push.

---

## 📊 Model Performance Metrics

| Metric | Score |
|---|---|
| **Test Accuracy** | **98.39%** |
| **ROC-AUC Score** | **0.9989** |
| **5-Fold Cross Validation F1-Score** | **0.9725 ± 0.0072** |
| **Normal Traffic F1-Score** | **0.99** |
| **Congested Traffic F1-Score** | **0.97** |
| **Training Samples** | **4,980 Real-World Telemetry Samples** |

---

## 🔌 API Reference

### `GET /api/interfaces`
Returns system TShark installation status and active network adapters.
```json
{
  "tshark_path": "C:\\Program Files\\Wireshark\\tshark.exe",
  "tshark_available": true,
  "interfaces": [
    { "id": "Wi-Fi", "name": "Wi-Fi (Native Live)" },
    { "id": "Ethernet", "name": "Ethernet (Native Live)" }
  ]
}
```

### `WebSocket /ws`
Establishes a bi-directional streaming connection for real-time packet telemetry and ML predictions.

---

## 🚀 Quickstart Guide

### Option 1: Run Locally (Python 3.11)
```bash
# Clone repository
git clone https://github.com/KushalThakare/Congestion.git
cd Congestion

# Install requirements
pip install -r requirements.txt

# Start Uvicorn Server
python -m uvicorn app:app --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser and click **Start Analysis**.

---

### Option 2: Run via Docker
```bash
# Build production Docker image
docker build -t congestion-net:latest .

# Run with host networking mode
docker run -d --name congestion_app --network host congestion-net:latest
```

---

### Option 3: Record Traffic & Retrain Model
```bash
# Record Wi-Fi traffic sessions
python src/record_traffic.py --label normal --duration 180 --interface "Wi-Fi"
python src/record_traffic.py --label high_throughput --duration 180 --interface "Wi-Fi"
python src/record_traffic.py --label congested --duration 180 --interface "Wi-Fi"

# Retrain model on recorded PCAPs
python main.py --real-pcap
```

---

## 🌐 Deployment Guide (Hosting Options)

### 1. Render / Railway / Koyeb (Recommended Free Web Hosting)
1. Link your GitHub repository `KushalThakare/Congestion` to **[Render.com](https://render.com)** or **[Railway.app](https://railway.app)**.
2. Select **Web Service** -> Build Command: `pip install -r requirements.txt` -> Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`.
3. Render/Railway will host your FastAPI server and WebSockets live on a public HTTPS URL.

### 2. Docker Container / VPS / AWS EC2 / DigitalOcean
1. Spin up an Ubuntu / Debian VPS.
2. Clone repository and run `docker-compose up -d --build`.
3. Access your live application at `http://your-server-ip:8000`.

---

## 🛠️ Tech Stack
- **Backend & WebSockets**: FastAPI, Uvicorn, Python 3.11
- **Machine Learning & Analytics**: Scikit-Learn, Pandas, NumPy, Joblib
- **Network Telemetry**: Psutil, TShark, Sliding Window Aggregator
- **Frontend UI**: Vanilla JavaScript (ES6+), Chart.js, HTML5, Vanilla CSS (Nordic Minimalist Theme)
- **DevOps & CI/CD**: Docker, Docker Compose, GitHub Actions
