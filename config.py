"""Configuration module for the Discord meeting transcription bot."""

import os
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client, Client
from faster_whisper import WhisperModel

# Load environment variables
load_dotenv()

# Environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Whisper model configuration
WHISPER_MODEL_SIZE = "pariya47/distill-whisper-th-large-v3-ct2"
whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cuda", compute_type="float16")

# Thai meeting assistant system prompt
MEETING_ASSISTANT_PROMPT = """
คุณคือผู้ช่วยประชุม (meeting‐assistant) มีหน้าที่อ่านบันทึกการประชุมทั้งหมด แล้วสร้าง:
รายการหัวข้ออภิปรายหลัก (bullet points)
รายการงานที่ได้รับมอบหมายในรูปแบบ "ผู้รับมอบหมาย → งาน → กำหนดเวลา (ถ้ามี)"
สำหรับเป้าหมาย การตัดสินใจ หรือขั้นตอนถัดไป
ให้ผลลัพธ์ออกมาใน 3 ส่วน ชื่อว่า:
• "หัวข้ออภิปราย"
• "งานที่ได้รับมอบหมาย"
• "เป้าหมายและการตัดสินใจ"
แต่ละบูลเล็ตรายการไม่เกินหนึ่งประโยค และใช้ข้อมูลจาก MongoDB memory ให้ครบถ้วน
"""
