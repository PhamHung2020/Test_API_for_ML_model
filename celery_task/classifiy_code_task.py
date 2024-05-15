from celery import Task
import logging

from ai_model import get_model_tokenizer


class ClassifyCodeTask(Task):
    abstract = True

    def __init__(self):
        super().__init__()
        self.device = "cuda"
        self.tokenizer = None
        self.classifier = None

    def __call__(self, *args, **kwargs):
        if self.classifier is None:
            logging.info('Loading Model...')
            tokenizer, classifier = get_model_tokenizer(device=self.device)
            self.tokenizer = tokenizer
            self.classifier = classifier
            logging.info('Model loaded')

        return self.run(*args, **kwargs)
