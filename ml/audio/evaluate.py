import argparse
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, roc_curve
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification, pipeline

from preprocessing import load_mono_16khz


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--test", required=True); parser.add_argument("--model", required=True)
    args = parser.parse_args(); frame = pd.read_csv(args.test)
    feature = AutoFeatureExtractor.from_pretrained(args.model); model = AutoModelForAudioClassification.from_pretrained(args.model)
    clf = pipeline("audio-classification", model=model, feature_extractor=feature)
    labels, scores = [], []
    for row in frame.itertuples():
        result = clf(load_mono_16khz(row.file), top_k=None)
        spoof_score = next((x["score"] for x in result if x["label"].lower() in {"spoof", "fake", "1"}), None)
        if spoof_score is None: raise ValueError("Checkpoint label mapping must contain a spoof class")
        labels.append(int(row.label)); scores.append(spoof_score)
    predicted = [int(x >= .5) for x in scores]
    fpr, tpr, _ = roc_curve(labels, scores, pos_label=1)
    eer_index = int(np.nanargmin(np.abs(fpr - (1 - tpr))))
    print({"accuracy": accuracy_score(labels, predicted), "eer": float((fpr[eer_index] + (1-tpr[eer_index]))/2), "confusion_matrix": confusion_matrix(labels, predicted).tolist()})


if __name__ == "__main__": main()
