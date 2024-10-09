# ChatPod: Chat with YouTube Podcasts and Videos

一個用於下載 YouTube 影片的逐字稿，生成摘要，並透過聊天介面與逐字稿進行互動的工具。

## 介面截圖

### 看 Podcast 摘要
![看 podcast 摘要的截圖](images/UI1.png)

### 跟 Podcast 內容聊天
![跟 podcast 內容聊天的截圖](images/UI2.png)

## 功能

- 下載 YouTube 頻道或單個影片的逐字稿。
- 使用 OpenAI Whisper 將影片轉換成文字。
- 生成影片摘要，便於理解影片內容。
- 使用圖形化界面 (UI) 與逐字稿內容互動，提問影片相關的問題。

## 技術架構

- `youtube_video_processor_huggingface.py`：負責下載 YouTube 影片，並生成逐字稿。
- `utils.py`：輔助工具，包括 API 客戶端初始化和檔案讀寫。
- `transcript_UI.py`：PyQt5 使用者介面，用於展示逐字稿和與其互動。

## 安裝與環境設置

### 前置條件

- Python 3.8 以上版本
- pip

### 安裝步驟

1. 克隆這個專案：
    ```bash
    git clone https://github.com/yourusername/youtube-transcript-chat.git
    ```
2. 進入專案目錄：
    ```bash
    cd youtube-transcript-chat
    ```
3. 安裝所需依賴：
    ```bash
    pip install -r requirements.txt
    ```

## 使用方式

### 下載影片逐字稿

運行以下命令來處理 YouTube 影片或頻道：

```bash
python youtube_video_processor_huggingface.py channel "https://www.youtube.com/channel/yourchannelurl" --output_dir ./transcriptions
```

或者處理單個影片：

```bash
python youtube_video_processor_huggingface.py single "https://www.youtube.com/watch?v=yourvideoid" --output_dir ./transcriptions
```

### 啟動 UI 介面

生成逐字稿後，運行以下命令啟動 UI：

```bash
python transcript_UI.py
```

這將啟動圖形化界面，允許使用者選擇逐字稿與之互動，並生成影片的摘要。

## 檔案結構

- `youtube_video_processor_huggingface.py`：影片下載與轉錄。
- `utils.py`：輔助函數，包括 API 初始化和 JSON 檔案讀寫。
- `transcript_UI.py`：使用者介面。
- `requirements.txt`：所需的 Python 套件。

## 範例

- 處理 YouTube 頻道影片並生成摘要：
  ```bash
  python youtube_video_processor_huggingface.py channel "https://www.youtube.com/channel/yourchannelurl" --output_dir ./transcriptions
  ```
- 啟動 UI 與逐字稿進行互動：
  ```bash
  python transcript_UI.py
  ```


