import functools
import hashlib
import os
import pickle
import time
import types
import warnings
from collections.abc import Callable
from typing import Any

import dill
import numpy as np
import pandas as pd
from diskcache import Cache
from xxhash import xxh32

from .common import logger, settings
from .telemetry.runtime import emit_cache_event


def _seed() -> int:
    """Return the active xxhash seed (process-singleton override-friendly)."""
    return settings.seed


def _cache_dir() -> str:
    """Return the active cache directory (process-singleton override-friendly)."""
    return settings.cache_dir


@functools.lru_cache(maxsize=8)
def _shared_cache(directory: str) -> Cache:
    """Return a shared :class:`diskcache.Cache` keyed by directory.

    Previously :func:`cacheable` opened ``Cache(directory=cachedir)`` on every
    call, which performed a synchronous ``mkdir`` + sqlite open per
    invocation. Re-using a single ``Cache`` per directory is both faster and
    safer (diskcache itself is process-safe).
    """
    return Cache(directory=directory)


#: Module-level switch controlling whether :func:`convert_to_type` will
#: attempt to interpret string arguments as filesystem paths and hash them
#: as ``FileType`` / ``DirType``. The historic default was ``True``, which
#: silently invalidated cache keys when files moved or were renamed and made
#: it impossible to pass arbitrary strings that happened to look like paths.
#: New code should pass an explicit ``arg_types={"x": FileType}`` instead.
#: This module-level toggle exists to make the deprecation gradual rather
#: than abrupt.
PATH_SNIFFING_ENABLED = bool(int(os.environ.get("SCALABLE_PATH_SNIFFING", "1")))


class GenericType:
    """The GenericType class is a base class for all types that can be hashed.

    Parameters
    ----------
    value : Any
        The value to be hashed.
    """

    def __init__(self, value: Any) -> None:
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
            x = xxh32(seed=_seed())
            x.update(str(os.path.basename(self.value)).encode('utf-8'))
            with open(self.value, 'rb') as file:
                # Stream the file in chunks so we don't load multi-GB files
                # entirely into memory just to hash them.
                for chunk in iter(lambda: file.read(1024 * 1024), b""):
                    x.update(chunk)
            return x.intdigest()
        raise ValueError(f"File does not exist: {self.value!r}")

class DirType(GenericType):
    """The DirType class is used to hash directories.

    Parameters
    ----------
    value : str
        The path to the directory.
    """

    def __hash__(self) -> int:
        if not os.path.exists(self.value):
            raise ValueError(f"Directory does not exist: {self.value!r}")
        x = xxh32(seed=_seed())
        x.update(str(os.path.basename(self.value)).encode('utf-8'))
        for filename in sorted(os.listdir(self.value)):
            x.update(filename.encode('utf-8'))
            path = os.path.join(self.value, filename)
            if os.path.isfile(path):
                with open(path, 'rb') as file:
                    for chunk in iter(lambda: file.read(1024 * 1024), b""):
                        x.update(chunk)
            elif os.path.isdir(path):
                x.update(hash_to_bytes(hash(DirType(path))))
        return x.intdigest()

class ValueType(GenericType):
    """Hash for generic primitive values (int, str, float, bytes, bool)."""

    def __hash__(self) -> int:
        x = xxh32(seed=_seed())
        x.update(str(self.value).encode('utf-8'))
        return x.intdigest()

class ObjectType(GenericType):
    """Hash for composite objects (lists, tuples, dicts, fall-through pickle).

    Notes
    -----
    The original implementation silently swallowed *any* exception when
    sorting dict keys. We narrow that to :class:`TypeError` and log a debug
    message so unexpected errors surface during development.
    """

    def __hash__(self) -> int:
        x = xxh32(seed=_seed())
        if isinstance(self.value, (list, tuple)):
            for element in self.value:
                x.update(hash_to_bytes(hash(convert_to_type(element))))
        elif isinstance(self.value, dict):
            keys = list(self.value.keys())
            try:
                keys = sorted(keys)
            except TypeError:
                logger.debug(
                    "Dict keys not totally orderable; hashing in insertion order."
                )
            for key in keys:
                x.update(hash_to_bytes(hash(convert_to_type(key))))
                x.update(hash_to_bytes(hash(convert_to_type(self.value[key]))))
        else:
            try:
                x.update(pickle.dumps(self.value))
            except (pickle.PicklingError, TypeError) as exc:
                raise TypeError(
                    f"ObjectType cannot hash {type(self.value).__name__}; "
                    "wrap it in a custom GenericType subclass with a defined "
                    "__hash__ or pass arg_types= to @cacheable."
                ) from exc
        return x.intdigest()

