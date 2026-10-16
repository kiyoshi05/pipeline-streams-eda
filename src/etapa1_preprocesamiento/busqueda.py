"""Búsqueda binaria implementada a mano sobre listas ordenadas.

Todas las funciones aceptan una ``clave`` opcional que se aplica a cada
elemento consultado, para poder buscar directamente en una lista de eventos.

    lower_bound, upper_bound, contiene, rango  -> O(log n) comparaciones
    busqueda_lineal                            -> O(n); solo para comparar
"""


def lower_bound(datos, x, clave=None, lo=0, hi=None):
    """Primer índice i con clave(datos[i]) >= x (len(datos) si no hay)."""
    if hi is None:
        hi = len(datos)
    while lo < hi:
        mid = (lo + hi) // 2
        valor = datos[mid] if clave is None else clave(datos[mid])
        if valor < x:
            lo = mid + 1
        else:
            hi = mid
    return lo


def upper_bound(datos, x, clave=None, lo=0, hi=None):
    """Primer índice i con clave(datos[i]) > x (len(datos) si no hay)."""
    if hi is None:
        hi = len(datos)
    while lo < hi:
        mid = (lo + hi) // 2
        valor = datos[mid] if clave is None else clave(datos[mid])
        if x < valor:
            hi = mid
        else:
            lo = mid + 1
    return lo


def contiene(datos, x, clave=None):
    """True si algún elemento tiene clave igual a x."""
    i = lower_bound(datos, x, clave)
    if i == len(datos):
        return False
    valor = datos[i] if clave is None else clave(datos[i])
    return valor == x


def rango(datos, desde, hasta, clave=None):
    """Índices (i, j) tales que datos[i:j] tiene las claves en [desde, hasta]."""
    i = lower_bound(datos, desde, clave)
    j = upper_bound(datos, hasta, clave, lo=i)
    return i, j


def busqueda_lineal(datos, x, clave=None):
    """Índice del primer elemento con clave igual a x, o -1. O(n)."""
    for i, elemento in enumerate(datos):
        valor = elemento if clave is None else clave(elemento)
        if valor == x:
            return i
    return -1
