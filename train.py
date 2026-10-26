"""Train the secondary risk model and print its cross-validated metrics."""

from src.ml_model import train

if __name__ == "__main__":
    _, metrics = train()
    print("Model trained and saved.")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
