import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

model = genai.GenerativeModel("gemini-1.5-pro")  # ✅ Updated model name
response = model.generate_content("Summarize: The sky is blue because of Rayleigh scattering.")
print(response.text)
