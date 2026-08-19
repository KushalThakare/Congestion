import pandas as pd
import numpy as np
import os
import urllib.request
from src.aggregator import SlidingWindowAggregator

# NSL-KDD column names
NSL_KDD_COLUMNS = [
    'duration', 'protocol_type', 'service', 'flag', 'src_bytes', 'dst_bytes',
    'land', 'wrong_fragment', 'urgent', 'hot', 'num_failed_logins', 'logged_in',
    'num_compromised', 'root_shell', 'su_attempted', 'num_root', 'num_file_creations',
    'num_shells', 'num_access_files', 'num_outbound_cmds', 'is_host_login',
    'is_guest_login', 'count', 'srv_count', 'serror_rate', 'srv_serror_rate',
    'rerror_rate', 'srv_rerror_rate', 'same_srv_rate', 'diff_srv_rate',
    'srv_diff_host_rate', 'dst_host_count', 'dst_host_srv_count',
    'dst_host_same_srv_rate', 'dst_host_diff_srv_rate', 'dst_host_same_src_port_rate',
    'dst_host_srv_diff_host_rate', 'dst_host_serror_rate', 'dst_host_srv_serror_rate',
    'dst_host_rerror_rate', 'dst_host_srv_rerror_rate', 'label', 'difficulty'
]

DOS_ATTACKS = {'neptune', 'smurf', 'pod', 'teardrop', 'land', 'back', 'apache2',
               'udpstorm', 'processtable', 'mailbomb'}

NSL_KDD_TRAIN_URL = "https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTrain+.txt"
NSL_KDD_TEST_URL  = "https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTest+.txt"


def download_nsl_kdd(data_dir="data"):
    os.makedirs(data_dir, exist_ok=True)
    train_path = os.path.join(data_dir, "KDDTrain+.txt")
    test_path  = os.path.join(data_dir, "KDDTest+.txt")

    for url, path in [(NSL_KDD_TRAIN_URL, train_path), (NSL_KDD_TEST_URL, test_path)]:
        if not os.path.exists(path):
            print(f"Downloading {os.path.basename(path)}...")
            try:
                urllib.request.urlretrieve(url, path)
                print(f"  Saved to {path}")
            except Exception as e:
                print(f"  Download failed: {e}")
                return False
        else:
            print(f"  {os.path.basename(path)} already exists, skipping download.")
    return True


def load_nsl_kdd(data_dir="data"):
    train_path = os.path.join(data_dir, "KDDTrain+.txt")
    test_path  = os.path.join(data_dir, "KDDTest+.txt")

    train_df = pd.read_csv(train_path, header=None, names=NSL_KDD_COLUMNS)
    test_df  = pd.read_csv(test_path,  header=None, names=NSL_KDD_COLUMNS)

    for df in [train_df, test_df]:
        df['congestion'] = df['label'].apply(
            lambda x: 1 if x.strip().lower() in DOS_ATTACKS else 0
        )
        df.drop(columns=['label', 'difficulty'], inplace=True)

    cat_cols = ['protocol_type', 'service', 'flag']
    train_df = pd.get_dummies(train_df, columns=cat_cols)
    test_df  = pd.get_dummies(test_df,  columns=cat_cols)

    train_df, test_df = train_df.align(test_df, join='left', axis=1, fill_value=0)

    print(f"NSL-KDD loaded — Train: {len(train_df)} rows | Test: {len(test_df)} rows")
    print(f"Congestion rate — Train: {train_df['congestion'].mean():.2%} | "
          f"Test: {test_df['congestion'].mean():.2%}")

    return train_df, test_df


def generate_synthetic_dataset(n=6000, save_path="data/dataset.csv"):
    """
    Realistic time-series synthetic dataset aggregated using a 1.5-second sliding window.
    Features: average_rtt, retransmission_rate, throughput_mbps, window_size_trend, average_rto, current_window_size.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    rng = np.random.default_rng(42)

    aggregator = SlidingWindowAggregator(window_size_sec=1.5)
    rows = []

    current_time = 0.0
    phase = 0  # 0: normal, 1: congested, 2: recovery

    for i in range(n):
        # Change phase every ~70 packets
        if i % 70 == 0:
            phase = (phase + 1) % 3

        if phase == 0:
            # Normal network phase
            dt = rng.uniform(0.005, 0.02)
            pkt = dict(
                packet_size   = float(rng.integers(400, 1460)),
                rto           = float(rng.uniform(40, 160)),
                retransmission= float(rng.poisson(0.02)),
                window_size   = float(rng.integers(45000, 65535)),
                packet_rate   = float(rng.integers(100, 300)),
                rtt           = float(rng.uniform(8, 45)),
            )
            is_congested = 0
        elif phase == 1:
            # Congested network phase (window reduction, high RTT & RTO, retransmissions)
            dt = rng.uniform(0.015, 0.05)
            win = max(3000.0, 65535.0 - ((i % 70) * 800.0) + rng.uniform(-1000, 1000))
            pkt = dict(
                packet_size   = float(rng.integers(60, 400)),
                rto           = float(rng.uniform(800, 2500)),
                retransmission= float(rng.poisson(0.8) + 1),
                window_size   = win,
                packet_rate   = float(rng.integers(700, 1200)),
                rtt           = float(rng.uniform(150, 350)),
            )
            is_congested = 1
        else:
            # Recovery phase (window growing, latency dropping)
            dt = rng.uniform(0.008, 0.025)
            win = min(50000.0, 10000.0 + ((i % 70) * 600.0) + rng.uniform(-1000, 1000))
            pkt = dict(
                packet_size   = float(rng.integers(200, 1200)),
                rto           = float(rng.uniform(150, 600)),
                retransmission= float(rng.poisson(0.1)),
                window_size   = win,
                packet_rate   = float(rng.integers(200, 600)),
                rtt           = float(rng.uniform(35, 110)),
            )
            is_congested = 0

        current_time += dt
        feats = aggregator.add_packet(pkt, current_time=current_time)
        feats['congestion'] = is_congested
        rows.append(feats)

    data = pd.DataFrame(rows)
    data.to_csv(save_path, index=False)
    print(f"Synthetic windowed dataset saved -> {save_path}")
    print(f"Congestion rate: {data['congestion'].mean():.2%} ({data['congestion'].sum()} / {n} samples)")
    return data


def load_pcap_dataset(pcap_dir="data/pcaps", save_path="data/real_world_dataset.csv"):
    """Load and extract rolling window features from organic PCAP files."""
    from src.pcap_processor import process_all_pcaps
    df = process_all_pcaps(pcap_dir=pcap_dir, save_path=save_path)
    return df


def generate_dataset(use_real=False, use_pcap=False, data_dir="data"):
    if use_pcap:
        df = load_pcap_dataset(pcap_dir=os.path.join(data_dir, "pcaps"),
                               save_path=os.path.join(data_dir, "real_world_dataset.csv"))
        if not df.empty:
            return df, None
        print("Falling back to synthetic time-series generator because no PCAP data was found.")

    if use_real:
        print("Note: Real-time dashboard uses packet-level features. NSL-KDD dataset is connection-level and incompatible with live capture.")
        print("Forcing generation of packet-level synthetic dataset for dashboard compatibility.")

    data = generate_synthetic_dataset(save_path=os.path.join(data_dir, "dataset.csv"))
    return data, None


if __name__ == "__main__":
    generate_dataset(use_real=True)


