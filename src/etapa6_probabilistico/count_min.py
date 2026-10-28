"""Etapa 6: Count-Min Sketch.

Cuenta cuántas veces apareció cada clave en un stream usando una tabla de d
filas por w columnas de contadores, con una función hash por fila. Al sumar una
clave se incrementa, en cada fila, el contador de la columna que le toca. Al
estimar, se devuelve el **mínimo** de esos d contadores: como las colisiones
solo pueden sumar de más, el mínimo es la fila menos contaminada y la estimación
nunca queda por debajo del valor real (puede quedar por encima).

Por qué aquí: para detectar velocidad anómala necesitamos saber cuántos eventos
llegaron de una misma IP o dispositivo en una ventana de tiempo. Un ``dict`` de
contadores exactos guarda una entrada por clave distinta (millones de IP en un
stream grande); el sketch usa memoria fija d*w sin importar cuántas claves haya,
a cambio de un pequeño sobreconteo acotado.

Garantías para un sketch de ancho w = ⌈e/ε⌉ y profundidad d = ⌈ln(1/δ)⌉:
    estimado(x) >= real(x)                           siempre
    estimado(x) <= real(x) + ε * total               con probabilidad >= 1 - δ

Complejidad: sumar y estimar son O(d), es decir O(1) respecto al número de
claves; la memoria es O(d*w), fija.
"""

import math
from array import array
from hashlib import blake2b
from random import Random

_PRIMO = (1 << 61) - 1          # primo de Mersenne para el hashing universal
_MASCARA_64 = (1 << 64) - 1


def _token(clave):
    """Convierte una clave cualquiera en un entero de 64 bits estable."""
    return int.from_bytes(blake2b(str(clave).encode("utf-8"), digest_size=8).digest(), "big")


class CountMinSketch:
    """Contador de frecuencias aproximado con memoria fija."""

    def __init__(self, epsilon=0.001, delta=0.01, ancho=None, profundidad=None, semilla=42):
        if ancho is None:
            ancho = math.ceil(math.e / epsilon)
        if profundidad is None:
            profundidad = max(1, math.ceil(math.log(1 / delta)))
        if ancho < 1 or profundidad < 1:
            raise ValueError("ancho y profundidad deben ser >= 1")
        self.ancho = ancho
        self.profundidad = profundidad
        self.epsilon = epsilon
        self.delta = delta
        self._filas = [array("Q", bytes(8 * ancho)) for _ in range(profundidad)]  # ceros
        rng = Random(semilla)
        self._coef = [(rng.randrange(1, _PRIMO), rng.randrange(_PRIMO)) for _ in range(profundidad)]
        self.total = 0

    # --- Operaciones ---------------------------------------------------------

    def _columnas(self, clave):
        t = _token(clave) & _MASCARA_64
        for a, b in self._coef:
            yield ((a * t + b) % _PRIMO) % self.ancho

    def sumar(self, clave, cantidad=1):
        """Suma ``cantidad`` a la cuenta de la clave. O(d)."""
        if cantidad < 0:
            raise ValueError("Count-Min no admite cantidades negativas")
        for fila, col in zip(self._filas, self._columnas(clave)):
            fila[col] += cantidad
        self.total += cantidad
        return self

    def estimar(self, clave):
        """Cota superior de la cuenta de la clave: mínimo sobre las d filas. O(d)."""
        return min(fila[col] for fila, col in zip(self._filas, self._columnas(clave)))

    # --- Información ----------------------------------------------------------

    @property
    def memoria_bytes(self):
        """Memoria de la tabla de contadores (fija, no depende de las claves vistas)."""
        return sum(f.buffer_info()[1] * f.itemsize for f in self._filas)

    @property
    def error_absoluto_garantizado(self):
        """Sobreconteo máximo esperado con prob. >= 1 - δ: ε * total."""
        return self.epsilon * self.total
