from typing import Dict, List, Any
from overrides import overrides
import logging
import torch

from allennlp.data import TextFieldTensors, Vocabulary
from allennlp.models.model import Model
from allennlp.modules import Seq2VecEncoder, TextFieldEmbedder
from allennlp.nn.util import get_text_field_mask
from allennlp.modules import InputVariationalDropout

logger = logging.getLogger(__name__)


@Model.register("machamp_model")
class MachampModel(Model):
    """
    """

    def __init__(
            self,
            vocab: Vocabulary,
            text_field_embedder: TextFieldEmbedder,
            encoder: Seq2VecEncoder,
            decoders: Dict[str, Model],
            tasks: List[str],
            task_types: List[str],
            dropout: float = None,
            **kwargs
    ) -> None:
        super().__init__(vocab, **kwargs)
        self._text_field_embedder = text_field_embedder

        self.encoder = encoder
        self._classifier_input_dim = self.encoder.get_output_dim()

        if dropout:
            self._dropout = InputVariationalDropout(dropout)
            self._dropout_sents = torch.nn.Dropout(dropout)
        else:
            self._dropout = None

        self.decoders = torch.nn.ModuleDict(decoders)

        self.tasks = tasks
        self.task_types = task_types

        self.counter = 0
        self.metrics = {}

    def forward(self,
                tokens: TextFieldTensors,
                dataset=None,
                metadata: List[Dict[str, Any]] = None,
                **kwargs: Dict[str, torch.LongTensor]
                ) -> Dict[str, torch.Tensor]:
        """
        """
        gold_labels = kwargs

        tasks_to_handle = []
        task_types_to_handle = []
        for task, task_type in zip(self.tasks, self.task_types):
            s2s_and_in = task_type == "seq2seq" and task + '_target_words' in metadata[0]['col_idxs']
            dep_and_in = task_type == 'dependency' and task + '_rels' in metadata[0]['col_idxs']
            if s2s_and_in or dep_and_in or task in metadata[0]['col_idxs']:
                tasks_to_handle.append(task)
                task_types_to_handle.append(task_type)

        sent_count = task_types_to_handle.count('classification')
        mask = get_text_field_mask(tokens)

        embedded_text = self._text_field_embedder(tokens)
        if sent_count > 0:
            embedded_text_sent = self.encoder(self._text_field_embedder(tokens), mask=mask)

        if self._dropout:
            embedded_text = self._dropout(embedded_text)
            if sent_count > 0:
                embedded_text_sent = self._dropout_sents(embedded_text_sent)

        logits = {}
        class_probabilities = {}
        output_dict = {"logits": logits,
                       "class_probabilities": class_probabilities}
        loss = 0.0

        for task, task_type in zip(tasks_to_handle, task_types_to_handle):
            if task_type == 'classification':
                task_gold_labels = None if task not in gold_labels else gold_labels[task]
                pred_output = self.decoders[task].forward(embedded_text_sent, task_gold_labels)
                class_probabilities[task] = pred_output["class_probabilities"]
            elif task_type == 'dependency':
                tags_gold_labels = None if task + '_rels' not in gold_labels else gold_labels[task + '_rels']
                indices_gold_labels = None if task + '_head_indices' not in gold_labels else gold_labels[task + '_head_indices']
                pred_output = self.decoders[task].forward(embedded_text, mask=mask,
                                                          gold_head_tags=tags_gold_labels,
                                                          gold_head_indices=indices_gold_labels)
                class_probabilities[task + '_rels'] = pred_output[task + "_rels"]
                class_probabilities[task + '_head_indices'] = pred_output[task + "_head_indices"]
            elif task_type == 'unsupervised':
                task_gold_labels = None if task not in gold_labels else gold_labels[task]
                pred_output = self.decoders[task].forward(embedded_text, task_gold_labels)
            elif task_type == 'seq2seq':
                task_gold_labels = None if task + '_target' not in gold_labels else gold_labels[task + '_target']
                pred_output = self.decoders[task].forward(embedded_text, mask, task_gold_labels)
                class_probabilities[task] = pred_output["class_probabilities"]
            else:
                task_gold_labels = None if task not in gold_labels else gold_labels[task]
                pred_output = self.decoders[task].forward(embedded_text, task_gold_labels, mask=mask)
                class_probabilities[task] = pred_output["class_probabilities"]

            if 'loss' in pred_output:
                logits[task] = pred_output['loss']

            dep_and_in = task_type == "dependency" and task + "_rels" in gold_labels
            s2s_and_in = task_type == "seq2seq" and task + '_target_words' in gold_labels
            if dep_and_in or s2s_and_in or task in gold_labels:
                loss += pred_output["loss"]

        if gold_labels:
            output_dict['loss'] = loss

        if metadata is not None:
            output_dict["tokens"] = [x["tokens"] for x in metadata]
            output_dict["full_data"] = [x['full_data'] for x in metadata]
            output_dict["col_idxs"] = [x['col_idxs'] for x in metadata]

            # Rob: Warning, hacky!, allennlp requires them to be in the length of metadata, in the dump_lines I just use the first
            output_dict['tasks'] = [self.tasks for _ in metadata]
            output_dict["task_types"] = [self.task_types for _ in metadata]
        output_dict['mask'] = mask
        return output_dict

    @overrides
    def make_output_human_readable(
        self, output_dict: Dict[str, torch.Tensor]
    ) -> Dict[str, torch.Tensor]:

        for task in self.tasks:
            is_dep = self.task_types[self.tasks.index(task)] == 'dependency'
            if task in output_dict['class_probabilities']: 
                output_dict[task] = self.decoders[task].make_output_human_readable(output_dict['class_probabilities'][task])
            elif is_dep and task + '_rels' in output_dict['class_probabilities']:
                dep_tags = output_dict['class_probabilities'][task + '_rels']
                dep_heads = output_dict['class_probabilities'][task + '_head_indices']
                mask = output_dict['mask']
                output_dict[task + '_rels'], output_dict[task + '_head_indices'] = \
                                    self.decoders[task].make_output_human_readable(dep_tags, dep_heads, mask)
        
        if output_dict['loss'] == 0:
            output_dict['loss'] = [output_dict['loss']]
        return output_dict



    def get_metrics(self, reset: bool = False) -> Dict[str, float]:
        metrics = {}
        for task in self.tasks:
            for name, task_metric in self.decoders[task].get_metrics(reset).items():
                if name.split("/")[-1] in ["acc", 'ppl']:
                    metrics[name] = task_metric
                elif name.split('/')[-1].lower() in ['las']:
                    metrics[name] = task_metric['LAS']
                elif name.split('/')[-1] in ['micro-f1', 'macro-f1']:
                    metrics[name] = task_metric['fscore']
                elif name.split("/")[-1] == "span_f1":
                    metrics[name] = task_metric["f1-measure-overall"]
                elif name.split("/")[-1] == "multi_span_f1":
                    metrics[name] = task_metric["f1-measure-overall"]
                elif name.split("/")[-1] == "bleu":
                    metrics[name] = task_metric["BLEU"]
                else:
                    logger.error(f"ERROR. Metric: {name} unrecognized.")
        # The "sum" metric summing all tracked metrics keeps a good measure of patience for early stopping and saving
        metrics_to_track = set()
        for task, task_type in zip(self.tasks, self.task_types):
            metrics_to_track.add(task if task_type != 'dependency' else 'las')

        metric_sum = 0
        for name, metric in metrics.items():
            if not name.startswith("_") and set(name.split("/")).intersection(metrics_to_track):
                if not name.endswith("ppl"):
                    metric_sum += metric

        metrics[".run/.sum"] = metric_sum
        #metrics[".run/.counter"] = self.counter
        #self.counter+= 0.001
        return metrics
