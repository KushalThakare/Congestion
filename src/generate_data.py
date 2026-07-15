import pandas as pd
import numpy as np
import os
import urllib.request

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

# NSL-KDD attack types → congestion-relevant labels
# We map DoS (Denial of Service) attacks as congestion=1, normal=0
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

    # Encode categorical columns
    cat_cols = ['protocol_type', 'service', 'flag']
    train_df = pd.get_dummies(train_df, columns=cat_cols)
    test_df  = pd.get_dummies(test_df,  columns=cat_cols)

    # Align columns (test may have fewer categories)
    train_df, test_df = train_df.align(test_df, join='left', axis=1, fill_value=0)

    print(f"NSL-KDD loaded — Train: {len(train_df)} rows | Test: {len(test_df)} rows")
    print(f"Congestion rate — Train: {train_df['congestion'].mean():.2%} | "
          f"Test: {test_df['congestion'].mean():.2%}")

    return train_df, test_df


def generate_synthetic_dataset(n=6000, save_path="data/dataset.csv"):
    """
    Realistic synthetic dataset aligned with live dashboard metrics.
    Features: packet_size, rto, retransmission, window_size, packet_rate, rtt.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    np.random.seed(42)

    packet_size = np.random.randint(60, 1500, n).astype(float)
    rto         = np.random.uniform(50, 400, n)
    retrans     = np.random.poisson(0.3, n).astype(float)
    window_size = np.random.randint(8000, 65535, n).astype(float)
    packet_rate = np.random.randint(100, 1000, n).astype(float)
    rtt         = np.random.uniform(10, 200, n)

    # All features contribute to a congestion score (weighted)
    score = (
        (packet_rate / 1000)        * 0.30 +
        (rto / 400)                 * 0.25 +
        (retrans / 5)               * 0.20 +
        (1 - window_size / 65535)   * 0.15 +
        (rtt / 200)                 * 0.10
    )
    congestion = ((score + np.random.normal(0, 0.06, n)) > 0.50).astype(int)

    # Adjust feature values for congested scenarios to look realistic
    rto[congestion == 1]         *= np.random.uniform(2, 5, congestion.sum())
    window_size[congestion == 1] *= np.random.uniform(0.1, 0.4, congestion.sum())
    retrans[congestion == 1]     += np.random.randint(3, 10, congestion.sum())

    data = pd.DataFrame({
        'packet_size':    packet_size,
        'rto':            rto,
        'retransmission': retrans,
        'window_size':    window_size,
        'packet_rate':    packet_rate,
        'rtt':            rtt,
        'congestion':     congestion,
    })

    data.to_csv(save_path, index=False)
    print(f"Synthetic dataset saved -> {save_path}")
    print(f"Congestion rate: {congestion.mean():.2%} ({congestion.sum()} / {n} samples)")
    return data


def generate_dataset(use_real=True, data_dir="data"):
    """
    Main entry point.
    Since NSL-KDD uses connection-level metrics which are incompatible with 
    real-time packet-level detection, we force the packet-level synthetic generator.
    """
    if use_real:
        print("Note: Real-time dashboard uses packet-level features. NSL-KDD dataset is connection-level and incompatible with live capture.")
        print("Forcing generation of packet-level synthetic dataset for dashboard compatibility.")

    data = generate_synthetic_dataset(save_path=os.path.join(data_dir, "dataset.csv"))
    return data, None  # (train_df, test_df=None) for synthetic


if __name__ == "__main__":
    generate_dataset(use_real=True)
