import argparse
from yt_dlp import YoutubeDL
import os
from datetime import datetime, timedelta
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import time
import torch
import re
import json 
from difflib import SequenceMatcher

def is_similar(title1, title2, threshold=0.7):
    # 計算兩個字串的相似度
    ratio = SequenceMatcher(None, title1, title2).ratio()
    return ratio >= threshold

def get_video_info(video_url, output_dir):
    with YoutubeDL({'quiet': True}) as ydl:
        info_dict = ydl.extract_info(video_url, download=False)

    channel_name = info_dict.get('uploader', 'Unknown Channel')
    video_title = info_dict.get('title', None)
    info_dict['title'] = re.sub(r'[\/:*?"<>|]', '_', video_title)
    info_dict['transcript_dir'] = os.path.join(output_dir, channel_name)
    os.makedirs(info_dict['transcript_dir'], exist_ok=True)
    return info_dict

def download_subtitles(video_url, output_dir):
    """檢查並下載影片字幕，返回字幕檔案路徑，如果無字幕則返回 None"""
    with YoutubeDL({'quiet': True}) as ydl:
        info_dict = ydl.extract_info(video_url, download=False)

    channel_name = info_dict.get('uploader', 'Unknown Channel')
    video_title = info_dict.get('title', None)
    video_title = re.sub(r'[\/:*?"<>|]', '_', video_title)
    transcript_dir = os.path.join(output_dir, channel_name)
    os.makedirs(transcript_dir, exist_ok=True)

    # 設定下載字幕的選項
    ydl_opts_subtitles = {
        'writesubtitles': True,  # 下載字幕
        'skip_download': True,   # 不下載影片本身
        'subtitleslangs': ['zh-TW'],  # 指定字幕語言（可根據需求調整
        'outtmpl': os.path.join(transcript_dir, f'{video_title}.%(ext)s'),  # 字幕檔名
        'quiet': True,
    }

    with YoutubeDL(ydl_opts_subtitles) as ydl:
        ydl.download([video_url])  # 下載字幕

    # 檢查字幕文件是否存在
    subtitle_path = os.path.join(transcript_dir, f"{video_title}.zh-TW.vtt")  # 假設字幕格式為 .vtt
    if os.path.exists(subtitle_path):
        print(f"字幕已下載：{subtitle_path}")
        return subtitle_path
    else:
        print("影片沒有可用的字幕")
        return None
    
def clean_emoji(desstr,restr=''):  
    #過濾表情符號   
    try:  
        co = re.compile(u'['u'\U0001F300-\U0001F64F' u'\U0001F680-\U0001F6FF'u'\u2600-\u2B55]+')  
    except re.error:  
        co = re.compile(u'('u'\ud83c[\udf00-\udfff]|'u'\ud83d[\udc00-\ude4f\ude80-\udeff]|'u'[\u2600-\u2B55])+')  
    return co.sub(restr,desstr)

# 新增函數：讀取現有的 JSON 文件（如果存在）
def load_metadata_from_json(json_path):
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as json_file:
            metadata = json.load(json_file)
        print(f"已載入現有的元數據。")
    else:
        metadata = {}
        print(f"未找到現有元數據，將創建新的元數據文件。")
    return metadata

# 新增函數：儲存元數據到 JSON 文件
def save_metadata_to_json(metadata, json_path):
    with open(json_path, 'w', encoding='utf-8') as json_file:
        json.dump(metadata, json_file, ensure_ascii=False, indent=4)
    print(f"元數據已儲存到 {json_path}")

# Step 1: 提取 YouTube 頻道中近五天的影片網址
def get_video_urls(channel_url):
    # 計算五天前的日期
    cutoff_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')

    # 設定 yt-dlp 選項，使用 dateafter 篩選條件
    ydl_opts = {
        'extract_flat': True,  # 不下載影片，只提取資訊
        'skip_download': True,  # 跳過下載
        'quiet': True,  # 避免輸出過多訊息
        'dateafter': cutoff_date,  # 篩選五天前的影片
        'playlistreverse': True,  # 從最新的影片開始
        'playlist_items': '1:20',  # 限制檢查的影片數量，避免處理整個頻道
    }

    # 使用 yt-dlp 提取影片網址
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(channel_url, download=False)

    # 獲取時長大於30分鐘的影片網址
    video_urls = []
    for entry in info_dict['entries']:
        duration = entry.get('duration', 0)  # 影片長度（秒）
        if duration > 1800:  # 30分鐘 = 1800秒
            video_urls.append(entry['url'])

    return video_urls

