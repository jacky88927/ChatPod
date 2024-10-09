import sys
import json
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit, QTabWidget, QGroupBox, QComboBox, QLineEdit, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QIcon, QColor
from utils import (initialize_openai_client, initialize_groq_client, get_openai_response, 
                   get_groq_response, load_json_data, save_json_data, load_transcript, SummaryWorker)
from youtube_video_processor import process_single_video

groq_api_key = "Your groq api key"
openai_api_key = "Your openai api key"


class DownloadThread(QThread):
    download_finished = pyqtSignal(str)  # 定義一個信號，會發送一個字符串

    def __init__(self, url, output_dir, json_path):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.json_path = json_path

    def run(self):
        """在這裡執行下載操作"""
        try:
            # 假設 process_single_video 是用於下載的函數
            process_single_video(self.url, output_dir=self.output_dir, json_path=self.json_path)
            self.download_finished.emit("逐字稿和摘要已成功下載並顯示！")  # 發送信號，並傳遞字符串參數
        except Exception as e:
            self.download_finished.emit(f"下載過程中出現錯誤：{str(e)}")  # 發送錯誤消息

class VideoTranscriptsApp(QWidget):
    def __init__(self, data, file_path):
        super().__init__()
        self.data = data
        self.file_path = file_path
        self.current_transcript = ""
        self.current_summary = ""
        self.current_chat_history = []  # 用於儲存聊天歷史
        self.chat_histories = {}  # 用於儲存每個逐字稿的聊天歷史
        self.current_button = None
        self.current_video_info = None
        self.summary_worker = None
        self.chat_worker = None  # 用來處理聊天回應的 worker thread
        self.loading_timer = None
        self.use_openai = False
        self.transcript_sent = False
        self.model = "llama-3.1-70b-versatile"
        self.api_client = initialize_groq_client(groq_api_key)
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Podcast ChatBot')
        self.setMinimumWidth(1200)
        self.setGeometry(100, 100, 1200, 700)

        self.setStyleSheet("""
            QWidget {
                background-color: #f4f4f4;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            QGroupBox {
                font-size: 15px;
                font-weight: bold;
                border: none;
                padding: 10px 5px;
                margin-top: 5px;
                border-radius: 4px;
                background-color: transparent;
            }
            QGroupBox::title {
                font-weight: bold;
                color: #111;
                subcontrol-origin: margin;
                padding-left: 5px;
            }
            QTabWidget::pane {
                border-top: 2px solid #ccc;
            }
            QTextEdit, QLineEdit {
                background-color: #ffffff;
                border: 1px solid #ddd;
                padding: 10px;
                font-size: 15px;
                color: #333333;
                border-radius: 4px;
            }
            QComboBox {
                padding: 5px 10px;
                font-size: 14px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #fff;
                color: #333;
                min-width: 150px;
            }
            QPushButton {
                background-color: #2D9CDB;
                color: #ffffff;
                border-radius: 5px;
                padding: 8px;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #56CCF2;
            }
        """)

        main_layout = QHBoxLayout()
        sidebar_layout = QVBoxLayout()

        # 使用 QHBoxLayout 來水平排列 URL 輸入框和下載按鈕
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("輸入youtube網址...")
        self.url_input.setStyleSheet("padding: 8px;")
        url_layout.addWidget(self.url_input)

        self.download_button = QPushButton("下載")
        self.download_button.clicked.connect(self.download_transcript)
        url_layout.addWidget(self.download_button)

        # 將 URL 輸入框和下載按鈕的布局添加到 sidebar_layout 的頂部
        sidebar_layout.addLayout(url_layout)

        for category, videos in self.data.items():
            group_box = QGroupBox(f"{category}", self)
            group_layout = QVBoxLayout()

            group_box.setStyleSheet("background-color: transparent;")

            for video_title, video_info in videos.items():
                button = QPushButton(video_title, self)
                button.setCheckable(True)
                button.setStyleSheet("""
                    QPushButton {
                        padding: 12px;
                        font-size: 15px;
                        background-color: #ffffff;
                        color: #333333;
                        border-radius: 5px;
                    }
                    QPushButton:checked {
                        background-color: #56CCF2;
                        border: 2px solid #2D9CDB;
                        color: #ffffff;
                    }
                    QPushButton:hover {
                        background-color: #E6F7FF;
                    }
                """)
                
                button_shadow = QGraphicsDropShadowEffect()
                button_shadow.setBlurRadius(15)
                button_shadow.setOffset(0, 0)
                button_shadow.setColor(QColor(0, 0, 0, 80))
                button.setGraphicsEffect(button_shadow)

                button.clicked.connect(lambda checked, info=video_info, btn=button: self.load_transcript_and_summary(info, btn))
                group_layout.addWidget(button)

            group_box.setLayout(group_layout)
            sidebar_layout.addWidget(group_box)

        main_layout.addLayout(sidebar_layout)

        right_layout = QVBoxLayout()
        right_panel_widget = QWidget()
        right_panel_widget.setLayout(right_layout)
        right_panel_widget.setMinimumWidth(600)

        api_layout = QHBoxLayout()
        api_label = QLabel("Select API:", self)
        api_layout.addWidget(api_label)
        self.api_selection = QComboBox(self)
        self.api_selection.addItem("Groq llama 3.1 70b")
        self.api_selection.addItem("Groq llama 3.1 8b")
        self.api_selection.addItem("OpenAI gpt-4o-mini")
        self.api_selection.currentIndexChanged.connect(self.change_api)
        api_layout.addWidget(self.api_selection)
        api_layout.addStretch()
        right_layout.addLayout(api_layout)

        self.tab_widget = QTabWidget(self)

        self.system_message_display = QTextEdit(self)
        self.system_message_display.setReadOnly(True)

        self.transcript_display = QTextEdit(self)
        self.transcript_display.setReadOnly(True)
        self.summary_display = QTextEdit(self)
        self.summary_display.setReadOnly(True)

        self.chat_display = QTextEdit(self)
        self.chat_display.setReadOnly(True)
        self.chat_input = QLineEdit(self)
        self.chat_input.setPlaceholderText("Enter your message...")
        self.chat_input.returnPressed.connect(self.send_chat_message)

        chat_layout = QVBoxLayout()
        chat_layout.addWidget(self.chat_display)
        chat_layout.addWidget(self.chat_input)

        chat_widget = QWidget()
        chat_widget.setLayout(chat_layout)

        self.tab_widget.addTab(self.summary_display, "Summary")
        self.tab_widget.addTab(chat_widget, "Chat")
        self.tab_widget.addTab(self.transcript_display, "Transcript")
        self.tab_widget.addTab(self.system_message_display, "System Messages")

        self.tab_widget.currentChanged.connect(self.update_buttons_visibility)

        right_layout.addWidget(self.tab_widget)

        self.button_layout = QHBoxLayout()
        self.save_button = QPushButton("確認儲存", self)
        self.save_button.clicked.connect(self.save_summary)
        self.save_button.setEnabled(False)
        self.button_layout.addWidget(self.save_button)

        self.regenerate_button = QPushButton("重新生成", self)
        self.regenerate_button.clicked.connect(self.regenerate_summary)
        self.regenerate_button.setEnabled(False)
        self.button_layout.addWidget(self.regenerate_button)

        right_layout.addLayout(self.button_layout)
        main_layout.addWidget(right_panel_widget)
        self.setLayout(main_layout)

    def download_transcript(self):
        """下載並處理逐字稿"""
        url = self.url_input.text().strip()
        if not url:
            self.system_message_display.append("請輸入有效的youtube網址！")
            self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.system_message_display))  # 切換到系統訊息頁面
            return

        # 清空輸入框中的文字
        self.url_input.clear()

        self.system_message_display.append("正在開始下載！")
        self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.system_message_display))  # 切換到系統訊息頁面

        # 創建和啟動下載執行緒
        self.download_thread = DownloadThread(url, './transcriptions', './transcriptions/metadata.json')
        self.download_thread.download_finished.connect(self.on_download_finished)  # 連接信號和槽
        self.download_thread.start()

    def on_download_finished(self, message):
        """下載完成後的處理"""
        self.system_message_display.append(message)
        if "成功" in message:
            self.system_message_display.append("已下載")

    def update_buttons_visibility(self):
        """更新按鈕顯示狀態"""
        current_tab_index = self.tab_widget.currentIndex()
        if current_tab_index == 0:  # 0 表示 "Summary" 標籤
            self.save_button.show()
            self.regenerate_button.show()
        else:
            self.save_button.hide()
            self.regenerate_button.hide()



    def change_api(self, index):
        """切換使用的API"""
        if index == 0:
            self.use_openai = False
            self.model = "llama-3.1-70b-versatile"
            self.api_client = initialize_groq_client(groq_api_key)
        elif index == 1:
            self.use_openai = False
            self.model = "llama-3.1-8b-instant"
            self.api_client = initialize_groq_client(groq_api_key)
        else:
            self.use_openai = True
            self.model = "gpt-4o-mini"
            self.api_client = initialize_openai_client(openai_api_key)

    def load_transcript_and_summary(self, video_info, button):
        """切換逐字稿時的處理"""
        # 如果點擊的標題與當前選中的標題相同，則不執行任何操作
        if self.current_button == button and button.isChecked():
            return

        # 保存當前逐字稿的聊天歷史
        if self.current_video_info:
            self.chat_histories[self.current_video_info['transcript_path']] = self.current_chat_history

        # 重置之前選中的按鈕狀態
        if self.current_button and self.current_button != button:
            self.current_button.setChecked(False)
            self.current_button.setStyleSheet("""
                QPushButton {
                    padding: 12px;
                    font-size: 15px;
                    background-color: #ffffff;
                    color: #333333;
                    border-radius: 5px;
                }
                QPushButton:checked {
                    background-color: #56CCF2;
                    border: 2px solid #2D9CDB;
                    color: #ffffff;
                }
                QPushButton:hover {
                    background-color: #E6F7FF;
                }
            """)

        # 設置當前選中的按鈕
        self.current_button = button
        self.current_button.setChecked(True)
        self.current_video_info = video_info

        transcript_path = video_info['transcript_path']
        self.current_transcript = load_transcript(transcript_path)
        self.transcript_display.setText(self.current_transcript)

        # 加載之前的聊天歷史，或者設置為空
        self.current_chat_history = self.chat_histories.get(transcript_path, [])
        self.transcript_sent = False  # 重置，因為是新逐字稿

        self.chat_display.clear()  # 清空聊天顯示
        for message in self.current_chat_history:
            role = "User" if message["role"] == "user" else "Assistant"
            self.chat_display.append(f"{role}: {message['content']}")

        # 檢查是否已存在摘要
        if 'summary' in video_info:
            self.current_summary = video_info['summary']
            self.summary_display.setText(self.current_summary)
            self.save_button.setEnabled(True)
            self.regenerate_button.setEnabled(True)
        else:
            self.start_loading_animation()  # 開始動態顯示 "生成中..."
            self.save_button.setEnabled(False)
            self.regenerate_button.setEnabled(True)

            # 終止之前的摘要生成 worker thread
            if self.summary_worker and self.summary_worker.isRunning():
                self.summary_worker.terminate()

            # 開始生成摘要（使用 Worker thread）
            self.summary_worker = SummaryWorker(self.current_transcript, self.use_openai, self.model, self.api_client, "summary")
            self.summary_worker.summary_generated.connect(self.display_summary)
            self.summary_worker.start()

    def start_loading_animation(self):
        """啟動'生成中...'的動態效果"""
        self.loading_text = "生成中"
        self.loading_timer = QTimer(self)
        self.loading_timer.timeout.connect(self.update_loading_text)
        self.loading_timer.start(500)

    def update_loading_text(self):
        """更新'生成中...'的文字效果"""
        self.loading_text += "."
        if len(self.loading_text) > 8:
            self.loading_text = "生成中"
        self.summary_display.setText(self.loading_text)

    def stop_loading_animation(self):
        """停止'生成中...'的動態效果"""
        if self.loading_timer:
            self.loading_timer.stop()
            self.loading_timer = None

    def display_summary(self, summary):
        """顯示摘要內容"""
        self.stop_loading_animation()
        self.current_summary = summary
        self.summary_display.setText(summary)
        self.save_button.setEnabled(True)

    def save_summary(self):
        """保存摘要到metadata.json"""
        for category, videos in self.data.items():
            for video_title, video_info in videos.items():
                if video_info == self.current_video_info:
                    self.data[category][video_title]['summary'] = self.current_summary
                    save_json_data(self.file_path, self.data)
                    return

    def regenerate_summary(self):
        """重新生成摘要"""
        if self.current_transcript:
            self.start_loading_animation()
            self.save_button.setEnabled(False)

            if self.summary_worker and self.summary_worker.isRunning():
                self.summary_worker.terminate()

            self.summary_worker = SummaryWorker(self.current_transcript, self.use_openai, self.model, self.api_client, "summary")
            self.summary_worker.summary_generated.connect(self.display_summary)
            self.summary_worker.start()

    def send_chat_message(self):
        """處理用戶聊天輸入"""
        user_input = self.chat_input.text()
        if user_input.strip() == "":
            return

        # 更新聊天歷史並顯示
        self.current_chat_history.append({"role": "user", "content": user_input})

        # 使用 HTML 顯示用戶消息
        self.chat_display.append(
            f'<div style="color:#12095c; padding:8px; border-radius:5px; margin:5px 0; display:flex; align-items:center;">'
            f'<img src="icons/user_icon.png" alt="User Icon" style="width:24px; height:24px; margin-right:8px; vertical-align:top;">'
            f'<span style="line-height: 24px;">{" "+user_input}</span></div>'
        )
        self.chat_input.clear()

        # 如果這是第一次發送聊天訊息，加入逐字稿內容
        if not self.transcript_sent:
            initial_prompt = [
                {"role": "system", "content": "你是一個聊天助手，請根據以下逐字稿內容回答用戶的問題。回答時使用html格式做回覆，不要有任何多餘的符號，不要隨意加粗或放大字體。"},
                {"role": "user", "content": "逐字稿內容: " + self.current_transcript}
            ]
            self.current_chat_history = initial_prompt + self.current_chat_history
            self.transcript_sent = True

        # 創建一個 worker 來處理聊天回應
        self.chat_worker = SummaryWorker(
            content=self.current_chat_history,
            use_openai=self.use_openai,
            model=self.model,
            client=self.api_client,
            mode="chat"
        )
        self.chat_worker.summary_generated.connect(self.display_chat_response)
        self.chat_worker.start()

    def display_chat_response(self, response):
        """顯示聊天回應"""
        self.current_chat_history.append({"role": "assistant", "content": response})

        # 使用 HTML 顯示助手消息
        self.chat_display.append(
            f'<div style="color:#000000; padding:8px; border-radius:5px; margin:5px 0; display:flex; align-items:center;">'
            f'<img src="icons/assistant_icon2.png" alt="Assistant Icon" style="width:24px; height:24px; margin-right:8px; vertical-align:top;">'
            f'<span style="line-height: 24px;">{" "+response}</span></div>'
        )



# Load data from JSON file
file_path = './transcriptions/metadata.json'
data = load_json_data(file_path)

# Create the application
app = QApplication(sys.argv)

# 設置應用程式圖標
app.setWindowIcon(QIcon('icons/assistant_icon.png'))  # 使用 .ico 文件

# Apply a global stylesheet for the app
app.setStyleSheet("""
    QPushButton {
        background-color: #4CAF50;
        color: white;
        border-radius: 5px;
        padding: 10px;
    }
    QPushButton:hover {
        background-color: #45a049;
    }
    QScrollArea {
        border: none;
    }
""")

viewer = VideoTranscriptsApp(data, file_path)
viewer.show()
sys.exit(app.exec_())
