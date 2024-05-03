import os
import pickle
from diskcache import Cache
from xxhash import xxh32

from .common import logger, cachedir, SEED

def hash_to_bytes(hash):
    return hash.to_bytes((hash.bit_length() + 7) // 8, 'big')

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
            filenames = os.listdir(self.value)
            filenames = sorted(filenames)
            for filename in filenames:
                x.update(filename.encode('utf-8'))
                path = os.path.join(self.value, filename)
                if os.path.isfile(path):
                    with open(path, 'rb') as file:
                        x.update(file.read())
                elif os.path.isdir(path):
                    x.update(hash_to_bytes(hash(DirType(path))))
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
        if isinstance(self.value, list):
            value_list = self.value
            if all(isinstance(element, str) for element in self.value):
                value_list = sorted(self.value)
            for element in value_list:
                type_object = convert_to_type(element)
                x.update(hash_to_bytes(hash(type_object)))
        else:
            x.update(pickle.dumps(self.value))
        digest = x.intdigest()
        return digest
    

def convert_to_type(arg):
    ret = None
    if isinstance(arg, str):
        if os.path.isfile(arg):
            ret = FileType(arg)
        elif os.path.isdir(arg):
            ret = DirType(arg)
        else:
            ret = ValueType(arg)
    elif isinstance(arg, (int, float, bool, bytes)):
        ret = ValueType(arg)
    else:
        ret = ObjectType(arg)
    return ret

def get_wrapped(arg, arg_name, arg_types):
    wrapped_arg = None
    if arg_name in arg_types:
        arg_type = arg_types[arg_type]
        wrapped_arg = arg_type(arg)
    else:
        wrapped_arg = convert_to_type(arg)
    return wrapped_arg

def cacheable(return_type, recompute=False, store=True, **arg_types):
    def decorator(func):
        def inner(*args, **kwargs):
            keys = []
            x = xxh32(seed=SEED)
            x.update(func.__code__.co_code)
            keys.append(x.intdigest())
            arg_names = func.__code__.co_varnames[:func.__code__.co_argcount]
            default_values = {}
            if func.__defaults__:
                default_values = dict(zip(arg_names[-len(func.__defaults__):], func.__defaults__))
            final_args = {}
            for index in range(len(args)):
                arg = args[index]
                arg_name = arg_names[index]
                final_args[arg_name] = arg
            for keyword, arg in kwargs.items():
                final_args[keyword] = arg
            for keyword, arg in default_values.items():
                if keyword not in final_args:
                    final_args[keyword] = arg
            for keyword, arg in final_args.items():
                wrapped_arg = get_wrapped(arg, keyword, arg_types)
                keys.append(hash(ValueType(keyword)))
                keys.append(hash(wrapped_arg))
            ret = None
            key = hash(ObjectType(sorted(keys)))
            disk = Cache(directory=cachedir)
            if key in disk and not recompute:
                value = disk.get(key)
                if value is None:
                    raise KeyError(f"Key for function {func.__name__} could not be found.")
                stored_digest = value[0]
                new_digest = hash(return_type(value[1]))
                if new_digest == stored_digest:
                    ret = value[1]
            if ret is None:
                ret = func(*args, **kwargs)
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

