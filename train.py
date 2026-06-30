import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from config import (
    MODEL_PATH, VECTORIZER_PATH,
    METRICS_PATH, MODEL_DIR,
    TEST_SIZE, RANDOM_STATE, MAX_FEATURES
)

def create_sample_data():
    data = {
        'code': [
            'def add(a, b):\n    """Add two numbers."""\n    return a + b',
            'password = "admin123"\nexec(user_input)',
            'def func():\n    try:\n        pass\n    except:\n        pass',
            'import os\ndef clean():\n    """Clean files."""\n    return True',
            'eval(input())\nos.system(cmd)\npassword="secret"',
            'def calc(x, y):\n    """Calculate."""\n    return x * y',
            'cursor.execute("SELECT * FROM users WHERE id=" + uid)',
            'def helper():\n    """Helper function."""\n    return None',
            'md5_hash = hashlib.md5(data)\npassword="1234"',
            'def process(data):\n    """Process data."""\n    return data',
            'def greet(name):\n    """Greet."""\n    return f"Hello {name}"',
            'api_key = "abc123secret"\nimport subprocess',
            'def multiply(a,b):\n    """Multiply."""\n    return a*b',
            'exec(user_data)\neval(input_data)',
            'def divide(a,b):\n    """Divide."""\n    return a/b',
            'secret = "password123"\nos.system(user_cmd)',
            'def is_valid(x):\n    """Check valid."""\n    return x > 0',
            'import pickle\npickle.loads(user_data)',
            'def square(n):\n    """Square."""\n    return n*n',
            'password="root"\ncursor.execute("SELECT "+uid)',
        ],
        'label': [0,1,1,0,1,0,1,0,1,0,0,1,0,1,0,1,0,1,0,1]
    }
    return pd.DataFrame(data)

def train_model():
    print("🚀 Training started...")
    df = create_sample_data()
    print(f"✅ Dataset size: {len(df)} samples")

    X = df['code']
    y = df['label']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )

    vectorizer = TfidfVectorizer(max_features=MAX_FEATURES)
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    model = LogisticRegression(random_state=RANDOM_STATE)
    model.fit(X_train_vec, y_train)

    y_pred = model.predict(X_test_vec)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"✅ Model Accuracy: {accuracy * 100:.2f}%")

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(vectorizer, VECTORIZER_PATH)
    print(f"✅ Model saved!")

    metrics = {
        'accuracy': round(accuracy, 4),
        'total_samples': len(df),
        'train_samples': len(X_train),
        'test_samples': len(X_test),
        'model': 'Logistic Regression',
        'vectorizer': 'TF-IDF',
        'max_features': MAX_FEATURES
    }
    with open(METRICS_PATH, 'w') as f:
        json.dump(metrics, f, indent=4)

    print("\n🎉 Training Complete!")
    return model, vectorizer, metrics

if __name__ == "__main__":
    model, vectorizer, metrics = train_model()
    print(f"📊 Accuracy: {metrics['accuracy'] * 100:.2f}%")