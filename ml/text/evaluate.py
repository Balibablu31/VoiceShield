import argparse
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from transformers import pipeline


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--test", required=True); parser.add_argument("--model", required=True); args = parser.parse_args()
    frame = pd.read_csv(args.test).dropna(subset=["text", "label"])
    classifier = pipeline("text-classification", model=args.model, tokenizer=args.model, truncation=True)
    outputs = classifier(frame.text.astype(str).tolist(), batch_size=8, truncation=True, max_length=512)
    labels = [str(x["label"]) for x in outputs]; expected = frame.label.astype(str).tolist()
    print({"accuracy": accuracy_score(expected, labels), "report": classification_report(expected, labels, output_dict=True, zero_division=0), "confusion_matrix": confusion_matrix(expected, labels).tolist()})


if __name__ == "__main__": main()