# Step 2: 下載 YouTube 影片音訊並轉換為 MP3 格式
def download_audio_and_thumbnail(video_url, output_dir):
    # 使用 yt-dlp 提取影片資訊（不下載）
    with YoutubeDL({'quiet': True}) as ydl:
        info_dict = ydl.extract_info(video_url, download=False)

    channel_name = info_dict.get('uploader', 'Unknown Channel')
    transcript_dir = os.path.join(output_dir, channel_name)
    os.makedirs(transcript_dir, exist_ok=True)  # 創建節目資料夾

    video_title = info_dict.get('title', None)
    video_title = re.sub(r'[\/:*?"<>|]', '_', video_title)

    # 設定下載選項（音訊）
    ydl_opts_audio = {
        'format': 'bestaudio/best',  # 僅下載最佳音質
        'outtmpl': os.path.join(transcript_dir, f'{video_title}.%(ext)s'),  # 使用截取的標題作為檔名
        'postprocessors': [{  # 使用後處理器將檔案轉換為 MP3
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',  # 設定音訊格式為 mp3
            'preferredquality': '192',  # 設定音訊質量
        }],
    }

    # 設定下載選項（封面圖片）
    ydl_opts_thumbnail = {
        'skip_download': True,  # 跳過下載影片
        'writethumbnail': True,  # 下載縮圖
        'outtmpl': os.path.join(transcript_dir, f'{video_title}.%(ext)s'),  # 縮圖使用截取的標題作為檔名
        'quiet': True,
    }

    # 下載音訊
    with YoutubeDL(ydl_opts_audio) as ydl:
        ydl.extract_info(video_url, download=True)

    # 下載封面圖片
    with YoutubeDL(ydl_opts_thumbnail) as ydl:
        ydl.extract_info(video_url, download=True)

    # 生成音訊檔案路徑與縮圖檔案路徑
    audio_file = os.path.join(transcript_dir, f"{video_title}.mp3")
    thumbnail_file = os.path.join(transcript_dir, f"{video_title}.jpg")  # 假設縮圖檔案為 jpg 格式

    return audio_file, thumbnail_file, video_title

# Step 3: 使用 Hugging Face Distil-Whisper 模型轉錄 MP3 為文字
def transcribe_audio(audio_file):

    # 記錄開始時間
    start_time = time.time()

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    model_id = "openai/whisper-medium"

    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id, torch_dtype=torch_dtype, use_safetensors=True
    )
    model.to(device)

    processor = AutoProcessor.from_pretrained(model_id)

    pipe = pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        max_new_tokens=128,
        chunk_length_s=15,
        batch_size=16,
        torch_dtype=torch_dtype,
        device=device,
    )

    transcription_text = pipe(audio_file)["text"]

    # 記錄結束時間
    end_time = time.time()

    # 計算轉錄所花費的時間
    transcription_time = end_time - start_time
    print(f"轉錄音訊所花費的時間：{transcription_time:.2f} 秒")

    return transcription_text

# Function 1: 處理頻道 URL
def process_channel_videos(channel_url, output_dir, json_path, use_similarity_check=False):
    # 載入現有的元數據
    global metadata
    metadata = load_metadata_from_json(json_path)
    
    video_urls = get_video_urls(channel_url)
    video_urls = video_urls[::-1]  # 反轉順序 (由新到舊)
    print(f"取得的符合條件的影片數量：{len(video_urls)}")

    for video_url in video_urls:
        # 提取影片資訊
        channel_name, video_title, upload_date, original_url = extract_video_info(video_url)
        
        print(f"\n處理影片：{video_title} - 上傳日期：{upload_date}")

        if datetime.now() - upload_date > timedelta(days=7):
            print(f"跳過較舊的影片")
            break

        # 選擇使用相似度比對或是檔案是否存在的檢查方法
        if use_similarity_check:
            # 使用相似度比對方法檢查是否存在相似的逐字稿
            transcript_exists = False
            if channel_name in metadata:
                for existing_title in metadata[channel_name].keys():
                    if is_similar(video_title, existing_title):
                        print(f"發現相似的逐字稿，跳過影片: {video_title}")
                        transcript_exists = True
                        break
            if transcript_exists:
                continue
        else:
            # 使用原本的方法檢查逐字稿檔案是否存在
            transcript_path = os.path.join(output_dir, channel_name, f"{channel_name}_{upload_date.strftime('%Y-%m-%d')}_{video_title}.txt")
            if os.path.exists(transcript_path):
                print(f"逐字稿已存在，跳過影片: {video_title}")
                continue

        # 嘗試下載字幕
        subtitle_file = download_subtitles(video_url, output_dir)

        if subtitle_file:
            # 如果找到字幕，清理字幕並存儲
            transcription_text = clean_subtitles(subtitle_file)
            os.remove(subtitle_file)  # 刪除原始字幕文件
        else:
            # 如果沒有字幕，下載音訊並進行轉錄
            audio_file, thumbnail_file, truncated_title = download_audio_and_thumbnail(video_url, output_dir)
            transcription_text = transcribe_audio(audio_file)

        # 儲存轉錄文字到檔案
        transcript_path = save_transcription(transcription_text, output_dir, channel_name, upload_date, video_title)

        # 更新元數據
        update_metadata(metadata, channel_name, video_title, upload_date, original_url, transcript_path)
    
    # 儲存更新後的元數據到 JSON
    save_metadata_to_json(metadata, json_path)