class UtilityType(GenericType):
    """Hash for numpy arrays and pandas dataframes.

    More utility data types can be added by subclassing or registering.
    """

    def __hash__(self) -> int:
        x = xxh32(seed=_seed())
        if isinstance(self.value, np.ndarray):
            # Include dtype + shape so two arrays with the same byte stream
            # but different shapes hash differently.
            x.update(str(self.value.dtype).encode('utf-8'))
            x.update(str(self.value.shape).encode('utf-8'))
            x.update(self.value.tobytes())
        elif isinstance(self.value, pd.DataFrame):
            x.update(pickle.dumps(self.value))
        else:  # pragma: no cover - defensive; predicate in convert_to_type guards us
            raise TypeError(f"UtilityType does not support {type(self.value).__name__}")
        return x.intdigest()
    
def hash_to_bytes(hash: int) -> bytes:
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

def convert_to_type(arg: Any) -> GenericType:
    """Convert ``arg`` to a hashable :class:`GenericType` subclass.

    The mapping is heuristic. For deterministic cache keys, prefer
    annotating arguments explicitly via ``@cacheable(arg_types={...})``.

    Path sniffing
    -------------
    Historically, any string that resolved to an existing file or directory
    was wrapped as :class:`FileType` / :class:`DirType`, which silently:

    * read entire files into the hash, making cache keys depend on file
      contents that were never mentioned in the function signature, and
    * conflated literal string arguments with paths (e.g. passing
      ``"/etc"`` would hash the entire ``/etc`` directory).

    Path sniffing now emits a :class:`DeprecationWarning` on first use per
    process. Disable it by setting ``SCALABLE_PATH_SNIFFING=0`` in the
    environment, or — preferred — by passing an explicit ``arg_types=``
    mapping to :func:`cacheable`.
    """
    if isinstance(arg, str):
        if PATH_SNIFFING_ENABLED:
            try:
                is_file = os.path.isfile(arg)
                is_dir = (not is_file) and os.path.isdir(arg)
            except (OSError, ValueError):
                is_file = is_dir = False
            if is_file or is_dir:
                _warn_path_sniffing_once(arg)
                return FileType(arg) if is_file else DirType(arg)
        return ValueType(arg)
    if isinstance(arg, (int, float, bool, bytes)):
        return ValueType(arg)
    if isinstance(arg, (np.ndarray, pd.DataFrame)):
        return UtilityType(arg)
    if isinstance(arg, (list, dict, tuple)):
        return ObjectType(arg)
    logger.warning(
        "Could not identify type for argument of type %s. Falling back to "
        "ObjectType (pickle). For deterministic cache keys, pass arg_types= "
        "to @cacheable.",
        type(arg).__name__,
    )
    return ObjectType(arg)


_PATH_SNIFFING_WARNED = False


def _warn_path_sniffing_once(value: str) -> None:
    """Emit a single DeprecationWarning per process for path-sniffing usage."""
    global _PATH_SNIFFING_WARNED
    if _PATH_SNIFFING_WARNED:
        return
    _PATH_SNIFFING_WARNED = True
    warnings.warn(
        "Implicit path-sniffing in convert_to_type() is deprecated. "
        f"Argument {value!r} was treated as a file/dir path because it "
        "resolved on disk. Pass arg_types={...: FileType/DirType} explicitly "
        "to @cacheable, or set SCALABLE_PATH_SNIFFING=0 to disable.",
        DeprecationWarning,
        stacklevel=3,
    )

