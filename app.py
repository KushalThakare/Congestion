import asyncio
import time
import os
import joblib
import pandas as pd
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

# Load trained Random Forest model
MODEL_PATH = "models/random_forest_congestion.pkl"
if os.path.exists(MODEL_PATH):
    MODEL = joblib.load(MODEL_PATH)
    print(f"Loaded ML model from {MODEL_PATH}")
else:
    raise FileNotFoundError(f"Trained model not found at {MODEL_PATH}. Please run python main.py first.")

app = FastAPI(title="CongestionNet API")

# Ensure static files directory exists
os.makedirs("static", exist_ok=True)

class CaptureManager:
    def __init__(self):
        self.active_task = None
        self.threshold = 0.50

    def set_threshold(self, threshold: float):
        self.threshold = threshold

    async def start(self, websocket: WebSocket, mode: str, tshark_path: str = None, iface: str = None):
        await self.stop()
        if mode == "simulate":
            self.active_task = asyncio.create_task(self.simulate_loop(websocket))
        elif mode == "live":
            self.active_task = asyncio.create_task(self.tshark_loop(websocket, tshark_path, iface))

    async def stop(self):
        if self.active_task and not self.active_task.done():
            self.active_task.cancel()
            try:
                await self.active_task
            except asyncio.CancelledError:
                pass
        self.active_task = None

    async def simulate_loop(self, websocket: WebSocket):
        rng = np.random.default_rng()
        t = 0
        try:
            while True:
                phase = (t // 25) % 3      # 0=normal, 1=congested, 2=recovery
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

                # Inference
                features = pd.DataFrame([pkt])
                prob = float(MODEL.predict_proba(features)[0][1])
                label = 1 if prob >= self.threshold else 0

                await websocket.send_json({
                    "type": "packet",
                    "data": pkt,
                    "probability": prob,
                    "label": label,
                    "timestamp": time.strftime("%H:%M:%S")
                })
                t += 1
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            pass

    async def tshark_loop(self, websocket: WebSocket, tshark_path: str, iface: str):
        if not tshark_path:
            tshark_path = "tshark"

        cmd = [tshark_path]
        if iface and iface.strip():
            cmd.extend(['-i', iface.strip()])
        cmd.extend([
            '-T', 'fields',
            '-e', 'frame.len',
            '-e', 'tcp.analysis.rto',
            '-e', 'tcp.analysis.retransmission',
            '-e', 'tcp.window_size',
            '-e', 'frame.time_delta',
            '-e', 'tcp.analysis.ack_rtt',
            '-E', 'separator=,',
            '-l',
        ])

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        except Exception as e:
            await websocket.send_json({
                "type": "error",
                "message": f"Failed to start tshark: {e}"
            })
            return

        try:
            while True:
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                parts = line.split(',')
                if len(parts) < 6:
                    continue

                def sf(v, d=0.0):
                    try:
                        return float(v) if v.strip() else d
                    except:
                        return d

                time_delta = sf(parts[4], 0.01)
                pkt = dict(
                    packet_size   = sf(parts[0]),
                    rto           = sf(parts[1]) * 1000.0,
                    retransmission= 1.0 if parts[2].strip() else 0.0,
                    window_size   = sf(parts[3]),
                    packet_rate   = 1.0 / time_delta if time_delta > 0 else 100.0,
                    rtt           = sf(parts[5]) * 1000.0,
                )

                # Inference
                features = pd.DataFrame([pkt])
                prob = float(MODEL.predict_proba(features)[0][1])
                label = 1 if prob >= self.threshold else 0

                await websocket.send_json({
                    "type": "packet",
                    "data": pkt,
                    "probability": prob,
                    "label": label,
                    "timestamp": time.strftime("%H:%M:%S")
                })
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await websocket.send_json({
                "type": "error",
                "message": f"tshark capture error: {e}"
            })
        finally:
            if proc and proc.returncode is None:
                try:
                    proc.terminate()
                    await proc.wait()
                except:
                    pass

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    manager = CaptureManager()
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            if action == "start":
                mode = data.get("mode", "simulate")
                tshark_path = data.get("tshark_path", "")
                iface = data.get("interface", "")
                threshold = data.get("threshold", 0.50)
                manager.set_threshold(threshold)
                await manager.start(websocket, mode, tshark_path, iface)
                await websocket.send_json({
                    "type": "status",
                    "running": True,
                    "mode": mode
                })
            elif action == "stop":
                await manager.stop()
                await websocket.send_json({
                    "type": "status",
                    "running": False,
                    "mode": None
                })
            elif action == "set_threshold":
                threshold = data.get("threshold", 0.50)
                manager.set_threshold(threshold)
    except WebSocketDisconnect:
        await manager.stop()
    except Exception as e:
        await manager.stop()
        print(f"WebSocket error: {e}")

# Serve UI from static folder at root
app.mount("/", StaticFiles(directory="static", html=True), name="static")
