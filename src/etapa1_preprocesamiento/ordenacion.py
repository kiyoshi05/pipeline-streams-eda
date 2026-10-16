"""Algoritmos de ordenación implementados a mano para la etapa 1.

Todos reciben una secuencia y una función ``clave`` opcional, devuelven una
lista nueva y no modifican la entrada. La clave se calcula una sola vez por
elemento y se ordena un arreglo paralelo de claves y valores, en lugar de
recalcular la clave en cada comparación.

    merge_sort  O(n log n) siempre, O(n) espacio, estable   <- el que usa la etapa
    quicksort   O(n log n) esperado, O(n^2) peor caso, no estable
    insercion   O(n^2), estable; solo como línea base
"""

import random


def _preparar(datos, clave):
    valores = list(datos)
    llaves = valores[:] if clave is None else [clave(x) for x in valores]
    return llaves, valores


def merge_sort(datos, clave=None):
    """Merge sort iterativo (de abajo hacia arriba).

    Fusiona tramos de ancho 1, 2, 4, ... alternando entre el arreglo original
    y uno auxiliar, así no hay recursión ni copias por cada división.
    Ante claves iguales conserva el orden de llegada (es estable).
    """
    llaves, valores = _preparar(datos, clave)
    n = len(valores)
    if n < 2:
        return valores
    llaves_aux = [None] * n
    valores_aux = [None] * n
    ancho = 1
    while ancho < n:
        for izq in range(0, n, 2 * ancho):
            med = min(izq + ancho, n)
            der = min(izq + 2 * ancho, n)
            _fusionar(llaves, valores, llaves_aux, valores_aux, izq, med, der)
        llaves, llaves_aux = llaves_aux, llaves
        valores, valores_aux = valores_aux, valores
        ancho *= 2
    return valores


def _fusionar(llaves, valores, llaves_dest, valores_dest, izq, med, der):
    """Fusiona los tramos ordenados [izq, med) y [med, der) en el destino."""
    i, j, k = izq, med, izq
    while i < med and j < der:
        # Comparación estricta: en un empate gana el de la izquierda (estabilidad).
        if llaves[j] < llaves[i]:
            llaves_dest[k] = llaves[j]
            valores_dest[k] = valores[j]
            j += 1
        else:
            llaves_dest[k] = llaves[i]
            valores_dest[k] = valores[i]
            i += 1
        k += 1
    if i < med:
        llaves_dest[k:der] = llaves[i:med]
        valores_dest[k:der] = valores[i:med]
    else:
        llaves_dest[k:der] = llaves[j:der]
        valores_dest[k:der] = valores[j:der]


def quicksort(datos, clave=None, semilla=0):
    """Quicksort iterativo con pivote aleatorio y partición en tres.

    La partición en tres (menores, iguales, mayores) evita el peor caso
    cuando hay muchas claves repetidas, que es justo el caso de duplicados.
    Se procesa primero el tramo más pequeño para que la pila sea O(log n).
    """
    llaves, valores = _preparar(datos, clave)
    n = len(valores)
    if n < 2:
        return valores
    azar = random.Random(semilla)
    pila = [(0, n - 1)]
    while pila:
        lo, hi = pila.pop()
        if lo >= hi:
            continue
        p = azar.randint(lo, hi)
        pivote = llaves[p]
        menor, i, mayor = lo, lo, hi
        while i <= mayor:
            if llaves[i] < pivote:
                llaves[menor], llaves[i] = llaves[i], llaves[menor]
                valores[menor], valores[i] = valores[i], valores[menor]
                menor += 1
                i += 1
            elif pivote < llaves[i]:
                llaves[mayor], llaves[i] = llaves[i], llaves[mayor]
                valores[mayor], valores[i] = valores[i], valores[mayor]
                mayor -= 1
            else:
                i += 1
        # Quedan [lo, menor) < pivote, [menor, mayor] == pivote, (mayor, hi] > pivote.
        izquierdo = (lo, menor - 1)
        derecho = (mayor + 1, hi)
        if menor - lo > hi - mayor:
            pila.append(izquierdo)
            pila.append(derecho)
        else:
            pila.append(derecho)
            pila.append(izquierdo)
    return valores


def insercion(datos, clave=None):
    """Ordenación por inserción: O(n^2). Línea base para comparar."""
    llaves, valores = _preparar(datos, clave)
    for i in range(1, len(valores)):
        llave = llaves[i]
        valor = valores[i]
        j = i - 1
        while j >= 0 and llave < llaves[j]:
            llaves[j + 1] = llaves[j]
            valores[j + 1] = valores[j]
            j -= 1
        llaves[j + 1] = llave
        valores[j + 1] = valor
    return valores
