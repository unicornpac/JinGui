"""
共享依赖 —— 认证、频率限制
"""
import os
import secrets
import time
import threading
from collections import defaultdict
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()


def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """验证管理员密码"""
    correct = os.environ.get("ADMIN_PASSWORD", "jingui2026")
    if not secrets.compare_digest(credentials.password.encode(), correct.encode()):
        raise HTTPException(
            status_code=401,
            detail="密码错误",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ==================== 简易速率限制器 ====================

class SimpleRateLimiter:
    """基于内存滑动窗口的速率限制器（无需外部依赖）"""

    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _get_key(self, request: Request) -> str:
        """以 IP + 路由为 key"""
        client_ip = request.client.host if request.client else "unknown"
        # 取路由前缀进行限流（如 POST /api/agent/session/xxx/message → /api/agent/session/message）
        route = request.url.path
        # 将数字 ID 替换为占位符，聚合同类端点的计数
        import re
        route = re.sub(r'/\d+', '/{id}', route)
        return f"{client_ip}:{request.method}:{route}"

    def is_allowed(self, request: Request, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """返回 (是否允许, 剩余次数)"""
        key = self._get_key(request)
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            # 清理过期记录
            self._windows[key] = [t for t in self._windows[key] if t > cutoff]
            count = len(self._windows[key])

            if count >= max_requests:
                return False, 0

            self._windows[key].append(now)
            remaining = max_requests - count - 1
            return True, remaining

    def limit(self, max_requests: int, window_seconds: int = 60):
        """返回 FastAPI 依赖函数"""

        def _limiter(request: Request):
            allowed, remaining = self.is_allowed(request, max_requests, window_seconds)
            if not allowed:
                retry_after = window_seconds
                raise HTTPException(
                    status_code=429,
                    detail=f"请求过于频繁，请 {retry_after} 秒后重试（限制 {max_requests} 次/{window_seconds}秒）",
                    headers={"Retry-After": str(retry_after), "X-RateLimit-Remaining": "0"},
                )
            return remaining

        return Depends(_limiter)


# 全局实例
_limiter = None


def get_limiter() -> SimpleRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = SimpleRateLimiter()
    return _limiter


# 预设限制策略（作为便捷函数）
def limit_agent_message(request: Request):
    return get_limiter().is_allowed(request, 30, 60)[0] or _raise_429(30, 60)


def limit_agent_start(request: Request):
    return get_limiter().is_allowed(request, 10, 60)[0] or _raise_429(10, 60)


def limit_upload(request: Request):
    return get_limiter().is_allowed(request, 5, 3600)[0] or _raise_429(5, 3600)


def limit_analysis(request: Request):
    return get_limiter().is_allowed(request, 10, 60)[0] or _raise_429(10, 60)


def _raise_429(max_req: int, window: int):
    unit = "秒" if window < 120 else ("分" if window < 7200 else "时")
    val = window if window < 120 else (window // 60 if window < 7200 else window // 3600)
    raise HTTPException(
        status_code=429,
        detail=f"请求过于频繁，请稍后重试（限制 {max_req} 次/{val}{unit}）",
        headers={"Retry-After": str(window)},
    )
