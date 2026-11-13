import argparse
import pandas as pd
import torch
from datasets import Dataset
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification, Trainer, TrainingArguments

from preprocessing import load_mono_16khz


def main():
    parser = argparse.ArgumentParser(description="Fine-tune wav2vec2 on prepared audio CSV splits.")
    parser.add_argument("--train", required=True, help="CSV columns: file,label (0=bona fide, 1=spoof)")
    parser.add_argument("--validation", required=True); parser.add_argument("--model", default="facebook/wav2vec2-base")
    parser.add_argument("--output", required=True); args = parser.parse_args()
    extractor = AutoFeatureExtractor.from_pretrained(args.model)
    def prepare(path):
        frame = pd.read_csv(path)
        if not {"file", "label"}.issubset(frame.columns): raise ValueError("CSV must contain file,label")
        frame["label"] = frame.label.astype(int)
        if not set(frame.label.unique()).issubset({0, 1}): raise ValueError("labels must be 0 or 1")
        ds = Dataset.from_pandas(frame, preserve_index=False)
        def featurize(batch):
            audio = load_mono_16khz(batch["file"])
            return extractor(audio, sampling_rate=16000)
        ds = ds.map(featurize)
        return ds.rename_column("label", "labels")
    model = AutoModelForAudioClassification.from_pretrained(args.model, num_labels=2, label2id={"bonafide":0,"spoof":1}, id2label={0:"bonafide",1:"spoof"})
    def collate(features):
        labels = torch.tensor([item.pop("labels") for item in features], dtype=torch.long)
        batch = extractor.pad(features, padding=True, return_tensors="pt")
        batch["labels"] = labels
        return batch
    trainer = Trainer(model=model, args=TrainingArguments(output_dir=args.output, eval_strategy="epoch", save_strategy="epoch", num_train_epochs=3, per_device_train_batch_size=4, per_device_eval_batch_size=4, load_best_model_at_end=True), train_dataset=prepare(args.train), eval_dataset=prepare(args.validation), processing_class=extractor, data_collator=collate)
    trainer.train(); trainer.save_model(args.output); extractor.save_pretrained(args.output)


if __name__ == "__main__": main()
