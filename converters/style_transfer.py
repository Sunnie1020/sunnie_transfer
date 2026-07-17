from pathlib import Path
from typing import Callable

from PIL import Image

MODEL_ID = "runwayml/stable-diffusion-v1-5"

STYLE_PROMPTS = {
    "2d": (
        "2D anime style illustration, cel shading, clean line art, vibrant colors, "
        "flat coloring, Japanese animation style"
    ),
    "storybook": (
        "children's storybook illustration, warm pastel colors, hand-drawn, whimsical, "
        "soft watercolor textures, gentle lighting"
    ),
    "princess": (
        "Disney princess animation style, elegant, fairy tale illustration, "
        "sparkling and colorful, classic animated movie style"
    ),
    "3d": (
        "3D animated character render, Pixar style, soft studio lighting, smooth shading, "
        "cute and expressive, high quality 3D render"
    ),
    "plush": (
        "cute small soft plush doll keychain made of fabric, adorable felt toy, "
        "stitched seams, plain white background, product photo"
    ),
}

NEGATIVE_PROMPT = "blurry, low quality, distorted, deformed, extra limbs, watermark, text"

_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        import torch
        from diffusers import StableDiffusionImg2ImgPipeline

        _pipeline = StableDiffusionImg2ImgPipeline.from_pretrained(
            MODEL_ID, torch_dtype=torch.float32, safety_checker=None, use_safetensors=True
        )
        _pipeline.to("cpu")
    return _pipeline


def convert_photo_to_style(
    input_path: str,
    output_path: str,
    style: str,
    on_progress: Callable[[float], None] | None = None,
) -> str:
    """실사 사진을 로컬 Stable Diffusion(img2img)으로 그림체로 바꾼다."""
    prompt = STYLE_PROMPTS.get(style)
    if prompt is None:
        raise ValueError(f"지원하지 않는 스타일입니다: {style}")

    pipeline = _get_pipeline()

    with Image.open(input_path) as opened:
        image = opened.convert("RGB")
        # 가로/세로 모두 8의 배수로 맞추고, 너무 크면 처리 시간이 지나치게 길어지므로 768px 기준으로 줄인다.
        max_side = 768
        scale = min(1.0, max_side / max(image.width, image.height))
        new_width = max(8, round(image.width * scale / 8) * 8)
        new_height = max(8, round(image.height * scale / 8) * 8)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    num_steps = 30

    def _report_step(pipe, step_index, timestep, callback_kwargs):
        if on_progress:
            on_progress(min(99, round((step_index + 1) / num_steps * 100)))
        return callback_kwargs

    result = pipeline(
        prompt=prompt,
        negative_prompt=NEGATIVE_PROMPT,
        image=image,
        strength=0.65,
        guidance_scale=7.5,
        num_inference_steps=num_steps,
        callback_on_step_end=_report_step if on_progress else None,
    )
    result.images[0].save(output_path)

    if not Path(output_path).exists():
        raise RuntimeError("그림 변환에 실패했습니다.")

    if on_progress:
        on_progress(100)

    return output_path
