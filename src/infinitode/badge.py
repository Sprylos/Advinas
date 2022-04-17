from __future__ import annotations

__all__ = ('Badge',)


class Badge:
    '''Represents an in-game pinned badge.'''
    __slots__ = (
        'icon_img',
        'icon_color',
        'overlay_img',
        'overlay_color'
    )

    def __init__(self, iconImg: str, iconColor: str, overlayImg: str, overlayColor: str) -> None:
        self.icon_img = iconImg
        self.icon_color = iconColor
        self.overlay_img = overlayImg
        self.overlay_color = overlayColor
