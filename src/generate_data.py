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


def generate_synthetic_dataset(n=2000, save_path="data/dataset.csv"):
    """
    Realistic synthetic fallback.
    All 4 features contribute meaningfully to the congestion label,
    with added noise so the model has to actually learn.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    np.random.seed(42)

    packet_rate   = np.random.randint(100, 1000, n)
    rtt           = np.random.randint(10, 300, n)
    queue_length  = np.random.randint(1, 100, n)
    packet_loss   = np.random.randint(0, 15, n)

    # All features contribute to a congestion score (weighted)
    congestion_score = (
        (packet_rate  / 1000) * 0.35 +
        (queue_length / 100)  * 0.30 +
        (packet_loss  / 15)   * 0.20 +
        (rtt          / 300)  * 0.15
    )

    # Add noise so threshold isn't perfectly clean
    noise = np.random.normal(0, 0.06, n)
    congestion = ((congestion_score + noise) > 0.50).astype(int)

    data = pd.DataFrame({
        'packet_rate':  packet_rate,
        'rtt':          rtt,
        'queue_length': queue_length,
        'packet_loss':  packet_loss,
        'congestion':   congestion,
    })

    data.to_csv(save_path, index=False)
    print(f"Synthetic dataset saved → {save_path}")
    print(f"Congestion rate: {congestion.mean():.2%} ({congestion.sum()} / {n} samples)")
    return data


def generate_dataset(use_real=True, data_dir="data"):
    """
    Main entry point.
    Tries NSL-KDD first; falls back to realistic synthetic if download fails.
    """
    if use_real:
        success = download_nsl_kdd(data_dir)
        if success:
            return load_nsl_kdd(data_dir)
        else:
            print("Falling back to synthetic dataset...")

    data = generate_synthetic_dataset(save_path=os.path.join(data_dir, "dataset.csv"))
    return data, None  # (train_df, test_df=None) for synthetic


if __name__ == "__main__":
    generate_dataset(use_real=True)
