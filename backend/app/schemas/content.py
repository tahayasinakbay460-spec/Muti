"""Uygulama geneli içerik şemaları."""
from pydantic import BaseModel


class DemoLogin(BaseModel):
    username: str
    password: str


class AppInfo(BaseModel):
    # Doluysa giriş ekranı "Demo hesabı: ..." ipucunu gösterir (yalnızca demo/vitrin yayınında).
    demo_login: DemoLogin | None = None
