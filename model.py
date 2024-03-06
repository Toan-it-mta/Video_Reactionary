from transformers import AutoModelForSequenceClassification, TrainingArguments, Trainer, AutoTokenizer, DataCollatorWithPadding, TrainerCallback
import pandas as pd
from datasets import Dataset
from utils import compute_metrics, preprocessing_text
from copy import deepcopy

def load_train_valid_dataset(train_data_dir:str, val_size:float):
    """
    Load bộ dữ liệu và chia train/valid
    Parameters
    ----------
    train_data_dir : str , Đường dẫn tới file train.csv
    val_size : float , Tỷ lệ của tập Valid

    """
    df = pd.read_csv(train_data_dir)
    df = df[df['text'].notna()]
    del df['dataset']
    df_valid = df.sample(frac=val_size)
    df_valid['text'] = df_valid['text'].apply(preprocessing_text)
    df_train = df.drop(df_valid.index)
    df_train['text'] = df_train['text'].apply(preprocessing_text)
    train_dataset = Dataset.from_pandas(df_train)
    valid_dataset = Dataset.from_pandas(df_valid)
    return train_dataset, valid_dataset

class CustomCallback(TrainerCallback):
    def __init__(self, trainer) -> None:
        super().__init__()
        self._trainer = trainer

    def on_epoch_end(self, args, state, control, **kwargs):
        """
        Thực hiện đánh giá lại tập Train
        """
        if control.should_evaluate:
            control_copy = deepcopy(control)
            self._trainer.evaluate(eval_dataset=self._trainer.train_dataset, metric_key_prefix="train")
            return control_copy
    
class Model_Reactionary_Detection:
    def __init__(self, labId:str = "reactionary_detection", model_name:str = 'distilbert-base-uncased', train_data_dir:str = "./datasets/train.csv", val_size:float = 0.1):
        """
        Parameters
        ----------
        labId : str, optional, default: 'reactionary_detection' , Nhãn của bài Lab
        model_name : str, optional, default: 'distilbert-base-uncased' , Tên của mô hình cần Fine-tune
        train_data_dir : str, optional, default: './datasets/train.csv' , Đường dẫn tới file Train.csv
        val_size : float, optional, default: 0.1 , Tỷ lệ tập Valid

        """
        
        self.id2label = {0: "NEGATIVE", 1: "POSITIVE"}
        self.label2id = {"NEGATIVE": 0, "POSITIVE": 1}
        self.labId = labId
        self.model_name = model_name
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name, num_labels=2, id2label=self.id2label, label2id=self.label2id
        )
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.train_dataset, self.valid_dataset = load_train_valid_dataset(train_data_dir,val_size)
        self.data_collator = DataCollatorWithPadding(tokenizer=self.tokenizer)

    
    def preprocess_function(self, examples):
        """
        Tiền xử lý dữ liệu
        """
        return self.tokenizer(examples["text"], truncation=True)
    
    def train(self, learning_rate:float = 1e-5, EPOCHS:int = 10, BS:int = 16):
        """
        Mô hình thực thi huyến luyện
        Parameters
        ----------
        learning_rate : float, optional, default: 1e-05 , Learning reate
        EPOCHS : int, optional, default: 10 , Số epochs huấn luyện
        BS : int, optional, default: 16 ,  Độ lớn của Batch Size

        """
        self.train_dataset = self.train_dataset.map(self.preprocess_function, batched=True)
        self.valid_dataset = self.valid_dataset.map(self.preprocess_function, batched=True)
        training_args = TrainingArguments(
            output_dir=f"./modelDir/{self.labId}/log_train/{self.model_name}",
            evaluation_strategy="epoch",
            save_strategy="no",
            per_device_train_batch_size=BS,
            per_device_eval_batch_size=BS,
            learning_rate=learning_rate,
            num_train_epochs=1,
            lr_scheduler_type='constant',
            logging_strategy = "no",
            # logging_steps=25, #sau bao nhiêu step thì sẽ log lại lr, epochs, loss
            report_to=["tensorboard"],
            # load_best_model_at_end=True,
            # metric_for_best_model="accuracy"
        )
        trainer = Trainer(
            model = self.model,
            args = training_args,
            train_dataset = self.train_dataset, # type: ignore
            eval_dataset = self.valid_dataset, # type: ignore
            tokenizer = self.tokenizer,
            data_collator = self.data_collator,
            compute_metrics = compute_metrics, # type: ignore
        )
        trainer.add_callback(CustomCallback(trainer))
        for _ in range(EPOCHS):
            trainer.train()
            trainer.save_model(f"./modelDir/{self.labId}/log_train/{self.model_name}/ckpt-{_+1}")
            yield {
                "epoch" : _ + 1,
                "train_accuracy" : trainer.state.log_history[0]["train_accuracy"],
                "train_loss": trainer.state.log_history[0]["train_loss"],
                "eval_accuracy" : trainer.state.log_history[1]["eval_accuracy"],
                "eval_loss": trainer.state.log_history[1]["eval_loss"]
            }
            
# if __name__ == "__main__":
#     model = Model_Reactionary_Detection()
#     results = []
#     results_generator = model.train()
#     for result in results_generator:
#         results.append(result)
#     print(results)
