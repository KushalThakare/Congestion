import time
from collections import deque
import numpy as np


class SlidingWindowAggregator:
    """
    In-memory sliding window buffer (default 1.5s) to eliminate packet-level
    prediction noise and compute rolling statistical features.
    """
    def __init__(self, window_size_sec: float = 1.5):
        self.window_size_sec = window_size_sec
        self.buffer = deque()

    def reset(self):
        self.buffer.clear()

    def add_packet(self, pkt: dict, current_time: float = None) -> dict:
        if current_time is None:
            current_time = time.time()

        self.buffer.append((current_time, pkt))

        # Remove packets older than window_size_sec
        cutoff = current_time - self.window_size_sec
        while self.buffer and self.buffer[0][0] < cutoff:
            self.buffer.popleft()

        return self.compute_features(current_time)

    def compute_features(self, current_time: float = None) -> dict:
        if not self.buffer:
            return {
                'average_rtt': 0.0,
                'retransmission_rate': 0.0,
                'throughput_mbps': 0.0,
                'window_size_trend': 0.0,
                'average_rto': 0.0,
                'current_window_size': 0.0
            }

        times = [t for t, _ in self.buffer]
        pkts = [p for _, p in self.buffer]
        total_pkts = len(pkts)

        if current_time is None:
            current_time = times[-1]

        start_time = times[0]
        # Use actual duration in window, capped at a reasonable lower bound to avoid division by zero
        duration = max(current_time - start_time, 0.05)

        # 1. average_rtt: Rolling mean of valid TCP Round-Trip Times
        rtts = [p['rtt'] for p in pkts if p.get('rtt', 0) > 0]
        average_rtt = float(np.mean(rtts)) if rtts else float(pkts[-1].get('rtt', 0.0))

        # 2. retransmission_rate: Ratio of TCP retransmission packets to total TCP packets
        retrans_count = sum(1 for p in pkts if p.get('retransmission', 0) > 0)
        retransmission_rate = float(retrans_count / total_pkts)

        # 3. throughput_mbps: Total packet bytes parsed divided by window duration (in Mbps)
        total_bytes = sum(p.get('packet_size', 0) for p in pkts)
        throughput_mbps = float((total_bytes * 8.0) / (duration * 1_000_000.0))

        # 4. window_size_trend: Rate of change of tcp.window_size
        first_win = pkts[0].get('window_size', 0.0)
        last_win = pkts[-1].get('window_size', 0.0)
        window_size_trend = float((last_win - first_win) / duration)

        # 5. average_rto: Rolling mean of RTO
        rtos = [p['rto'] for p in pkts if 'rto' in p]
        average_rto = float(np.mean(rtos)) if rtos else float(pkts[-1].get('rto', 0.0))

        # 6. current_window_size: Latest window size
        current_window_size = float(pkts[-1].get('window_size', 0.0))

        return {
            'average_rtt': average_rtt,
            'retransmission_rate': retransmission_rate,
            'throughput_mbps': throughput_mbps,
            'window_size_trend': window_size_trend,
            'average_rto': average_rto,
            'current_window_size': current_window_size
        }
