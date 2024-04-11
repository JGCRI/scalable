import functools
from .support import hash_function, filename_to_file
import joblib.memory as jm
import joblib.hashing as jh
import joblib.func_inspect as jf

class ModifiedMemorizedFunc(jm.MemorizedFunc):

    @property
    def func_code_info(self):
        if hasattr(self.func, '__code__'):
            if self._func_code_id is None:
                self._func_code_id = id(self.func.__code__)
            elif id(self.func.__code__) != self._func_code_id:
                self._func_code_info = None

        if self._func_code_info is None:
            self._func_code_info = hash_function(self.func)
        return self._func_code_info
    
    def _get_argument_hash(self, *args, **kwargs):
        return jh.hash(filename_to_file(jf.filter_args(self.func, self.ignore, args, kwargs)),
                            coerce_mmap=(self.mmap_mode is not None))


class ModifiedMemory(jm.Memory):

    def cache(self, func=None, ignore=None, verbose=None, mmap_mode=False,
              cache_validation_callback=None):
        if (cache_validation_callback is not None and
                not callable(cache_validation_callback)):
            raise ValueError(
                "cache_validation_callback needs to be callable. "
                f"Got {cache_validation_callback}."
            )
        if func is None:
            return functools.partial(
                self.cache, ignore=ignore,
                mmap_mode=mmap_mode,
                verbose=verbose,
                cache_validation_callback=cache_validation_callback
            )
        if self.store_backend is None:
            return jm.NotMemorizedFunc(func)
        if verbose is None:
            verbose = self._verbose
        if mmap_mode is False:
            mmap_mode = self.mmap_mode
        if isinstance(func, ModifiedMemorizedFunc):
            func = func.func
        return ModifiedMemorizedFunc(
            func, location=self.store_backend, backend=self.backend,
            ignore=ignore, mmap_mode=mmap_mode, compress=self.compress,
            verbose=verbose, timestamp=self.timestamp,
            cache_validation_callback=cache_validation_callback
        )

cachedir = "./cache"
disk = ModifiedMemory(location=cachedir, verbose=0, mmap_mode='r')

MODULE = "caching"

def cache_submit(client, func, *args, **kwargs):
    func.__module__ = MODULE
    func.__qualname__ = func.__name__
    func = disk.cache(func)
    return client.submit(func, *args, **kwargs)

def cache_map(client, func, *args, **kwargs):
    func.__module__ = MODULE
    func.__qualname__ = func.__name__
    func = disk.cache(func)
    return client.map(func, *args, **kwargs)

def cache_run(client, func, *args, **kwargs):
    func.__module__ = MODULE
    func.__qualname__ = func.__name__
    func = disk.cache(func)
    return client.run(func, *args, **kwargs)


