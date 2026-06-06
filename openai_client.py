import base64
import os
import logging
from openai import AsyncOpenAI
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def transcribe_voice(file_path: str) -> str:
    """Transcribe a voice message using Whisper."""
    with open(file_path, "rb") as audio_file:
        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
    return transcript.text


async def analyze_image(image_path: str) -> str:
    """Analyze an uploaded image using GPT-4o vision."""
    with open(image_path, "rb") as img_file:
        image_data = base64.b64encode(img_file.read()).decode("utf-8")

    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
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
                            "Подробно опиши что изображено на фото. "
                            "Укажи: тип объекта (здание, продукт, человек, пейзаж и т.д.), "
                            "ключевые элементы которые нельзя менять (лица, логотипы, текст, архитектура, упаковка), "
                            "стиль, освещение, цвета, фон. "
                            "Ответ на русском языке, кратко и по делу."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}",
                            "detail": "high"
                        },
                    },
                ],
            }
        ],
        max_tokens=800,
    )
    return response.choices[0].message.content


async def generate_prompt(user_data: dict) -> str:
    """Generate a professional AI prompt based on collected user data."""
    system = (
        "You are an expert AI prompt engineer specializing in image and video generation. "
        "Generate highly detailed, professional prompts optimized for AI image generation tools. "
        "Always write prompts in English. Use clear sections. Be specific and detailed."
    )

    image_info = user_data.get("image_analysis", "")
    description = user_data.get("description", "")
    style = user_data.get("style", "realistic")
    tool = user_data.get("tool", "general AI image generator")

    user_message = f"""
Create a professional AI image generation prompt based on this information:

{"📷 REFERENCE PHOTO ANALYSIS: " + image_info if image_info else ""}
{"📝 USER DESCRIPTION: " + description if description else ""}
🎨 STYLE: {style}
🛠 TARGET TOOL: {tool}

Write a detailed prompt with these sections:

[MAIN TASK]
Describe exactly what to generate.

[PRESERVE - DO NOT CHANGE]
List all elements that must remain identical: faces, logos, text, architectural details, product packaging, colors, layout. If reference photo was provided, extract these from the photo analysis. Be very specific.

[STYLE & MOOD]
Visual style, atmosphere, mood.

[LIGHTING]
Lighting setup and conditions.

[COMPOSITION]
Camera angle, framing, perspective, depth.

[QUALITY]
Resolution, render quality tags (photorealistic, 8K, ultra-detailed, etc.)

[NEGATIVE PROMPT]
What to avoid, what not to distort or change.

Make it ready to copy and paste directly into {tool}. Be thorough and specific.
"""

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        max_tokens=1500,
    )
    return response.choices[0].message.content


async def refine_prompt(original_prompt: str, correction: str) -> str:
    """Update an existing prompt based on user correction."""
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert AI prompt engineer. "
                    "Update the given prompt based on the correction. "
                    "Keep all preservation rules unless user explicitly removes them. "
                    "Return only the updated prompt in English with the same section structure."
                )
            },
            {
                "role": "user",
                "content": f"Original prompt:\n{original_prompt}\n\nCorrection:\n{correction}\n\nReturn updated prompt only."
            }
        ],
        max_tokens=1500,
    )
    return response.choices[0].message.content


async def generate_image_dalle(prompt: str) -> bytes:
    """Generate an image using DALL-E 3."""
    import aiohttp

    # DALL-E has a 4000 char limit, trim if needed
    dalle_prompt = prompt[:3900]

    response = await client.images.generate(
        model="dall-e-3",
        prompt=dalle_prompt,
        size="1024x1024",
        quality="hd",
        n=1,
    )

    image_url = response.data[0].url
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as resp:
            return await resp.read()


async def generate_image_gemini(prompt: str) -> bytes:
    """Generate an image using Google Gemini Imagen."""
    import aiohttp
    from config import GOOGLE_API_KEY

    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY не настроен в .env файле")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key={GOOGLE_API_KEY}"
    payload = {
        "instances": [{"prompt": prompt[:1500]}],
        "parameters": {"sampleCount": 1}
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise ValueError(f"Gemini API error {resp.status}: {text[:200]}")
            data = await resp.json()
            image_b64 = data["predictions"][0]["bytesBase64Encoded"]
            return base64.b64decode(image_b64)


async def test_api_connection() -> str:
    """Test OpenAI API connection and return status."""
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
        )
        return "ok"
    except Exception as e:
        return str(e)