def cacheable(
    return_type: type[GenericType] | Callable[..., Any] | None = None,
    void: bool = False,
    check_output: bool = False,
    recompute: bool = False,
    store: bool = True,
    **arg_types: type[GenericType],
) -> Callable[[Callable[..., Any]], Callable[..., Any]] | Callable[..., Any]:
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
        # Compute the function-identity component of the cache key once at
        # decoration time. ``dill.source.getsource`` raises for lambdas,
        # functools.partial, REPL definitions, etc. — fall back to a stable
        # fingerprint built from the qualified name + bytecode in those cases.
        try:
            func_source = dill.source.getsource(func)
            func_fingerprint = func_source.encode("utf-8")
        except (OSError, TypeError) as exc:
            logger.debug(
                "dill.source.getsource(%s) failed (%s); falling back to "
                "qualname+bytecode fingerprint.",
                getattr(func, "__qualname__", repr(func)),
                exc,
            )
            qualname = getattr(func, "__qualname__", repr(func))
            module = getattr(func, "__module__", "?") or "?"
            code = getattr(func, "__code__", None)
            bytecode = code.co_code if code is not None else b""
            func_fingerprint = (
                f"{module}.{qualname}".encode()
                + b"\x00"
                + hashlib.sha256(bytecode).digest()
            )

        x = xxh32(seed=_seed())
        x.update(func_fingerprint)
        func_digest = x.intdigest()

        @functools.wraps(func)
        def inner(*args, **kwargs):
            keys = [func_digest]
            code = getattr(func, "__code__", None)
            if code is not None:
                arg_names = code.co_varnames[: code.co_argcount]
            else:  # pragma: no cover - builtins / C-level callables
                arg_names = ()
            default_values = {}
            if getattr(func, "__defaults__", None):
                default_values = dict(
                    zip(arg_names[-len(func.__defaults__):], func.__defaults__, strict=False)
                )
            final_args = {}
            for index, arg in enumerate(args):
                if index < len(arg_names):
                    final_args[arg_names[index]] = arg
                else:
                    final_args[f"__pos_{index}"] = arg
            for keyword, arg in kwargs.items():
                final_args[keyword] = arg
            for keyword, arg in default_values.items():
                final_args.setdefault(keyword, arg)
            for keyword, arg in final_args.items():
                if keyword in arg_types:
                    wrapped_arg = arg_types[keyword](arg)
                else:
                    wrapped_arg = convert_to_type(arg)
                keys.append(hash(ValueType(keyword)))
                keys.append(hash(wrapped_arg))

            key = hash(ObjectType(sorted(keys)))
            disk = _shared_cache(_cache_dir())
            ret = None
            lookup_start = time.monotonic()
            if key in disk and not recompute:
                value = disk.get(key)
                if value is None:
                    raise KeyError(
                        f"Key for function {func.__name__} could not be found."
                    )
                stored_digest, stored_value = value[0], value[1]
                if check_output:
                    if return_type is None:
                        new_digest = hash(convert_to_type(stored_value))
                    else:
                        new_digest = hash(return_type(stored_value))
                    if new_digest == stored_digest:
                        ret = stored_value
                    elif not disk.delete(key, retry=True):
                        logger.warning(
                            "%s could not be deleted from cache after hash "
                            "mismatch.",
                            func.__name__,
                        )
                else:
                    ret = stored_value
                emit_cache_event(
                    function_name=getattr(func, "__qualname__", func.__name__),
                    key_digest=str(key),
                    hit=True,
                    duration_s=max(time.monotonic() - lookup_start, 0.0),
                )
            if ret is None:
                compute_start = time.monotonic()
                ret = func(*args, **kwargs)
                if store:
                    if return_type is None:
                        new_digest = hash(convert_to_type(ret))
                    else:
                        new_digest = hash(return_type(ret))
                    if not disk.add(key=key, value=[new_digest, ret], retry=True):
                        logger.warning(
                            "%s could not be added to cache.", func.__name__
                        )
                emit_cache_event(
                    function_name=getattr(func, "__qualname__", func.__name__),
                    key_digest=str(key),
                    hit=False,
                    duration_s=max(time.monotonic() - compute_start, 0.0),
                )
            return ret

        return func if void else inner

    if func is not None:
        return decorator(func)
    return decorator
