import openai
import os
from dotenv import load_dotenv
load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

def summarize_text(text):
    prompt = f"Summarize the following YouTube transcript:\n\n{text}\n\nSummary:"
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        max_tokens=400
    )
    
    return response.choices[0].message.content.strip()
