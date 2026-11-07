"""Six original, editable studio starting points. Never carry media references."""

from .video_schema import StudioDocument


def builtin_templates():
    presets = (
        ("apresentacao", "Apresentação", "vertical", "#13233c", "sans", "fade"),
        ("produto", "Produto em destaque", "square", "#224433", "sans", "zoom"),
        ("tutorial", "Tutorial rápido", "horizontal", "#222638", "mono", "none"),
        ("evento", "Convite para evento", "vertical", "#542350", "serif", "fade"),
        ("depoimento", "Depoimento", "square", "#403326", "serif", "none"),
        ("novidade", "Novidade", "vertical", "#143e52", "sans", "pan"),
    )
    return [{
        "id": "builtin-" + key,
        "name": name,
        "document": StudioDocument(
            title=name, format=shape,
            scenes=[{"text": name, "duration": 5, "background": background,
                     "font": font, "animation": animation, "transition": "fade"},
                    {"text": "Escreva sua mensagem aqui", "duration": 5,
                     "background": background, "font": font}],
        ).model_dump(mode="json"),
    } for key, name, shape, background, font, animation in presets]
