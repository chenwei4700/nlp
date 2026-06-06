# -*- coding: utf-8 -*-
"""
Train a CPBL / MLB news classifier.

Pipeline:
1. Load baseball_news.csv.
2. Segment Chinese text with Jieba and the custom baseball dictionary.
3. Convert text to TF-IDF vectors.
4. Train an SVM classifier and report accuracy.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import jieba
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


SCRIPT_DIR = Path(__file__).resolve().parent
CSV_PATH = SCRIPT_DIR / "baseball_news.csv"
DICT_PATH = SCRIPT_DIR / "baseball_dict.txt"
MODEL_PATH = SCRIPT_DIR / "svm_baseball_classifier.joblib"
REPORT_PATH = SCRIPT_DIR / "classification_report.txt"

RANDOM_STATE = 42
TEST_SIZE = 0.2


def load_jieba_dictionary(dict_path: Path) -> None:
    """Load the custom baseball dictionary when it exists."""
    if dict_path.exists():
        jieba.load_userdict(str(dict_path))
        print(f"[OK] Loaded Jieba user dictionary: {dict_path.name}")
    else:
        print(f"[WARN] Jieba user dictionary not found: {dict_path}")


def normalize_text(text: object) -> str:
    """Keep useful Chinese, English, and number tokens; normalize whitespace."""
    text = "" if pd.isna(text) else str(text)
    text = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def jieba_tokenize(text: str) -> list[str]:
    """Tokenize text with Jieba for TfidfVectorizer."""
    text = normalize_text(text)
    tokens = []
    for token in jieba.lcut(text):
        token = token.strip()
        if len(token) > 1:
            tokens.append(token)
    return tokens


def load_dataset(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    required_columns = {"title", "content", "label"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required CSV columns: {missing}")

    df = df.dropna(subset=["label"]).copy()
    df["text"] = (
        df["title"].fillna("").astype(str)
        + " "
        + df["content"].fillna("").astype(str)
    )
    df = df[df["text"].str.strip().str.len() > 0]
    df = df[df["label"].isin(["CPBL", "MLB"])]

    if df.empty:
        raise ValueError("No usable CPBL / MLB rows found in the CSV.")

    return df.reset_index(drop=True)


def build_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    tokenizer=jieba_tokenize,
                    token_pattern=None,
                    lowercase=False,
                    min_df=2,
                    max_df=0.9,
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                ),
            ),
            ("svm", LinearSVC(C=1.0, random_state=RANDOM_STATE)),
        ]
    )


def format_report(
    accuracy: float,
    y_test: pd.Series,
    y_pred: list[str],
    train_size: int,
    test_size: int,
) -> str:
    labels = ["CPBL", "MLB"]
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    report = classification_report(y_test, y_pred, labels=labels, digits=4)

    return "\n".join(
        [
            "CPBL / MLB Baseball News Classification Report",
            "=" * 52,
            f"Model: TF-IDF + Linear SVM",
            f"Train rows: {train_size}",
            f"Test rows: {test_size}",
            f"Accuracy: {accuracy:.4f}",
            "",
            "Classification report:",
            report,
            "Confusion matrix (rows=true, columns=predicted):",
            "        CPBL  MLB",
            f"CPBL    {cm[0][0]:>3}  {cm[0][1]:>3}",
            f"MLB     {cm[1][0]:>3}  {cm[1][1]:>3}",
        ]
    )


def main() -> None:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    load_jieba_dictionary(DICT_PATH)
    df = load_dataset(CSV_PATH)

    print(f"[OK] Loaded dataset: {len(df)} rows")
    print("[INFO] Label counts:")
    for label, count in df["label"].value_counts().sort_index().items():
        print(f"  {label}: {count}")

    x_train, x_test, y_train, y_test = train_test_split(
        df["text"],
        df["label"],
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=df["label"],
    )

    model = build_pipeline()
    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)
    accuracy = accuracy_score(y_test, y_pred)
    report_text = format_report(
        accuracy=accuracy,
        y_test=y_test,
        y_pred=y_pred,
        train_size=len(x_train),
        test_size=len(x_test),
    )

    print()
    print(report_text)

    REPORT_PATH.write_text(report_text, encoding="utf-8")
    joblib.dump(model, MODEL_PATH)

    print()
    print(f"[OK] Saved report: {REPORT_PATH}")
    print(f"[OK] Saved model: {MODEL_PATH}")


if __name__ == "__main__":
    main()
