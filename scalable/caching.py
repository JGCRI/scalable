import os
import pickle
from .common import logger
from diskcache import Cache
from xxhash import xxh32

SEED = 987654321

class GenericType:
    def __init__(self, value):
        self.value = value

class FileType(GenericType):
    def __hash__(self) -> int:
        digest = 0
        if os.path.exists(self.value):
            with open(self.value, 'rb') as file:
                x = xxh32(seed=SEED)
                x.update(str(self.value).encode('utf-8'))
                x.update(file.read())
                digest = x.intdigest()
        else:
            raise ValueError("File does not exist..")
        return digest

class DirType(GenericType):
    def __hash__(self) -> int:
        digest = 0
        x = xxh32(seed=SEED)
        x.update(str(self.value).encode('utf-8'))
        if os.path.exists(self.value):
            for filename in os.listdir(self.value):
                x.update(filename.encode('utf-8'))
                path = os.path.join(self.value, filename)
                with open(path, 'rb') as file:
                    x.update(file.read())
            digest = x.intdigest()
        else:
            raise ValueError("Directory does not exist..")
        return digest

class ValueType(GenericType):
    def __hash__(self) -> int:
        digest = 0
        x = xxh32(seed=SEED)
        x.update(str(self.value).encode('utf-8'))
        digest = x.intdigest()
        return digest

class ObjectType(GenericType):
    def __hash__(self) -> int:
        digest = 0
        x = xxh32(seed=SEED)
        x.update(str(self.value).encode('utf-8'))
        x.update(pickle.dumps(self.value))
        digest = x.intdigest()
        return digest

        


cachedir = "/tmp"

def cacheable(return_type, recompute=False, store=True):
    def decorator(func):
        def inner(*args, **kwargs):
            key = 0
            new_args = []
            new_kwargs = {}
            x = xxh32(seed=SEED)
            x.update(func.__code__.co_code)
            key += x.intdigest()
            for arg in args:
                key += hash(arg)
                new_args.append(arg.value)
            for keyword, arg in kwargs.items():
                kw = ValueType(keyword)
                key += hash(kw)
                key += hash(arg)
                new_kwargs[keyword] = arg.value
            ret = None
            disk = Cache(directory=cachedir)
            if key in disk and not recompute:
                value = disk.get(key)
                if value is None:
                    raise KeyError(f"Key for function {func.__name__} could not be found.")
                stored_digest = value[0]
                new_digest = hash(return_type(value[1]))
                if new_digest == stored_digest:
                    ret = value[1]
            print(f"key is {key}")
            if ret is None:
                ret = func(*new_args, **new_kwargs)
                if store:
                    value = [hash(return_type(ret)), ret]
                    print(value)
                    if not disk.add(key=key, value=value, retry=True):
                        logger.warn(f"{func.__name__} could not be added to cache.")
            disk.close()
            return ret
        ret = inner
        if return_type is None:
            ret = func
        return ret
    return decorator

