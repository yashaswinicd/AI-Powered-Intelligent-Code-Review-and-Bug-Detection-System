import os
import joblib
from config import MODEL_PATH, VECTORIZER_PATH

# =============================
# Load Model
# =============================
def load_model():
    try:
        model = joblib.load(MODEL_PATH)
        vectorizer = joblib.load(VECTORIZER_PATH)
        print("✅ Model loaded successfully!")
        return model, vectorizer
    except FileNotFoundError:
        print("⚠️ Model not found! Run train.py first.")
        return None, None

# =============================
# Predict Code Quality
# =============================
def predict(code):
    model, vectorizer = load_model()

    if model is None:
        return {
            'prediction': 'Unknown',
            'confidence': 0,
            'message': 'Model not trained yet. Run train.py first!'
        }

    # Vectorize input
    code_vec = vectorizer.transform([code])

    # Predict
    prediction = model.predict(code_vec)[0]
    probability = model.predict_proba(code_vec)[0]
    confidence = round(max(probability) * 100, 2)

    result = {
        'prediction': 'Bad Code' if prediction == 1 else 'Good Code',
        'confidence': confidence,
        'label': int(prediction),
        'message': (
            '⚠️ Issues detected in code!'
            if prediction == 1
            else '✅ Code looks good!'
        )
    }
    return result

# =============================
# Test maadalu
# =============================
if __name__ == "__main__":
    test_codes = [
        'def add(a, b):\n    """Add numbers."""\n    return a + b',
        'password = "admin123"\neval(user_input)',
    ]

    for i, code in enumerate(test_codes, 1):
        print(f"\n--- Test {i} ---")
        result = predict(code)
        print(f"Prediction  : {result['prediction']}")
        print(f"Confidence  : {result['confidence']}%")
        print(f"Message     : {result['message']}")