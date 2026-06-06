import base64
import os
from openai import AsyncOpenAI
from config import OPENAI_API_KEY

client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def transcribe_voice(file_path: str) -> str:
    """Transcribe a voice message using Whisper."""
    with open(file_path, "rb") as audio_file:
        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ru",
        )
    return transcript.text


async def analyze_image(image_path: str) -> str:
    """Analyze an uploaded image and describe what is visible."""
    with open(image_path, "rb") as img_file:
        image_data = base64.b64encode(img_file.read()).decode("utf-8")

    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    mime_type = mime_map.get(ext, "image/jpeg")

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Опиши подробно, что изображено на этом фото. "
                            "Укажи: людей (лица, одежда), логотипы, текст, здания, продукты, "
                            "фон, освещение, стиль. Ответ на русском языке."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                    },
                ],
            }
        ],
        max_tokens=600,
    )
    return response.choices[0].message.content


async def generate_prompt(user_data: dict) -> str:
    """Generate a professional AI prompt based on collected user data."""
    system = (
        "You are an expert AI prompt engineer. "
        "Generate highly detailed, professional prompts for AI image/video generation tools. "
        "Prompts must be in English. "
        "Structure the prompt with clearly labeled sections."
    )

    user_message = f"""
Create a professional AI generation prompt based on the following information:

User description: {user_data.get('description', '')}
Image analysis (if photo uploaded): {user_data.get('image_analysis', 'No reference photo')}
Result type: {user_data.get('result_type', 'image')}
Output preference: {user_data.get('output_type', 'both')}
Elements to preserve: {user_data.get('preserve', 'none specified')}
Style: {user_data.get('style', 'realistic')}
Lighting: {user_data.get('lighting', 'natural')}
Target tool: {user_data.get('tool', 'general')}
Platform: {user_data.get('platform', 'general')}

Structure the prompt with these sections:
1. [MAIN TASK] - Core description of what to generate
2. [PRESERVE] - Elements that must not be changed (faces, logos, text, architecture, packaging, colors, layout)
3. [STYLE] - Visual style and mood
4. [LIGHTING] - Lighting setup
5. [COMPOSITION] - Camera angle, framing, perspective
6. [QUALITY] - Resolution and quality tags (4K, 8K, photorealistic, etc.)
7. [NEGATIVE] - What to avoid or not change
{"8. [CAMERA MOVEMENT] - Motion, camera path, duration (for video)" if user_data.get('result_type') == 'video' else ""}

Make the prompt copy-paste ready, rich in detail, and optimized for {user_data.get('tool', 'AI image generation')}.
"""

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        max_tokens=1200,
    )
    return response.choices[0].message.content


async def refine_prompt(original_prompt: str, correction: str) -> str:
    """Update an existing prompt based on user correction."""
    system = (
        "You are an expert AI prompt engineer. "
        "Update the given prompt based on the user's correction. "
        "Keep all important preservation rules unless the user explicitly removes them. "
        "Return only the updated prompt in English, with the same section structure."
    )

    user_message = f"""
Original prompt:
{original_prompt}

User correction (in Russian or English):
{correction}

Update the prompt accordingly. Keep existing preservation rules unless the user says to remove them.
"""

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        max_tokens=1200,
    )
    return response.choices[0].message.content


async def generate_image(prompt: str) -> bytes:
    """Generate an image using DALL-E 3 and return the image bytes."""
    # Use only the first 3 sections to stay within DALL-E's prompt limit
    dalle_prompt = prompt[:3900]  # DALL-E has a 4000 char limit

    response = await client.images.generate(
        model="dall-e-3",
        prompt=dalle_prompt,
        size="1024x1024",
        quality="hd",
        n=1,
    )

    image_url = response.data[0].url

    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as resp:
            return await resp.read()


async def chat_reply(system_prompt: str, user_message: str, history: list = None) -> str:
    """Generic GPT-4o call for conversational replies."""
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=500,
    )
    return response.choices[0].message.content
