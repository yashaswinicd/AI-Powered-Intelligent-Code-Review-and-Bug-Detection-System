"""Small machine-learning component: a secondary "risk" classifier.

The rule engine is the primary detector. This model is a lightweight
second opinion that scores how much a Python snippet *resembles* code
containing known risky patterns. It is trained on a labelled set of
snippets generated from templates (see ``build_dataset``), so its metrics
describe that set, not real-world code.

The model trains itself automatically the first time it is needed, so no
pre-built pickle has to be shipped (pickles are tied to the scikit-learn
version that created them).
"""

import json
import os
import random

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, f1_score, precision_score,
                             recall_score)
from sklearn.pipeline import make_pipeline

from config.settings import METRICS_PATH, MODEL_DIR, MODEL_PATH, RANDOM_STATE

_CLEAN = [
    'def {f}({a}, {b}):\n    """Add two numbers."""\n    return {a} + {b}\n',
    'def {f}(items):\n    total = 0\n    for item in items:\n'
    '        total += item\n    return total\n',
    'class {C}:\n    def __init__(self, {a}):\n        self.{a} = {a}\n\n'
    '    def get(self):\n        return self.{a}\n',
    'import json\n\ndef {f}(path):\n    with open(path) as fh:\n'
    '        return json.load(fh)\n',
    'def {f}(n):\n    if n <= 1:\n        return 1\n'
    '    return n * {f}(n - 1)\n',
    'try:\n    value = int(input())\nexcept ValueError as err:\n'
    '    print(err)\n',
    'def {f}(data):\n    return [x * 2 for x in data if x > 0]\n',
    "import os\n{a} = os.environ.get('{A}', '')\nprint({a})\n",
    'def {f}(a, b):\n    if b == 0:\n        return None\n    return a / b\n',
    "cursor.execute('SELECT * FROM users WHERE id = ?', ({a},))\n",
    'def {f}(words):\n    counts = {{}}\n    for w in words:\n'
    '        counts[w] = counts.get(w, 0) + 1\n    return counts\n',
    'import hashlib\n{a} = hashlib.sha256(b"{w}").hexdigest()\n',
    'def {f}(path):\n    try:\n        return open(path).read()\n'
    '    except FileNotFoundError:\n        return ""\n',
    'for i in range(10):\n    if i % 2 == 0:\n        print(i)\n',
    'def {f}(items, bucket=None):\n    bucket = bucket or []\n'
    '    bucket.extend(items)\n    return bucket\n',
]
_RISKY = [
    "password = '{w}'\nprint(password)\n",
    "result = eval(input())\nprint(result)\n",
    'def {f}(a):\n    try:\n        return 1 / a\n    except:\n        pass\n',
    "import os\nos.system('rm ' + {a})\n",
    "query = 'SELECT * FROM users WHERE name = ' + {a}\ncursor.execute(query)\n",
    'import hashlib\nh = hashlib.md5({a}.encode()).hexdigest()\n',
    'x = 10\ny = 0\nprint(x / y)\n',
    'import pickle\ndata = pickle.loads({a})\n',
    'def {f}(items=[]):\n    items.append(1)\n    return items\n',
    "api_key = '{w}'\nprint(api_key)\n",
    'exec({a})\n',
    "if {a} == None:\n    print('missing')\n",
    "secret = '{w}'\ntoken = '{w}x'\n",
    'def {f}(a):\n    try:\n        run({a})\n    except:\n        pass\n',
    'import subprocess\nsubprocess.call({a}, shell=True)\n',
]
_NAMES = ["data", "value", "item", "user", "count", "path", "text", "num",
          "result", "name", "total", "key"]
_FUNCS = ["process", "compute", "load", "handle", "run", "check", "build",
          "parse", "update", "fetch"]
_WORDS = ["admin123", "letmein", "s3cr3t", "qwerty99", "hunter22", "pass1234"]


def build_dataset(samples_per_template=12, seed=RANDOM_STATE):
    rng = random.Random(seed)
    texts, labels, groups = [], [], []
    for label, templates in ((0, _CLEAN), (1, _RISKY)):
        for t_index, template in enumerate(templates):
            for _ in range(samples_per_template):
                names = rng.sample(_NAMES, 2)
                code = template.format(
                    f=rng.choice(_FUNCS), C=rng.choice(_FUNCS).capitalize(),
                    a=names[0], b=names[1], A=names[0].upper(),
                    w=rng.choice(_WORDS))
                texts.append(code)
                labels.append(label)
                groups.append(t_index % 5)  # template index decides the fold
    return texts, np.array(labels), np.array(groups)


def _pipeline():
    return make_pipeline(
        TfidfVectorizer(token_pattern=r"[A-Za-z_][A-Za-z_0-9]*|[^\sA-Za-z_0-9]",
                        ngram_range=(1, 2), sublinear_tf=True),
        LogisticRegression(max_iter=1000, C=3.0))


def train(save=True):
    texts, labels, groups = build_dataset()
    # Template-grouped cross-validation: every test fold contains only
    # templates the model has never seen, so near-duplicate snippets cannot
    # leak from training into testing.
    scores = {"accuracy": [], "precision": [], "recall": [], "f1": []}
    for fold in range(5):
        test_idx = np.where(groups == fold)[0]
        train_idx = np.where(groups != fold)[0]
        model = _pipeline()
        model.fit([texts[i] for i in train_idx], labels[train_idx])
        pred = model.predict([texts[i] for i in test_idx])
        truth = labels[test_idx]
        scores["accuracy"].append(accuracy_score(truth, pred))
        scores["precision"].append(precision_score(truth, pred))
        scores["recall"].append(recall_score(truth, pred))
        scores["f1"].append(f1_score(truth, pred))

    model = _pipeline()
    model.fit(texts, labels)
    metrics = {
        "samples": len(texts),
        "templates": len(_CLEAN) + len(_RISKY),
        "validation": "5-fold, folds split by template (unseen templates)",
        **{k: round(float(np.mean(v)), 4) for k, v in scores.items()},
        "note": ("Snippets are generated from templates. Each test fold "
                 "holds out whole templates. Metrics describe this "
                 "synthetic set, not real-world code; the rule engine is "
                 "the primary detector."),
    }
    if save:
        os.makedirs(MODEL_DIR, exist_ok=True)
        joblib.dump(model, MODEL_PATH)
        with open(METRICS_PATH, "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, indent=2)
    return model, metrics


class RiskModel:
    """Loads the model, training it first if it is missing or unreadable."""

    def __init__(self):
        self.model = None
        self.available = False
        self._load()

    def _load(self):
        try:
            if os.path.exists(MODEL_PATH):
                self.model = joblib.load(MODEL_PATH)
            else:
                self.model, _ = train()
            self.available = True
        except Exception:
            try:
                self.model, _ = train()
                self.available = True
            except Exception:
                self.available = False

    def predict(self, code):
        if not self.available:
            return None
        try:
            probability = float(self.model.predict_proba([code])[0][1])
        except Exception:
            return None
        return {"risk_probability": round(probability, 3),
                "label": "risky" if probability >= 0.5 else "clean"}


def load_metrics():
    try:
        with open(METRICS_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None
