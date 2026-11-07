"""Six original editable use cases, with no embedded third-party media."""

from .video_schema import StudioDocument


def builtin_templates():
    presets = (
        (
            "reels",
            "Reels de divulgação",
            "vertical",
            "#13233c",
            "sans",
            "pan",
            (
                "Uma ideia que merece atenção",
                "Mostre seu diferencial aqui",
                "Convide para conhecer seu projeto",
            ),
        ),
        (
            "produto",
            "Apresentação de produtos",
            "square",
            "#224433",
            "sans",
            "zoom",
            ("Seu produto em destaque", "Conte os benefícios e como comprar"),
        ),
        (
            "promocao",
            "Promoções",
            "vertical",
            "#542350",
            "sans",
            "fade",
            (
                "Sua oferta começa aqui",
                "Informe preço, condições e validade",
                "Adicione seu contato e a chamada final",
            ),
        ),
        (
            "tutorial",
            "Tutorial rápido",
            "vertical",
            "#222638",
            "mono",
            "none",
            (
                "Passo 1: apresente o objetivo",
                "Passo 2: mostre como fazer",
                "Passo 3: confira o resultado",
            ),
        ),
        (
            "servico",
            "Anúncios de serviços",
            "vertical",
            "#143e52",
            "sans",
            "pan",
            ("Que problema seu serviço resolve?", "Mostre a solução e como agendar"),
        ),
        (
            "institucional",
            "Vídeo institucional",
            "horizontal",
            "#403326",
            "serif",
            "fade",
            (
                "Apresente sua organização",
                "Conte sua missão e seus valores",
                "Compartilhe seu próximo passo",
            ),
        ),
    )
    return [
        {
            "id": "builtin-" + key,
            "name": name,
            "document": StudioDocument(
                title=name,
                format=shape,
                scenes=[
                    {
                        "text": text,
                        "duration": 5,
                        "background": background,
                        "font": font,
                        "animation": animation if index == 0 else "none",
                        "text_animation": "fade",
                        "transition": "fade",
                        "x": 50,
                        "y": 50,
                        "font_size": 36,
                    }
                    for index, text in enumerate(copy)
                ],
            ).model_dump(mode="json"),
        }
        for key, name, shape, background, font, animation, copy in presets
    ]
