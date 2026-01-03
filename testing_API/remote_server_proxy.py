
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import os

# --- 配置 ---
# 本地监听端口（远程服务器上的服务端口）
REMOTE_SERVICE_PORT = 8000

# 模型服务地址（通过 SSH 隧道映射后的本地地址）
# 注意：前提是已经在远程服务器上执行了 SSH 隧道命令，将本地服务器的 6006 映射到了远程服务器的 6006
MODEL_API_BASE = "http://localhost:6006/v1" 
MODEL_API_KEY = "EMPTY"
MODEL_NAME = "qwen-7b"

app = FastAPI(title="Remote Model Proxy Service")

class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.7

class GenerateResponse(BaseModel):
    response: str
    usage: dict

# 初始化 OpenAI 客户端连接本地映射端口
client = OpenAI(
    api_key=MODEL_API_KEY,
    base_url=MODEL_API_BASE
)

@app.get("/")
def health_check():
    return {"status": "ok", "proxy_target": MODEL_API_BASE}

@app.post("/generate", response_model=GenerateResponse)
def generate_text(req: GenerateRequest):
    """
    接收远程请求 -> 通过隧道调用本地模型 -> 返回结果
    """
    try:
        print(f"收到请求: {req.prompt[:50]}...")
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
        
        return GenerateResponse(response=result_text, usage=usage)
        
    except Exception as e:
        print(f"调用模型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print(f"启动远程代理服务，监听端口: {REMOTE_SERVICE_PORT}")
    print(f"请确保 SSH 隧道已建立：ssh -L 6006:localhost:6006 ...")
    uvicorn.run(app, host="0.0.0.0", port=REMOTE_SERVICE_PORT)
