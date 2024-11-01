import dill
import os
import pickle
import types

import numpy as np
import pandas as pd

from diskcache import Cache
from xxhash import xxh32

from .common import SEED, cachedir, logger


class GenericType:
    """The GenericType class is a base class for all types that can be hashed.

    Parameters
    ----------
    value : Any
        The value to be hashed.
    """

    def __init__(self, value):
        self.value = value

class FileType(GenericType):
    """The FileType class is used to hash files.

    Parameters
    ----------
    value : str
        The path to the file.
    """

    def __hash__(self) -> int:
        if os.path.exists(self.value):
            digest = 0
            with open(self.value, 'rb') as file:
                x = xxh32(seed=SEED)
                x.update(str(os.path.basename(self.value)).encode('utf-8'))
                x.update(file.read())
                digest = x.intdigest()
        else:
            raise ValueError("File does not exist..")
        return digest

class DirType(GenericType):
    """The DirType class is used to hash directories.
    
    Parameters
    ----------
    value : str
        The path to the directory.
    """

    def __hash__(self) -> int:
        if os.path.exists(self.value):
            digest = 0
            x = xxh32(seed=SEED)
            x.update(str(os.path.basename(self.value)).encode('utf-8'))
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
    """The ValueType class is used to hash generic values such as int, str, 
    float, bytes, etc. 
    
    Parameters
    ----------
    value : Any
        The value to be hashed.
    """

    def __hash__(self) -> int:
        digest = 0
        x = xxh32(seed=SEED)
        x.update(str(self.value).encode('utf-8'))
        digest = x.intdigest()
        return digest

class ObjectType(GenericType):
    """The ObjectType class is used to hash objects, with primary support for 
    lists and dicts. Pickle is used to hash such objects.
    
    Parameters
    ----------
    value : Any
        The object to be hashed.
    """

    def __hash__(self) -> int:
        digest = 0
        x = xxh32(seed=SEED)
        if isinstance(self.value, list):
            value_list = self.value
            for element in value_list:
                x.update(hash_to_bytes(hash(convert_to_type(element))))
        elif isinstance(self.value, dict):
            keys = self.value.keys()
            try:
                keys = sorted(keys)
            except:
                pass
            for key in keys:
                x.update(hash_to_bytes(hash(convert_to_type(key))))
                x.update(hash_to_bytes(hash(convert_to_type(self.value[key]))))
        else:
            x.update(pickle.dumps(self.value))
        digest = x.intdigest()
        return digest

class UtilityType(GenericType):
    """The UtilityType class is used to hash utility data types such as numpy 
    arrays and pandas dataframes. 

    More utility data types can be added as needed.

    Parameters
    ----------
    value : Any
        The utility data type to be hashed.
    """

    def __hash__(self) -> int:
        digest = 0
        x = xxh32(seed=SEED)
        if isinstance(self.value, np.ndarray):
            x.update(self.value.tobytes())
        elif isinstance(self.value, pd.DataFrame):
            x.update(pickle.dumps(self.value))
        digest = x.intdigest()
        return digest
    
