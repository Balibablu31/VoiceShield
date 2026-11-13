# VoiceShield model development foundation

No checkpoints, dataset downloads, or training jobs are included. Use a GPU runtime such as Colab for fine-tuning. Keep dataset access terms and provenance with each experiment.

## Text

Prepare UTF-8 CSV files with `text,label` columns. Use the official LIAR train/validation/test splits and its six original labels (`pants-fire`, `false`, `barely-true`, `half-true`, `mostly-true`, `true`); do not collapse these to factual truth without a documented research protocol. FakeNewsNet source packages vary and may have separate article, social-context, and label files; prepare and audit a derived CSV without mixing splits or re-sharing restricted content. Run `python ml/text/train.py --train train.csv --validation validation.csv --output ml/checkpoints/text-en` from the project root.

Hindi and Marathi datasets should use the same columns, with a distinct, documented label set and language-specific split files. Pick a MuRIL or IndicBERT encoder and fine-tune it for the task before setting the corresponding application model variable. A base encoder is not a classifier.

## Audio

Obtain ASVspoof under its own terms. Put protocol files and audio in a private dataset directory. The protocol parser expects whitespace-delimited rows with speaker, file ID, and label fields (official LA protocol convention); `bonafide` maps to 0 and `spoof` to 1. Verify protocol conventions for a dataset release before training. Resample and convert to mono 16 kHz during dataset loading. Evaluate with accuracy and EER, and preserve the protocol and checkpoint provenance.

## Registration

Set `VOICESHIELD_EN_MODEL`, `VOICESHIELD_HI_MODEL`, and `VOICESHIELD_MR_MODEL` to local fine-tuned model directories or verified Hugging Face model IDs. Confirm model card, label mapping, license, and evaluation before registering. No pretrained checkpoint is endorsed or bundled by this repository.
