import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import subprocess
import time
from app import find_tshark_path


def parse_args():
    parser = argparse.ArgumentParser(description="Record real-world network traffic to PCAP file.")
    parser.add_argument('--label', choices=['normal', 'high_throughput', 'congested'],
                        required=True, help='Label/class for the captured session.')
    parser.add_argument('--duration', type=int, default=180,
                        help='Capture duration in seconds (default: 180s / 3 mins).')
    parser.add_argument('--interface', type=str, default='',
                        help='Network interface name or index (e.g. "Wi-Fi" or "1").')
    parser.add_argument('--out-dir', type=str, default='data/pcaps',
                        help='Directory to save the PCAP output file.')
    return parser.parse_args()


def record():
    args = parse_args()
    tshark_path = find_tshark_path()

    if not tshark_path or not os.path.exists(tshark_path):
        print("Error: tshark executable not found. Please install Wireshark / tshark first.")
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)
    out_file = os.path.join(args.out_dir, f"{args.label}.pcap")

    target_iface = args.interface.strip() if args.interface else "Wi-Fi"

    cmd = [tshark_path, '-a', f'duration:{args.duration}', '-w', out_file, '-i', target_iface]

    print("=" * 60)
    print(f"  Recording Session: [{args.label.upper()}]")
    print("=" * 60)
    print(f"  Duration   : {args.duration} seconds")
    print(f"  Interface  : {target_iface}")
    print(f"  Saving to  : {out_file}")
    print(f"  Status     : Recording active... Perform your [{args.label}] traffic activities now!")
    print("=" * 60)

    try:
        proc = subprocess.Popen(cmd)
        start_time = time.time()
        while proc.poll() is None:
            elapsed = int(time.time() - start_time)
            remaining = max(0, args.duration - elapsed)
            sys.stdout.write(f"\r  [RECORDING] Elapsed: {elapsed}s | Remaining: {remaining}s   ")
            sys.stdout.flush()
            time.sleep(1)
        print(f"\n\nCapture complete! Saved -> {out_file}")
    except KeyboardInterrupt:
        print("\nRecording stopped early by user.")
        if proc.poll() is None:
            proc.terminate()


if __name__ == "__main__":
    record()
