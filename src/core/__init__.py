import time
from functools import cached_property

ITERATIONS = 10_000_000


class WithSlotsProperty:
    __slots__ = ('_value',)

    def __init__(self):
        self._value = None

    @property
    def value(self):
        if self._value is None:
            self._value = 42
        return self._value


class WithCachedProperty:
    @cached_property
    def value(self):
        return 42


class WithSlotsPlain:
    __slots__ = ('value',)

    def __init__(self):
        self.value = 42


class WithDictPlain:
    def __init__(self):
        self.value = 42


def bench(label, fn):
    start = time.perf_counter()
    fn()
    elapsed = time.perf_counter() - start
    print(f"{label:<50} {elapsed:.3f}s")


# Прогрев
obj1 = WithSlotsProperty(); obj1.value
obj2 = WithCachedProperty(); obj2.value
obj3 = WithSlotsPlain()
obj4 = WithDictPlain()

print(f"\n{'Benchmark':<50} {'Time':>6}")
print("-" * 60)

bench(
    "slots + @property (новый объект каждый раз)",
    lambda: [WithSlotsProperty().value for _ in range(ITERATIONS)]
)

bench(
    "cached_property (новый объект каждый раз)",
    lambda: [WithCachedProperty().value for _ in range(ITERATIONS)]
)

bench(
    "slots + @property (один объект, повторные вызовы)",
    lambda: [obj1.value for _ in range(ITERATIONS)]
)

bench(
    "cached_property (один объект, повторные вызовы)",
    lambda: [obj2.value for _ in range(ITERATIONS)]
)

bench(
    "slots plain attr (один объект)",
    lambda: [obj3.value for _ in range(ITERATIONS)]
)

bench(
    "dict plain attr (один объект)",
    lambda: [obj4.value for _ in range(ITERATIONS)]
)