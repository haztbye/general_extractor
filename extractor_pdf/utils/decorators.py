from threading import Lock
from typing import Type, TypeVar, Callable

T = TypeVar('T')

def singleton(cls: Type[T]) -> Callable[..., T]:
    """
    线程安全的单例模式装饰器
    
    用法:
    @singleton
    class MyClass:
        pass
    """
    _instances = {}
    _lock = Lock()
    
    def get_instance(*args, **kwargs) -> T:
        if cls not in _instances:
            with _lock:
                if cls not in _instances:
                    _instances[cls] = cls(*args, **kwargs)
        return _instances[cls]
    
    return get_instance