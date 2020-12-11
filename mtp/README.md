# MaChAmp: Massive Choice, Ample Tasks

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[![Machamp](docs/machamp.png)]()

> One arm alone can move mountains. 


This code base is an extension of the
[AllenNLP](https://github.com/allenai/allennlp) library with a focus on
multi-task learning.  It has support for training on multiple datasets for a
variety of standard NLP tasks.  For more information we refer to the paper:
[Massive Choice, Ample Tasks (MACHAMP): A Toolkit for Multi-task Learning in
NLP](http://robvandergoot.com/doc/machamp.pdf)

[![Machamp](docs/architecture.png)]()

## Installation
To install all necessary packages run:

```
pip3 install --user -r requirements.txt
```

## Training
To train the model, you need to write a configuration file. Below we show an
example of such a file for training a model for the English Web Treebank in 
the Universal Dependencies format. 

```
{
    "UD-EWT": {
        "train_data_path": "data/ewt.train",
        "validation_data_path": "data/ewt.dev",
        "word_idx": 1,
        "tasks": {
            "lemma": {
                "task_type": "string2string",
                "column_idx": 2
            },
            "upos": {
                "task_type": "seq",
                "column_idx": 3
            },
            "xpos": {
                "task_type": "seq",
                "column_idx": 4
            },
            "morph": {
                "task_type": "seq",
                "column_idx": 5
            },
            "dependency": {
                "task_type": "dependency",
                "column_idx": 6
            }
        }
    }
}

```

Every dataset needs at least a name (UD-EWT), a `train_data_path`,
`validation_data_path`, and `word_idx`. The `word_idx` tells the model in which
column the input words can be found. 

Every task requires a unique name, a `task_type` and a `column_idx`. The
`task_type` should be one of `seq`, `string2string`, `dependency`, `multi_seq`,
`seq_bio`, `classification`, these are explained in more detail below. 

```
python3 train.py --dataset_config configs/ewt.json --device 0
```

You can set `--device -1` to use the cpu. The model will be saved in
`logs/ewt/<date>_<time>` (you can also specify another name for the model with
`--name`).  We have prepared several scripts to download data, and
corresponding configuration files, these can be found in the `configs` and the
`test` directory.

**Warning** We currently do not support the enhanced UD format, where words are
splitted or inserted. scripts/misc/cleanConll.py can be used to remove these.
(This script makes use of https://github.com/bplank/ud-conversion-tools)

## Training on multiple datasets

This is rather straightforward, all you have to do is add multiple datasets in
the config file. For example, if we want to do supertagging (from the PMB),
jointly with XPOS tags (from the UD) and RTE (Glue), the config file would look as follows:

```
{
    "UD": {
        "train_data_path": "ewt.train",
        "validation_data_path": "ewt.dev",
        "word_idx": 1,
        "tasks": {
            "upos": {
                "task_type": "seq",
                "column_idx": 3
            }
        }
    },
    "PMB": {
        "train_data_path": "pmb.train",
        "validation_data_path": "pmb.dev",
        "word_idx": 0,
            "ccg": {
                "task_type": "seq",
                "column_idx": 3
            }
        }
    },
    "RTE": {
        "train_data_path": "data/glue/RTE.train",
        "validation_data_path": "data/glue/RTE.dev",
        "sent_idxs": [0,1],
        "tasks": {
            "rte": {
                "column_idx": 2,
                "task_type": "classification",
                "adaptive": true
            }
        }
    }
}
``` 

## How to

Task types:

* [seq](docs/seq.md): standard sequence labeling.
* [string2string](docs/string2string.md): same as sequence labeling, but learns a conversion from the original word to the instance, and uses that as label (useful for lemmatization). 
* [seq_bio](docs/seq_bio.md): a masked CRF decoder enforcing complying with the BIO-scheme.
* [multiseq](docs/multiseq.md): sequence labeling when the number of labels for each instance is not known in advance.
* [dependency](docs/dependency.md): dependency parsing
* [classification](docs/classification.md): sentence classification, predicts a label for N utterances of text
[comment]: <> (* [unsupervised](docs/unsupervised.md)
[comment]: <> (* [seq2seq](docs/seq2seq)

Other things:

* [Change bert embeddings](docs/change_embeds.md)
* [Predict on other datasets](docs/predict_data.md)
* [Predict on raw data](docs/predict_raw.md)
* [Change evaluation metric](docs/metrics.md)
* [Hyperparameters](docs/hyper.md)
* [Proportional sampling](docs/proportional.md)
* [Task-specific parameters](docs/task_params.md) (loss weight)
* [Adding a new task-type](docs/new_task_type.md)


## FAQ
Q: Performance seems low, how can I double check if everything runs correctly?  
A: see the test folder, practically, you should be able to run `./test/runAll.sh` and all output of `check.py` should be green .

Q: It doesn't run for UD data?  
A: we do not support enhanced dependencies (yet), which means you have to remove some special annotations, for which you can use `scripts/misc/cleanconl.py`

Q: Memory usage is too high, how can I reduce this?  
A: Some setups should run on 12GB gpu memory. However, depending on the task-type, pre-trained embeddings and training data, it might require 16GB.
To reduce data usage, you could try:

* Use smaller embeddings
* smaller `batch_size` or `max_len` in your parameters config
* use our old version based on Allennlp 0.9; it needs slightly less memory, but has less funcionality. 
* Run on CPU (`--device -1`), which is actually only 4-10 times slower.

Q: what should I cite?  
```
@misc{vandergoot-etal-2020-machamp,
    title={Massive Choice, Ample Tasks (MaChAmp):A Toolkit for Multi-task Learning in NLP},
    author={Rob van der Goot and Ahmet {\"U}st{\"u}n and Alan Ramponi and Barbara Plank},
    year={2020},
    eprint={2005.14672},
    archivePrefix={arXiv},
    primaryClass={cs.CL}
}
```

[comment]: <> (Q: Amazing stuff!, but I was looking for resources on Machamps language:)

[comment]: <> (A: No problem, we have collected a dataset from utterances transcribed from wild Machamps as well as Machamps belonging to Pokémon trainers. It can be found on TODO)

