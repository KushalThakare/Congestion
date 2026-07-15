"""
main.py — Network Congestion Detection Pipeline
------------------------------------------------
Usage:
    python main.py                    # NSL-KDD + Random Forest (default)
    python main.py --synthetic        # Use realistic synthetic data
    python main.py --model gb         # Use Gradient Boosting
    python main.py --no-plots         # Skip saving result plots
"""

import argparse
from src.generate_data import generate_dataset
from src.train_model import train
from src.evaluate import evaluate


def parse_args():
    parser = argparse.ArgumentParser(description="Network Congestion Detector")
    parser.add_argument('--synthetic', action='store_true',
                        help='Use synthetic data instead of NSL-KDD')
    parser.add_argument('--model', choices=['random_forest', 'gb'],
                        default='random_forest',
                        help='Model type: random_forest | gb (gradient boosting)')
    parser.add_argument('--no-plots', action='store_true',
                        help='Skip saving evaluation plots')
    return parser.parse_args()


def main():
    args = parse_args()
    model_type = 'gradient_boosting' if args.model == 'gb' else 'random_forest'
    use_real   = not args.synthetic

    print("=" * 55)
    print("  Network Congestion Detection — Starting Pipeline")
    print("=" * 55)
    print(f"  Data source : {'Synthetic (realistic)' if args.synthetic else 'NSL-KDD'}")
    print(f"  Model       : {model_type}")

    # Step 1 — Load / Generate Data
    result = generate_dataset(use_real=use_real)
    train_df, test_df = result if isinstance(result, tuple) else (result, None)

    # Step 2 — Train
    model, X_test, y_test, feature_names = train(
        train_df=train_df,
        test_df=test_df,
        model_type=model_type,
    )

    # Step 3 — Evaluate
    metrics = evaluate(
        model, X_test, y_test,
        feature_names=feature_names,
        save_plots=not args.no_plots
    )

    print("\nPipeline complete.")
    if not args.no_plots:
        print("Plots saved in → results/")
    return metrics


if __name__ == "__main__":
    main()
