
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import os

# ================= 配置区域 =================
# 1. 这个 FastAPI 服务监听的端口（在远程服务器上）
REMOTE_APP_PORT = 8000

# 2. 本地服务器（模型端）的地址
# 这里的 localhost:6006 指的是 SSH 隧道在远程服务器上映射的入口
# 数据流向：用户 -> 远程服务器:8000 -> 远程服务器:6006 (SSH隧道入口) -> 本地服务器:6006 (模型API)
MODEL_API_BASE = "http://localhost:6006/v1" 
MODEL_API_KEY = "EMPTY"
MODEL_NAME = "qwen-7b"
# ===========================================

app = FastAPI(title="Remote Model Client")

class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.7

class GenerateResponse(BaseModel):
    response: str
    usage: dict

# 初始化 OpenAI 客户端
client = OpenAI(
    api_key=MODEL_API_KEY,
    base_url=MODEL_API_BASE
)

@app.get("/")
def health_check():
    """检查服务是否存活，并尝试连接模型"""
    try:
        models = client.models.list()
        return {
            "status": "online", 
            "proxy_port": REMOTE_APP_PORT, 
            "tunnel_target": MODEL_API_BASE,
            "model_connected": True,
            "available_models": [m.id for m in models.data]
        }
    except Exception as e:
        return {
            "status": "warning", 
            "detail": "FastAPI 服务已启动，但无法连接到模型。请检查 SSH 隧道是否已建立！",
            "error": str(e)
        }

@app.post("/generate", response_model=GenerateResponse)
def generate_text(req: GenerateRequest):
    try:
        print(f"[收到请求] Prompt: {req.prompt[:20]}...")
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "user", "content": req.prompt}
            ],
            max_tokens=req.max_tokens,
            temperature=req.temperature
        )
        
        result_text = completion.choices[0].message.content
        usage = {
            "prompt_tokens": completion.usage.prompt_tokens,
            "completion_tokens": completion.usage.completion_tokens,
            "total_tokens": completion.usage.total_tokens
        }
        print(f"[生成成功] Output: {result_text[:20]}...")
        return GenerateResponse(response=result_text, usage=usage)
        
    except Exception as e:
        print(f"[调用失败] {e}")
        raise HTTPException(status_code=502, detail=f"无法连接到模型 API。请确保 SSH 隧道已开启 (localhost:6006)。错误信息: {str(e)}")

if __name__ == "__main__":
    print(f"=== 远程服务器调用端启动 ===")
    print(f"1. 监听端口: {REMOTE_APP_PORT}")
    print(f"2. 目标模型: {MODEL_API_BASE} (依赖 SSH 隧道)")
    print(f"3. 测试命令: curl http://localhost:{REMOTE_APP_PORT}/generate ...")
    uvicorn.run(app, host="0.0.0.0", port=REMOTE_APP_PORT)
