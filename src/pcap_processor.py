import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import glob
import subprocess
import pandas as pd
from app import find_tshark_path
from src.aggregator import SlidingWindowAggregator


def sf(val, default=0.0):
    try:
        return float(val.strip()) if val.strip() else default
    except Exception:
        return default


def process_pcap_file(pcap_path: str, is_congested: int, tshark_path: str = None) -> pd.DataFrame:
    """
    Parse a PCAP file using tshark, feed packets through SlidingWindowAggregator,
    and return a DataFrame of rolling features.
    """
    if not tshark_path:
        tshark_path = find_tshark_path()

    if not tshark_path or not os.path.exists(tshark_path):
        raise FileNotFoundError("tshark binary not found. Cannot parse PCAP files.")

    cmd = [
        tshark_path,
        '-r', pcap_path,
        '-Y', 'tcp',
        '-c', '25000',
        '-T', 'fields',
        '-e', 'frame.len',
        '-e', 'tcp.analysis.rto',
        '-e', 'tcp.analysis.retransmission',
        '-e', 'tcp.window_size',
        '-e', 'frame.time_delta',
        '-e', 'tcp.analysis.ack_rtt',
        '-e', 'frame.time_epoch',
        '-E', 'separator=,',
    ]

    print(f"Parsing PCAP: {os.path.basename(pcap_path)} (label: {is_congested})...")
    res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
    if res.returncode != 0:
        print(f"Warning: tshark failed on {pcap_path}: {res.stderr}")
        return pd.DataFrame()

    lines = res.stdout.splitlines()
    aggregator = SlidingWindowAggregator(window_size_sec=1.5)
    rows = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split(',')
        if len(parts) < 6:
            continue

        time_delta = sf(parts[4], 0.01)
        epoch_time = sf(parts[6], 0.0) if len(parts) >= 7 else None

        pkt = dict(
            packet_size   = sf(parts[0]),
            rto           = sf(parts[1]) * 1000.0,
            retransmission= 1.0 if parts[2].strip() else 0.0,
            window_size   = sf(parts[3]),
            packet_rate   = 1.0 / time_delta if time_delta > 0 else 100.0,
            rtt           = sf(parts[5]) * 1000.0,
        )

        wf = aggregator.add_packet(pkt, current_time=epoch_time if epoch_time > 0 else None)
        wf['congestion'] = is_congested
        rows.append(wf)

    print(f"  Extracted {len(rows)} windowed samples from {os.path.basename(pcap_path)}")
    return pd.DataFrame(rows)


def process_all_pcaps(pcap_dir="data/pcaps", save_path="data/real_world_dataset.csv") -> pd.DataFrame:
    """
    Process all PCAP files in pcap_dir and generate real_world_dataset.csv.
    Files containing 'congest' in name are labeled as 1, others as 0.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    pcap_files = glob.glob(os.path.join(pcap_dir, "*.pcap*"))

    if not pcap_files:
        print(f"No PCAP files found in {pcap_dir}.")
        return pd.DataFrame()

    dfs = []
    tshark_path = find_tshark_path()

    for path in pcap_files:
        filename = os.path.basename(path).lower()
        is_congested = 1 if ('congest' in filename or 'drop' in filename or 'delay' in filename) else 0
        df = process_pcap_file(path, is_congested=is_congested, tshark_path=tshark_path)
        if not df.empty:
            dfs.append(df)

    if not dfs:
        print("No valid data extracted from PCAPs.")
        return pd.DataFrame()

    combined_df = pd.concat(dfs, ignore_index=True)
    combined_df.to_csv(save_path, index=False)
    print(f"\nReal-world PCAP dataset generated -> {save_path} ({len(combined_df)} samples)")
    print(f"Congestion rate: {combined_df['congestion'].mean():.2%}")
    return combined_df


if __name__ == "__main__":
    process_all_pcaps()