# Function 2: 處理單個影片 URL
def process_single_video(video_url, output_dir, json_path):
    global metadata
    metadata = load_metadata_from_json(json_path)

    print(f"\n開始下載和轉錄影片音訊: {video_url}")

    # 優先嘗試下載字幕
    subtitle_file = download_subtitles(video_url, output_dir)

    if subtitle_file:
        transcription_text = clean_subtitles(subtitle_file)
        os.remove(subtitle_file)  # 刪除字幕文件
    else:
        # 沒有字幕的情況下，進行音訊下載和轉錄
        audio_file, thumbnail_file, video_title = download_audio_and_thumbnail(video_url, output_dir)
        transcription_text = transcribe_audio(audio_file)

    # 提取和處理影片信息
    channel_name, video_title, upload_date, original_url = extract_video_info(video_url)

    # 儲存轉錄文字
    transcript_path = save_transcription(transcription_text, output_dir, channel_name, upload_date, video_title)
    
    # 更新元數據
    update_metadata(metadata, channel_name, video_title, upload_date, original_url, transcript_path)
    
    # 儲存更新後的元數據到 JSON
    save_metadata_to_json(metadata, json_path)


def clean_subtitles(subtitle_file):
    """從字幕文件中去除時間戳和空行"""
    cleaned_lines = []
    with open(subtitle_file, 'r', encoding='utf-8') as f:
        transcription_text = f.read().splitlines()
        timestamp_pattern_vtt = re.compile(r'^\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}$')
        for line in transcription_text:
            # 檢查這行是否是時間戳格式的行，並排除空行
            if not timestamp_pattern_vtt.match(line) and line.strip() != '':
                cleaned_lines.append(line)
    cleaned_text = '\n'.join(cleaned_lines)
    print(f"字幕清理完成，純文字內容已提取。")
    return cleaned_text


def extract_video_info(video_url):
    """提取影片的基本信息"""
    with YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(video_url, download=False)
    
    channel_name = info.get('uploader', 'Unknown Channel')
    upload_date = datetime.strptime(info['upload_date'], '%Y%m%d')
    original_url = f"https://www.youtube.com/watch?v={info.get('id')}"
    video_title = info.get('title', 'Unknown')
    video_title = re.sub(r'[\/:*?"<>|]', '_', video_title)
    
    return channel_name, video_title, upload_date, original_url


def save_transcription(transcription_text, output_dir, channel_name, upload_date, video_title):
    """儲存轉錄文字到檔案"""
    transcript_dir = os.path.join(output_dir, channel_name)
    os.makedirs(transcript_dir, exist_ok=True)

    transcript_path = os.path.join(transcript_dir, f"{channel_name}_{upload_date.strftime('%Y-%m-%d')}_{video_title}.txt")
    
    with open(transcript_path, 'w', encoding='utf-8') as f:
        f.write(transcription_text)
    
    print(f"轉錄完成！文字稿已儲存到: {transcript_path}")
    
    return transcript_path


def update_metadata(metadata, channel_name, video_title, upload_date, original_url, transcript_path):
    """更新元數據字典並包括逐字稿路徑"""
    if channel_name not in metadata:
        metadata[channel_name] = {}
    
    metadata[channel_name][video_title] = {
        'upload_date': upload_date.strftime('%Y-%m-%d'),
        'original_url': original_url,
        'transcript_path': transcript_path  # 新增這一行來儲存逐字稿的路徑
    }


def main():
    # 設定 argparse 來解析命令列參數
    parser = argparse.ArgumentParser(description="處理 YouTube 頻道或單個影片的轉錄和字幕下載")
    parser.add_argument('mode', choices=['channel', 'single'], help="選擇要處理的模式：'channel' 處理頻道影片，'single' 處理單個影片")
    parser.add_argument('url', help="YouTube 頻道 URL 或影片 URL")
    parser.add_argument('--output_dir', default='./transcriptions', help="輸出目錄，預設為 './transcriptions'")
    parser.add_argument('--metadata_path', default='./transcriptions/metadata.json', help="元數據位置，預設為 './transcriptions/metadata.json'")
    args = parser.parse_args()
    
    # 設定輸出目錄
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # 根據 mode 選擇處理方法
    if args.mode == 'channel':
        process_channel_videos(args.url, output_dir, args.metadata_path)
    elif args.mode == 'single':
        process_single_video(args.url, output_dir, args.metadata_path)

if __name__ == "__main__":
    main()