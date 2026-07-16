from bpy.types import UILayout

""" 
    Como los operadores cargan antes que las cosas de ui, tengo q tener esta utilidad en operadores 
    también para que no diga que ui esta parcialmente cargado y no poder usar multiline_print en los operadores
"""


def ops_multiline_print(layout: UILayout, text: str, max_words: int) -> None:
    feedback = layout.box().column(align=True)
    words = text.split()
    for i in range(0, len(words), max_words):
        sentence = words[i:i+max_words]
        sentence = " ".join(sentence)
        if i == 0:
            feedback.label(text=sentence, icon='INFO')
        else:
            feedback.label(text=sentence)
