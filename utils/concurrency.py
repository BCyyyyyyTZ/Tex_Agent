"""
异步/并发工具封装。
提供在同步上下文中运行异步代码、并发任务管理和并发数量控制的工具函数。
"""
import asyncio
import concurrent.futures
from typing import Coroutine, Any, Optional, List


def run_async(coro: Coroutine) -> Any:
    """
    在同步上下文中运行异步协程。

    自动处理已有事件循环（如 Jupyter Notebook、已运行的 asyncio 环境）的情况：
    - 若当前已有运行中的事件循环，则在新线程中开启独立事件循环执行协程。
    - 若没有运行中的事件循环，则直接使用 asyncio.run() 执行。

    Args:
        coro: 需要运行的异步协程对象。

    Returns:
        协程的返回值。

    Example:
        result = run_async(some_async_function())
    """
    try:
        asyncio.get_running_loop()
        # 已有正在运行的事件循环，在新线程中另起炉灶
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    except RuntimeError:
        # 没有正在运行的事件循环，直接运行
        return asyncio.run(coro)


async def gather_with_timeout(
    *coros: Coroutine,
    timeout: Optional[float] = None,
    return_exceptions: bool = True,
) -> List[Any]:
    """
    并发执行多个协程，支持可选的超时控制。

    Args:
        *coros: 需要并发执行的协程对象序列。
        timeout: 超时时间（秒）。None 表示不限制超时。
        return_exceptions: True 表示将异常作为结果返回而非抛出，
                           False 表示任一协程抛出异常时立即传播。

    Returns:
        各协程结果列表，顺序与输入一致。

    Raises:
        asyncio.TimeoutError: 若设置了 timeout 且超时。

    Example:
        results = await gather_with_timeout(
            fetch_data("url1"),
            fetch_data("url2"),
            timeout=30.0,
        )
    """
    gathered = asyncio.gather(*coros, return_exceptions=return_exceptions)
    if timeout is not None:
        return await asyncio.wait_for(gathered, timeout=timeout)
    return await gathered


async def run_with_semaphore(
    coro: Coroutine,
    semaphore: asyncio.Semaphore,
) -> Any:
    """
    使用信号量控制并发数量地运行协程。
    适用于需要限制同时发起的 LLM/API 请求数量的场景。

    Args:
        coro: 协程对象。
        semaphore: asyncio.Semaphore 实例，控制最大并发数。

    Returns:
        协程的返回值。

    Example:
        sem = asyncio.Semaphore(3)  # 最多 3 个并发
        tasks = [run_with_semaphore(call_llm(q), sem) for q in queries]
        results = await asyncio.gather(*tasks)
    """
    async with semaphore:
        return await coro
