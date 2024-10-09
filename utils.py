from groq import Groq
from openai import OpenAI
from PyQt5.QtCore import QThread, pyqtSignal
import json

def initialize_openai_client(api_key):
    return OpenAI(api_key=api_key)

def initialize_groq_client(api_key):
    return Groq(api_key=api_key)

def get_openai_response(transcript, client, model):
    completion = client.chat.completions.create(
        model=model,
        messages=transcript  # 使用完整的聊天歷史
    )
    message = completion.choices[0].message.content
    return message

def get_groq_response(transcript, client, model):
    chat_completion = client.chat.completions.create(
        messages=transcript,  # 使用完整的聊天歷史
        model=model,
    )
    return chat_completion.choices[0].message.content.strip()

def load_json_data(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def save_json_data(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def load_transcript(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

class SummaryWorker(QThread):
    summary_generated = pyqtSignal(str)

    def __init__(self, content, use_openai, model, client, mode):
        super().__init__()
        self.content = content
        self.use_openai = use_openai
        self.model = model
        self.client = client
        self.mode = mode  # 'summary' or 'chat'

    def run(self):
        if self.mode == "summary":
            summary_prompt = "你是一個專業的逐字稿摘要生成器。當你收到逐字稿時，請產生一份詳盡且專業的摘要。摘要應專注於總結主持人關於企業、股市、產業及經濟面的看法和觀點。最重要的是摘要必須包括逐字稿中提到的每一間企業，條列式列出整理整理主持人對這些企業的近期看法和相關消息，每個觀點都要包含在摘要內。若逐字稿中有廣告、業配或與上述主題無關的閒聊內容，請忽略。僅需列出摘要內容，不需要包含任何額外的對話或說明。使用繁體中文回復。回答時使用html格式做回覆，不要有任何多餘的符號，不要隨意加粗或放大字體。"
            if self.use_openai:
                summary = get_openai_response([{"role":"system", "content":summary_prompt}, {"role": "user", "content": "逐字稿: " + self.content}], self.client, self.model)
            else:
                summary = get_groq_response([{"role":"system", "content":summary_prompt}, {"role": "user", "content": "逐字稿: " + self.content}], self.client, self.model)
            self.summary_generated.emit(summary)
        elif self.mode == "chat":
            if self.use_openai:
                response = get_openai_response(self.content, self.client, self.model)
            else:
                response = get_groq_response(self.content, self.client, self.model)
            self.summary_generated.emit(response)
