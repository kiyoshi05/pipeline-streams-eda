"""Etapa 3: almacenamiento, lookup y caché (tabla hash, LRU y matriz dispersa)."""

from src.etapa3_lookup.lookup import PESOS_INTERACCION, Etapa3Lookup
from src.etapa3_lookup.lru import CacheLRU
from src.etapa3_lookup.matriz_dispersa import MatrizDispersa
from src.etapa3_lookup.tabla_hash import TablaHash

__all__ = [
    "CacheLRU",
    "Etapa3Lookup",
    "MatrizDispersa",
    "PESOS_INTERACCION",
    "TablaHash",
]
