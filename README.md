# 📡 CongestionNet — Real-Time ML Network Telemetry & Congestion Detection

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-1.2+-orange.svg)](https://scikit-learn.org/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-blue.svg)](https://www.docker.com/)
[![CI/CD Pipeline](https://github.com/KushalThakare/Congestion/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/KushalThakare/Congestion/actions)

**CongestionNet** is a production-grade, end-to-end Machine Learning and network telemetry product. It analyzes live TCP packet streams, performs **sliding-window feature smoothing**, detects queueing delay & bufferbloat, and predicts network congestion risks in real time using **FastAPI WebSockets** and a retrained **Random Forest Classifier**.

---

## 🌟 Key Architectural Features

1. **Real-Time Sliding Window Feature Aggregator (Phase 1)**
   - Eliminates volatile single-packet noise via a 1.5-second time-bounded rolling window buffer (`src/aggregator.py`).
   - Extracts 6 smoothed rolling metrics: `average_rtt`, `retransmission_rate`, `throughput_mbps`, `window_size_trend`, `average_rto`, `current_window_size`.

2. **Native OS Interface Auto-Discovery & Zero-Dependency Engine (Phase 2 & 4)**
   - Auto-locates active physical adapters (`Wi-Fi`, `Ethernet`) via `psutil` OS kernel telemetry (`GET /api/interfaces`).
   - Runs zero-dependency native network telemetry without requiring external `tshark` binaries.

3. **Organic Real-World PCAP Training Pipeline (Phase 3)**
   - Automated CLI packet recorder (`src/record_traffic.py`) and PCAP telemetry parser (`src/pcap_processor.py`).
   - Trained on **4,980 organic PCAP telemetry samples** (`normal`, `high_throughput`, `congested`).

4. **Production Dockerization & CI/CD Pipeline (Phase 4)**
   - Fully containerized via `Dockerfile` and `docker-compose.yml` (`--network host`).
   - Continuous Integration via **GitHub Actions** (`.github/workflows/ci-cd.yml`).

---

## 📊 Model Performance Metrics

| Metric | Score |
|---|---|
| **Test Accuracy** | **98.39%** |
| **ROC-AUC Score** | **0.9989** |
| **5-Fold Cross Validation F1-Score** | **0.9725 ± 0.0072** |
| **Normal Traffic F1-Score** | **0.99** |
| **Congested Traffic F1-Score** | **0.97** |

---

## 🚀 Quickstart Guide

### 1. Run Locally
```bash
# Clone repository
git clone https://github.com/KushalThakare/Congestion.git
cd Congestion

# Install dependencies
pip install -r requirements.txt

# Start FastAPI Uvicorn Server
python -m uvicorn app:app --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser and click **Start Analysis**!

---

### 2. Run with Docker
```bash
# Build Docker container
docker build -t congestion-net:latest .

# Run container with host network privileges
docker run -d --name congestion_app --network host congestion-net:latest
```

---

### 3. Record Traffic & Retrain Model
```bash
# Record Wi-Fi traffic sessions
python src/record_traffic.py --label normal --duration 180 --interface "Wi-Fi"
python src/record_traffic.py --label high_throughput --duration 180 --interface "Wi-Fi"
python src/record_traffic.py --label congested --duration 180 --interface "Wi-Fi"

# Extract features and retrain ML model
python main.py --real-pcap
```

---

## 🛠️ Tech Stack
- **Backend & WebSockets**: FastAPI, Uvicorn, Python 3.11
- **Machine Learning & Analytics**: Scikit-Learn, Pandas, NumPy, Joblib
- **Network Telemetry**: Psutil, TShark, Sliding Window Aggregator
- **Frontend UI**: Vanilla JavaScript (ES6+), Chart.js, HTML5, Vanilla CSS (Nordic Minimalist Theme)
- **DevOps & CI/CD**: Docker, Docker Compose, GitHub Actions
