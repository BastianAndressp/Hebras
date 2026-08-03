from app.knowledge_utils import chunk_score, chunk_text


def test_chunk_text_splits_large_text():
    text = " ".join(f"palabra{i}" for i in range(0, 15))
    chunks = chunk_text(text, chunk_size=5, overlap=1)
    assert len(chunks) == 4
    assert chunks[0].startswith("palabra0")
    assert chunks[-1].endswith("palabra14")


def test_chunk_score_prefers_shared_terms():
    query = "horario retiro stock"
    relevant = "Nuestro horario de retiro y stock disponible"
    unrelated = "Bienvenido al asistente de ventas"
    assert chunk_score(query, relevant) > chunk_score(query, unrelated)