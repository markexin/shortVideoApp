from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import random
import string
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

import requests

from pipeline.image_generator import ImageGenerationRequest


DEFAULT_BASE_URL = "https://openapi.liblibai.cloud"
DEFAULT_TEXT2IMG_ENDPOINT = "/api/generate/webui/text2img/ultra"
DEFAULT_STATUS_ENDPOINT = "/api/generate/webui/status"


def sign_liblib_request(
    endpoint: str,
    access_key: str,
    secret_key: str,
    timestamp: str,
    nonce: str,
) -> dict[str, str]:
    data = f"{endpoint}&{timestamp}&{nonce}"
    digest = hmac.new(secret_key.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()
    signature = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return {
        "AccessKey": access_key,
        "Timestamp": timestamp,
        "SignatureNonce": nonce,
        "Signature": signature,
    }


def image_size_for_ratio(aspect_ratio: str) -> dict[str, int]:
    if aspect_ratio == "16:9":
        return {"width": 1280, "height": 720}
    return {"width": 1080, "height": 1920}


class LiblibImageAdapter:
    def __init__(
        self,
        access_key: str,
        secret_key: str,
        template_uuid: str,
        base_url: str = DEFAULT_BASE_URL,
        endpoint: str = DEFAULT_TEXT2IMG_ENDPOINT,
        status_endpoint: str = DEFAULT_STATUS_ENDPOINT,
        timeout: int = 600,
        poll_interval: float = 3.0,
        checkpoint_id: str = "",
        lora_model_id: str = "",
        lora_weight: float = 0.8,
        sampler: int = 15,
        steps: int = 24,
        cfg_scale: float = 7.0,
        clip_skip: int = 2,
        session: Any | None = None,
        timestamp_factory: Callable[[], str] | None = None,
        nonce_factory: Callable[[], str] | None = None,
    ):
        self.access_key = access_key
        self.secret_key = secret_key
        self.template_uuid = template_uuid
        self.base_url = base_url.rstrip("/")
        self.endpoint = endpoint
        self.status_endpoint = status_endpoint
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.checkpoint_id = checkpoint_id
        self.lora_model_id = lora_model_id
        self.lora_weight = lora_weight
        self.sampler = sampler
        self.steps = steps
        self.cfg_scale = cfg_scale
        self.clip_skip = clip_skip
        self.session = session or requests.Session()
        self.timestamp_factory = timestamp_factory or self._timestamp
        self.nonce_factory = nonce_factory or self._nonce

    async def generate_image(self, request: ImageGenerationRequest) -> dict:
        return await asyncio.to_thread(self._generate_sync, request)

    def _generate_sync(self, request: ImageGenerationRequest) -> dict:
        try:
            payload = self._build_payload(request)
            generate_uuid = self._submit(payload)
            image_url = self._wait_for_success(generate_uuid)
            image_urls = image_url if isinstance(image_url, list) else [image_url]
            local_paths = self._download_images(image_urls, request.output_path)
            return {
                "status": "success",
                "local_path": local_paths[0],
                "local_paths": local_paths,
                "provider": "liblib",
                "metadata": {"generateUuid": generate_uuid, "imageUrls": image_urls},
            }
        except Exception as exc:
            return {"status": "failed", "error": str(exc), "provider": "liblib"}

    def _build_payload(self, request: ImageGenerationRequest) -> dict[str, Any]:
        if self.endpoint == "/api/generate/webui/text2img":
            return self._build_standard_payload(request)
        params: dict[str, Any] = {
            "prompt": request.prompt,
            "imageSize": image_size_for_ratio(request.aspect_ratio),
            "imgCount": max(1, min(int(request.img_count or 1), 4)),
        }
        return {
            "templateUuid": self.template_uuid,
            "generateParams": params,
        }

    def _build_standard_payload(self, request: ImageGenerationRequest) -> dict[str, Any]:
        if not self.checkpoint_id:
            raise ValueError("LIBLIB_CHECKPOINT_ID 不能为空: 普通 WebUI 文生图需要指定基础模型。")
        size = image_size_for_ratio(request.aspect_ratio)
        params: dict[str, Any] = {
            "checkPointId": self.checkpoint_id,
            "prompt": request.prompt,
            "negativePrompt": request.negative_prompt or "",
            "clipSkip": self.clip_skip,
            "sampler": self.sampler,
            "steps": self.steps,
            "cfgScale": self.cfg_scale,
            "width": size["width"],
            "height": size["height"],
            "imgCount": max(1, min(int(request.img_count or 1), 4)),
            "randnSource": 0,
            "seed": -1,
            "restoreFaces": 0,
        }
        if self.lora_model_id:
            params["additionalNetwork"] = [
                {"modelId": self.lora_model_id, "weight": self.lora_weight}
            ]
        return {
            "templateUuid": self.template_uuid,
            "generateParams": params,
        }

    def _submit(self, payload: dict[str, Any]) -> str:
        data = self._post_json(self.endpoint, payload)
        generate_uuid = data.get("data", {}).get("generateUuid")
        if not generate_uuid:
            raise RuntimeError(f"liblib 生图响应缺少 generateUuid: {data}")
        return str(generate_uuid)

    def _wait_for_success(self, generate_uuid: str) -> list[str]:
        deadline = time.time() + self.timeout
        last_message = ""
        while time.time() < deadline:
            data = self._post_json(self.status_endpoint, {"generateUuid": generate_uuid})
            status_data = data.get("data", {})
            status = int(status_data.get("generateStatus", 0) or 0)
            last_message = str(status_data.get("generateMsg") or "")
            if status == 5:
                images = status_data.get("images") or []
                if not images:
                    raise RuntimeError(f"liblib 生图成功但没有返回图片: {data}")
                image_urls = [str(image.get("imageUrl")) for image in images if image.get("imageUrl")]
                if not image_urls:
                    raise RuntimeError(f"liblib 图片结果缺少 imageUrl: {data}")
                return image_urls
            if status == 6:
                raise RuntimeError(last_message or f"liblib 生图失败: {generate_uuid}")
            time.sleep(self.poll_interval)
        raise TimeoutError(f"等待 liblib 生图任务超时: {generate_uuid} {last_message}".strip())

    def _post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(self._signed_url(endpoint), json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        if int(data.get("code", 0) or 0) != 0:
            raise RuntimeError(f"liblib API 错误: code={data.get('code')}, msg={data.get('msg')}")
        return data

    def _download_images(self, image_urls: list[str], output_path: str) -> list[str]:
        paths = self._output_paths(output_path, len(image_urls))
        for image_url, path in zip(image_urls, paths):
            response = self.session.get(image_url, timeout=120)
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
        return [str(path) for path in paths]

    @staticmethod
    def _output_paths(output_path: str, count: int) -> list[Path]:
        path = Path(output_path)
        if count <= 1:
            return [path]
        return [
            path.with_name(f"{path.stem}_{index:02d}{path.suffix}")
            for index in range(1, count + 1)
        ]

    def _signed_url(self, endpoint: str) -> str:
        params = sign_liblib_request(
            endpoint=endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            timestamp=self.timestamp_factory(),
            nonce=self.nonce_factory(),
        )
        return f"{self.base_url}{endpoint}?{urlencode(params)}"

    @staticmethod
    def _timestamp() -> str:
        return str(int(time.time() * 1000))

    @staticmethod
    def _nonce() -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(random.choice(alphabet) for _ in range(16))
