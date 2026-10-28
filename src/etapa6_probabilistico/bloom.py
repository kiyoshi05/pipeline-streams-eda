"""Etapa 6: filtro de Bloom.

Un filtro de Bloom responde "¿he visto esta clave?" usando un arreglo de m bits
y k funciones hash. Al agregar una clave se encienden sus k bits; al consultar,
si alguno de esos k bits está en 0 la clave seguro no está (nunca hay falsos
negativos), y si todos están en 1 la clave probablemente está (puede haber
falsos positivos).

Por qué aquí: la lista negra de IP y dispositivos conocidos por fraude puede
tener millones de entradas. Un ``set`` guarda cada clave completa; el filtro de
Bloom guarda solo bits y usa una fracción de la memoria a cambio de una tasa de
falsos positivos controlada. En un stream de pagos, "revisar con más cuidado"
un evento legítimo (falso positivo) es barato; dejar pasar un fraude conocido
(falso negativo) no se puede permitir, y el filtro garantiza que eso no ocurra.

Dimensionado óptimo para n claves y probabilidad de falso positivo p:
    m = -n * ln(p) / (ln 2)^2        bits
    k = (m / n) * ln 2               funciones hash (se redondea)

Los k índices se derivan de un solo hash de 128 bits por doble hashing
(Kirsch-Mitzenmacher): g_i(x) = (h1(x) + i * h2(x)) mod m. Así se calcula un
único blake2b por clave en vez de k hashes independientes.

Complejidad: agregar y consultar son O(k), es decir O(1) respecto a n.
"""

import math
from hashlib import blake2b

_MASCARA_64 = (1 << 64) - 1


def _dimensionar(n_esperado, prob_fp):
    """Devuelve (bits, num_hashes) óptimos para n claves y prob. de falso positivo."""
    if n_esperado < 1:
        raise ValueError("n_esperado debe ser >= 1")
    if not 0.0 < prob_fp < 1.0:
        raise ValueError("prob_fp debe estar en (0, 1)")
    bits = math.ceil(-n_esperado * math.log(prob_fp) / (math.log(2) ** 2))
    bits = max(8, (bits + 7) & ~7)          # múltiplo de 8 para llenar bytes enteros
    num_hashes = max(1, round(bits / n_esperado * math.log(2)))
    return bits, num_hashes


class FiltroBloom:
    """Conjunto probabilístico: sin falsos negativos, con falsos positivos acotados."""

    def __init__(self, n_esperado=10_000, prob_fp=0.01):
        self.bits, self.num_hashes = _dimensionar(n_esperado, prob_fp)
        self.n_esperado = n_esperado
        self.prob_fp_objetivo = prob_fp
        self._arreglo = bytearray(self.bits // 8)   # todos los bits en 0
        self._n = 0                                  # claves agregadas (con repetición de set-bits aparte)

    # --- Índices -------------------------------------------------------------

    def _indices(self, clave):
        """k posiciones de bit para la clave, por doble hashing sobre un blake2b de 128 bits."""
        resumen = blake2b(str(clave).encode("utf-8"), digest_size=16).digest()
        h1 = int.from_bytes(resumen[:8], "big") & _MASCARA_64
        h2 = int.from_bytes(resumen[8:], "big") & _MASCARA_64
        h2 |= 1                                       # impar: recorre bien todo el arreglo
        for i in range(self.num_hashes):
            yield (h1 + i * h2) % self.bits

    # --- Operaciones ---------------------------------------------------------

    def agregar(self, clave):
        """Enciende los k bits de la clave. O(k). Devuelve False si ya estaba (quizá)."""
        ya_estaba = True
        for pos in self._indices(clave):
            byte, bit = divmod(pos, 8)
            mascara = 1 << bit
            if not (self._arreglo[byte] & mascara):
                self._arreglo[byte] |= mascara
                ya_estaba = False
        self._n += 1
        return not ya_estaba

    def contiene(self, clave):
        """True si la clave probablemente está; False si seguro no está. O(k)."""
        for pos in self._indices(clave):
            byte, bit = divmod(pos, 8)
            if not (self._arreglo[byte] & (1 << bit)):
                return False
        return True

    def actualizar(self, claves):
        """Agrega todas las claves de un iterable."""
        for clave in claves:
            self.agregar(clave)
        return self

    # --- Información ----------------------------------------------------------

    def __len__(self):
        return self._n

    def __contains__(self, clave):
        return self.contiene(clave)

    @property
    def bits_encendidos(self):
        return sum(bin(b).count("1") for b in self._arreglo)

    @property
    def memoria_bytes(self):
        """Memoria del arreglo de bits (lo único que crece con los datos)."""
        return len(self._arreglo)

    @property
    def tasa_fp_estimada(self):
        """Probabilidad de falso positivo estimada con la carga actual del arreglo.

        (1 - e^{-k n / m})^k, usando el número de claves agregadas.
        """
        if self._n == 0:
            return 0.0
        exponente = -self.num_hashes * self._n / self.bits
        return (1 - math.exp(exponente)) ** self.num_hashes
