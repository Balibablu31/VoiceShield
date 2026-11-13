import argparse
import pandas as pd
from datasets import Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments


def load_csv(path):
    frame = pd.read_csv(path).dropna(subset=["text", "label"])
    labels = sorted(frame.label.astype(str).unique())
    label_to_id = {label: i for i, label in enumerate(labels)}
    return frame, labels, label_to_id


def main():
    parser = argparse.ArgumentParser(description="Fine-tune a text classifier on prepared VoiceShield CSV splits.")
    parser.add_argument("--train", required=True); parser.add_argument("--validation", required=True)
    parser.add_argument("--model", default="google-bert/bert-base-uncased"); parser.add_argument("--output", required=True)
    args = parser.parse_args()
    train, labels, label_to_id = load_csv(args.train); valid, _, valid_labels = load_csv(args.validation)
    unknown = sorted(set(valid_labels) - set(labels))
    if unknown: raise ValueError(f"Validation labels absent from training split: {unknown}")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    def encode(batch):
        return tokenizer(batch["text"], truncation=True, max_length=512)
    def dataset(frame):
        ids = frame.label.astype(str).map(label_to_id)
        if ids.isna().any(): raise ValueError("A split contains labels absent from the training split")
        ds = Dataset.from_pandas(frame.assign(label_id=ids.astype(int)), preserve_index=False)
        ds = ds.map(encode, batched=True)
        return ds.rename_column("label_id", "labels")
    model = AutoModelForSequenceClassification.from_pretrained(args.model, num_labels=len(labels), id2label={i:l for l,i in label_to_id.items()}, label2id=label_to_id)
    trainer = Trainer(model=model, args=TrainingArguments(output_dir=args.output, eval_strategy="epoch", save_strategy="epoch", num_train_epochs=3, per_device_train_batch_size=8, per_device_eval_batch_size=8, load_best_model_at_end=True), train_dataset=dataset(train), eval_dataset=dataset(valid), processing_class=tokenizer)
    trainer.train(); trainer.save_model(args.output); tokenizer.save_pretrained(args.output)
    with open(f"{args.output}/labels.txt", "w", encoding="utf-8") as out:
        out.write("\n".join(labels))


if __name__ == "__main__": main()
