How to add custom hash functions for cacheable
==============================================

The cacheable decorator uses a hash function to generate a key for each of 
the arguments passed to the function along with the return value. This hash 
function is internally decided based on the type of the argument. However, this
decision can be a bit unreliable if the arguments or return value have custom
or complex data types. The data types which can be recognized automatically 
(so you don't need to pass any classes). Before we move ahead, let's see how
the cacheable decorator works.

.. code-block:: python

    from scalable import *


    # No arguments are passed to the decorator because the arguments in the function
    # are of primitive data types which are recognized by the decorator.
    @cacheable
    def add(a: int, b: int):
        return a + b


    # Since the argument of the check function is a custom data type, it would be 
    # best to pass the person class to the decorator so that the person object 
    # passed to the function can be hashed properly. It is assumed that the Person
    # class has a __hash__() method.
    @cacheable(person=Person)
    def check(person: Person):
        if person.name is None:
            return False
        return True

    # The decorator is passed all the argument types and the return value data type.
    # The argument types are not needed in this specific case because the arguments
    # are of primitive data types which are recognized by the decorator.
    @cacheable(name=str, age=int, return_type=Person)
    def make_person(name: str, age: int):
        return Person(name, age)



The `add` function is a simple function that takes two integers and returns 
their sum. int is a primitive data type and is recognized by the decorator. 
The `check` function takes a custom data type `Person` as an argument. The 
`Person` class is passed to the decorator as the value for the `person` 
keyword which matches the argument name in the function. 

The `Person` class should have an implemented `__hash__` method that ideally 
returns a unique hash for each object. As an example, let's make an example 
Person class and implement a `__hash__` method for it.

.. code-block:: python

    # xxhash is used here but any hashing library can be used (hashlib is built-in)
    # However, xxhash is a non-cryptographic hash library which is much faster 
    # than hashlib or other cryptographic libraries. 
    # xxhash can be installed by running `pip install xxhash`

    from xxhash import xxh32
    import scalable

    class Person:
        def __init__(self, name: str, age: int):
            self.name = name
            self.age = age

        def __hash__(self):
            digest = 0
            # It is important to use the same seed value at each invocation. An 
            # easy way to ensure this is to use the seed value scalable. 
            # However, any constant value for seed can be used. Some value must be
            # used to ensure that the hash is consistent across different
            # invocations.
            x = xxh32(seed=scalable.SEED)
            x.update(self.name.encode('utf-8'))
            x.update(str(self.age).encode('utf-8'))
            digest = x.intdigest()
            return digest

The `Person` class with the `__hash__` method can be directly passed to the 
decorator. This would allow the decorator to hash the `Person` object properly. 

For any data types that are used in arguments or return values, the data type
class should be passed to the decorator for the most reliable behavior. If 
needed, please feel free to open an issue  
`here <https://github.com/JGCRI/scalable/issues>`_.