def hash_to_bytes(hash):
    """Converts a hash (or int) to bytes.
    
    Parameters
    ----------
    hash : int
        The hash to be converted to bytes.
    
    Returns
    -------
    bytes
        The bytes representation.
    """
    return hash.to_bytes((hash.bit_length() + 7) // 8, 'big')

def convert_to_type(arg):
    """Converts a given argument to a hashable type. 
    
    An attempt is made to identify the type of the argument but it's 
    correctness is not guaranteed for exotic data types/representations.
    
    Parameters
    ----------
    arg : Any
        The argument to be converted.
    
    Returns
    -------
    GenericType/ValueType/FileType/DirType/ObjectType/UtilityType
        The hashable type class.
    """
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
    elif isinstance(arg, (np.ndarray, pd.DataFrame)):
        ret = UtilityType(arg)
    else:
        logger.warning(f"Could not identify type for argument: {arg}. Using default hash function. " 
                    "For more reliable performance, either wrap the argument in a class with a defined"
                    " __hash__() function or open an issue on the scalable Github: github.com/JGCRI/scalable.")
        ret = ObjectType(arg)
    return ret

def cacheable(return_type=None, void=False, check_output=False, recompute=False, store=True, **arg_types):
    """Decorator function to cache the output of a function.
    
    This function is used to cache other functions' outputs for certain 
    arguments. The function hashes multiple things for a given function
    including its name, code content, arguments, and anything else hashed by 
    the hash() function of the arguments. All arguments are wrapped in a 
    type class to enable calling hash() on them. Such type classes can be 
    and often are custom. Since argument types are estimated and not 
    guaranteed to be correct with more exotic data types, it's best practice
    to specify the return value's type class along with the type classes of 
    all the arguments. 

    Parameters
    ----------
    return_type : Any
        The type class for the return value of the function. Usually 
        a value between ValueType, FileType, DirType, ObjectType but custom
        classes with a defined hash() function can be used as well. Defaults 
        to None. If None, the return_type will be estimated which is not 
        guaranteed to be correct.
    void : bool, optional
        Whether the function returns a value or not. A function is void if it 
        does not return a value. The default is False.
    check_output : bool, optional
        Whether to check the output of a function has the same hash as when 
        it was stored. Useful to ensure entities like files haven't been
        modified since initially stored. The default is False.
    recompute : bool, optional
        Whether to recompute the value or not. The default is False.
    store : bool, optional
        Whether to store the value in the cache or not. The default is True.
    arg_types : dict
        The type classes for the arguments of the function. The keys are the 
        argument names and the values are the type classes. If none are given
        for a certain argument, the type class will be estimated which is not
        guaranteed to be correct.

    Examples
    --------
    >>> @cacheable
        def func(arg1, arg2):
            ...

    >>> @cacheable()
        def func(arg1, arg2):
            ...
    
    >>> @cacheable(void=True)
        def func(arg1, arg2):
            ...
    
    >>> @cacheable(ValueType)
        def func(arg1, arg2):
            ...
    
    >>> @cacheable(return_type=DirType, arg1=UtilityType, arg2=FileType)
        def func(arg1, arg2):
            ...
    
    >>> @cacheable(return_type=ValueType, recompute=False, store=True, arg1=DirType, arg2=FileType)
        def func(arg1, arg2):
            ...
    """
    func = None
    if isinstance(return_type, types.FunctionType):
        func = return_type
        return_type = None
    def decorator(func):
        def inner(*args, **kwargs):
            keys = []
            x = xxh32(seed=SEED)
            func_str = dill.source.getsource(func)
            x.update(func_str.encode('utf-8'))
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
                wrapped_arg = None
                if keyword in arg_types:
                    arg_type = arg_types[keyword]
                    wrapped_arg = arg_type(arg)
                else:
                    wrapped_arg = convert_to_type(arg)
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
                new_digest = 0
                if check_output:
                    if return_type is None:
                        new_digest = hash(convert_to_type(value[1]))
                    else:
                        new_digest = hash(return_type(value[1]))
                    if new_digest == stored_digest:
                        ret = value[1]
                    elif not disk.delete(key, True):
                        logger.warning(f"{func.__name__} could not be deleted from cache after hash"
                                    " mismatch.")
                else:
                    ret = value[1]             
            if ret is None:
                ret = func(*args, **kwargs)
                if store:
                    new_digest = 0
                    if return_type is None:
                        new_digest = hash(convert_to_type(ret))
                    else:
                        new_digest = hash(return_type(ret))
                    value = [new_digest, ret]
                    if not disk.add(key=key, value=value, retry=True):
                        logger.warning(f"{func.__name__} could not be added to cache.")
            disk.close()
            return ret
        ret = inner
        if void:
            ret = func
        return ret
    ret = decorator
    if func is not None:
        ret = decorator(func)
    return ret