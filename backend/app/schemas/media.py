"""
Fotoğraf yükleme JSON şemaları.
"""
from pydantic import BaseModel


class MediaOut(BaseModel):
    id: int
    url: str      # herkese açık adres; profil/anı/oda formunda bu adres gönderilir
