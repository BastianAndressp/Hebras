from app.knowledge_utils import extract_text_from_upload


def test_extract_text_from_txt_upload():
    text = extract_text_from_upload("faq.txt", "text/plain", b"Hola mundo\nLinea 2")
    assert text == "Hola mundo\nLinea 2"