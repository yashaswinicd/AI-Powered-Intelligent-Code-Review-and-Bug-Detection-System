# Models

`code_review_model.pkl` is created automatically the first time the app (or
`python train.py`) needs it, so it is not stored in Git. A pickle is tied to
the scikit-learn version that wrote it; training takes about a second.

The model is a secondary classifier (TF-IDF + logistic regression) trained on
template-generated Python snippets. `model_metrics.json` holds its validation
results; folds are split by template so test snippets are never near
duplicates of training snippets. See the main README for how to read them.
